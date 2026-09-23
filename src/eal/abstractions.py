"""Closed, typed argument-pattern lowering without textual substitution."""
from __future__ import annotations

from dataclasses import replace

from .model import Argument, ArgumentOrigin, Diagnostic, Pattern, Program

MAX_PATTERN_APPLICATIONS = 1000
MAX_EXPANDED_REFERENCES = 100_000
PARAMETER_KINDS = frozenset({"claim", "reasoning", "evidence", "assumption"})


def _references(pattern: Pattern):
    """Yield each body reference with the required kind of its clause."""
    yield pattern.conclusion, "claim", "conclusion"
    yield pattern.reasoning, "reasoning", "reasoning"
    for field, kind in (("evidence", "evidence"), ("assumptions", "assumption"),
                        ("premises", "claim")):
        for name in getattr(pattern, field):
            yield name, kind, field
    if pattern.binding is not None:
        yield pattern.binding, "evidence", "binding"


def lower_patterns(program: Program) -> Program:
    """Check all definitions, resolve named arguments and expand valid uses.

    Patterns have no global captures or nested applications. Substitution acts
    only on typed reference fields, preserving the identity of each dependency.
    Invalid lowering records diagnostics; static validation blocks execution.
    Reapplying this pass is idempotent, including its declaration accounting.
    """
    diagnostics: list[Diagnostic] = []

    def error(code, message, declaration, expected=None, actual=None):
        diagnostics.append(Diagnostic(code, message, declaration,
                                      program.locations.get(declaration), expected, actual))

    tables = {"claim": program.claims, "reasoning": program.reasoning,
              "evidence": program.evidence, "assumption": program.assumptions,
              "environment": program.environments, "tool": program.tools,
              "argument": program.arguments, "objection": program.objections,
              "pattern": program.patterns, "application": program.applications}
    symbol_kinds = {name: kind for kind, table in tables.items() for name in table}
    invalid_patterns = set()
    for pattern in program.patterns.values():
        before = len(diagnostics)
        if not (pattern.evidence or pattern.assumptions or pattern.premises):
            error("empty_pattern", "An argument pattern requires evidence, assumptions or premise claims",
                  pattern.name)
        parameters = {}
        for parameter in pattern.parameters:
            if parameter.name in parameters:
                error("duplicate_pattern_parameter",
                      f"Parameter {parameter.name!r} is declared more than once", pattern.name)
            parameters[parameter.name] = parameter.kind
            if parameter.kind not in PARAMETER_KINDS:
                error("invalid_pattern_parameter_kind",
                      f"Parameter {parameter.name!r} requires claim, reasoning, evidence or assumption",
                      pattern.name, "claim | reasoning | evidence | assumption", parameter.kind)
        for name, expected, clause in _references(pattern):
            actual = parameters.get(name)
            if actual is None:
                error("unbound_pattern_reference",
                      f"{clause} reference {name!r} must name a declared parameter; global capture is forbidden",
                      pattern.name, expected, "undeclared parameter")
            elif actual != expected:
                error("pattern_reference_kind",
                      f"{clause} parameter {name!r} has kind {actual!r}; expected {expected!r}",
                      pattern.name, expected, actual)
        if len(diagnostics) > before or pattern.name in program.duplicates:
            invalid_patterns.add(pattern.name)

    # Drop previously generated arguments so repeat lowering never copies output
    # back into the authored input or mistakes it for a name collision.
    arguments = {name: argument for name, argument in program.arguments.items()
                 if argument.origin is None}
    authored_names = set().union(*(set(table) for kind, table in tables.items()
                                  if kind not in ("argument", "application")), arguments)
    old_expansion_count = len(program.arguments) - len(arguments)
    if len(program.applications) > MAX_PATTERN_APPLICATIONS:
        declaration = next(iter(program.applications))
        error("resource_limit", f"At most {MAX_PATTERN_APPLICATIONS} pattern applications are supported",
              declaration)
        return replace(program, arguments=arguments, lowering_diagnostics=tuple(diagnostics),
                       declaration_count=program.declaration_count - old_expansion_count)

    expanded_references = 0
    for application in program.applications.values():
        before = len(diagnostics)
        pattern = program.patterns.get(application.pattern)
        if pattern is None:
            error("unknown_pattern", f"Unknown pattern {application.pattern!r}", application.name,
                  "pattern", symbol_kinds.get(application.pattern, "unknown reference"))
            continue
        if application.name in authored_names or application.name in program.duplicates:
            error("generated_symbol_collision",
                  f"Generated argument {application.name!r} collides with another declaration", application.name)
        if pattern.name in invalid_patterns:
            error("invalid_pattern", f"Pattern {pattern.name!r} has an invalid definition", application.name)
            continue
        parameters = {parameter.name: parameter.kind for parameter in pattern.parameters}
        bindings = {}
        for binding in application.arguments:
            if binding.name in bindings:
                error("duplicate_pattern_argument",
                      f"Argument {binding.name!r} is supplied more than once", application.name)
            bindings[binding.name] = binding.reference
            expected = parameters.get(binding.name)
            if expected is None:
                error("unknown_pattern_argument",
                      f"Pattern {pattern.name!r} has no parameter {binding.name!r}", application.name)
            elif binding.reference not in tables[expected]:
                actual = symbol_kinds.get(binding.reference, "unknown reference")
                error("pattern_argument_kind",
                      f"Argument {binding.name!r} must reference {expected}; {binding.reference!r} is {actual}",
                      application.name, expected, actual)
        for missing in sorted(parameters.keys() - bindings.keys()):
            error("missing_pattern_argument",
                  f"Pattern {pattern.name!r} requires argument {missing!r}", application.name,
                  parameters[missing], "missing")
        if len(diagnostics) != before:
            continue
        reference_count = sum(1 for _ in _references(pattern))
        if expanded_references + reference_count > MAX_EXPANDED_REFERENCES:
            error("resource_limit",
                  f"Pattern expansion permits at most {MAX_EXPANDED_REFERENCES} references", application.name)
            break
        expanded_references += reference_count
        arguments[application.name] = Argument(
            application.name, bindings[pattern.conclusion], bindings[pattern.reasoning],
            tuple(bindings[name] for name in pattern.evidence),
            tuple(bindings[name] for name in pattern.assumptions),
            tuple(bindings[name] for name in pattern.premises),
            bindings[pattern.binding] if pattern.binding is not None else None,
            ArgumentOrigin(pattern.name, application.name))
    new_expansion_count = sum(argument.origin is not None for argument in arguments.values())
    return replace(program, arguments=arguments, lowering_diagnostics=tuple(diagnostics),
                   declaration_count=program.declaration_count - old_expansion_count + new_expansion_count)
