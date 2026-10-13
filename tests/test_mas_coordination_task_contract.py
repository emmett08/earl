"""Adversarial task correspondence, not a model capability measurement."""

from dataclasses import replace
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from experiments.mas_coordination.cases import CLAIMS, prepare_case, preseed
from experiments.mas_coordination.task_contract import (
    CandidateCheck, SEMANTIC_DEFINITIONS, TaskContract, check_candidate, validate_answer,
)


def worker_answer(contract, statuses, conclusion):
    return {"statuses": statuses, "scope": dict(contract.requested_scope),
            "assessed_at": contract.assessed_at, "conclusion": conclusion,
            "production_supported": False}


@pytest.mark.parametrize("case_id", ["nominal", "stale", "scope_mismatch", "measured_failure"])
def test_correspondence_and_classification_use_real_eal(tmp_path, case_id):
    case = prepare_case(case_id, tmp_path / case_id)
    contract = TaskContract.from_case(case, task_id="task001")
    check = check_candidate(case.knowledge, contract, case.entry_id)
    assessments = preseed(case)
    if case_id == "scope_mismatch":
        assert not check.ok and check.code == "context_mismatch"
        answer = worker_answer(contract, {claim: None for claim in CLAIMS}, "out_of_scope")
    else:
        assert check.ok and check.code is None
        answer = worker_answer(contract, {claim: value["status"] for claim, value in assessments.items()},
                               {"nominal": "sample_pass", "stale": "unresolved", "measured_failure": "sample_fail"}[case_id])
    assert validate_answer(contract, check, assessments, answer) == []
    assert TaskContract.from_dict(contract.to_dict()).task_digest == contract.task_digest
    assert CandidateCheck.from_dict(check.to_dict()) == check
    assert contract.to_dict()["semantic_definitions"] == SEMANTIC_DEFINITIONS


@pytest.mark.parametrize("field,value,code", [
    ("service", "another-api", "context_mismatch"),
    ("build_id", "demo-build-43", "context_mismatch"),
    ("dataset", "production", "context_mismatch"),
    ("run_id", "another-run", "workload_mismatch"),
    ("concurrent_clients", 20, "workload_mismatch"),
])
def test_all_workload_fields_are_pinned_not_only_default_context(tmp_path, field, value, code):
    case = prepare_case("nominal", tmp_path)
    original = TaskContract.from_case(case)
    changed = replace(original, requested_scope={**original.requested_scope, field: value})
    assert changed.task_digest != original.task_digest
    check = check_candidate(case.knowledge, changed, case.entry_id)
    assert not check.ok and check.code == code


@pytest.mark.parametrize("field,value", [
    ("minimum_requests", 101), ("maximum_sample_p95_ms", 201),
    ("maximum_error_rate_percent", 2), ("evidence_max_age_seconds", 86401),
])
def test_requested_threshold_or_freshness_change_is_a_different_task(tmp_path, field, value):
    case = prepare_case("nominal", tmp_path)
    original = TaskContract.from_case(case)
    changed = replace(original, criteria={**original.criteria, field: value})
    assert changed.task_digest != original.task_digest
    assert check_candidate(case.knowledge, changed, case.entry_id).code == "criteria_mismatch"


@pytest.mark.parametrize("old,new,code", [
    ('"run_id": "demo-load-001"', '"run_id": "another-run"', "workload_mismatch"),
    ('"concurrent_clients": 10', '"concurrent_clients": 20', "workload_mismatch"),
    ("max_age 86400.0", "max_age 42.0", "criteria_mismatch"),
    ("require passes == true", "require fails == true", "criteria_mismatch"),
])
def test_changed_actual_source_cannot_claim_task_correspondence(tmp_path, old, new, code):
    case = prepare_case("nominal", tmp_path)
    case.source_path.write_text(case.source_path.read_text().replace(old, new))
    # Establish a new source anchor so the semantic check, rather than revision
    # invalidation, detects the workload/method/freshness difference.
    contract = TaskContract.from_case(case)
    assert check_candidate(case.knowledge, contract, case.entry_id).code == code


def test_source_edit_after_task_creation_has_explicit_disposition(tmp_path):
    case = prepare_case("nominal", tmp_path)
    contract = TaskContract.from_case(case)
    case.source_path.write_text(case.source_path.read_text().replace("The synthetic report", "This synthetic report"))
    check = check_candidate(case.knowledge, contract, case.entry_id)
    assert check.code == "source_changed"
    answer = worker_answer(contract, {claim: None for claim in CLAIMS}, "out_of_scope")
    assert validate_answer(contract, check, None, answer) == []


def test_time_method_and_registry_participate_in_task_identity(tmp_path):
    case = prepare_case("nominal", tmp_path)
    contract = TaskContract.from_case(case)
    for changed in (replace(contract, assessed_at="2026-09-26T10:00:01Z"),
                    replace(contract, method="engineering/another-method/1"),
                    replace(contract, method_registry_fingerprint="0" * 64)):
        assert changed.task_digest != contract.task_digest
    assert check_candidate(case.knowledge, replace(contract, method="engineering/another-method/1"), case.entry_id).code == "criteria_mismatch"
    assert check_candidate(case.knowledge, replace(contract, method_registry_fingerprint="0" * 64), case.entry_id).code == "criteria_mismatch"


def test_missing_candidate_and_unknown_effect_remain_unassessed(tmp_path):
    case = prepare_case("nominal", tmp_path)
    contract = TaskContract.from_case(case)
    check = check_candidate(case.knowledge, contract, "missing")
    assert check.code == "evidence_unavailable"
    unknown = replace(check, code="effect_outcome_unknown", detail="Reserved execution outcome cannot be reconciled")
    answer = worker_answer(contract, {claim: None for claim in CLAIMS}, "unresolved")
    assert validate_answer(contract, unknown, None, answer) == []
    wrong = worker_answer(contract, {claim: "unsupported" for claim in CLAIMS}, "sample_fail")
    assert {item["path"] for item in validate_answer(contract, unknown, None, wrong)} == {"statuses", "conclusion"}


def test_wrong_claim_time_scope_or_forged_assessment_is_not_a_scoped_answer(tmp_path):
    case = prepare_case("nominal", tmp_path)
    contract = TaskContract.from_case(case)
    check = check_candidate(case.knowledge, contract, case.entry_id)
    assessments = preseed(case)
    answer = worker_answer(contract, {claim: value["status"] for claim, value in assessments.items()}, "sample_pass")
    wrong = {**answer, "scope": {**answer["scope"], "run_id": "another-run"}}
    assert validate_answer(contract, check, assessments, wrong)[0]["code"] == "workload_mismatch"
    wrong = {**answer, "production_supported": True}
    assert validate_answer(contract, check, assessments, wrong)[0]["path"] == "production_supported"
    wrong = {**answer, "assessed_at": "2026-09-26T10:00:01Z"}
    assert validate_answer(contract, check, assessments, wrong)[0]["path"] == "assessed_at"
    forged = {**assessments, CLAIMS[0]: {**assessments[CLAIMS[0]], "status": "unsupported"}}
    assert any(item["code"] == "evidence_unavailable" for item in validate_answer(contract, check, forged, answer))
    late = replace(contract, assessed_at="2026-09-26T10:00:01Z")
    late_check = check_candidate(case.knowledge, late, case.entry_id)
    assert any(item["code"] == "evidence_unavailable" for item in validate_answer(late, late_check, assessments, worker_answer(late, answer["statuses"], "sample_pass")))


def test_task_maps_are_immutable_and_type_sensitive(tmp_path):
    case = prepare_case("nominal", tmp_path)
    contract = TaskContract.from_case(case)
    with pytest.raises(TypeError):
        contract.requested_scope["build_id"] = "other"
    with pytest.raises(ValueError):
        replace(contract, requested_scope={**contract.requested_scope, "concurrent_clients": True})
    with pytest.raises(ValueError):
        replace(contract, criteria={**contract.criteria, "maximum_sample_p95_ms": float("nan")})
    altered = contract.to_dict()
    altered["requested_scope"]["run_id"] = "other"
    with pytest.raises(ValueError, match="identity differs"):
        TaskContract.from_dict(altered)


def test_v2_schema_rejects_inline_answers_statuses_packets_and_unknown_codes():
    schema = json.loads((Path(__file__).parents[1] / "experiments/mas_coordination/recovery-schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    common = {"schema": "EAL/MAS-coordination/2", "message_id": "m1", "task_id": "task001",
              "task_digest": "a" * 64, "sender": "assessor", "recipient": "reviewer",
              "reply_to": "request1", "attempt": 0}
    outcome = {**common, "kind": "outcome", "finding_id": "finding1",
               "assessment_refs": {claim: f"assessment{index}" for index, claim in enumerate(CLAIMS)}}
    disposition = {**common, "kind": "disposition", "finding_id": "finding1",
                   "outcome": "incomplete", "code": "evidence_unavailable"}
    request = {**common, "kind": "request", "reply_to": None, "candidate_entry_id": "load_test"}
    for message in (request, outcome, disposition):
        assert not list(validator.iter_errors(message))
    for invalid in ({**outcome, "status": "supported"}, {**outcome, "packet": {}},
                    {**outcome, "answer": {}}, {**disposition, "code": "unsupported"},
                    {**request, "attempt": 1}, {**disposition, "attempt": 2},
                    {**disposition, "assessment_refs": outcome["assessment_refs"]}):
        assert list(validator.iter_errors(invalid))
