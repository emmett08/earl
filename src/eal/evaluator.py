"""Pure bounded support derivation over scoped observations and explicit objections.

The calculus evaluates authored relations. It cannot establish that a natural-
language rationale is true, deductively valid, or sufficient for its conclusion.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import math
import operator
from typing import Any

from .model import Diagnostic, Environment, Predicate, Program
from .modes import assess_mode
from .semantics import parse_time, validate, objection_scopes
from .propositions import prepare_binding, check_result

MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 100_000
MAX_RECORD_BYTES = 4 * 1024 * 1024


def _json_value(value, depth=0, budget=None):
    if budget is None:
        budget = [MAX_JSON_NODES]
    budget[0] -= 1
    if depth > MAX_JSON_DEPTH or budget[0] < 0:
        raise ValueError("JSON resource limit exceeded")
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("JSON numbers must be finite")
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("JSON object keys must be strings")
        return {key: _json_value(item, depth + 1, budget) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item, depth + 1, budget) for item in value]
    raise ValueError("Only JSON values are accepted")


def _canonical_bytes(value) -> bytes:
    return json.dumps(_json_value(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def canonical_digest(value) -> str:
    """SHA-256 of canonical finite UTF-8 JSON, with bounded nesting and nodes."""
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def environment_fingerprint(name: str, context: Mapping[str, Any]) -> str:
    return canonical_digest({"environment": name, "context": context})


def _entry(status, reasons, **details):
    return {"status": status, "reasons": reasons, **details}


@dataclass(frozen=True)
class _PredicateCheck:
    holds: bool
    comparable: bool
    reason: str


@dataclass(frozen=True)
class EvidenceVerdict:
    """Private structural decision alongside the unchanged public evidence entry.

    ``complete`` means identity, scope, freshness, payload and every declared
    predicate could be checked. A complete predicate may still evaluate false.
    """

    entry: dict[str, Any]
    complete: bool


def _check_predicate(predicate: Predicate, value) -> _PredicateCheck:
    actual = value
    for field in predicate.path.split("."):
        if not isinstance(actual, Mapping) or field not in actual:
            return _PredicateCheck(False, False, f"Field {predicate.path!r} is missing")
        actual = actual[field]
    expected = predicate.expected
    numeric = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)
    same_type = type(actual) is type(expected) or (numeric(actual) and numeric(expected))
    if not same_type or isinstance(actual, (dict, list)):
        return _PredicateCheck(False, False, f"Field {predicate.path!r} has an incompatible type")
    if isinstance(actual, float) and not math.isfinite(actual):
        return _PredicateCheck(False, False, f"Field {predicate.path!r} is not finite")
    comparison = {"==": operator.eq, "!=": operator.ne, "<": operator.lt,
                  "<=": operator.le, ">": operator.gt, ">=": operator.ge}[predicate.operator]
    try:
        satisfied = comparison(actual, expected)
    except TypeError:
        return _PredicateCheck(False, False, f"Field {predicate.path!r} cannot use {predicate.operator}")
    return _PredicateCheck(satisfied, True,
                           f"Field {predicate.path!r} {predicate.operator} {expected!r} "
                           f"{'holds' if satisfied else 'does not hold'} (observed {actual!r})")


def _predicate(predicate: Predicate, value) -> tuple[bool, str]:
    """Retain the public diagnostic and ordering contract for existing callers."""
    check = _check_predicate(predicate, value)
    return check.holds, check.reason


def assess_environment(environment: Environment, context: Mapping[str, Any]) -> dict:
    """Produce the same public scope entry for evaluation and packet checks."""
    outcomes = [_predicate(predicate, context) for predicate in environment.predicates]
    return _entry("matched" if all(ok for ok, _ in outcomes) else "out_of_scope",
                  [reason for _, reason in outcomes])


def assess_evidence_record(program: Program, name: str, record: Mapping | None, *,
                           instant: datetime, context: Mapping[str, Any],
                           environment_matched: bool) -> EvidenceVerdict:
    """Check a record once, independently of explanation wording."""
    evidence = program.evidence[name]
    reasons = []
    if not environment_matched:
        reasons.append(f"Environment {evidence.environment!r} does not match supplied context")
    if not isinstance(record, Mapping):
        reasons.append("No evidence record is available")
        return EvidenceVerdict(_entry("unavailable", reasons), False)
    tool = program.tools[evidence.tool]
    expected = {"evidence_id": name, "source_digest": program.source_digest,
                "tool": tool.name, "tool_version": tool.version, "mode": tool.mode,
                "evidence_kind": evidence.kind,
                "environment": evidence.environment,
                "environment_fingerprint": environment_fingerprint(evidence.environment, context),
                "input_digest": canonical_digest(evidence.input)}
    for key, wanted in expected.items():
        if record.get(key) != wanted:
            reasons.append(f"Record {key} does not match the declared evidence request")
    if record.get("status") != "ok":
        reasons.append("Tool execution did not produce an ok observation")
    if not isinstance(record.get("run_id"), str) or not record["run_id"].strip():
        reasons.append("Record requires a nonempty run_id")
    try:
        collected = parse_time(record.get("collected_at"))
        age = (instant - collected).total_seconds()
        if age < 0:
            reasons.append("Observation is dated after the assessment time")
        elif age > evidence.max_age:
            reasons.append(f"Observation age {age:g}s exceeds max_age {evidence.max_age:g}s")
    except (ValueError, TypeError, OverflowError):
        reasons.append("Record collected_at must be an ISO-8601 timestamp with timezone")
    try:
        if "value" not in record:
            raise ValueError("Record has no JSON value")
        encoded = _canonical_bytes(record["value"])
        if len(encoded) > MAX_RECORD_BYTES:
            raise ValueError("Record value exceeds byte limit")
        if hashlib.sha256(encoded).hexdigest() != record.get("data_digest"):
            reasons.append("Record data_digest does not match its JSON value")
    except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
        reasons.append(f"Invalid observation value: {exc}")
    complete = not reasons
    if complete:
        outcomes = [_check_predicate(p, record["value"]) for p in evidence.predicates]
        reasons = [outcome.reason for outcome in outcomes]
        complete = all(outcome.comparable for outcome in outcomes)
        available = all(outcome.holds for outcome in outcomes)
    else:
        available = False
    return EvidenceVerdict(_entry("available" if available else "unavailable", reasons,
                                  tool=tool.name, mode=tool.mode, run_id=record.get("run_id")), complete)


def evaluate(program: Program, records: Mapping[str, Mapping], *, now: datetime | str,
             context: Mapping[str, Any], registry=None) -> dict:
    """Derive scoped claim statuses with explicit time and explanatory dependencies.

    Evidence integrity fields are checked for consistency, not authenticated.
    Independent alternative arguments survive attacks on another derivation.
    """
    from .methods import default_registry
    registry = registry or default_registry()
    instant = parse_time(now)
    if not isinstance(context, Mapping) or not isinstance(records, Mapping):
        raise ValueError("Context and records must be mappings")
    if len(records) > 4096:
        raise ValueError("At most 4096 evidence records may be supplied")
    diagnostics = validate(program, registry=registry)
    result = {"language": program.language, "source_digest": program.source_digest,
              "assessed_at": instant.isoformat().replace("+00:00", "Z"),
              "context_fingerprint": canonical_digest(context),
              "method_registry_fingerprint": registry.fingerprint,
              "valid": not diagnostics, "diagnostics": [asdict(d) for d in diagnostics],
              **{name: {} for name in ("environments", "evidence", "assumptions", "reasoning",
                                      "objections", "arguments", "claims")}}
    if diagnostics:
        return result
    for name, environment in program.environments.items():
        result["environments"][name] = assess_environment(environment, context)
    for name, evidence in program.evidence.items():
        result["evidence"][name] = assess_evidence_record(
            program, name, records.get(name), instant=instant, context=context,
            environment_matched=result["environments"][evidence.environment]["status"] == "matched"
        ).entry

    return _evaluate_arguments(program, records, instant, result, registry)


def _compute_argument(program, argument, claim, records, premises, registry):
    """Calculate a locally usable method result before dialectical acceptance.

    Premise entries here describe source-available derivations, not accepted
    arguments. The support/attack solver separately decides final acceptance.
    """
    method = program.reasoning[argument.reasoning]
    source_ids = set(argument.evidence) | set(method.backing)
    source_ids.update(program.assumptions[a].validation for a in argument.assumptions)
    sources = [{"id": e, "kind": program.evidence[e].kind, "value": records[e]["value"]}
               for e in sorted(source_ids)]
    binding = None
    if claim.proposition is not None:
        selected = next(item for item in sources if item["id"] == argument.binding)
        payload, binding = prepare_binding(claim.proposition, method.method,
                                           argument.binding, selected["value"], registry=registry)
        sources = [{**item, "value": payload} if item["id"] == argument.binding else item
                   for item in sources]
    if binding is not None and binding["status"] == "unsupported":
        return {"status": "unsupported", "method": method.method,
                "reasons": binding["reasons"], "details": {}, "binding": binding}, False
    computation = assess_mode(method.method, sources, premises, registry=registry)
    if binding is not None:
        if computation["status"] == "supported":
            binding = check_result(claim.proposition, method.method, computation["details"], binding,
                                   registry=registry)
        else:
            binding = {**binding, "status": "unsupported",
                       "reasons": ["The bound computation did not produce a usable result"]}
        computation["binding"] = binding
    if computation["status"] != "supported":
        return computation, False
    outcomes = [_predicate(p, computation["details"]) for p in method.predicates]
    computation = {**computation, "predicates": [
        {"holds": ok, "reason": reason} for ok, reason in outcomes]}
    usable = all(ok for ok, _ in outcomes) and (binding is None or binding["status"] == "supported")
    return computation, usable


def _evaluate_arguments(program, records, instant, result, registry):
    """EAL/2 finite least-information AND/OR support and attack semantics."""
    from .dialectic import ArgumentationError, MAX_COMPOSED_EDGES, solve_composed

    # Source availability is independent of whether a derivation is accepted.
    # In particular, an attack cycle never makes a source available by itself.
    for name, assumption in program.assumptions.items():
        reasons = []
        if result["environments"][assumption.environment]["status"] != "matched":
            status = "out_of_scope"
            reasons.append(f"Environment {assumption.environment!r} does not match supplied context")
        else:
            if assumption.valid_from and instant < parse_time(assumption.valid_from):
                reasons.append("The assumption's validity interval has not begun")
            if assumption.valid_until and instant >= parse_time(assumption.valid_until):
                reasons.append("The assumption's validity interval has ended")
            if result["evidence"][assumption.validation]["status"] != "available":
                reasons.append(f"Validation evidence {assumption.validation!r} is unavailable")
            status = "unsupported" if reasons else "supported"
            if not reasons:
                reasons.append(f"Validation evidence {assumption.validation!r} holds within the declared interval")
        result["assumptions"][name] = _entry(status, reasons, validation=assumption.validation)
    for name, reasoning in program.reasoning.items():
        reasons = [f"Method {reasoning.method}: backing evidence {e!r} is unavailable" for e in reasoning.backing
                   if result["evidence"][e]["status"] != "available"]
        result["reasoning"][name] = _entry(
            "unsupported" if reasons else "supported",
            reasons or [f"Method {reasoning.method} and backing are locally available; acceptance is assessed per application"],
            rationale=reasoning.rationale, backing=list(reasoning.backing),
            method=reasoning.method)
    by_conclusion = {name: [] for name in program.claims}
    for argument in program.arguments.values():
        by_conclusion[argument.conclusion].append(argument.name)
    source_claims = {}
    source_arguments = {}
    local_arguments = {}

    def source_claim(name):
        if name in source_claims:
            return source_claims[name]
        claim = program.claims[name]
        in_scope = result["environments"][claim.environment]["status"] == "matched"
        viable = []
        for argument_name in by_conclusion[name]:
            argument = program.arguments[argument_name]
            reasons = []
            computation = {"status": "not_run", "method": program.reasoning[argument.reasoning].method,
                           "reasons": ["Required sources are unavailable or out of scope"], "details": {}}
            dependencies = {"evidence": list(argument.evidence), "assumptions": list(argument.assumptions),
                            "premises": list(argument.premises), "reasoning": argument.reasoning}
            premise_entries = [{"id": p, **source_claim(p)} for p in argument.premises]
            source_states = [result["evidence"][e]["status"] == "available" for e in argument.evidence]
            source_states += [result["assumptions"][a]["status"] == "supported" for a in argument.assumptions]
            source_states.append(result["reasoning"][argument.reasoning]["status"] == "supported")
            for e in argument.evidence:
                reasons.append(f"Evidence {e!r} is {result['evidence'][e]['status']}")
            for a in argument.assumptions:
                reasons.append(f"Assumption {a!r} is locally {result['assumptions'][a]['status']}")
            for p in premise_entries:
                reasons.append(f"Premise claim {p['id']!r} {'has' if p['source_usable'] else 'lacks'} a source-usable derivation")
            if not in_scope:
                status = "out_of_scope"
                reasons.append(f"Conclusion environment {claim.environment!r} does not match supplied context")
                usable = False
            elif not all(source_states):
                status, usable = "unsupported", False
            else:
                # For local computation, a named premise is a declared input
                # obligation. Its acceptability is checked only by the solver.
                method_premises = [{**p, "status": "supported"} for p in premise_entries]
                computation, usable = _compute_argument(program, argument, claim, records,
                                                        method_premises, registry)
                computation["premise_acceptance"] = "deferred_to_composed_solver"
                reasons.extend(computation["reasons"])
                reasons.extend(p["reason"] for p in computation.get("predicates", []))
                if "binding" in computation:
                    reasons.extend(computation["binding"]["reasons"])
                status = "supported" if usable else "unsupported"
            local_arguments[argument_name] = usable
            possible = usable and all(p["source_usable"] for p in premise_entries)
            source_arguments[argument_name] = possible
            if status == "supported" and not possible:
                status = "unsupported"
            result["arguments"][argument_name] = _entry(
                status, reasons, conclusion=name, dependencies=dependencies,
                reasoning_result=computation, source_usable=possible, locally_usable=usable,
                origin=asdict(argument.origin) if argument.origin is not None else None)
            if possible:
                viable.append(argument_name)
        entry = {"status": "supported" if viable else "unsupported", "source_usable": bool(viable),
                 "statement": claim.statement, "environment": claim.environment,
                 "proposition": asdict(claim.proposition) if claim.proposition else None,
                 "source_arguments": viable}
        source_claims[name] = entry
        return entry

    for name in program.claims:
        source_claim(name)
    scopes = objection_scopes(program)
    nodes = {f"argument:{name}": {"usable": local_arguments[name],
                                  "premises": list(dict.fromkeys(argument.premises))}
             for name, argument in program.arguments.items()}
    claims = {name: [f"argument:{a}" for a in argument_names]
              for name, argument_names in by_conclusion.items()}
    objection_sources = {}
    for name, objection in program.objections.items():
        environment = next(iter(scopes[name]))
        local = result["environments"][environment]["status"] == "matched" and all(
            result["evidence"][e]["status"] == "available" for e in objection.evidence)
        possible = local and all(source_claims[p]["source_usable"] for p in objection.premises)
        objection_sources[name] = possible
        nodes[f"objection:{name}"] = {"usable": local, "premises": list(dict.fromkeys(objection.premises))}
        result["objections"][name] = _entry(
            "inactive", [f"Objection evidence {e!r} is {result['evidence'][e]['status']}" for e in objection.evidence],
            target_kind=objection.target_kind, target=objection.target, environment=environment,
            evidence=list(objection.evidence), premises=list(objection.premises), source_usable=possible)

    attacks = set()
    dependency_edges = sum(len(node["premises"]) for node in nodes.values()) + sum(map(len, claims.values()))
    try:
        for name, objection in program.objections.items():
            source = f"objection:{name}"
            scope = next(iter(scopes[name]))
            if objection.target_kind == "objection":
                targets = [f"objection:{objection.target}"]
            else:
                targets = []
                for argument_name, argument in program.arguments.items():
                    if program.claims[argument.conclusion].environment != scope:
                        continue
                    applies = ((objection.target_kind == "claim" and argument.conclusion == objection.target)
                               or (objection.target_kind == "reasoning" and argument.reasoning == objection.target)
                               or (objection.target_kind == "assumption" and objection.target in argument.assumptions)
                               or (objection.target_kind == "argument" and argument_name == objection.target))
                    if applies:
                        targets.append(f"argument:{argument_name}")
            for target in targets:
                attacks.add((source, target))
                if len(attacks) + dependency_edges > MAX_COMPOSED_EDGES:
                    raise ArgumentationError("Composed attack and support graph exceeds the edge limit")
        grounded = solve_composed(nodes, claims, [list(edge) for edge in sorted(attacks)])
    except ArgumentationError as exc:
        result["valid"] = False
        result["diagnostics"].append(asdict(Diagnostic("resource_limit", str(exc))))
        for group in ("arguments", "claims", "objections"):
            result[group] = {}
        return result
    attackers = {name: [] for name in nodes}
    for source, target in sorted(attacks):
        attackers[target].append(source)
    result["dialectic"] = {**grounded, "attacks": [list(edge) for edge in sorted(attacks)],
                            "construction": "EAL/2 scoped applications with conjunctive claim support"}
    for name, argument in program.arguments.items():
        entry = result["arguments"][name]
        label = grounded["nodes"][f"argument:{name}"]
        entry["grounded_label"] = label
        entry["attackers"] = attackers[f"argument:{name}"]
        entry["premise_labels"] = {p: grounded["claims"][p] for p in argument.premises}
        entry["reasons"].append(f"Least-information acceptability label: {label}")
        if source_arguments[name]:
            entry["status"] = "supported" if label == "accepted" else "contested"
    for name, objection in program.objections.items():
        entry = result["objections"][name]
        label = grounded["nodes"][f"objection:{name}"]
        entry["grounded_label"] = label
        entry["attackers"] = attackers[f"objection:{name}"]
        entry["premise_labels"] = {p: grounded["claims"][p] for p in objection.premises}
        entry["status"] = ({"accepted": "active", "rejected": "defeated", "undecided": "undecided"}[label]
                           if objection_sources[name] else "inactive")
        entry["reasons"].append(f"Least-information acceptability label: {label}")
        for p in objection.premises:
            entry["reasons"].append(f"Supporting claim {p!r} is {grounded['claims'][p]}")
    for name, claim in program.claims.items():
        label = grounded["claims"][name]
        supporting = [a for a in by_conclusion[name] if result["arguments"][a]["status"] == "supported"]
        contested = [a for a in by_conclusion[name] if result["arguments"][a]["status"] == "contested"]
        in_scope = result["environments"][claim.environment]["status"] == "matched"
        if not in_scope:
            status, reasons = "out_of_scope", [f"Environment {claim.environment!r} does not match supplied context"]
        elif supporting:
            status, reasons = "supported", [f"Accepted derivations: {', '.join(supporting)}"]
        elif contested:
            status, reasons = "contested", [f"Source-usable derivations are rejected or undecided: {', '.join(contested)}"]
        else:
            status, reasons = "unsupported", ["No source-usable derivation supplies support; this does not establish falsity"]
        reasons.append(f"Least-information acceptability label: {label}; rejection does not establish claim falsity")
        direct = {o: result["objections"][o]["status"] for o, obj in program.objections.items()
                  if obj.target_kind == "claim" and obj.target == name}
        result["claims"][name] = _entry(
            status, reasons, grounded_label=label, statement=claim.statement, environment=claim.environment,
            supporting_arguments=supporting, contested_arguments=contested,
            objections=[o for o, s in direct.items() if s == "active"],
            undecided_objections=[o for o, s in direct.items() if s == "undecided"],
            objection_statuses=direct, source_usable=source_claims[name]["source_usable"],
            proposition=asdict(claim.proposition) if claim.proposition else None, prose_verified=False)
    # A method declaration is reusable across environments; objections apply to
    # applications in their source scope rather than globally disabling it.
    for kind, declarations in (("reasoning", program.reasoning), ("assumption", program.assumptions)):
        entries = result["assumptions" if kind == "assumption" else "reasoning"]
        for name in declarations:
            applicable = {o: result["objections"][o]["status"] for o, obj in program.objections.items()
                          if obj.target_kind == kind and obj.target == name}
            entries[name]["objection_statuses"] = applicable
            if kind == "assumption" and entries[name]["status"] == "supported" and any(
                    status in ("active", "undecided") for status in applicable.values()):
                entries[name]["status"] = "contested"
    return result
