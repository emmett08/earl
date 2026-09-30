"""ANTLR recogniser and parse-tree-to-typed-AST visitor (Parr's first passes)."""
from __future__ import annotations

import hashlib
import json

from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener

from .generated.EALLexer import EALLexer
from .generated.EALParser import EALParser
from .generated.EALVisitor import EALVisitor
from .abstractions import lower_patterns
from .model import (Application, Argument, ArgumentationDirective, Assumption, Claim, Environment, Evidence,
                    Pattern, PatternBinding, PatternParameter, Reasoning, Objection,
                    Predicate, Program, Proposition, SourceSpan, Tool)

MAX_SOURCE_BYTES = 1024 * 1024
MAX_TOKENS = 100_000


class EALSyntaxError(ValueError):
    """A source cannot be recognised as an EAL program."""


class _Errors(ErrorListener):
    def __init__(self):
        self.errors = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append(f"{line}:{column + 1}: {msg}")


def _string(node):
    value = json.loads(node.getText())
    # JSON escape syntax permits unpaired UTF-16 surrogates. EAL interchange,
    # canonical source and observation identities require actual UTF-8 text.
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        symbol = getattr(node, "symbol", node)
        raise EALSyntaxError(
            f"{symbol.line}:{symbol.column + 1}: String contains an unpaired Unicode surrogate"
        ) from exc
    return value


def _ids(ctx):
    return tuple(node.getText() for node in ctx.identifier()) if ctx else ()


def _span(ctx):
    stop = ctx.stop
    text = stop.text or ""
    lines = text.split("\n")
    return SourceSpan(ctx.start.line, ctx.start.column + 1,
                      stop.line + len(lines) - 1,
                      stop.column + len(text) + 1 if len(lines) == 1 else len(lines[-1]) + 1)


class _ASTBuilder(EALVisitor):
    def __init__(self):
        self.defaults = {}

    def visitDeclaration(self, ctx):
        child = ctx.getChild(0)
        if isinstance(child, EALParser.ContextDeclContext):
            return self.visit(child)
        return [(self.visit(child), _span(child))]

    def visitContextDecl(self, ctx):
        additions = {}
        for attribute in ctx.contextAttribute():
            key = attribute.start.text
            if key in additions:
                self.fail(attribute, f"Duplicate context default {key!r}")
            if attribute.identifier():
                value = attribute.identifier().getText()
            elif attribute.NUMBER():
                value = float(attribute.NUMBER().getText())
            else:
                value = _string(attribute.STRING())
            additions[key] = value
        previous = self.defaults
        self.defaults = {**previous, **additions}
        try:
            return [item for declaration in ctx.declaration()
                    for item in self.visit(declaration)]
        finally:
            self.defaults = previous

    @staticmethod
    def fail(ctx, message):
        raise EALSyntaxError(f"{ctx.start.line}:{ctx.start.column + 1}: {message}")

    def fields(self, ctx, wrappers, kind, required):
        result, predicates = {}, []
        for wrapper in wrappers:
            field = wrapper.getChild(0)
            key = field.start.text
            if key == "require":
                predicates.append(self.visit(field))
                continue
            if key in result:
                self.fail(field, f"Duplicate field {key!r}")
            if key == "proposition":
                value = self.visit(field)
            elif key == "result":
                value = Predicate(self.visit(field.key()), field.comparator().getText(),
                                  self.visit(field.jsonScalar()))
            elif hasattr(field, "identifier"):
                value = field.identifier().getText()
            elif hasattr(field, "jsonValue"):
                value = self.visit(field.jsonValue())
            elif hasattr(field, "referenceList"):
                value = _ids(field.referenceList())
            elif hasattr(field, "NUMBER"):
                value = float(field.NUMBER().getText())
            else:
                value = _string(field.STRING())
            result[key] = value
        applicable = {
            "evidence": ("environment", "tool", "max_age"),
            "assumption": ("environment", "valid_from", "valid_until"),
            "claim": ("environment",),
        }.get(kind, ())
        for key in applicable:
            if key not in result and key in self.defaults:
                result[key] = self.defaults[key]
        missing = set(required) - result.keys()
        if missing:
            self.fail(ctx, "Missing field after context inheritance: " + ", ".join(sorted(missing)))
        result["predicates"] = tuple(predicates)
        if kind == "evidence" and not predicates:
            self.fail(ctx, "Evidence requires at least one require predicate")
        return result

    def groups(self, ctx, rule):
        result = {}
        for group in getattr(ctx, rule)():
            key = group.start.text
            if key in result:
                self.fail(group, f"Duplicate support group {key!r}")
            result[key] = _ids(group)
        return result

    def argument_fields(self, ctx):
        groups = self.groups(ctx.support(), "supportGroup")
        return (ctx.conclusionRef.getText(), ctx.reasoningRef.getText(),
                groups.get("evidence", ()), groups.get("assumptions", ()),
                groups.get("premises", ()),
                ctx.bindingRef.getText() if ctx.bindingRef else None)

    def visitArgumentationDirective(self, ctx):
        words = ctx.getChild(0).getText()
        names = ctx.identifier()
        rank_text = ctx.NUMBER().getText() if words == "rank" else None
        return ArgumentationDirective(
            words,
            names[0].getText(),
            names[1].getText() if words == "contrary" else None,
            int(rank_text) if rank_text is not None and rank_text.isdigit() else None,
            _string(ctx.STRING()), _span(ctx))

    def visitEnvironmentDecl(self, ctx):
        return Environment(ctx.identifier().getText(), tuple(self.visit(p) for p in ctx.predicate()))

    def visitToolDecl(self, ctx):
        return Tool(ctx.identifier().getText(), _string(ctx.versionField().STRING()))

    def visitEvidenceDecl(self, ctx):
        f = self.fields(ctx, ctx.evidenceField(), "evidence",
                        ("tool", "kind", "environment", "max_age"))
        return Evidence(ctx.identifier().getText(), f["tool"], f["kind"], f["environment"],
                        f["max_age"], f.get("input", {}), f["predicates"])

    def visitAssumptionDecl(self, ctx):
        f = self.fields(ctx, ctx.assumptionField(), "assumption",
                        ("statement", "environment", "validate"))
        return Assumption(ctx.identifier().getText(), f["statement"], f["environment"],
                          f["validate"], f.get("valid_from"), f.get("valid_until"))

    def visitReasoningDecl(self, ctx):
        f = self.fields(ctx, ctx.reasoningField(), "reasoning", ("method", "rationale"))
        return Reasoning(ctx.identifier().getText(), f["method"], f["rationale"],
                         f.get("backing", ()), f["predicates"])

    def visitClaimDecl(self, ctx):
        f = self.fields(ctx, ctx.claimField(), "claim", ("statement", "environment"))
        return Claim(ctx.identifier().getText(), f["statement"], f["environment"], f.get("proposition"))

    def visitPropositionDecl(self, ctx):
        keys = ("subject", "quantity", "unit", "scope", "valid_from", "valid_until", "result", "query")
        f = self.fields(ctx, ctx.propositionField(), "proposition", keys)
        return Proposition(*(f[key] for key in keys))

    def visitArgumentDecl(self, ctx):
        return Argument(ctx.identifier().getText(), *self.argument_fields(ctx.argumentFlow()))

    def visitPatternDecl(self, ctx):
        return Pattern(ctx.identifier().getText(),
                       tuple(self.visit(parameter) for parameter in ctx.patternParameter()),
                       *self.argument_fields(ctx.argumentFlow()))

    def visitPatternParameter(self, ctx):
        return PatternParameter(ctx.identifier().getText(), ctx.parameterKind().getText())

    def visitApplicationDecl(self, ctx):
        return Application(ctx.identifier(0).getText(), ctx.identifier(1).getText(),
                           tuple(self.visit(binding) for binding in ctx.patternBinding()))

    def visitPatternBinding(self, ctx):
        return PatternBinding(ctx.identifier(0).getText(), ctx.identifier(1).getText())

    def visitObjectionDecl(self, ctx):
        groups = self.groups(ctx.objectionSupport(), "objectionGroup")
        return Objection(ctx.identifier(0).getText(), ctx.targetKind().getText(),
                         ctx.identifier(1).getText(), groups.get("evidence", ()), groups.get("premises", ()))

    def visitPredicate(self, ctx):
        return Predicate(self.visit(ctx.key()), ctx.comparator().getText(), self.visit(ctx.jsonScalar()))

    def visitKey(self, ctx):
        return _string(ctx.STRING()) if ctx.STRING() else ctx.getText()

    def visitJsonScalar(self, ctx):
        return _string(ctx.STRING()) if ctx.STRING() else json.loads(ctx.getText())

    def visitJsonValue(self, ctx):
        return self.visit(ctx.getChild(0))

    def visitJsonObject(self, ctx):
        keys = [_string(k) for k in ctx.STRING()]
        if len(set(keys)) != len(keys):
            raise EALSyntaxError(f"{ctx.start.line}:{ctx.start.column + 1}: Duplicate JSON object key")
        return dict(zip(keys, (self.visit(v) for v in ctx.jsonValue())))

    def visitJsonArray(self, ctx):
        return [self.visit(v) for v in ctx.jsonValue()]


def parse(source: str) -> Program:
    """Recognise source and build a typed AST; semantic validation is separate."""
    if not isinstance(source, str):
        raise EALSyntaxError("Source must be a string")
    try:
        encoded = source.encode("utf-8")
    except UnicodeError as exc:
        raise EALSyntaxError("Source must be valid Unicode") from exc
    if len(encoded) > MAX_SOURCE_BYTES:
        raise EALSyntaxError(f"Source exceeds {MAX_SOURCE_BYTES} bytes")
    listener = _Errors()
    lexer = EALLexer(InputStream(source))
    lexer.removeErrorListeners()
    lexer.addErrorListener(listener)
    tokens = CommonTokenStream(lexer)
    tokens.fill()
    if len(tokens.tokens) > MAX_TOKENS:
        raise EALSyntaxError(f"Source exceeds {MAX_TOKENS} tokens")
    parser = EALParser(tokens)
    parser.removeErrorListeners()
    parser.addErrorListener(listener)
    try:
        tree = parser.program()
    except RecursionError as exc:
        raise EALSyntaxError("Source nesting exceeds parser resources") from exc
    if listener.errors:
        raise EALSyntaxError("\n".join(listener.errors[:20]))
    builder = _ASTBuilder()
    groups = {name: {} for name in ("environments", "tools", "evidence", "assumptions",
                                    "reasoning", "claims", "arguments", "objections",
                                    "patterns", "applications")}
    destinations = {Environment: "environments", Tool: "tools", Evidence: "evidence",
                    Assumption: "assumptions", Reasoning: "reasoning", Claim: "claims",
                    Argument: "arguments", Objection: "objections",
                    Pattern: "patterns", Application: "applications"}
    symbols = set()
    duplicates = []
    locations = {}
    argumentation_directives = []
    try:
        declarations = [item for declaration in tree.declaration()
                        for item in builder.visit(declaration)]
        for value, span in declarations:
            if isinstance(value, ArgumentationDirective):
                argumentation_directives.append(value)
                continue
            if value.name in symbols:
                duplicates.append(value.name)
            symbols.add(value.name)
            locations[value.name] = span
            groups[destinations[type(value)]][value.name] = value
    except EALSyntaxError:
        raise
    except (RecursionError, ValueError, OverflowError) as exc:
        raise EALSyntaxError(f"Invalid JSON data: {exc}") from exc
    program = Program(language=_string(tree.STRING()), source_digest=hashlib.sha256(encoded).hexdigest(),
                      **groups, argumentation_directives=tuple(argumentation_directives), duplicates=tuple(duplicates), locations=locations,
                      declaration_count=len(declarations) + len(groups["patterns"]))
    return lower_patterns(program)
