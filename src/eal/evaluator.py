"""Pure bounded support derivation over scoped observations and explicit objections.

The calculus evaluates authored relations. It cannot establish that a natural-
language rationale is true, deductively valid, or sufficient for its conclusion.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
import math
import operator
from typing import Any

from .model import Predicate, Program
from .modes import assess_mode
from .semantics import parse_time, validate

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


def _predicate(predicate: Predicate, value) -> tuple[bool, str]:
    actual = value
    for field in predicate.path.split("."):
        if not isinstance(actual, Mapping) or field not in actual:
            return False, f"Field {predicate.path!r} is missing"
        actual = actual[field]
    expected = predicate.expected
    numeric = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)
    same_type = type(actual) is type(expected) or (numeric(actual) and numeric(expected))
    if not same_type or isinstance(actual, (dict, list)):
        return False, f"Field {predicate.path!r} has an incompatible type"
    if isinstance(actual, float) and not math.isfinite(actual):
        return False, f"Field {predicate.path!r} is not finite"
    comparison = {"==": operator.eq, "!=": operator.ne, "<": operator.lt,
                  "<=": operator.le, ">": operator.gt, ">=": operator.ge}[predicate.operator]
    try:
        satisfied = comparison(actual, expected)
    except TypeError:
        return False, f"Field {predicate.path!r} cannot use {predicate.operator}"
    return satisfied, (f"Field {predicate.path!r} {predicate.operator} {expected!r} "
                       f"{'holds' if satisfied else 'does not hold'} (observed {actual!r})")


def evaluate(program: Program, records: Mapping[str, Mapping], *, now: datetime | str,
             context: Mapping[str, Any]) -> dict:
    """Derive scoped claim statuses with explicit time and explanatory dependencies.

    Evidence integrity fields are checked for consistency, not authenticated.
    Independent alternative arguments survive attacks on another derivation.
    """
    instant = parse_time(now)
    if not isinstance(context, Mapping) or not isinstance(records, Mapping):
        raise ValueError("Context and records must be mappings")
    if len(records) > 4096:
        raise ValueError("At most 4096 evidence records may be supplied")
    diagnostics = validate(program)
    result = {"language": program.language, "source_digest": program.source_digest,
              "assessed_at": instant.isoformat().replace("+00:00", "Z"),
              "context_fingerprint": canonical_digest(context),
              "valid": not diagnostics, "diagnostics": [asdict(d) for d in diagnostics],
              **{name: {} for name in ("environments", "evidence", "assumptions", "reasoning",
                                      "objections", "arguments", "claims")}}
    if diagnostics:
        return result
    for name, environment in program.environments.items():
        outcomes = [_predicate(p, context) for p in environment.predicates]
        result["environments"][name] = _entry(
            "matched" if all(ok for ok, _ in outcomes) else "out_of_scope",
            [reason for _, reason in outcomes])
    for name, evidence in program.evidence.items():
        record = records.get(name)
        reasons = []
        if result["environments"][evidence.environment]["status"] != "matched":
            reasons.append(f"Environment {evidence.environment!r} does not match supplied context")
        if not isinstance(record, Mapping):
            reasons.append("No evidence record is available")
            result["evidence"][name] = _entry("unavailable", reasons)
            continue
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
        if not reasons:
            outcomes = [_predicate(p, record["value"]) for p in evidence.predicates]
            reasons = [reason for _, reason in outcomes]
            available = all(ok for ok, _ in outcomes)
        else:
            available = False
        result["evidence"][name] = _entry("available" if available else "unavailable", reasons,
                                           tool=tool.name, mode=tool.mode, run_id=record.get("run_id"))

    active = {kind: {} for kind in ("claim", "reasoning", "assumption")}
    for name, objection in program.objections.items():
        available = all(result["evidence"][e]["status"] == "available" for e in objection.evidence)
        result["objections"][name] = _entry(
            "active" if available else "inactive",
            [f"Objection evidence {e!r} is {result['evidence'][e]['status']}" for e in objection.evidence],
            target_kind=objection.target_kind, target=objection.target, evidence=list(objection.evidence))
        if available:
            active[objection.target_kind].setdefault(objection.target, []).append(name)
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
            if status == "supported" and name in active["assumption"]:
                status = "contested"
                reasons.append(f"Active objections: {', '.join(active['assumption'][name])}")
            if not reasons:
                reasons.append(f"Validation evidence {assumption.validation!r} holds within the declared interval")
        result["assumptions"][name] = _entry(status, reasons, validation=assumption.validation)
    for name, reasoning in program.reasoning.items():
        reasons = [f"Backing evidence {e!r} is unavailable" for e in reasoning.backing
                   if result["evidence"][e]["status"] != "available"]
        status = "unsupported" if reasons else "supported"
        if status == "supported" and name in active["reasoning"]:
            status = "contested"
            reasons.append(f"Active objections: {', '.join(active['reasoning'][name])}")
        if not reasons:
            reasons.append("The authored reasoning is available; its prose rationale is not mechanically proved")
        result["reasoning"][name] = _entry(status, reasons, rationale=reasoning.rationale,
                                             backing=list(reasoning.backing), mode=reasoning.mode)

    by_conclusion = {name: [] for name in program.claims}
    for argument in program.arguments.values():
        by_conclusion[argument.conclusion].append(argument)

    def assess_claim(name):
        if name in result["claims"]:
            return result["claims"][name]
        claim = program.claims[name]
        in_scope = result["environments"][claim.environment]["status"] == "matched"
        supporting, contested = [], []
        for argument in by_conclusion[name]:
            reasons = []
            computation = {"status": "not_run", "reasons": ["Required sources are unavailable or out of scope"], "details": {}}
            dependencies = {"evidence": list(argument.evidence), "assumptions": list(argument.assumptions),
                            "premises": list(argument.premises), "reasoning": argument.reasoning}
            if not in_scope:
                status = "out_of_scope"
                reasons.append(f"Conclusion environment {claim.environment!r} does not match supplied context")
            else:
                states = []
                for e in argument.evidence:
                    state = result["evidence"][e]["status"]
                    states.append("supported" if state == "available" else "unsupported")
                    reasons.append(f"Evidence {e!r} is {state}")
                for a in argument.assumptions:
                    state = result["assumptions"][a]["status"]
                    states.append(state)
                    reasons.append(f"Assumption {a!r} is {state}")
                for p in argument.premises:
                    state = assess_claim(p)["status"]
                    states.append(state)
                    reasons.append(f"Premise claim {p!r} is {state}")
                reasoning_state = result["reasoning"][argument.reasoning]["status"]
                states.append(reasoning_state)
                reasons.append(f"Reasoning {argument.reasoning!r} is {reasoning_state}")
                if any(state in ("unsupported", "out_of_scope") for state in states):
                    status = "unsupported"
                else:
                    method = program.reasoning[argument.reasoning]
                    source_ids = set(argument.evidence) | set(method.backing)
                    source_ids.update(program.assumptions[a].validation for a in argument.assumptions)
                    sources = [{"id": e, "kind": program.evidence[e].kind, "value": records[e]["value"]}
                               for e in sorted(source_ids) if result["evidence"][e]["status"] == "available"]
                    premises = [{"id": p, **result["claims"][p]} for p in argument.premises]
                    computation = assess_mode(method.mode, sources, premises)
                    reasons.extend(computation["reasons"])
                    if computation["status"] == "supported":
                        outcomes = [_predicate(p, computation["details"]) for p in method.predicates]
                        reasons.extend(reason for _, reason in outcomes)
                        computation = {**computation, "predicates": [
                            {"holds": ok, "reason": reason} for ok, reason in outcomes]}
                        if not all(ok for ok, _ in outcomes):
                            status = "unsupported"
                        else:
                            status = "contested" if "contested" in states else "supported"
                    else:
                        status = "unsupported"
                if name in active["claim"]:
                    reasons.append(f"Active claim objections: {', '.join(active['claim'][name])}")
                    if status == "supported":
                        status = "contested"
            result["arguments"][argument.name] = _entry(status, reasons, conclusion=name,
                                                          dependencies=dependencies, reasoning_result=computation)
            if status == "supported":
                supporting.append(argument.name)
            elif status == "contested":
                contested.append(argument.name)
        if not in_scope:
            status, reasons = "out_of_scope", [f"Environment {claim.environment!r} does not match supplied context"]
        elif supporting:
            status, reasons = "supported", [f"Uncontested derivations: {', '.join(supporting)}"]
        elif contested:
            status, reasons = "contested", [f"Contested derivations: {', '.join(contested)}"]
        else:
            status, reasons = "unsupported", ["No usable derivation supplies support; this does not establish falsity"]
            if name in active["claim"]:
                reasons.append(f"Active objections without a usable supporting derivation: {', '.join(active['claim'][name])}")
        entry = _entry(status, reasons, statement=claim.statement, environment=claim.environment,
                       supporting_arguments=supporting, contested_arguments=contested,
                       objections=active["claim"].get(name, []))
        result["claims"][name] = entry
        return entry

    for name in program.claims:
        assess_claim(name)
    return result
