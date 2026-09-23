"""ANTLR recogniser and parse-tree-to-typed-AST visitor (Parr's first passes)."""
from __future__ import annotations

import hashlib
import json

from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener

from .generated.EALLexer import EALLexer
from .generated.EALParser import EALParser
from .generated.EALVisitor import EALVisitor
from .model import (Argument, Assumption, Claim, Environment, Evidence,
                    Reasoning, Objection, Predicate, Program, Tool)

MAX_SOURCE_BYTES = 1024 * 1024
MAX_TOKENS = 100_000


class EALSyntaxError(ValueError):
    """A source cannot be recognised as an EAL 0.1 program."""


class _Errors(ErrorListener):
    def __init__(self):
        self.errors = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append(f"{line}:{column + 1}: {msg}")


def _string(node):
    return json.loads(node.getText())


def _ids(ctx):
    return tuple(node.getText() for node in ctx.ID()) if ctx else ()


class _ASTBuilder(EALVisitor):
    def visitEnvironmentDecl(self, ctx):
        return Environment(ctx.ID().getText(), tuple(self.visit(p) for p in ctx.predicate()))

    def visitToolDecl(self, ctx):
        return Tool(ctx.ID().getText(), _string(ctx.STRING()), ctx.executionMode().getText())

    def visitEvidenceDecl(self, ctx):
        return Evidence(ctx.ID(0).getText(), ctx.ID(1).getText(), ctx.ID(2).getText(), ctx.ID(3).getText(),
                        float(ctx.NUMBER().getText()),
                        self.visit(ctx.jsonValue()) if ctx.jsonValue() else {},
                        tuple(self.visit(p) for p in ctx.predicate()))

    def visitAssumptionDecl(self, ctx):
        strings = ctx.STRING()
        # Keyword positions distinguish an omitted valid_from from valid_until.
        dates = {}
        for i, child in enumerate(ctx.children[:-1]):
            if child.getText() in ("valid_from", "valid_until"):
                dates[child.getText()] = _string(ctx.children[i + 1])
        return Assumption(ctx.ID(0).getText(), _string(strings[0]),
                          ctx.ID(1).getText(), ctx.ID(2).getText(),
                          dates.get("valid_from"), dates.get("valid_until"))

    def visitReasoningDecl(self, ctx):
        return Reasoning(ctx.ID().getText(), ctx.reasoningMode().getText(), _string(ctx.STRING()),
                         _ids(ctx.idList()), tuple(self.visit(p) for p in ctx.predicate()))

    def visitClaimDecl(self, ctx):
        return Claim(ctx.ID(0).getText(), _string(ctx.STRING()), ctx.ID(1).getText())

    def visitArgumentDecl(self, ctx):
        return Argument(ctx.ID(0).getText(), ctx.ID(1).getText(), ctx.ID(2).getText(),
                        _ids(ctx.evidenceRefs), _ids(ctx.assumptionRefs), _ids(ctx.premiseRefs))

    def visitObjectionDecl(self, ctx):
        return Objection(ctx.ID(0).getText(), ctx.targetKind().getText(),
                         ctx.ID(1).getText(), _ids(ctx.idList()))

    def visitPredicate(self, ctx):
        return Predicate(_string(ctx.STRING()), ctx.comparator().getText(), self.visit(ctx.jsonScalar()))

    def visitJsonScalar(self, ctx):
        return json.loads(ctx.getText())

    def visitJsonValue(self, ctx):
        return self.visit(ctx.getChild(0))

    def visitJsonObject(self, ctx):
        keys = [_string(k) for k in ctx.STRING()]
        if len(set(keys)) != len(keys):
            raise EALSyntaxError("Duplicate JSON object key")
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
                                    "reasoning", "claims", "arguments", "objections")}
    destinations = {Environment: "environments", Tool: "tools", Evidence: "evidence",
                    Assumption: "assumptions", Reasoning: "reasoning", Claim: "claims",
                    Argument: "arguments", Objection: "objections"}
    symbols = set()
    duplicates = []
    try:
        for declaration in tree.declaration():
            value = builder.visit(declaration.getChild(0))
            if value.name in symbols:
                duplicates.append(value.name)
            symbols.add(value.name)
            groups[destinations[type(value)]][value.name] = value
    except (RecursionError, ValueError, OverflowError) as exc:
        raise EALSyntaxError(f"Invalid JSON data: {exc}") from exc
    return Program(language=_string(tree.STRING()), source_digest=hashlib.sha256(encoded).hexdigest(),
                   **groups, duplicates=tuple(duplicates), declaration_count=len(tree.declaration()))
