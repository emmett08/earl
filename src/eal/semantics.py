"""Name binding and static checks, kept separate from recognition and evaluation."""
from __future__ import annotations

from collections import deque
from dataclasses import replace
from datetime import datetime, timezone
import json
import math
import re

from .model import Diagnostic, Program
from .abstractions import lower_patterns
from .modes import evidence_kind, validate_mode
from .propositions import proposition_errors

MAX_DECLARATIONS = 4096
MAX_PREMISE_DEPTH = 128
_PATH = re.compile(r"[A-Za-z_][A-Za-z_0-9-]*(?:\.[A-Za-z_][A-Za-z_0-9-]*)*\Z")


def parse_time(value: str | datetime) -> datetime:
    """Parse an explicit instant, rejecting naive timestamps and dates."""
    if isinstance(value, str):
        if "T" not in value:
            raise ValueError("Timestamp requires a date and time separated by T")
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise ValueError("Timestamp is outside the supported UTC range") from exc


def _check_json_resources(value):
    pending = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if depth > 64 or nodes > 100_000:
            raise ValueError("JSON resource limit exceeded")
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)


def validate(program: Program, *, registry=None) -> list[Diagnostic]:
    """Resolve names, verify types/scopes, reject cycles and resource excess."""
    from .methods import default_registry, is_method_identifier
    registry = registry or default_registry()
    problems: list[Diagnostic] = [
        diagnostic if diagnostic.span is not None else replace(
            diagnostic, span=program.locations.get(diagnostic.declaration))
        for diagnostic in program.lowering_diagnostics
    ]

    def error(code, message, declaration=None, *, expected=None, actual=None):
        problems.append(Diagnostic(code, message, declaration,
                                   program.locations.get(declaration), expected, actual))

    def reference(name, table, kind, owner):
        if name not in table:
            error("unknown_reference", f"Unknown {kind} {name!r}", owner,
                  expected=kind, actual=name)
            return False
        return True

    def scope(actual, expected, owner, dependency):
        if actual != expected:
            error("environment_mismatch", f"{dependency!r} uses environment {actual!r}; expected {expected!r}", owner,
                  expected=expected, actual=actual)

    # The retained authoring form and executable arguments must denote the same
    # program, including when callers construct or replace the typed IR directly.
    lowered = lower_patterns(program)
    stored_diagnostics = tuple(replace(d, span=None) for d in program.lowering_diagnostics)
    fresh_diagnostics = tuple(replace(d, span=None) for d in lowered.lowering_diagnostics)
    if (lowered.arguments != program.arguments or fresh_diagnostics != stored_diagnostics
            or lowered.declaration_count != program.declaration_count):
        changed = next((name for name in dict.fromkeys((*program.arguments, *lowered.arguments))
                        if program.arguments.get(name) != lowered.arguments.get(name)), None)
        error("stale_pattern_expansion",
              "Stored arguments or diagnostics differ from the declared patterns and applications; lower the edited program again",
              changed)

    if program.language != "EAL/2":
        error("unsupported_language", f"Expected EAL/2, found {program.language!r}",
              expected="EAL/2", actual=program.language)
    if program.declaration_count > MAX_DECLARATIONS:
        error("resource_limit", f"At most {MAX_DECLARATIONS} declarations are supported")
        return problems
    for name in program.duplicates:
        error("duplicate_symbol", f"Symbol {name!r} is declared more than once", name)
    for collection in (program.environments, program.evidence, program.reasoning):
        for value in collection.values():
            for predicate in value.predicates:
                if not _PATH.fullmatch(predicate.path):
                    error("invalid_path", "Predicate paths must be dotted JSON object field names", value.name)
                expected = predicate.expected
                if isinstance(expected, float) and not math.isfinite(expected):
                    error("invalid_number", "Predicate numbers must be finite", value.name)
                if predicate.operator in ("<", "<=", ">", ">=") and (expected is None or isinstance(expected, bool)):
                    error("invalid_comparison", "Ordered comparisons require a number or string", value.name)
    for value in program.tools.values():
        if not value.version.strip():
            error("empty_version", "A tool requires an explicit nonempty version", value.name)
    for value in program.evidence.values():
        reference(value.tool, program.tools, "tool", value.name)
        reference(value.environment, program.environments, "environment", value.name)
        if not math.isfinite(value.max_age) or value.max_age < 0:
            error("invalid_age", "max_age must be a finite nonnegative number of seconds", value.name)
        try:
            _check_json_resources(value.input)
            json.dumps(value.input, allow_nan=False, ensure_ascii=False).encode("utf-8")
        except (ValueError, TypeError, RecursionError):
            error("invalid_input", "Tool input must be finite JSON data", value.name)
    for value in program.assumptions.values():
        if not value.statement.strip():
            error("empty_statement", "An assumption requires a statement", value.name)
        reference(value.environment, program.environments, "environment", value.name)
        if reference(value.validation, program.evidence, "validation evidence", value.name):
            scope(program.evidence[value.validation].environment, value.environment, value.name, value.validation)
        dates = []
        for label, timestamp in (("valid_from", value.valid_from), ("valid_until", value.valid_until)):
            if timestamp is not None:
                try:
                    dates.append(parse_time(timestamp))
                except ValueError:
                    error("invalid_timestamp", f"{label} requires an ISO-8601 timestamp with timezone", value.name)
        if len(dates) == 2 and dates[0] >= dates[1]:
            error("invalid_interval", "valid_from must precede valid_until", value.name)
    for value in program.reasoning.values():
        contract = registry.get(value.method)
        if not is_method_identifier(value.method):
            error("invalid_method_reference", "A method requires an explicit versioned identifier such as 'structured/1'", value.name,
                  expected="versioned method identifier", actual=value.method)
        elif contract is None:
            error("unknown_method", f"Unknown registered reasoning method {value.method!r}; use an installed versioned identifier", value.name,
                  expected="registered versioned method identifier", actual=value.method)
        if not value.rationale.strip():
            error("empty_rationale", "A reasoning declaration requires its rationale", value.name)
        for item in value.backing:
            reference(item, program.evidence, "backing evidence", value.name)
    for value in program.claims.values():
        if not value.statement.strip():
            error("empty_statement", "A claim requires a statement", value.name)
        reference(value.environment, program.environments, "environment", value.name)
        if value.proposition is not None:
            for message in proposition_errors(value.proposition, registry=registry):
                error("invalid_proposition", message, value.name)
    for value in program.arguments.values():
        conclusion_exists = reference(value.conclusion, program.claims, "conclusion claim", value.name)
        reasoning_exists = reference(value.reasoning, program.reasoning, "reasoning", value.name)
        if not (value.evidence or value.assumptions or value.premises):
            error("empty_argument", "An argument requires evidence, assumptions or premise claims", value.name)
        expected = program.claims[value.conclusion].environment if conclusion_exists else None
        for items, table, kind in ((value.evidence, program.evidence, "evidence"),
                                   (value.assumptions, program.assumptions, "assumption"),
                                   (value.premises, program.claims, "premise claim")):
            for item in items:
                if reference(item, table, kind, value.name) and expected is not None:
                    scope(table[item].environment, expected, value.name, item)
        if reasoning_exists:
            method = program.reasoning[value.reasoning]
            contract = registry.get(method.method)
            source_ids = set(value.evidence) | set(method.backing)
            source_ids.update(program.assumptions[a].validation for a in value.assumptions
                              if a in program.assumptions)
            proposition = program.claims[value.conclusion].proposition if conclusion_exists else None
            if proposition is not None:
                if value.binding is None:
                    error("missing_binding", "A typed conclusion requires an explicit evidence binding", value.name)
                else:
                    if reference(value.binding, program.evidence, "bound evidence", value.name):
                        if value.binding not in source_ids:
                            error("binding_source", "Bound evidence must be a source of this argument", value.name)
                        if program.evidence[value.binding].kind != evidence_kind(method.method, registry=registry):
                            error("binding_source", "Binding must select the method's computational evidence", value.name)
                for message in proposition_errors(proposition, method.method, registry=registry):
                    error("proposition_method", message, value.name)
            elif value.binding is not None:
                error("untyped_binding", "An evidence binding requires a typed conclusion", value.name)
            if proposition is None and contract is not None and contract.builtin_mode != "structured" and not method.predicates:
                error("missing_reasoning_predicate", "An untyped computational conclusion requires an explicit output predicate", value.name)
            kinds = [program.evidence[e].kind for e in sorted(source_ids) if e in program.evidence]
            for message in validate_mode(method.method, kinds, registry=registry):
                error("reasoning_evidence_contract", message, value.name)
            if expected is not None:
                for item in method.backing:
                    if item in program.evidence:
                        scope(program.evidence[item].environment, expected, value.name, item)
    target_tables = {"claim": program.claims, "reasoning": program.reasoning,
                     "assumption": program.assumptions, "argument": program.arguments,
                     "objection": program.objections}
    scopes = objection_scopes(program)
    for value in program.objections.values():
        table = target_tables[value.target_kind]
        target_exists = reference(value.target, table, value.target_kind, value.name)
        if not value.evidence and not value.premises:
            error("empty_objection", "An objection requires evidence or premise claims", value.name)
        if len(scopes[value.name]) > 1:
            error("environment_mismatch", "An objection's evidence and premise claims must share one environment", value.name)
        expected = set()
        if target_exists:
            if value.target_kind in ("claim", "assumption"):
                expected.add(table[value.target].environment)
            elif value.target_kind == "argument":
                conclusion = table[value.target].conclusion
                if conclusion in program.claims:
                    expected.add(program.claims[conclusion].environment)
            elif value.target_kind == "objection":
                expected.update(scopes[value.target])
        for items, sources, kind in ((value.evidence, program.evidence, "objection evidence"),
                                     (value.premises, program.claims, "objection premise claim")):
            for item in items:
                if reference(item, sources, kind, value.name):
                    for environment in sorted(expected):
                        scope(sources[item].environment, environment, value.name, item)
    # Edges point from a conclusion to its premises. Remove leaves iteratively,
    # computing longest paths without depending on Python recursion limits.
    graph = {name: set() for name in program.claims}
    for argument in program.arguments.values():
        if argument.conclusion in graph:
            graph[argument.conclusion].update(p for p in argument.premises if p in graph)
    incoming = {name: set() for name in graph}
    remaining = {name: len(deps) for name, deps in graph.items()}
    depth = {name: 0 for name in graph}
    for name, deps in graph.items():
        for dep in deps:
            incoming[dep].add(name)
    ready = deque(name for name in graph if not remaining[name])
    visited = 0
    while ready:
        name = ready.popleft()
        visited += 1
        for dependent in incoming[name]:
            depth[dependent] = max(depth[dependent], depth[name] + 1)
            remaining[dependent] -= 1
            if remaining[dependent] == 0:
                ready.append(dependent)
    if visited != len(graph):
        blocked = next(name for name in graph if remaining[name])
        error("dependency_cycle", "Premise claims must form an acyclic dependency graph", blocked)
    if depth and max(depth.values()) > MAX_PREMISE_DEPTH:
        error("resource_limit", f"Premise chains may contain at most {MAX_PREMISE_DEPTH} edges",
              max(depth, key=depth.get))
    return problems


def objection_scopes(program: Program) -> dict[str, set[str]]:
    """Infer source scopes without traversing the potentially cyclic attack graph."""
    return {name: {program.evidence[e].environment for e in value.evidence if e in program.evidence}
                  | {program.claims[p].environment for p in value.premises if p in program.claims}
            for name, value in program.objections.items()}
