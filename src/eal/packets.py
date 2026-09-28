"""Compact, claim-focused projections of immutable EAL assessments.

The packet is a navigation and reasoning aid.  The assessment identified by
``assessment_id`` remains authoritative; the packet never copies observations,
tool output, model input, formal queries, or arbitrary method extension fields.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
from collections.abc import KeysView
from typing import Any, Mapping, Sequence

from .builtin_methods import BUILTIN_SPECS
from .evaluator import canonical_digest
from .semantics import parse_time


PACKET_SCHEMA = "EAL/assessment-packet/2"
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]{0,127}\Z", re.ASCII)
_METHOD = re.compile(r"(?:1|[A-Za-z_][A-Za-z_0-9./:-]{0,127})\Z", re.ASCII)
_RECORD_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z", re.ASCII)
_DIGEST = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_CLAIM_STATES = frozenset({"supported", "contested", "unsupported", "out_of_scope"})
_ARGUMENT_STATES = frozenset({"supported", "contested", "unsupported", "out_of_scope"})
_OBJECTION_STATES = frozenset({"active", "undecided", "defeated", "inactive"})
_EVIDENCE_ISSUES = frozenset({"out_of_scope", "missing_observation", "invalid_observation",
                              "tool_error", "stale_observation", "predicate_not_met"})
_SAFE_METHOD_SCALARS = {
    "structured/1": ("authored", "mechanically_proved"),
    "deductive/1": ("valuations", "satisfying_premise_valuations"),
    "inductive/1": ("sample_size", "successes", "confidence"),
    "causal/1": ("sample_size", "treatment_size", "control_size"),
    "analogical/1": ("feature_count", "matched"),
}


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError("Assessment packet requires bounded EAL identifiers")
    return value


def _state(value: Any, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError("Assessment packet contains an unknown result status")
    return value


def _digest(value: Any) -> str | None:
    return value if isinstance(value, str) and _DIGEST.fullmatch(value) else None


def _scalar(value: Any) -> bool:
    return type(value) is bool or type(value) in (int, float) and (type(value) is int or math.isfinite(value))


def _bounded(value: Any, limit: int = 128) -> str | None:
    """Only identifiers and short declared labels enter a model-facing packet."""
    if isinstance(value, str) and len(value.encode("utf-8")) <= limit and _METHOD.fullmatch(value):
        return value
    return None


def _record_identifier(value: Any) -> str | None:
    return value if isinstance(value, str) and _RECORD_ID.fullmatch(value) else None


@dataclass(frozen=True)
class PacketLimits:
    max_bytes: int = 16_384
    max_claims: int = 16
    max_arguments: int = 24
    max_objections: int = 32
    max_assumptions: int = 32
    max_evidence: int = 48
    max_outputs: int = 16
    max_availability_issues: int = 6
    max_observations_per_claim: int = 16
    max_statement_bytes: int = 1024

    def __post_init__(self) -> None:
        if type(self.max_bytes) is not int or self.max_bytes < 4096:
            raise ValueError("Packet byte limit must be at least 4096")
        if type(self.max_statement_bytes) is not int or not 1 <= self.max_statement_bytes <= 4096:
            raise ValueError("Statement byte limit must be an integer between 1 and 4096")
        for field in ("max_claims", "max_arguments", "max_objections", "max_assumptions",
                      "max_evidence", "max_outputs", "max_availability_issues",
                      "max_observations_per_claim"):
            value = getattr(self, field)
            if type(value) is not int or not 1 <= value <= 128:
                raise ValueError(f"{field} must be an integer between 1 and 128")


class AssessmentPacketBuilder:
    """Project an assessment using registered output contracts and fixed limits.

    A host with extension methods supplies its method registry.  Without one,
    the built-in output declarations remain available; extension output values
    are omitted while the computation and typed binding statuses remain visible.
    """

    def __init__(self, *, limits: PacketLimits | None = None, method_registry: Any = None):
        self.limits = limits or PacketLimits()
        self.method_registry = method_registry

    def build(self, assessment: Mapping[str, Any], *, claims: Sequence[str] | None = None,
              collection: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not isinstance(assessment, Mapping) or assessment.get("valid") is not True:
            raise ValueError("A packet requires a valid, completed assessment")
        assessment_id = assessment.get("assessment_id")
        if not isinstance(assessment_id, str) or not 1 <= len(assessment_id) <= 128 or any(
                ord(char) < 33 or ord(char) > 126 for char in assessment_id):
            raise ValueError("A packet requires a stored assessment identifier")
        entries = assessment.get("claims")
        if not isinstance(entries, Mapping):
            raise ValueError("A packet requires assessed claims")
        if claims is None:
            selected = sorted(_identifier(name) for name in entries)[:self.limits.max_claims]
        elif (not isinstance(claims, (tuple, list)) or not claims
              or len(claims) > self.limits.max_claims or len(set(claims)) != len(claims)):
            raise ValueError("Select one to the configured maximum of distinct claims")
        else:
            selected = [_identifier(name) for name in claims]
            if any(name not in entries for name in selected):
                raise ValueError("The requested claim is absent from the assessment")
        collection_records = self._collection_records(assessment, collection)
        collection_id = assessment.get("collection_id")
        if collection_id is not None and _record_identifier(collection_id) != collection_id:
            raise ValueError("Collection identifier must be bounded")

        packet: dict[str, Any] = {
            "schema": PACKET_SCHEMA, "assessment_id": assessment_id,
            "collection_id": collection_id,
            "source_digest": _digest(assessment.get("source_digest")),
            "context_fingerprint": _digest(assessment.get("context_fingerprint")),
            "method_registry_fingerprint": _digest(assessment.get("method_registry_fingerprint")),
            "claims": {}, "premise_claims": {}, "arguments": {}, "assumptions": {},
            "objections": {}, "evidence": {},
            "omitted": {}, "summary_complete": True,
            "full_explanation": {"operation": "explain", "assessment_id": assessment_id, "detail": "full"},
        }
        omitted = packet["omitted"]
        if claims is None and len(entries) > len(selected):
            omitted["claims"] = len(entries) - len(selected)
        argument_entries = assessment.get("arguments", {})
        objection_entries = assessment.get("objections", {})
        assumption_entries = assessment.get("assumptions", {})
        evidence_entries = assessment.get("evidence", {})
        if not all(isinstance(group, Mapping) for group in (argument_entries, objection_entries,
                                                            assumption_entries, evidence_entries)):
            raise ValueError("Assessment dependencies must be mappings")

        argument_ids: set[str] = set()
        objection_ids: set[str] = set()
        for name in selected:
            entry = entries[name]
            if not isinstance(entry, Mapping):
                raise ValueError("Claim assessment must be an object")
            support = self._ids(entry.get("supporting_arguments", []))
            contested = self._ids(entry.get("contested_arguments", []))
            related = sorted(_identifier(arg) for arg, item in argument_entries.items()
                             if isinstance(item, Mapping) and item.get("conclusion") == name)
            argument_ids.update(related)
            direct = self._ids(entry.get("objections", [])) + self._ids(entry.get("undecided_objections", []))
            objection_ids.update(direct)
            for objection_id, objection in objection_entries.items():
                if (isinstance(objection, Mapping) and objection.get("target_kind") == "claim"
                        and objection.get("target") == name):
                    objection_ids.add(_identifier(objection_id))
            proposition = entry.get("proposition")
            claim_packet: dict[str, Any] = {
                "status": _state(entry.get("status"), _CLAIM_STATES),
                **self._claim_meaning(entry, omitted),
                "grounded_label": _bounded(entry.get("grounded_label")),
                "supporting_arguments": support[:self.limits.max_arguments],
                "contested_arguments": contested[:self.limits.max_arguments],
                "related_arguments": related[:self.limits.max_arguments],
                "active_objections": self._ids(entry.get("objections", []))[:self.limits.max_objections],
                "undecided_objections": self._ids(entry.get("undecided_objections", []))[:self.limits.max_objections],
            }
            if isinstance(proposition, Mapping):
                comparison = proposition.get("result")
                if isinstance(comparison, Mapping) and _scalar(comparison.get("expected")):
                    claim_packet["typed_result"] = {
                        "path": _bounded(comparison.get("path")),
                        "operator": comparison.get("operator") if comparison.get("operator") in
                        {"==", "!=", "<", "<=", ">", ">="} else None,
                        "expected": comparison["expected"],
                        "unit": _bounded(proposition.get("unit")),
                    }
            packet["claims"][name] = claim_packet

        # Follow declared claim premises, including every alternative route at
        # each premise.  A compact summary records the premise's own final
        # status; the graph remains in the stored full explanation.
        by_conclusion: dict[str, list[str]] = {}
        for arg_id, entry in argument_entries.items():
            if isinstance(entry, Mapping) and isinstance(entry.get("conclusion"), str):
                by_conclusion.setdefault(entry["conclusion"], []).append(_identifier(arg_id))
        pending = sorted(argument_ids)
        visited: set[str] = set()
        premise_ids: set[str] = set()
        while pending and len(visited) < 128:
            arg_id = pending.pop()
            if arg_id in visited or arg_id not in argument_entries:
                continue
            visited.add(arg_id)
            declaration = argument_entries[arg_id].get("dependencies", {})
            if not isinstance(declaration, Mapping):
                continue
            for premise in self._ids(declaration.get("premises", [])):
                premise_ids.add(premise)
                for alternative in by_conclusion.get(premise, []):
                    if alternative not in argument_ids:
                        argument_ids.add(alternative)
                        pending.append(alternative)
        if pending:
            omitted["premise_traversal"] = len(pending)
        # Include attacks on arguments, their reasoning and assumptions, then
        # follow objections that attack those objections (defences and cycles).
        assumptions: set[str] = set()
        evidence: set[str] = set()
        for name in sorted(argument_ids):
            entry = argument_entries[name]
            dependencies = entry.get("dependencies", {})
            dependencies = dependencies if isinstance(dependencies, Mapping) else {}
            assumptions.update(self._ids(dependencies.get("assumptions", [])))
            evidence.update(self._ids(dependencies.get("evidence", [])))
            objection_ids.update(self._ids(entry.get("attackers", []), prefixed=True))
            reasoning = dependencies.get("reasoning")
            reasoning_entry = assessment.get("reasoning", {}).get(reasoning, {})
            if isinstance(reasoning_entry, Mapping):
                evidence.update(self._ids(reasoning_entry.get("backing", [])))
            for objection_id, objection in objection_entries.items():
                if (isinstance(objection, Mapping) and objection.get("target_kind") == "reasoning"
                        and objection.get("target") == reasoning):
                    objection_ids.add(_identifier(objection_id))
        for name in sorted(assumptions):
            assumption = assumption_entries.get(name, {})
            if isinstance(assumption, Mapping):
                validation = assumption.get("validation")
                if isinstance(validation, str):
                    evidence.add(_identifier(validation))
                objection_ids.update(self._ids(assumption.get("objection_statuses", {}).keys()))
        queue = sorted(objection_ids)
        while queue and len(objection_ids) <= self.limits.max_objections:
            current = queue.pop(0)
            item = objection_entries.get(current)
            if not isinstance(item, Mapping):
                continue
            for candidate in self._ids(item.get("attackers", []), prefixed=True):
                if candidate not in objection_ids:
                    objection_ids.add(candidate)
                    queue.append(candidate)
            evidence.update(self._ids(item.get("evidence", [])))
            premise_ids.update(self._ids(item.get("premises", [])))
        for name in sorted(premise_ids)[:self.limits.max_claims]:
            premise = entries.get(name)
            if isinstance(premise, Mapping):
                packet["premise_claims"][name] = {
                    "status": _state(premise.get("status"), _CLAIM_STATES),
                    **self._claim_meaning(premise, omitted),
                }
        if len(premise_ids) > self.limits.max_claims:
            omitted["premise_claims"] = len(premise_ids) - self.limits.max_claims
        objection_premise_routes = {alternative for premise in premise_ids
                                    for alternative in by_conclusion.get(premise, [])
                                    if alternative not in argument_ids}
        if objection_premise_routes:
            omitted["objection_premise_routes"] = len(objection_premise_routes)

        for name in selected:
            references, route_omitted = self._claim_observations(
                name, entries, argument_entries, assumption_entries,
                objection_entries, assessment.get("reasoning", {}), evidence_entries)
            evidence.update(reference["evidence_id"] for reference in references)
            packet["claims"][name]["observation_ids"] = references[:self.limits.max_observations_per_claim]
            if route_omitted:
                omitted["claim_dependency_routes"] = omitted.get("claim_dependency_routes", 0) + 1
            if len(references) > self.limits.max_observations_per_claim:
                omitted["claim_observations"] = omitted.get("claim_observations", 0) + (
                    len(references) - self.limits.max_observations_per_claim)

        self._project_ids(packet["arguments"], argument_ids, argument_entries, self.limits.max_arguments,
                          "arguments", omitted, self._argument,
                          priority=lambda name: (0 if argument_entries[name].get("status") in
                                                 {"supported", "contested"} else 1, name))
        self._project_ids(packet["objections"], objection_ids, objection_entries, self.limits.max_objections,
                          "objections", omitted, self._objection,
                          priority=lambda name: ({"active": 0, "undecided": 1, "defeated": 2,
                                                  "inactive": 3}.get(objection_entries.get(name, {}).get("status"), 4), name))
        self._project_ids(packet["assumptions"], assumptions, assumption_entries, self.limits.max_assumptions,
                          "assumptions", omitted, self._assumption)
        self._project_ids(packet["evidence"], evidence, evidence_entries, self.limits.max_evidence,
                          "evidence", omitted, self._evidence)
        for name, item in packet["evidence"].items():
            missed = item.pop("issues_omitted", 0)
            if missed:
                omitted["availability_issues"] = omitted.get("availability_issues", 0) + missed
            failures_missed = item.pop("predicate_failures_omitted", 0)
            if failures_missed:
                omitted["predicate_failures"] = omitted.get("predicate_failures", 0) + failures_missed
            record = collection_records.get(name)
            if record is not None:
                self._observation_time(item, assessment, evidence_entries[name], record)
        packet["summary_complete"] = not bool(omitted)
        if self._size(packet) > self.limits.max_bytes:
            # A fixed-size navigation packet must not silently truncate a
            # decisive route.  The stored explanation remains retrievable.
            packet_claims = packet["claims"]
            packet = {key: packet[key] for key in ("schema", "assessment_id", "collection_id", "source_digest",
                       "context_fingerprint", "method_registry_fingerprint", "full_explanation")}
            packet["claims"] = {name: {"status": entry["status"], "statement": None,
                                       "prose_verified": False}
                                for name, entry in packet_claims.items()}
            packet.update(summary_complete=False, omitted={"details": "packet_byte_limit"})
            if self._size(packet) > self.limits.max_bytes:
                raise ValueError("Requested claims exceed the packet byte limit; request fewer claims")
        return packet

    def _claim_meaning(self, item: Mapping[str, Any], omitted: dict[str, Any]) -> dict[str, Any]:
        """Retain authored wording without converting formal support into prose truth."""
        statement = item.get("statement")
        result: dict[str, Any] = {"statement": None, "prose_verified": False}
        if not isinstance(statement, str):
            omitted["claim_statements"] = omitted.get("claim_statements", 0) + 1
            return result
        result["prose_verified"] = item.get("prose_verified") is True
        encoded = statement.encode("utf-8")
        bounded = encoded[:self.limits.max_statement_bytes].decode("utf-8", errors="ignore")
        result["statement"] = bounded
        missed = len(encoded) - len(bounded.encode("utf-8"))
        if missed:
            result["statement_truncated"] = True
            # Verification of a complete authored statement cannot be transferred
            # to a prefix, which may omit its negation or qualification.
            result["prose_verified"] = False
            omitted["claim_statement_bytes"] = omitted.get("claim_statement_bytes", 0) + missed
        return result

    @staticmethod
    def _collection_records(assessment: Mapping[str, Any], collection: Mapping[str, Any] | None) -> Mapping[str, Any]:
        if collection is None:
            return {}
        if not isinstance(collection, Mapping) or assessment.get("collection_id") is None:
            raise ValueError("Collection must belong to a collected assessment")
        if collection.get("collection_id") != assessment["collection_id"]:
            raise ValueError("Collection ID differs from the assessment")
        if collection.get("source_digest") != assessment.get("source_digest"):
            raise ValueError("Collection source differs from the assessment")
        if canonical_digest(collection.get("context")) != assessment.get("context_fingerprint"):
            raise ValueError("Collection context differs from the assessment")
        records = collection.get("records")
        if not isinstance(records, Mapping) or any(not isinstance(key, str) or not isinstance(value, Mapping)
                                                   for key, value in records.items()):
            raise ValueError("Collection records must map evidence IDs to observations")
        return records

    @staticmethod
    def _observation_time(projected: dict[str, Any], assessment: Mapping[str, Any],
                          assessed_evidence: Mapping[str, Any], record: Mapping[str, Any]) -> None:
        if record.get("run_id") != assessed_evidence.get("run_id"):
            raise ValueError("Observation ID differs from the assessed evidence")
        try:
            measured = parse_time(record.get("collected_at"))
            assessed = parse_time(assessment.get("assessed_at"))
            age = (assessed - measured).total_seconds()
            if not math.isfinite(age):
                raise ValueError("Observation age is not finite")
        except (ValueError, TypeError, OverflowError):
            projected["age_status"] = "invalid_timestamp"
            return
        if record.get("status") != "ok":
            projected["attempted_at"] = measured.isoformat().replace("+00:00", "Z")
            projected["age_status"] = "no_observation"
            return
        projected["observed_at"] = measured.isoformat().replace("+00:00", "Z")
        projected["age_seconds"] = age
        projected["age_status"] = ("future" if age < 0 else "stale" if "stale_observation" in
                                   assessed_evidence.get("availability_issues", []) else "within_max_age")

    @classmethod
    def _claim_observations(cls, claim: str, claims: Mapping[str, Any],
                            arguments: Mapping[str, Any], assumptions: Mapping[str, Any],
                            objections: Mapping[str, Any], reasoning: Mapping[str, Any],
                            evidence: Mapping[str, Any]) -> tuple[list[dict[str, Any]], bool]:
        """Find observation IDs used by support and challenges to one claim."""
        by_conclusion: dict[str, list[str]] = {}
        for argument_id, argument in arguments.items():
            if isinstance(argument, Mapping) and isinstance(argument.get("conclusion"), str):
                by_conclusion.setdefault(argument["conclusion"], []).append(_identifier(argument_id))
        by_target: dict[tuple[str, str], list[str]] = {}
        for objection_id, objection in objections.items():
            if (isinstance(objection, Mapping) and isinstance(objection.get("target_kind"), str)
                    and isinstance(objection.get("target"), str)):
                by_target.setdefault((objection["target_kind"], objection["target"]), []).append(
                    _identifier(objection_id))
        pending = [("claim", claim)]
        visited: set[tuple[str, str]] = set()
        evidence_ids: set[str] = set()
        while pending and len(visited) < 256:
            kind, identifier = pending.pop()
            node = (kind, identifier)
            if node in visited:
                continue
            visited.add(node)
            pending.extend(("objection", name) for name in by_target.get(node, []))
            if kind == "claim":
                if identifier in claims:
                    pending.extend(("argument", name) for name in by_conclusion.get(identifier, []))
                continue
            if kind == "argument":
                item = arguments.get(identifier)
                if not isinstance(item, Mapping):
                    continue
                dependencies = item.get("dependencies", {})
                if not isinstance(dependencies, Mapping):
                    continue
                evidence_ids.update(cls._ids(dependencies.get("evidence", [])))
                pending.extend(("claim", name) for name in cls._ids(dependencies.get("premises", [])))
                pending.extend(("assumption", name) for name in cls._ids(dependencies.get("assumptions", [])))
                rule = dependencies.get("reasoning")
                if isinstance(rule, str):
                    pending.append(("reasoning", _identifier(rule)))
                pending.extend(("objection", name) for name in cls._ids(
                    item.get("attackers", []), prefixed=True))
                continue
            if kind == "assumption":
                item = assumptions.get(identifier)
                if isinstance(item, Mapping) and isinstance(item.get("validation"), str):
                    evidence_ids.add(_identifier(item["validation"]))
                continue
            if kind == "reasoning":
                item = reasoning.get(identifier) if isinstance(reasoning, Mapping) else None
                if isinstance(item, Mapping):
                    evidence_ids.update(cls._ids(item.get("backing", [])))
                continue
            if kind == "objection":
                item = objections.get(identifier)
                if isinstance(item, Mapping):
                    evidence_ids.update(cls._ids(item.get("evidence", [])))
                    pending.extend(("claim", name) for name in cls._ids(item.get("premises", [])))
                    pending.extend(("objection", name) for name in cls._ids(
                        item.get("attackers", []), prefixed=True))
        references = []
        for evidence_id in sorted(evidence_ids):
            item = evidence.get(evidence_id)
            if isinstance(item, Mapping):
                references.append({"evidence_id": evidence_id,
                                   "observation_id": _record_identifier(item.get("run_id"))})
        return references, bool(pending)

    @staticmethod
    def _size(value: Mapping[str, Any]) -> int:
        return len(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8"))

    @staticmethod
    def _ids(values: Any, *, prefixed: bool = False) -> list[str]:
        if not isinstance(values, (tuple, list, set, KeysView)):
            return []
        result = []
        for value in values:
            if prefixed:
                if not isinstance(value, str) or not value.startswith("objection:"):
                    continue
                value = value.removeprefix("objection:")
            result.append(_identifier(value))
        return result

    @staticmethod
    def _project_ids(output: dict[str, Any], ids: set[str], entries: Mapping[str, Any], limit: int,
                     label: str, omitted: dict[str, Any], projector: Any, priority: Any = None) -> None:
        for name in sorted(ids, key=priority)[:limit]:
            item = entries.get(name)
            if isinstance(item, Mapping):
                output[name] = projector(item)
        if len(ids) > limit:
            omitted[label] = len(ids) - limit

    def _argument(self, item: Mapping[str, Any]) -> dict[str, Any]:
        computation = item.get("reasoning_result", {})
        computation = computation if isinstance(computation, Mapping) else {}
        method = _bounded(computation.get("method"))
        result: dict[str, Any] = {"status": _state(item.get("status"), _ARGUMENT_STATES),
                                  "conclusion": _identifier(item.get("conclusion")),
                                  "method_result": {"status": _state(computation.get("status"),
                                                                      frozenset({"supported", "unsupported", "not_run"})),
                                                    "method": method}}
        method_result = result["method_result"]
        for key in ("evidence_id", "input_digest", "bound_observation_digest"):
            value = computation.get(key)
            if key.endswith("digest"):
                value = _digest(value)
            else:
                value = _identifier(value) if isinstance(value, str) else None
            if value is not None:
                method_result[key] = value
        details = computation.get("details", {})
        if isinstance(details, Mapping):
            output = self._outputs(method, details)
            for key in _SAFE_METHOD_SCALARS.get(method, ()):
                if _scalar(details.get(key)) and len(output) < self.limits.max_outputs:
                    output[key] = details[key]
            if output:
                method_result["outputs"] = output
            if type(details.get("assumptions_verified")) is bool:
                method_result["assumptions_verified"] = details["assumptions_verified"]
        predicates = computation.get("predicates")
        if isinstance(predicates, list):
            method_result["require_holds"] = [entry["holds"] for entry in predicates[:16]
                                                     if isinstance(entry, Mapping) and type(entry.get("holds")) is bool]
            if len(predicates) > 16:
                method_result["require_omitted"] = len(predicates) - 16
        binding = computation.get("binding")
        if isinstance(binding, Mapping):
            trace: dict[str, Any] = {"status": _bounded(binding.get("status")),
                                     "evidence_id": _identifier(binding["evidence_id"])
                                     if isinstance(binding.get("evidence_id"), str) else None}
            for key in ("holds", "actual", "prose_verified", "physical_interpretation_verified"):
                if _scalar(binding.get(key)):
                    trace[key] = binding[key]
            unit = _bounded(binding.get("output_unit"))
            if unit is not None:
                trace["output_unit"] = unit
            digest = _digest(binding.get("input_payload_digest"))
            if digest is not None:
                trace["input_payload_digest"] = digest
            method_result["binding"] = trace
        dependencies = item.get("dependencies", {})
        if isinstance(dependencies, Mapping):
            result["premises"] = self._ids(dependencies.get("premises", []))[:16]
        return result

    def _outputs(self, method: str | None, details: Mapping[str, Any]) -> dict[str, Any]:
        contract = self.method_registry.get(method) if self.method_registry is not None else None
        if contract is not None:
            paths = contract.outputs
        else:
            spec = BUILTIN_SPECS.get(method.rpartition("/")[0]) if method else None
            paths = spec.outputs if spec and spec.identifier == method else {}
        output = {}
        for path in sorted(paths):
            if path.endswith(".*"):
                continue  # Dynamic map keys may disclose arbitrary input labels.
            value = details
            for component in path.split("."):
                if not isinstance(value, Mapping) or component not in value:
                    break
                value = value[component]
            else:
                if _scalar(value):
                    output[path] = value
            if len(output) == self.limits.max_outputs:
                break
        return output

    @staticmethod
    def _objection(item: Mapping[str, Any]) -> dict[str, Any]:
        return {"status": _state(item.get("status"), _OBJECTION_STATES),
                "target_kind": _bounded(item.get("target_kind")),
                "target": _identifier(item["target"]) if isinstance(item.get("target"), str) else None,
                "attackers": AssessmentPacketBuilder._ids(item.get("attackers", []), prefixed=True)[:16],
                "premises": AssessmentPacketBuilder._ids(item.get("premises", []))[:16]}

    @staticmethod
    def _assumption(item: Mapping[str, Any]) -> dict[str, Any]:
        result = {"status": _state(item.get("status"), _ARGUMENT_STATES),
                  "validation": _identifier(item["validation"])
                  if isinstance(item.get("validation"), str) else None}
        if item.get("time_status") in {"not_started", "expired", "within_interval"}:
            result["time_status"] = item["time_status"]
            for key in ("valid_from", "valid_until"):
                value = item.get(key)
                if value is not None:
                    result[key] = parse_time(value).isoformat()
        return result

    def _evidence(self, item: Mapping[str, Any]) -> dict[str, Any]:
        issues = item.get("availability_issues", [])
        if not isinstance(issues, list):
            raise ValueError("Evidence availability issues must be a list")
        known = sorted({issue for issue in issues if isinstance(issue, str) and issue in _EVIDENCE_ISSUES})
        shown = known[:self.limits.max_availability_issues]
        result = {"status": _state(item.get("status"), frozenset({"available", "unavailable"})),
                "availability_issues": shown,
                "issues_omitted": len(issues) - len(shown),
                "observation_id": _record_identifier(item.get("run_id")),
                "age_status": "unknown"}
        failures = item.get("predicate_failures", [])
        if not isinstance(failures, list):
            raise ValueError("Predicate failures must be a list")
        safe = [{"path": _bounded(f.get("path")), "issue": f["issue"]}
                for f in failures if isinstance(f, Mapping) and _bounded(f.get("path")) is not None
                and f.get("issue") in {"missing_field", "incompatible_type", "non_finite", "incomparable", "not_met"}]
        if safe:
            result["predicate_failures"] = safe[:self.limits.max_availability_issues]
        result["predicate_failures_omitted"] = len(failures) - min(len(safe), self.limits.max_availability_issues)
        return result
