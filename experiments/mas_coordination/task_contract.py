"""Task correspondence for the optional coordination recovery experiment.

This finite API-load profile checks explicit task/source bindings. It does not
verify arbitrary claim prose, perform EAL reasoning, or construct worker answers.
Python EAL assessments remain authoritative. The original /1 pilot is untouched.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import timezone
import math
from types import MappingProxyType
from typing import Any

from eal.api_load_methods import CONTRACT as API_CONTRACT
from eal.evaluator import canonical_digest
from eal.knowledge import EALKnowledgeBase
from eal.methods import check_implementation_identity
from eal.semantics import parse_time

from .cases import CLAIMS, FAILED_CLAIM, MET_CLAIM


TASK_SCHEMA = "EAL/MAS-coordination-task/2"
PAYLOAD_SCHEMA = "EAL/MAS-coordination/2"
DIAGNOSTIC_CODES = frozenset({
    "context_mismatch", "workload_mismatch", "criteria_mismatch",
    "source_changed", "evidence_unavailable", "effect_outcome_unknown",
})
SCOPE_FIELDS = frozenset({"service", "build_id", "run_id", "concurrent_clients", "dataset"})
CRITERIA_FIELDS = frozenset({
    "minimum_requests", "maximum_sample_p95_ms", "maximum_error_rate_percent",
    "evidence_max_age_seconds",
})
# These describe the pinned engineering/api-load-criteria/1 implementation,
# rather than interpreting new thresholds or replacing its computation.
METHOD_CRITERIA = {"minimum_requests": 100, "maximum_sample_p95_ms": 200,
                   "maximum_error_rate_percent": 1}
SEMANTIC_DEFINITIONS = {
    "sample_pass": "A corresponding checked assessment gives the passing claim status supported and the failing claim status unsupported. The identified synthetic sample meets the pinned criteria; no production guarantee follows.",
    "sample_fail": "A corresponding checked assessment gives the failing claim status supported and the passing claim status unsupported. An identified usable measurement fails at least one pinned criterion; missing or stale evidence is not a measured failure.",
    "unresolved": "The requested task has no decisive checked result, including missing, stale, contested, unavailable or uncertain-execution evidence. Preserve actual checked statuses; use null when the requested claim was not assessed.",
    "out_of_scope": "The available registered candidate does not correspond to the requested context, workload, criterion contract or pinned source revision. Report the requested scope and null unassessed statuses; do not relabel the candidate's result.",
    "host_authority": "Only trusted Python EAL findings and stored assessments establish references and claim statuses. Formal support does not verify authored claim prose. A handoff disposition does not change an EAL assessment.",
}


def _instant(value: str) -> str:
    return parse_time(value).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def diagnostic(code: str, detail: str, *, path: str | None = None) -> dict[str, str]:
    if code not in DIAGNOSTIC_CODES:
        raise ValueError("Unknown coordination diagnostic code")
    result = {"code": code, "detail": detail}
    if path is not None:
        result["path"] = path
    return result


@dataclass(frozen=True)
class TaskContract:
    task_id: str
    entry_id: str
    requested_scope: Mapping[str, Any]
    assessed_at: str
    criteria: Mapping[str, Any]
    method: str
    method_registry_fingerprint: str
    source_digest: str
    claims: tuple[str, ...] = CLAIMS

    def __post_init__(self) -> None:
        scope, criteria = dict(self.requested_scope), dict(self.criteria)
        if set(scope) != SCOPE_FIELDS or set(criteria) != CRITERIA_FIELDS:
            raise ValueError("Task requires the complete scope and criterion contract")
        if any(not isinstance(scope[key], str) or not scope[key] or len(scope[key]) > 128
               for key in SCOPE_FIELDS - {"concurrent_clients"}):
            raise ValueError("Task scope strings must be nonempty and bounded")
        if type(scope["concurrent_clients"]) is not int or scope["concurrent_clients"] < 1:
            raise ValueError("Task concurrent_clients must be a positive integer")
        if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
               for value in criteria.values()):
            raise ValueError("Task criteria must contain finite nonnegative numbers")
        if type(criteria["minimum_requests"]) is not int:
            raise ValueError("Task minimum_requests must be an integer")
        if tuple(self.claims) != CLAIMS:
            raise ValueError("This profile selects the passing and failing API-load claims")
        if not isinstance(self.task_id, str) or not self.task_id or len(self.task_id) > 128:
            raise ValueError("Task identity must be nonempty and bounded")
        for value in (self.source_digest, self.method_registry_fingerprint):
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("Task contract identities require SHA-256 digests")
        object.__setattr__(self, "requested_scope", MappingProxyType(scope))
        object.__setattr__(self, "criteria", MappingProxyType(criteria))
        object.__setattr__(self, "claims", tuple(self.claims))
        object.__setattr__(self, "assessed_at", _instant(self.assessed_at))

    @classmethod
    def from_case(cls, case: Any, *, task_id: str | None = None) -> TaskContract:
        task = case.task
        entry = case.knowledge.catalogue.get(case.entry_id)
        return cls(
            task_id=task_id or task.get("task_id", "task"), entry_id=case.entry_id,
            requested_scope=task["requested_scope"], assessed_at=task["assessed_at"],
            criteria=task["criteria"], method=API_CONTRACT.identifier,
            method_registry_fingerprint=entry["method_registry_fingerprint"],
            source_digest=entry["source_digest"], claims=tuple(task["claims"]),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> TaskContract:
        fields = {key: value[key] for key in (
            "task_id", "entry_id", "requested_scope", "assessed_at", "criteria", "method",
            "method_registry_fingerprint", "source_digest", "claims",
        )}
        contract = cls(**fields)
        if value.get("schema") != TASK_SCHEMA or value.get("task_digest") != contract.task_digest:
            raise ValueError("Stored task contract identity differs from its content")
        return contract

    def _identity(self) -> dict[str, Any]:
        return {"schema": TASK_SCHEMA, "task_id": self.task_id, "entry_id": self.entry_id,
                "requested_scope": dict(self.requested_scope), "assessed_at": self.assessed_at,
                "criteria": dict(self.criteria), "method": self.method,
                "method_registry_fingerprint": self.method_registry_fingerprint,
                "source_digest": self.source_digest, "claims": list(self.claims)}

    @property
    def task_digest(self) -> str:
        return canonical_digest(self._identity())

    def to_dict(self) -> dict[str, Any]:
        return {**self._identity(), "task_digest": self.task_digest,
                "semantic_definitions": deepcopy(SEMANTIC_DEFINITIONS)}


@dataclass(frozen=True)
class CandidateCheck:
    ok: bool
    code: str | None
    detail: str
    task_digest: str
    entry_id: str
    source_digest: str | None
    context_fingerprint: str | None
    method_registry_fingerprint: str | None

    def __post_init__(self) -> None:
        if type(self.ok) is not bool or (self.ok and self.code is not None) or (not self.ok and self.code not in DIAGNOSTIC_CODES):
            raise ValueError("Candidate finding requires an explicit valid disposition")

    @property
    def finding_id(self) -> str:
        return "finding_" + canonical_digest(self._fields())

    def _fields(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in (
            "ok", "code", "detail", "task_digest", "entry_id", "source_digest",
            "context_fingerprint", "method_registry_fingerprint",
        )}

    def to_dict(self) -> dict[str, Any]:
        return {**self._fields(), "finding_id": self.finding_id}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> CandidateCheck:
        result = cls(**{key: value[key] for key in (
            "ok", "code", "detail", "task_digest", "entry_id", "source_digest",
            "context_fingerprint", "method_registry_fingerprint",
        )})
        if value.get("finding_id") != result.finding_id:
            raise ValueError("Stored candidate finding identity differs from its content")
        return result


def check_candidate(kb: EALKnowledgeBase, contract: TaskContract, entry_id: str) -> CandidateCheck:
    """Check a pinned registered candidate without acquiring or evaluating evidence."""
    entry = None

    def finding(code: str | None, detail: str) -> CandidateCheck:
        return CandidateCheck(
            ok=code is None, code=code, detail=detail, task_digest=contract.task_digest,
            entry_id=entry_id, source_digest=None if entry is None else entry["source_digest"],
            context_fingerprint=None if entry is None else canonical_digest(entry["context"]),
            method_registry_fingerprint=None if entry is None else entry["method_registry_fingerprint"],
        )

    try:
        entry = kb.catalogue.get(entry_id, include_source=True)
    except KeyError:
        return finding("evidence_unavailable", "Registered candidate is unavailable")
    except (ValueError, OSError):
        return finding("source_changed", "Registered candidate source is unavailable or invalid")
    if entry_id != contract.entry_id or entry["source_digest"] != contract.source_digest:
        return finding("source_changed", "Candidate differs from the pinned registered source revision")
    if (entry["method_registry_fingerprint"] != contract.method_registry_fingerprint
            or kb.service.method_registry.fingerprint != contract.method_registry_fingerprint):
        return finding("criteria_mismatch", "Installed method registry differs from the task contract")
    wanted_context = {key: contract.requested_scope[key] for key in ("service", "build_id", "dataset")}
    if entry["context"] != wanted_context:
        return finding("context_mismatch", "Registered default context differs from the requested service, build or dataset")
    if set(contract.claims) - set(entry["claims"]):
        return finding("criteria_mismatch", "Registered candidate does not select both requested claims")
    if contract.method != API_CONTRACT.identifier or any(contract.criteria[key] != value for key, value in METHOD_CRITERIA.items()):
        return finding("criteria_mismatch", "Requested criteria differ from the installed API-load method's fixed limits")
    installed = kb.service.method_registry.get(contract.method)
    if installed is None:
        return finding("criteria_mismatch", "Requested reasoning method is not installed")
    try:
        check_implementation_identity(installed)
    except ValueError:
        return finding("criteria_mismatch", "Installed method implementation changed after registration")
    if installed.describe() != API_CONTRACT.describe():
        return finding("criteria_mismatch", "Installed API-load method differs from the trusted profile contract")
    try:
        program = kb.service.parse(entry["source"])
        plans = [kb.service.plan(entry["source"], claim) for claim in contract.claims]
        evidence_ids = {name for plan in plans for name in plan["evidence_ids"]}
        reasoning_ids = {name for plan in plans for name in plan["dependencies"]["reasoning"]}
        if not evidence_ids or not reasoning_ids:
            return finding("criteria_mismatch", "Candidate lacks the required evidence and reasoning bindings")
        for name in evidence_ids:
            evidence = program.evidence[name]
            if evidence.kind != "api_report" or not isinstance(evidence.input, dict):
                return finding("workload_mismatch", "Candidate evidence does not bind an API report workload")
            if any(type(evidence.input.get(key)) is not type(value) or evidence.input.get(key) != value
                   for key, value in contract.requested_scope.items()):
                return finding("workload_mismatch", "Source evidence input differs from the complete requested workload")
            if evidence.max_age != contract.criteria["evidence_max_age_seconds"]:
                return finding("criteria_mismatch", "Source evidence freshness limit differs from the task contract")
        if any(program.reasoning[name].method != contract.method for name in reasoning_ids):
            return finding("criteria_mismatch", "Candidate reasoning uses another method contract")
        # Each selected claim must connect the intended method output to support.
        for claim, output in ((MET_CLAIM, "passes"), (FAILED_CLAIM, "fails")):
            plan = next(plan for plan in plans if plan["claim"] == claim)
            methods = [program.reasoning[name] for name in plan["dependencies"]["reasoning"]]
            if not any(any(p.path == output and p.operator == "==" and p.expected is True
                           for p in method.predicates) for method in methods):
                return finding("criteria_mismatch", "Claim reasoning does not check its intended passing or failing result")
    except (KeyError, ValueError, TypeError):
        return finding("criteria_mismatch", "Candidate formal task bindings cannot be checked")
    return finding(None, "Registered source, workload, freshness and method correspond to the pinned task")


def validate_answer(contract: TaskContract, check: CandidateCheck,
                    assessments: Mapping[str, Any] | None, answer: Any) -> list[dict[str, str]]:
    """Check a worker-authored answer against trusted findings and assessments.

    ``assessments`` must be resolved by the trusted host from durable EAL IDs,
    never copied from worker data. This function diagnoses; it does not fill or
    revise answers, use a fixture answer key, or change any EAL status.
    """
    errors: list[dict[str, str]] = []
    if not isinstance(answer, dict) or set(answer) != {"statuses", "scope", "assessed_at", "conclusion", "production_supported"}:
        return [diagnostic("criteria_mismatch", "Answer requires exactly the declared fields", path="answer")]
    if check.task_digest != contract.task_digest:
        return [diagnostic("context_mismatch", "Trusted finding belongs to another task", path="task_digest")]
    if (answer["scope"] != dict(contract.requested_scope)
            or not isinstance(answer["scope"], dict)
            or any(type(answer["scope"].get(key)) is not type(value) for key, value in contract.requested_scope.items())):
        errors.append(diagnostic("workload_mismatch", "Answer must retain the complete requested scope", path="scope"))
    try:
        time_matches = isinstance(answer["assessed_at"], str) and _instant(answer["assessed_at"]) == contract.assessed_at
    except ValueError:
        time_matches = False
    if not time_matches:
        errors.append(diagnostic("context_mismatch", "Answer decision time differs from the task", path="assessed_at"))
    if answer["production_supported"] is not False:
        errors.append(diagnostic("criteria_mismatch", "Synthetic sample cannot establish production support", path="production_supported"))

    expected_statuses = {claim: None for claim in contract.claims}
    classification = "out_of_scope" if not check.ok and check.code in {
        "context_mismatch", "workload_mismatch", "criteria_mismatch", "source_changed",
    } else "unresolved"
    trusted_available = check.ok and isinstance(assessments, Mapping) and set(assessments) == set(contract.claims)
    if trusted_available:
        for claim in contract.claims:
            result = assessments[claim]
            packet = result.get("packet", {}) if isinstance(result, Mapping) else {}
            if not isinstance(packet, Mapping):
                packet = {}
            try:
                time_matches = _instant(result["assessed_at"]) == contract.assessed_at
            except (KeyError, TypeError, ValueError):
                time_matches = False
            valid = (isinstance(result, Mapping) and result.get("schema") == "EAL/registered-assessment/1"
                     and result.get("entry_id") == check.entry_id and result.get("claim") == claim
                     and result.get("source_digest") == check.source_digest
                     and result.get("context_fingerprint") == check.context_fingerprint
                     and packet.get("source_digest") == check.source_digest
                     and packet.get("context_fingerprint") == check.context_fingerprint
                     and packet.get("method_registry_fingerprint") == check.method_registry_fingerprint
                     and result.get("assessment_id") == packet.get("assessment_id")
                     and result.get("collection_id") == packet.get("collection_id")
                     and result.get("status") in {"supported", "unsupported", "contested", "out_of_scope"}
                     and packet.get("claims", {}).get(claim, {}).get("status") == result.get("status")
                     and time_matches)
            if not valid:
                errors.append(diagnostic("evidence_unavailable", "Checked assessment does not bind the requested claim and task", path=f"statuses.{claim}"))
                trusted_available = False
                break
            expected_statuses[claim] = result["status"]
        if trusted_available:
            passing, failing = expected_statuses[MET_CLAIM], expected_statuses[FAILED_CLAIM]
            if passing == "supported" and failing == "unsupported":
                classification = "sample_pass"
            elif failing == "supported" and passing == "unsupported":
                classification = "sample_fail"
        else:
            expected_statuses = {claim: None for claim in contract.claims}
    if (not isinstance(answer["statuses"], dict) or answer["statuses"] != expected_statuses):
        errors.append(diagnostic("criteria_mismatch", "Answer statuses differ from checked assessments or unassessed dispositions", path="statuses"))
    if answer["conclusion"] != classification:
        errors.append(diagnostic("criteria_mismatch", "Answer conclusion violates the declared pass, failure, unresolved or scope definition", path="conclusion"))
    return errors
