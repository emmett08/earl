"""Frozen synthetic tasks and outcome scoring for the coordination pilot.

These fixtures exercise the existing Python EAL implementation. They are not
measurements of an API or a representative engineering task population. The
trusted harness supplies the historical assessment time; model-facing registered
MCP operations do not gain a time or context override.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from eal.api_load_methods import registry as api_load_registry
from eal.knowledge import EALKnowledgeBase


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "api-load-test"
MET_CLAIM = "performance_criteria_met"
FAILED_CLAIM = "performance_criteria_failed"
CLAIMS = (MET_CLAIM, FAILED_CLAIM)
ENTRY_ID = "load_test"
OBSERVED_AT = "2026-09-25T10:00:00Z"
STALE_AT = "2026-09-26T10:00:01Z"
SOURCE_SCOPE = {
    "service": "orders-api",
    "build_id": "demo-build-42",
    "run_id": "demo-load-001",
    "concurrent_clients": 10,
    "dataset": "synthetic",
}
CASE_IDS = ("nominal", "stale", "scope_mismatch", "measured_failure")


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    partition: str
    assessed_at: str
    expected_statuses: Mapping[str, str | None]
    expected_conclusion: str
    requested_build: str = "demo-build-42"

    @property
    def requested_scope(self) -> dict[str, Any]:
        return {**SOURCE_SCOPE, "build_id": self.requested_build}


def case_spec(case_id: str) -> CaseSpec:
    """Return the frozen answer key; do not put this object in worker context."""
    if case_id == "nominal":
        return CaseSpec(case_id, "development", OBSERVED_AT,
                        {MET_CLAIM: "supported", FAILED_CLAIM: "unsupported"},
                        "sample_pass")
    if case_id == "stale":
        return CaseSpec(case_id, "development", STALE_AT,
                        {MET_CLAIM: "unsupported", FAILED_CLAIM: "unsupported"},
                        "unresolved")
    if case_id == "scope_mismatch":
        # The available host has assessed build-42. No accepted assessment of
        # build-43 exists. Null denotes unassessed, not an EAL support status.
        return CaseSpec(case_id, "held_out", OBSERVED_AT,
                        {MET_CLAIM: None, FAILED_CLAIM: None},
                        "out_of_scope", requested_build="demo-build-43")
    if case_id == "measured_failure":
        return CaseSpec(case_id, "held_out", OBSERVED_AT,
                        {MET_CLAIM: "unsupported", FAILED_CLAIM: "supported"},
                        "sample_fail")
    raise ValueError(f"Unknown coordination case: {case_id!r}")


@dataclass(frozen=True)
class PreparedCase:
    knowledge: EALKnowledgeBase
    entry_id: str
    assessed_at: str
    expected_statuses: Mapping[str, str | None]
    task: Mapping[str, Any]
    context: Mapping[str, Any]
    workspace: Path
    source_path: Path
    registry_path: Path
    spec: CaseSpec


def prepare_case(case_id: str, workspace: str | Path) -> PreparedCase:
    """Copy a teaching example into an empty, isolated run workspace.

    The registered source/context always identifies the supplied build-42 report.
    The scope-mismatch task asks about build-43 instead; delivery validation must
    reject a build-42 reference before the reviewer receives its packet.
    """
    spec = case_spec(case_id)
    destination = Path(workspace).resolve()
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise FileExistsError("Coordination fixtures require an empty run workspace")
    destination.mkdir(parents=True, exist_ok=True)

    source_path = destination / "source.eal"
    report_path = destination / "report.json"
    collector_path = destination / "collect_results.py"
    registry_path = destination / "tools.toml"
    raw = (EXAMPLE / "report.json").read_bytes()
    source = (EXAMPLE / "source.eal").read_text(encoding="utf-8")
    original_digest = hashlib.sha256(raw).hexdigest()
    if case_id == "measured_failure":
        report = json.loads(raw)
        # The original fixture has one non-2xx request. Mark one previously
        # successful attempt as a transport failure, preserving every latency.
        successful = next(row for row in report["requests"]
                          if 200 <= row["status_code"] < 300)
        successful["status_code"] = 0
        raw = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode("utf-8")
        source = source.replace(original_digest, hashlib.sha256(raw).hexdigest())
    report_path.write_bytes(raw)
    source_path.write_text(source, encoding="utf-8")
    shutil.copyfile(EXAMPLE / "collect_results.py", collector_path)

    argv = [sys.executable, str(collector_path), "--report", str(report_path)]
    pin = {"path": "collect_results.py",
           "sha256": hashlib.sha256(collector_path.read_bytes()).hexdigest()}
    registry_path.write_text(
        '[tools.load_test_report]\nkind = "command"\nversion = "1"\n'
        f'argv = {json.dumps(argv)}\n'
        f'env = {{PYTHONPATH = {json.dumps(str(ROOT / "src"))}}}\n'
        'timeout_seconds = 10\nmax_output_bytes = 16384\n'
        f'pinned_files = [{{path = {json.dumps(pin["path"])}, '
        f'sha256 = {json.dumps(pin["sha256"])}}}]\n',
        encoding="utf-8",
    )
    context = {key: SOURCE_SCOPE[key] for key in ("service", "build_id", "dataset")}
    knowledge = EALKnowledgeBase(destination, registry_path,
                                 method_registry=api_load_registry())
    knowledge.register("source.eal", entry_id=ENTRY_ID, context=context,
                       claims=list(CLAIMS), label="synthetic coordination pilot")

    task = {
        "case_id": case_id,
        "question": "Does the requested build's identified synthetic sample meet the declared load-test criteria?",
        "requested_scope": spec.requested_scope,
        "assessed_at": spec.assessed_at,
        "criteria": {"minimum_requests": 100, "maximum_sample_p95_ms": 200,
                     "maximum_error_rate_percent": 1, "evidence_max_age_seconds": 86400},
        "entry_id": ENTRY_ID,
        "claims": list(CLAIMS),
        "instructions": (
            "Use only an accepted checked handoff for the requested scope and decision time. "
            "A supported claim describes this identified synthetic sample, with no production guarantee. "
            "Keep measured criterion failure separate from missing, stale, or unavailable evidence. "
            "When no accepted assessment of the requested scope exists, both statuses are null "
            "(unassessed), not an invented host status. Original measurement time is preserved."
        ),
        "answer_contract": {
            "statuses": {claim: "supported | contested | unsupported | out_of_scope | null" for claim in CLAIMS},
            "scope": "the exact requested_scope object",
            "assessed_at": "the requested decision time",
            "conclusion": "sample_pass | sample_fail | unresolved | out_of_scope",
            "production_supported": False,
        },
    }
    return PreparedCase(knowledge, ENTRY_ID, spec.assessed_at, spec.expected_statuses,
                        task, context, destination, source_path, registry_path, spec)


def preseed(case: PreparedCase) -> dict[str, dict[str, Any]]:
    """Create genuine, persisted EAL assessments at the trusted fixture time."""
    return {claim: case.knowledge.assess(case.entry_id, claim, now=case.assessed_at)
            for claim in CLAIMS}


def score_response(case_id: str, answer: Any, *, delivery: str = "accepted") -> dict[str, Any]:
    """Score the exact task answer independently of handoff admission.

    A rejection is a transport/reference outcome, not proof of a correct answer.
    A reviewer can answer the scope-mismatch task correctly after rejection by
    retaining the requested scope and reporting unassessed statuses. Conversely,
    an accepted handoff can still lead to a wrong or overbroad answer.
    """
    if delivery not in {"accepted", "rejected", "unresolved"}:
        raise ValueError("delivery must be accepted, rejected, or unresolved")
    spec = case_spec(case_id)
    result: dict[str, Any] = {
        "case_id": case_id, "delivery": delivery, "answer_present": answer is not None,
        "answer_correct": None if answer is None else False,
        "resolved": False, "justified_unresolved": False, "errors": [],
    }
    if answer is None:
        result["errors"] = ["missing_answer"]
        return result
    if not isinstance(answer, dict):
        result["errors"] = ["answer_not_object"]
        return result
    errors = result["errors"]
    statuses = answer.get("statuses")
    if not isinstance(statuses, dict) or statuses != dict(spec.expected_statuses):
        errors.append("wrong_claim_statuses")
    scope = answer.get("scope")
    if (not isinstance(scope, dict) or scope != spec.requested_scope
            or any(type(scope.get(key)) is not type(value)
                   for key, value in spec.requested_scope.items())):
        errors.append("wrong_requested_scope")
    if answer.get("assessed_at") != spec.assessed_at:
        errors.append("wrong_decision_time")
    if answer.get("conclusion") != spec.expected_conclusion:
        errors.append("wrong_scoped_conclusion")
    if answer.get("production_supported") is not False:
        errors.append("production_qualification_missing_or_wrong")
    result["answer_correct"] = not errors
    result["resolved"] = not errors and spec.expected_conclusion in {"sample_pass", "sample_fail"}
    result["justified_unresolved"] = not errors and spec.expected_conclusion in {"unresolved", "out_of_scope"}
    return result
