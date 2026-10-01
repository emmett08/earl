"""ANTLR recognition into a typed lexical tree, followed by checked lowering."""
from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath

from antlr4 import CommonTokenStream, InputStream, ParserRuleContext
from antlr4.error.ErrorListener import ErrorListener

from .generated.EALLexer import EALLexer
from .generated.EALParser import EALParser
from .generated.EALVisitor import EALVisitor
from .limits import current_limits, using_limits
from .model import (Application, Argument, ArgumentationDirective, Assumption, Claim, Environment, Evidence,
                    Pattern, PatternBinding, PatternParameter, Reasoning, Objection,
                    Predicate, Program, Proposition, SourceSpan, Tool, Expression,
                    Block, Declaration, Module, SourceImport, Context, ArgumentBlock,
                    PatternGuard, ScopeTransfer)
from .expressions import make_predicate

MAX_SOURCE_BYTES = 1024 * 1024
MAX_TOKENS = 100_000
DEFAULT_FIELDS = {
    'tool': ('version',),
    'evidence': ('environment', 'tool', 'max_age', 'kind', 'input'),
    'assumption': ('environment', 'validate', 'valid_from', 'valid_until'),
    'claim': ('environment',),
    'reasoning': ('method',),
    'proposition': ('subject', 'quantity', 'unit', 'scope', 'valid_from', 'valid_until', 'query'),
}


class EALSyntaxError(ValueError):
    """Recognition or structural lowering failed; no recovered tree is executed."""


class _Errors(ErrorListener):
    def __init__(self):
        self.errors = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append(f'{line}:{column + 1}: {msg}')


def _string(node):
    value = json.loads(node.getText())
    try:
        value.encode('utf-8')
    except UnicodeError as exc:
        symbol = getattr(node, 'symbol', node)
        raise EALSyntaxError(f'{symbol.line}:{symbol.column + 1}: String contains an unpaired Unicode surrogate') from exc
    return value


def _span(ctx):
    text = ctx.stop.text or ''
    lines = text.split('\n')
    return SourceSpan(ctx.start.line, ctx.start.column + 1, ctx.stop.line + len(lines) - 1,
                      ctx.stop.column + len(text) + 1 if len(lines) == 1 else len(lines[-1]) + 1)


def _references(ctx):
    return tuple(reference.getText() for reference in ctx.reference()) if ctx else ()


class _ASTBuilder(EALVisitor):
    def __init__(self, resolver=None, origin=''):
        self.defaults = {}
        self.resolver = resolver
        self.origin = origin
        self.imports = {}
        self.import_sources = {}
        self.import_stack = []
        self.total_bytes = 0
        self.total_tokens = 0

    def block(self, declarations):
        return Block(tuple(self.visit(declaration) for declaration in declarations))

    def visitDeclaration(self, ctx):
        child = ctx.getChild(0)
        return Declaration(self.visit(child), _span(child), self.origin or None)

    def visitModuleDecl(self, ctx):
        return Module(ctx.qualifiedName().getText(), self.block(ctx.declaration()))

    def visitContextDecl(self, ctx):
        additions = {}
        for attribute in ctx.contextAttribute():
            name = attribute.start.text
            if name in additions:
                self.fail(attribute, f'Duplicate context default {name!r}')
            if attribute.qualifiedName():
                value = attribute.qualifiedName().getText()
            elif attribute.identifier():
                value = attribute.identifier().getText()
            elif attribute.signedNumber():
                value = float(attribute.signedNumber().getText())
            elif attribute.jsonValue():
                value = self.visit(attribute.jsonValue())
            else:
                value = _string(attribute.STRING())
            additions[name] = value
        previous = self.defaults
        self.defaults = {**previous, **additions}
        try:
            return Context(additions, self.block(ctx.declaration()))
        finally:
            self.defaults = previous

    def visitImportDecl(self, ctx):
        if self.resolver is None:
            self.fail(ctx, 'Source imports require a trusted host source resolver')
        requested = _string(ctx.STRING())
        if not requested or '\\' in requested or PurePosixPath(requested).is_absolute():
            self.fail(ctx, 'Imports require a relative POSIX source path')
        parts = []
        for part in (PurePosixPath(self.origin).parent / requested).parts:
            if part == '..':
                if not parts:
                    self.fail(ctx, 'Import escapes the source root')
                parts.pop()
            elif part != '.':
                parts.append(part)
        path = '/'.join(parts)
        if path in self.import_stack or path == self.origin:
            self.fail(ctx, f'Source import cycle at {path!r}')
        if len(self.import_stack) >= current_limits().expansion_depth:
            self.fail(ctx, 'Source import depth budget exceeded')
        try:
            if path not in self.import_sources:
                self.import_sources[path] = self.resolver(path)
            source = self.import_sources[path]
        except (ValueError, OSError, KeyError) as exc:
            self.fail(ctx, f'Cannot resolve source import {path!r}: {exc}')
        previous_origin, previous_defaults = self.origin, self.defaults
        self.origin, self.defaults = path, {}
        self.import_stack.append(path)
        try:
            tree = self.recognise(source)
            if _string(tree.STRING()) != 'EAL/3':
                self.fail(ctx, 'An imported source must declare EAL/3')
            body = self.block(tree.declaration())
        finally:
            self.import_stack.pop()
            self.origin, self.defaults = previous_origin, previous_defaults
        digest = hashlib.sha256(source.encode('utf-8')).hexdigest()
        self.imports[path] = digest
        return SourceImport(ctx.identifier().getText(), path, body, digest)

    @staticmethod
    def fail(ctx, message):
        raise EALSyntaxError(f'{ctx.start.line}:{ctx.start.column + 1}: {message}')

    def fields(self, ctx, wrappers, kind, required):
        result, predicates = {}, []
        for wrapper in wrappers:
            child = wrapper.getChild(0)
            field = child if isinstance(child, ParserRuleContext) else wrapper
            name = field.start.text
            if name == 'require':
                predicates.append(self.visit(field))
                continue
            if name in result:
                self.fail(field, f'Duplicate field {name!r}')
            if name in ('proposition', 'transfer'):
                value = self.visit(field)
            elif name == 'result':
                value = make_predicate(self.visit(field.expression()))
            elif hasattr(field, 'qualifiedName'):
                value = field.qualifiedName().getText()
            elif hasattr(field, 'identifier'):
                value = field.identifier().getText()
            elif hasattr(field, 'jsonValue'):
                value = self.visit(field.jsonValue())
            elif hasattr(field, 'referenceList'):
                value = _references(field.referenceList())
            elif hasattr(field, 'signedNumber'):
                value = float(field.signedNumber().getText())
            else:
                value = _string(field.STRING())
            result[name] = value
        for name in DEFAULT_FIELDS.get(kind, ()):
            if name not in result and name in self.defaults:
                result[name] = self.defaults[name]
        missing = set(required) - result.keys()
        if missing:
            self.fail(ctx, 'Missing field after context inheritance: ' + ', '.join(sorted(missing)))
        result['predicates'] = tuple(predicates)
        if kind == 'evidence' and not predicates:
            self.fail(ctx, 'Evidence requires at least one require predicate')
        return result

    def groups(self, ctx, rule):
        result = {}
        for group in getattr(ctx, rule)():
            name = group.start.text
            if name in result:
                self.fail(group, f'Duplicate support group {name!r}')
            result[name] = _references(group)
        return result

    def argument(self, name, ctx):
        groups = self.groups(ctx.support(), 'supportGroup')
        return Argument(name, ctx.conclusionRef.getText(), ctx.reasoningRef.getText(),
                        groups.get('evidence', ()), groups.get('assumptions', ()), groups.get('premises', ()),
                        ctx.bindingRef.getText() if ctx.bindingRef else None)

    def visitArgumentationDirective(self, ctx):
        kind = ctx.start.text
        names = ctx.qualifiedName()
        text = ctx.signedNumber().getText() if kind == 'rank' else None
        return ArgumentationDirective(kind, names[0].getText(), names[1].getText() if kind in ('contrary', 'prefer') else None,
                                      int(text) if text is not None and text.isdigit() else None,
                                      _string(ctx.STRING()), _span(ctx), self.origin or None)

    def visitEnvironmentDecl(self, ctx):
        return Environment(ctx.qualifiedName().getText(), tuple(self.visit(p) for p in ctx.predicate()))

    def visitToolDecl(self, ctx):
        f = self.fields(ctx, ctx.versionField(), 'tool', ('version',))
        return Tool(ctx.qualifiedName().getText(), f['version'])

    def visitEvidenceDecl(self, ctx):
        f = self.fields(ctx, ctx.evidenceField(), 'evidence', ('tool', 'kind', 'environment', 'max_age'))
        return Evidence(ctx.qualifiedName().getText(), f['tool'], f['kind'], f['environment'], f['max_age'],
                        f.get('input', {}), f['predicates'])

    def visitAssumptionDecl(self, ctx):
        f = self.fields(ctx, ctx.assumptionField(), 'assumption', ('statement', 'environment', 'validate'))
        return Assumption(ctx.qualifiedName().getText(), f['statement'], f['environment'], f['validate'],
                          f.get('valid_from'), f.get('valid_until'))

    def visitReasoningDecl(self, ctx):
        f = self.fields(ctx, ctx.reasoningField(), 'reasoning', ('method', 'rationale'))
        return Reasoning(ctx.qualifiedName().getText(), f['method'], f['rationale'], f.get('backing', ()),
                         f['predicates'], f.get('transfer'))

    def visitTransferField(self, ctx):
        names = [name.getText() for name in ctx.qualifiedName()]
        return ScopeTransfer(*names, _string(ctx.STRING()))

    def visitClaimDecl(self, ctx):
        f = self.fields(ctx, ctx.claimField(), 'claim', ('statement', 'environment'))
        return Claim(ctx.qualifiedName().getText(), f['statement'], f['environment'], f.get('proposition'))

    def visitPropositionDecl(self, ctx):
        names = ('subject', 'quantity', 'unit', 'scope', 'valid_from', 'valid_until', 'result', 'query')
        f = self.fields(ctx, ctx.propositionField(), 'proposition', names)
        return Proposition(*(f[name] for name in names))

    def visitArgumentDecl(self, ctx):
        name = ctx.qualifiedName().getText()
        flow = self.argument(name, ctx.argumentFlow())
        return ArgumentBlock(name, self.block(ctx.declaration()), flow) if ctx.declaration() or ctx.getChild(2).getText() == '{' else flow

    def visitPatternDecl(self, ctx):
        parameters = tuple(self.visit(parameter) for parameter in ctx.patternParameter())
        decreasing = ctx.identifier().getText() if ctx.identifier() else None
        if ctx.argumentFlow():
            flow = self.argument(ctx.qualifiedName().getText(), ctx.argumentFlow())
            return Pattern(flow.name, parameters, flow.conclusion, flow.reasoning, flow.evidence,
                           flow.assumptions, flow.premises, flow.binding, decreases=decreasing)
        return Pattern(ctx.qualifiedName().getText(), parameters, '', '', (), (), (),
                       body=self.block(ctx.declaration()), decreases=decreasing)

    def visitPatternParameter(self, ctx):
        kind = ctx.parameterKind().getText() + ('[]' if '[' in ctx.getText() else '')
        return PatternParameter(ctx.identifier().getText(), kind)

    def visitApplicationDecl(self, ctx):
        names = ctx.qualifiedName()
        return Application(names[0].getText(), names[1].getText(),
                           tuple(self.visit(binding) for binding in ctx.patternBinding()))

    def visitPatternBinding(self, ctx):
        values = ctx.bindingValue()
        refs = _references(values)
        reference = refs if values.getText().startswith('[') else refs[0]
        return PatternBinding(ctx.identifier().getText(), reference)

    def visitPatternGuard(self, ctx):
        before, after = [], []
        target = before
        for child in ctx.children:
            if child.getText() == 'else':
                target = after
            elif isinstance(child, EALParser.DeclarationContext):
                target.append(child)
        return PatternGuard(ctx.identifier().getText(), self.block(before),
                            self.block(after) if 'else' in [child.getText() for child in ctx.children] else None)

    def visitObjectionDecl(self, ctx):
        groups = self.groups(ctx.objectionSupport(), 'objectionGroup')
        return Objection(ctx.qualifiedName().getText(), ctx.targetKind().getText(), ctx.reference().getText(),
                         groups.get('evidence', ()), groups.get('premises', ()))

    def visitPredicate(self, ctx):
        return make_predicate(self.visit(ctx.expression()))

    def visitExpression(self, ctx):
        return self.visit(ctx.orExpression())

    def binary(self, ctx):
        result = self.visit(ctx.getChild(0))
        for index in range(2, ctx.getChildCount(), 2):
            symbol = ctx.getChild(index - 1).getText()
            right = self.visit(ctx.getChild(index))
            left = result
            if symbol in ('==', '!=', '<', '<=', '>', '>=') and left.kind == 'literal' and type(left.value) is str:
                left = Expression('field', left.value)
            result = Expression('binary', symbol, (left, right))
        return result

    visitOrExpression = binary
    visitAndExpression = binary
    visitComparisonExpression = binary
    visitAdditiveExpression = binary
    visitMultiplicativeExpression = binary

    def visitUnaryExpression(self, ctx):
        return (Expression('unary', ctx.start.text, (self.visit(ctx.unaryExpression()),))
                if ctx.unaryExpression() else self.visit(ctx.primaryExpression()))

    def visitPrimaryExpression(self, ctx):
        if ctx.qualifiedName():
            name = ctx.qualifiedName().getText()
            if '(' not in [child.getText() for child in ctx.children]:
                return Expression('field', name)
            arguments = tuple(self.visit(expr) for expr in ctx.expression())
            if name == 'field':
                if len(arguments) != 1 or arguments[0].kind != 'literal' or type(arguments[0].value) is not str:
                    self.fail(ctx, 'field requires one literal property path')
                return Expression('field', arguments[0].value)
            return Expression('call', name, arguments)
        if ctx.jsonValue():
            return Expression('literal', self.visit(ctx.jsonValue()))
        return self.visit(ctx.expression(0))

    def visitJsonScalar(self, ctx):
        return _string(ctx.STRING()) if ctx.STRING() else json.loads(ctx.getText())

    def visitJsonValue(self, ctx):
        return self.visit(ctx.getChild(0))

    def visitJsonObject(self, ctx):
        names = [_string(name) for name in ctx.STRING()]
        if len(set(names)) != len(names):
            self.fail(ctx, 'Duplicate JSON object key')
        return dict(zip(names, (self.visit(value) for value in ctx.jsonValue())))

    def visitJsonArray(self, ctx):
        return [self.visit(value) for value in ctx.jsonValue()]

    def recognise(self, source):
        if type(source) is not str:
            raise EALSyntaxError('Source must be a string')
        try:
            encoded = source.encode('utf-8')
        except UnicodeError as exc:
            raise EALSyntaxError('Source must be valid Unicode') from exc
        self.total_bytes += len(encoded)
        if self.total_bytes > current_limits().source_bytes:
            raise EALSyntaxError(f'Source bundle exceeds {current_limits().source_bytes} bytes')
        listener = _Errors()
        lexer = EALLexer(InputStream(source))
        lexer.removeErrorListeners(); lexer.addErrorListener(listener)
        tokens = CommonTokenStream(lexer)
        tokens.fill()
        self.total_tokens += len(tokens.tokens)
        if self.total_tokens > current_limits().source_tokens:
            raise EALSyntaxError(f'Source bundle exceeds {current_limits().source_tokens} tokens')
        parser = EALParser(tokens)
        parser.removeErrorListeners(); parser.addErrorListener(listener)
        try:
            tree = parser.program()
        except RecursionError as exc:
            raise EALSyntaxError('Source nesting exceeds parser resources') from exc
        if listener.errors:
            raise EALSyntaxError('\n'.join(listener.errors[:20]))
        return tree


def parse(source: str, *, limits=None, resolver=None, origin='') -> Program:
    """Recognise, resolve lexical names and expand closed typed patterns.

    A resolver supplies source text only. Filesystem access is owned by the host;
    parsing and evaluation never execute collectors or imported Python code.
    """
    with using_limits(limits or current_limits()):
        builder = _ASTBuilder(resolver, origin)
        tree = builder.recognise(source)
        try:
            body = builder.block(tree.declaration())
        except EALSyntaxError:
            raise
        except (RecursionError, ValueError, OverflowError) as exc:
            raise EALSyntaxError(f'Invalid source data: {exc}') from exc
        encoded = source.encode('utf-8')
        digest = hashlib.sha256(encoded).hexdigest()
        if builder.imports:
            digest = hashlib.sha256(json.dumps({'source': digest, 'imports': builder.imports},
                                               sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        program = Program(_string(tree.STRING()), digest, authored=body, imports=builder.imports)
        from .composition import lower_program
        return lower_program(program)
