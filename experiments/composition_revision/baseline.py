"""Independent typed configuration and evaluator for the finite coolant task.

This baseline deliberately uses neither EAL's parser nor its support/attack
solver. Its bounded acyclic rule profile covers this example, not every EAL/2
argument graph. Both arms receive equivalent observation envelopes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import hashlib
import json
import math
import re
from typing import Any, Mapping


TOOL = "bench_instrument"
TOOL_VERSION = "1"
ENVIRONMENT = "loop_a"
KIND = "measurement"


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def timestamp(value: str) -> datetime:
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if instant.tzinfo is None:
        raise ValueError("Assessment and observation times need a timezone")
    return instant


@dataclass(frozen=True)
class Criterion:
    field: str
    operator: str
    value: str | int | float | bool

    def accepts(self, reading: Mapping[str, Any]) -> bool:
        actual = reading.get(self.field)
        if self.field not in reading:
            return False
        if self.operator == "==":
            return type(actual) is type(self.value) and actual == self.value
        numeric = lambda item: type(item) in (int, float) and math.isfinite(item)
        if not numeric(actual) or not numeric(self.value):
            return False
        return {">=": actual >= self.value, "<=": actual <= self.value}[self.operator]


@dataclass(frozen=True)
class EvidenceSpec:
    name: str
    kind: str
    max_age: int
    criteria: tuple[Criterion, ...]
    request: Any = field(default_factory=dict)


@dataclass(frozen=True)
class Rule:
    name: str
    conclusion: str
    evidence: tuple[str, ...] = ()
    premises: tuple[str, ...] = ()


@dataclass(frozen=True)
class Challenge:
    name: str
    target_rule: str
    evidence: str


EVIDENCE: dict[str, EvidenceSpec] = {
    "power_bus": EvidenceSpec("power_bus", KIND, 300,
                              (Criterion("voltage_v", ">=", 24), Criterion("voltage_v", "<=", 28))),
    "pump_a_flow": EvidenceSpec("pump_a_flow", KIND, 60,
                                (Criterion("flow_lpm", ">=", 14), Criterion("sensor_id", "==", "A"))),
    "pump_b_flow": EvidenceSpec("pump_b_flow", KIND, 60,
                                (Criterion("flow_lpm", ">=", 14), Criterion("sensor_id", "==", "B"))),
    "exchanger_test": EvidenceSpec("exchanger_test", "test", 300,
                                   (Criterion("removed_heat_kw", ">=", 8),)),
    "pump_a_disagreement": EvidenceSpec("pump_a_disagreement", "test", 60,
                                        (Criterion("flow_sensors_disagree", "==", True),)),
}
RULES = (
    Rule("measured_power", "power_sufficient", ("power_bus",)),
    Rule("pump_a_route", "flow_sufficient", ("pump_a_flow",), ("power_sufficient",)),
    Rule("pump_b_route", "flow_sufficient", ("pump_b_flow",), ("power_sufficient",)),
    Rule("measured_rejection", "rejection_sufficient", ("exchanger_test",)),
    Rule("combined_loop", "cooling_at_8kw", (), ("flow_sufficient", "rejection_sufficient")),
)
CHALLENGES = (Challenge("disputed_pump_a", "pump_a_route", "pump_a_disagreement"),)
CLAIMS = tuple(dict.fromkeys(rule.conclusion for rule in RULES))
CONFIG_DIGEST = digest({"profile": "coolant-acyclic-typed-rules/1",
                        "environment": { "loop_id": "coolant-loop-A", "load_kw": 8 },
                        "tool": { "name": TOOL, "version": TOOL_VERSION },
                        "evidence": {key: asdict(item) for key, item in EVIDENCE.items()},
                        "rules": [asdict(item) for item in RULES],
                        "challenges": [asdict(item) for item in CHALLENGES]})


def _record_available(spec: EvidenceSpec, record: Mapping[str, Any] | None,
                      *, now: str, context: Mapping[str, Any]) -> bool:
    if not isinstance(record, Mapping):
        return False
    acquisition = {"tool": TOOL, "tool_version": TOOL_VERSION,
                   "input": spec.request, "context": dict(context)}
    request = {"evidence_id": spec.name, "environment": ENVIRONMENT, **acquisition}
    expected = {
        "evidence_id": spec.name,
        "source_digest": CONFIG_DIGEST,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "evidence_kind": spec.kind,
        "environment": ENVIRONMENT,
        "environment_fingerprint": digest({"environment": ENVIRONMENT, "context": context}),
        "input_digest": digest(spec.request),
        "input": spec.request,
        "context": context,
        "acquisition_request": acquisition,
        "acquisition_request_digest": digest(acquisition),
        "request_digest": digest(request),
        "status": "ok",
    }
    try:
        matches = all(digest(record.get(key)) == digest(value) for key, value in expected.items())
    except (TypeError, ValueError, OverflowError):
        return False
    if not matches:
        return False
    binding = record.get("tool_binding_digest")
    if not isinstance(binding, str) or re.fullmatch(r"[0-9a-f]{64}", binding) is None:
        return False
    if not isinstance(record.get("run_id"), str) or not record["run_id"].strip():
        return False
    value = record.get("value")
    try:
        valid_digest = isinstance(value, Mapping) and record.get("data_digest") == digest(value)
    except (TypeError, ValueError, OverflowError):
        return False
    if not valid_digest:
        return False
    try:
        age = (timestamp(now) - timestamp(record["collected_at"])).total_seconds()
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return 0 <= age <= spec.max_age and all(rule.accepts(value) for rule in spec.criteria)


def evaluate(records: Mapping[str, Mapping[str, Any]], *, now: str,
             context: Mapping[str, Any]) -> dict[str, Any]:
    """Assess the case with explicit AND/OR dependencies and one local challenge.

    The rule tuple is topologically ordered. A contested premise keeps its
    dependent rule contested; an independent accepted alternative prevails.
    Missing or rejected routes do not establish a contrary engineering claim.
    """
    in_scope = dict(context) == {"loop_id": "coolant-loop-A", "load_kw": 8}
    evidence = {name: "available" if in_scope and _record_available(spec, records.get(name),
                 now=now, context=context) else "unavailable"
                for name, spec in EVIDENCE.items()}
    objections = {item.name: "active" if evidence[item.evidence] == "available" else "inactive"
                  for item in CHALLENGES}
    claims: dict[str, str] = {}
    arguments: dict[str, str] = {}
    for claim_name in CLAIMS:
        routes: list[str] = []
        for rule in (item for item in RULES if item.conclusion == claim_name):
            if not in_scope:
                status = "out_of_scope"
            elif any(evidence[e] != "available" for e in rule.evidence) or any(
                    claims[p] in ("unsupported", "out_of_scope") for p in rule.premises):
                status = "unsupported"
            elif any(claims[p] == "contested" for p in rule.premises) or any(
                    challenge.target_rule == rule.name and objections[challenge.name] == "active"
                    for challenge in CHALLENGES):
                status = "contested"
            else:
                status = "supported"
            arguments[rule.name] = status
            routes.append(status)
        claims[claim_name] = ("out_of_scope" if not in_scope else "supported" if "supported" in routes
                              else "contested" if "contested" in routes else "unsupported")
    return {"claims": claims, "arguments": arguments, "evidence": evidence,
            "objections": objections}
