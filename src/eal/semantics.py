"""Name binding and static checks, kept separate from recognition and evaluation."""
from __future__ import annotations

from collections import deque
from dataclasses import fields, is_dataclass, replace
from datetime import datetime, timezone
from functools import lru_cache
import json
import math
import re
from types import UnionType
from typing import Any, get_args, get_origin, get_type_hints

from .model import Diagnostic, Program
from .abstractions import lower_patterns
from .modes import evidence_kind, validate_mode
from .propositions import proposition_errors

# Counts source declarations, reusable pattern bodies and generated arguments.
MAX_DECLARATIONS = 4096
MAX_PREMISE_DEPTH = 128
_PATH = re.compile(r"[A-Za-z_][A-Za-z_0-9-]*(?:\.[A-Za-z_][A-Za-z_0-9-]*)*\Z")
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")
# Contextual words explicitly admitted by grammar/identifier are absent here.
_RESERVED_NAMES = frozenset("""language environment tool version evidence kind max_age input assumption statement validate valid_from
valid_until reasoning rationale backing claim argument conclusion assumptions premises
objection target require true false null""".split())


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
    """Accept exactly finite UTF-8 JSON data, with bounded traversal."""
    pending = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if depth > 64 or nodes > 100_000:
            raise ValueError("JSON resource limit exceeded")
        if type(item) is dict:
            if any(type(key) is not str for key in item):
                raise ValueError("JSON object keys must be strings")
            for key in item:
                key.encode("utf-8")
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            item.encode("utf-8")
        elif type(item) is float:
            if not math.isfinite(item):
                raise ValueError("JSON numbers must be finite")
        elif item is not None and type(item) not in (bool, int):
            raise ValueError("Only JSON values are accepted")


@lru_cache(maxsize=None)
def _field_types(cls):
    return get_type_hints(cls)


def _ir_shape_errors(program):
    """Check the public typed-IR boundary before any pass dereferences it.

    Python dataclass annotations do not enforce types. Reject malformed direct
    constructions just as recognition rejects malformed authored source.
    JSON-bearing Any fields receive their dedicated checks in validation.
    """
    pending = [(program, Program, "program", None)]
    errors = []
    visited = 0
    while pending:
        value, expected, path, declaration = pending.pop()
        visited += 1
        if visited > 100_000:
            return [Diagnostic("resource_limit", "Typed IR exceeds 100000 structural values")]
        if expected is Any:
            continue
        origin = get_origin(expected)
        if origin is UnionType:
            alternatives = get_args(expected)
            expected = next((option for option in alternatives if type(value) is option), None)
            if expected is None:
                errors.append(Diagnostic("invalid_ir", f"{path} has the wrong type", declaration,
                                         expected=str(alternatives), actual=type(value).__name__))
                continue
            origin = get_origin(expected)
        expected_type = origin or expected
        if type(value) is not expected_type and not (expected_type is float and type(value) is int):
            errors.append(Diagnostic("invalid_ir", f"{path} has the wrong type", declaration,
                                     expected=str(expected), actual=type(value).__name__))
            continue
        if is_dataclass(value):
            owner = getattr(value, "name", declaration)
            declaration = owner if type(owner) is str else declaration
            types = _field_types(type(value))
            pending.extend((getattr(value, field.name), types[field.name], f"{path}.{field.name}", declaration)
                           for field in fields(value))
        elif expected_type is dict:
            key_type, value_type = get_args(expected)
            for key, child in value.items():
                pending.append((key, key_type, f"{path} key", declaration))
                pending.append((child, value_type, f"{path}[{key!r}]", declaration))
        elif expected_type is tuple:
            item_type, _ = get_args(expected)
            pending.extend((child, item_type, f"{path}[{index}]", declaration)
                           for index, child in enumerate(value))
        elif expected_type is str:
            try:
                value.encode("utf-8")
            except UnicodeError:
                errors.append(Diagnostic("invalid_unicode", f"{path} requires valid Unicode text", declaration))
    return errors


def _output_scalar_types(schema, path):
    """Return possible scalar types, None for unconstrained JSON, or no types.

    Unknown fields of a closed schema and traversal through a scalar have no
    possible type. Open JSON fields remain runtime-checked by their contract.
    """
    if "anyOf" in schema:
        choices = [_output_scalar_types(choice, path) for choice in schema["anyOf"]]
        return None if None in choices else set().union(*choices)
    kind = schema.get("type")
    if kind == "json":
        return None
    if not path:
        return {kind} if kind in {"number", "integer", "boolean", "string", "null"} else set()
    if kind != "object":
        return set()
    field, *rest = path
    child = schema.get("properties", {}).get(field, schema.get("additionalProperties", False))
    return _output_scalar_types(child, rest) if isinstance(child, dict) else set()


def validate(program: Program, *, registry=None) -> list[Diagnostic]:
    """Run ordered typed-IR, identity, declaration, binding and graph passes."""
    shape_errors = _ir_shape_errors(program)
    if shape_errors:
        return shape_errors
    from .methods import default_registry
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

    def identifier(name, owner):
        if not _IDENTIFIER.fullmatch(name) or name in _RESERVED_NAMES:
            error("invalid_identifier", f"{name!r} cannot be represented as an EAL identifier", owner)

    if not _validate_declarations(program, error, identifier):
        return problems
    _validate_predicates(program, error)
    _validate_tools_and_evidence(program, error, reference, identifier)
    _validate_assumptions(program, error, reference, scope)
    _validate_reasoning_and_claims(program, registry, error, reference)
    _validate_arguments(program, registry, error, reference, scope)
    _validate_objections(program, error, reference, scope)
    _validate_aspic_annotations(program, problems)
    _validate_dependencies(program, error)
    return problems


def _validate_declarations(program, error, identifier):
    """Check resource bounds, identity and expanded authoring consistency."""
    collections = (program.environments, program.tools, program.evidence,
                   program.assumptions, program.reasoning, program.claims,
                   program.arguments, program.objections, program.patterns,
                   program.applications)
    actual_count = sum(len(table) for table in collections) + len(program.patterns) + len(program.aspic)
    if max(actual_count, program.declaration_count) > MAX_DECLARATIONS:
        error("resource_limit", f"At most {MAX_DECLARATIONS} declaration/body records after pattern expansion are supported")
        return False
    # A mapping key and its declaration name are one identity, including for
    # callers using the Python IR API instead of the source recogniser.
    seen = set()
    duplicate_names = set(program.duplicates)
    for table in collections:
        for name, value in table.items():
            identifier(name, value.name)
            if name != value.name:
                error("declaration_identity", "Declaration key must equal its declared name", name,
                      expected=name, actual=value.name)
            generated = table is program.arguments and value.origin is not None
            if not generated:
                if name in seen:
                    duplicate_names.add(name)
                seen.add(name)
    for pattern in program.patterns.values():
        for parameter in pattern.parameters:
            identifier(parameter.name, pattern.name)
    for application in program.applications.values():
        for binding in application.arguments:
            identifier(binding.name, application.name)
    for name in sorted(duplicate_names):
        error("duplicate_symbol", f"Symbol {name!r} is declared more than once", name)

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
    return True


def _validate_predicates(program, error):
    """Check predicate paths, operands and operators in source order."""
    for collection in (program.environments, program.evidence, program.reasoning):
        for value in collection.values():
            if collection is not program.reasoning and not value.predicates:
                error("missing_predicate", "An environment or evidence declaration requires a predicate", value.name)
            for predicate in value.predicates:
                if not _PATH.fullmatch(predicate.path):
                    error("invalid_path", "Predicate paths must be dotted JSON object field names", value.name)
                if predicate.operator not in ("==", "!=", "<", "<=", ">", ">="):
                    error("invalid_comparison", "Predicate operator must be ==, !=, <, <=, > or >=", value.name)
                expected = predicate.expected
                if expected is not None and type(expected) not in (str, bool, int, float):
                    error("invalid_predicate", "Predicate operands must be JSON scalar values", value.name)
                elif isinstance(expected, str):
                    try:
                        expected.encode("utf-8")
                    except UnicodeError:
                        error("invalid_unicode", "Predicate operands require valid Unicode text", value.name)
                if isinstance(expected, float) and not math.isfinite(expected):
                    error("invalid_number", "Predicate numbers must be finite", value.name)
                if predicate.operator in ("<", "<=", ">", ">=") and (expected is None or isinstance(expected, bool)):
                    error("invalid_comparison", "Ordered comparisons require a number or string", value.name)


def _validate_tools_and_evidence(program, error, reference, identifier):
    """Check tool contracts and evidence requests."""
    for value in program.tools.values():
        if not value.version.strip():
            error("empty_version", "A tool requires an explicit nonempty version", value.name)
    for value in program.evidence.values():
        identifier(value.kind, value.name)
        reference(value.tool, program.tools, "tool", value.name)
        reference(value.environment, program.environments, "environment", value.name)
        try:
            finite_age = math.isfinite(value.max_age)
        except OverflowError:
            finite_age = False
        if not finite_age or value.max_age < 0:
            error("invalid_age", "max_age must be a finite nonnegative number of seconds", value.name)
        try:
            _check_json_resources(value.input)
            json.dumps(value.input, allow_nan=False, ensure_ascii=False).encode("utf-8")
        except (ValueError, TypeError, RecursionError):
            error("invalid_input", "Tool input must be finite JSON data", value.name)


def _validate_assumptions(program, error, reference, scope):
    """Check assumption bindings, scope and declared interval."""
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


def _validate_reasoning_and_claims(program, registry, error, reference):
    """Check method output predicates and claim propositions."""
    from .methods import is_method_identifier
    for value in program.reasoning.values():
        contract = registry.get(value.method)
        if not is_method_identifier(value.method):
            error("invalid_method_reference", "A method requires an explicit versioned identifier such as 'structured/1'", value.name,
                  expected="versioned method identifier", actual=value.method)
        elif contract is None:
            error("unknown_method", f"Unknown registered reasoning method {value.method!r}; use an installed versioned identifier", value.name,
                  expected="registered versioned method identifier", actual=value.method)
        if contract is not None:
            for predicate in value.predicates:
                types = _output_scalar_types(contract.output_schema, predicate.path.split("."))
                if types is None:
                    continue
                if not types:
                    error("reasoning_predicate_path", f"Method {value.method!r} has no scalar output at {predicate.path!r}",
                          value.name, expected="declared scalar method output", actual=predicate.path)
                    continue
                operand = predicate.expected
                actual = {str: "string", bool: "boolean", int: "number", float: "number",
                          type(None): "null"}.get(type(operand), type(operand).__name__)
                allowed = {"number" if kind == "integer" else kind for kind in types}
                if actual not in allowed:
                    error("reasoning_predicate_type", f"Predicate for {predicate.path!r} has an incompatible operand type",
                          value.name, expected=" | ".join(sorted(allowed)), actual=actual)
        if not value.rationale.strip():
            error("empty_rationale", "A reasoning declaration requires its rationale", value.name)
        for item in value.backing:
            reference(item, program.evidence, "backing evidence", value.name)
    for value in program.claims.values():
        if not value.statement.strip():
            error("empty_statement", "A claim requires a statement", value.name)
        reference(value.environment, program.environments, "environment", value.name)
        if value.proposition is not None:
            if not _PATH.fullmatch(value.proposition.result.path):
                error("invalid_path", "Proposition result paths must be dotted JSON object field names", value.name)
            if value.proposition.result.operator not in ("==", "!=", "<", "<=", ">", ">="):
                error("invalid_comparison", "Proposition operator must be ==, !=, <, <=, > or >=", value.name)
            for message in proposition_errors(value.proposition, registry=registry):
                error("invalid_proposition", message, value.name)


def _validate_arguments(program, registry, error, reference, scope):
    """Check argument dependencies and typed evidence bindings."""
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


def _validate_objections(program, error, reference, scope):
    """Check attack targets, source scopes and references."""
    target_tables = {"claim": program.claims, "reasoning": program.reasoning,
                     "assumption": program.assumptions, "argument": program.arguments,
                     "objection": program.objections}
    scopes = objection_scopes(program)
    for value in program.objections.values():
        table = target_tables.get(value.target_kind)
        if table is None:
            error("invalid_objection_target", "Objection target kind must be claim, reasoning, assumption, argument or objection",
                  value.name, actual=value.target_kind)
            continue
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


def _validate_aspic_annotations(program, problems):
    """Check authored formal relationships independently of EAL prose and observations."""
    targets = {"evidence": program.evidence, "assumption": program.assumptions,
               "argument": program.arguments, "objection": program.objections,
               "claim": program.claims}
    seen = set()
    ranked_arguments = {item.name for item in program.aspic
                        if item.kind == "rank" and item.target_kind == "argument"}

    def error(code, message, directive, *, expected=None, actual=None):
        problems.append(Diagnostic(code, message, directive.name, directive.span,
                                   expected, actual))

    for directive in program.aspic:
        if directive.kind == "strict":
            valid = directive.target_kind == "argument" and directive.other is None and directive.rank is None
            key = (directive.kind, directive.target_kind, directive.name)
        elif directive.kind == "rank":
            valid = (directive.target_kind in ("evidence", "assumption", "argument", "objection")
                     and directive.other is None and type(directive.rank) is int
                     and 0 <= directive.rank <= 1000)
            key = (directive.kind, directive.target_kind, directive.name)
        elif directive.kind == "contrary":
            valid = (directive.target_kind == "claim" and directive.rank is None
                     and directive.other is not None)
            key = (directive.kind, directive.name, directive.other)
        else:
            valid = False
            key = (directive.kind, directive.target_kind, directive.name)
        if not valid:
            error("invalid_aspic_annotation", "Invalid formal directive or rank; ranks must be integers from 0 through 1000", directive)
        if not directive.review.strip():
            error("missing_aspic_review", "A formal relationship requires a nonempty review reference", directive)
        if key in seen:
            error("duplicate_aspic_annotation", "A formal relationship is declared more than once", directive)
        seen.add(key)
        table = targets.get(directive.target_kind)
        if table is None or directive.name not in table:
            error("unknown_aspic_reference", f"Unknown formal {directive.target_kind} target {directive.name!r}", directive)
        if directive.kind == "contrary":
            if directive.other == directive.name:
                error("invalid_aspic_contrary", "A claim cannot be contrary to itself", directive)
            if directive.other not in program.claims:
                error("unknown_aspic_reference", f"Unknown contrary claim {directive.other!r}", directive)
            if directive.name in program.claims and directive.other in program.claims:
                first = program.claims[directive.name].environment
                second = program.claims[directive.other].environment
                if first != second:
                    error("aspic_environment_mismatch", "Contrary claims require the same EAL environment", directive,
                          expected=first, actual=second)
        if directive.kind == "strict" and directive.name in ranked_arguments:
            error("aspic_strict_rank", "A strict rule cannot have a defeasible rank", directive)


def _validate_dependencies(program, error):
    """Bound the acyclic premise graph without recursive traversal."""
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


def objection_scopes(program: Program) -> dict[str, set[str]]:
    """Infer source scopes without traversing the potentially cyclic attack graph."""
    return {name: {program.evidence[e].environment for e in value.evidence if e in program.evidence}
                  | {program.claims[p].environment for p in value.premises if p in program.claims}
            for name, value in program.objections.items()}
