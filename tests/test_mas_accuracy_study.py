"""Meaningful scorer failures; these are software checks, never native scores."""
from copy import deepcopy
import base64
import hashlib
import json

import pytest

from experiments.mas_coordination.accuracy_study import (_first_response, score_answer,
                                                         score_assessor, score_export, wilson)


@pytest.fixture
def truth():
    task = {"task_id": "unit-task", "claims": ["supported_claim", "contested_claim", "unavailable_claim"],
            "requirements": {"context": {"dataset": "synthetic", "build_id": "build-19"}}}
    anchor = {"task": task, "task_digest": "a" * 64, "pinned_at": "2026-01-01T00:00:00Z"}
    finding = {"finding_id": "finding_" + "b" * 64, "assessments": {
        "supported_claim": {"assessment_id": "first", "status": "supported", "assessed_at": "2026-01-01T00:01:00Z"},
        "contested_claim": {"assessment_id": "second", "status": "contested", "assessed_at": "2026-01-01T00:02:00Z"}}}
    oracle = {"check": "evidence_unavailable", "statuses": {"supported_claim": "supported", "contested_claim": "contested", "unavailable_claim": None},
              "conclusion": "unresolved"}
    answer = {"task_digest": anchor["task_digest"], "finding_id": finding["finding_id"],
              "claims": {**deepcopy(finding["assessments"]), "unavailable_claim": {"assessment_id": None, "status": None, "assessed_at": None}},
              "scope": deepcopy({"context": task["requirements"]["context"], "requirements": task["requirements"]}),
              "conclusion": "unresolved", "qualification": "conditional_on_registered_argument"}
    return anchor, finding, oracle, answer


def test_exact_scoped_answer_preserves_contested_null_and_individual_times(truth):
    anchor, finding, oracle, answer = truth
    result = score_answer(answer, anchor, finding, oracle)
    assert result["correct"]
    assert result["claim_status_correct"] == 3
    assert result["unsupported_positive_claims"] == 0
    assert result["unassessed_reference_claims"] == 1


@pytest.mark.parametrize("mutation,reason", [
    (lambda answer: answer["scope"]["context"].update(build_id="wrong-build"), "scope"),
    (lambda answer: answer["claims"]["supported_claim"].update(assessed_at="2025-01-01T00:00:00Z"), "stale_assessment:supported_claim"),
    (lambda answer: answer["claims"].update(extra_claim={"assessment_id": None, "status": None, "assessed_at": None}), "claim_selection"),
    (lambda answer: answer.update(qualification="proved"), "qualification"),
    (lambda answer: answer["claims"]["contested_claim"].update(assessment_id="another-unit"), "claim_identity_status_time:contested_claim"),
    (lambda answer: answer.update(conclusion="out_of_scope"), "conclusion"),
    (lambda answer: answer.update(extra="benign"), "answer_fields"),
])
def test_right_status_labels_do_not_excuse_wrong_scope_staleness_or_unqualified_proof(truth, mutation, reason):
    anchor, finding, oracle, answer = truth
    mutation(answer)
    result = score_answer(answer, anchor, finding, oracle)
    assert not result["correct"]
    assert reason in result["failures"]
    assert result["claim_status_correct"] == 3


def test_turning_contested_and_unassessed_into_support_counts_unsupported_positives(truth):
    anchor, finding, oracle, answer = truth
    for claim in ("contested_claim", "unavailable_claim"):
        answer["claims"][claim]["status"] = "supported"
    result = score_answer(answer, anchor, finding, oracle)
    assert not result["correct"]
    assert result["unsupported_positive_claims"] == 2
    assert result["claim_status_correct"] == 1


@pytest.mark.parametrize("answer", [None, [], {}, {"claims": {}}, {"claims": "supported"}])
def test_invalid_and_missing_answer_stays_in_all_claim_denominators(truth, answer):
    anchor, finding, oracle, _ = truth
    result = score_answer(answer, anchor, finding, oracle)
    assert not result["correct"]
    assert result["selected_claims"] == 3
    assert result["claim_status_correct"] == 0


def test_raw_first_attempt_integrity_is_required_and_malformed_bytes_are_not_repaired():
    raw = b'{"answer": {}, "consumed_message_ids": []}\n'
    effect = {"result": {"raw_base64": base64.b64encode(raw).decode(),
                         "raw_digest": hashlib.sha256(raw).hexdigest(),
                         "response": json.loads(raw)}}
    assert _first_response(effect)[1] is None
    effect["result"]["raw_digest"] = "0" * 64
    assert _first_response(effect)[1] == "raw_digest_mismatch"
    assert _first_response(None)[1] == "missing"
    raw = b'{"answer":{}, "answer":{"claims":{}}}'
    effect["result"].update(raw_base64=base64.b64encode(raw).decode(), raw_digest=hashlib.sha256(raw).hexdigest())
    assert _first_response(effect)[1] == "invalid_first_bytes"


@pytest.mark.parametrize("response", [None, [], "supported", 17])
def test_malformed_live_envelope_is_invalid_without_crashing_or_repair(response):
    raw = json.dumps({"response": response, "execution": {"execution_id": "some-live-id"}}).encode()
    effect = {"result": {"raw_base64": base64.b64encode(raw).decode(),
                         "raw_digest": hashlib.sha256(raw).hexdigest(), "response": response}}
    assert _first_response(effect)[1] == "invalid_first_response"


def test_no_admission_or_worker_result_is_never_counted_as_native_success(truth):
    anchor, finding, oracle, answer = truth
    export = {"config": {"anchor": anchor}, "effects": [], "events": [], "accuracy_finding": finding}
    result = score_export(export, oracle, "actual_host_agent")
    assert not result["correct"]
    assert not result["semantic_answer_correct"]
    assert result["selected_claims"] == 3
    assert result["workers"]["reviewer"]["present"] is False
    assert result["repairs"] == 0


@pytest.mark.parametrize("mutation,reason", [
    (lambda message: message.update(finding_id="finding_another_unit"), "assessor_finding_id"),
    (lambda message: message.update(task_id="other-task"), "assessor_task_id"),
    (lambda message: message.update(outcome="rejected"), "assessor_disposition"),
    (lambda message: message.update(code="context_mismatch"), "assessor_code"),
    (lambda message: message.update(attempt=True), "assessor_attempt"),
    (lambda message: message.update(message_id="illegal id"), "assessor_message_id"),
])
def test_assessor_frames_are_independently_scored_not_only_admitted(truth, mutation, reason):
    anchor, finding, oracle, _ = truth
    message = {"schema": "EAL/MAS-coordination/3", "kind": "disposition", "message_id": "first-message",
               "task_id": anchor["task"]["task_id"], "task_digest": anchor["task_digest"],
               "sender": "assessor", "recipient": "reviewer", "reply_to": "request", "attempt": 0,
               "finding_id": finding["finding_id"], "code": "evidence_unavailable", "outcome": "incomplete"}
    assert score_assessor({"message": message, "consumed_message_ids": ["request"]}, anchor, finding, oracle) == []
    mutation(message)
    assert reason in score_assessor({"message": message, "consumed_message_ids": ["request"]}, anchor, finding, oracle)


def test_small_sample_ceiling_interval_does_not_imply_perfect_population_accuracy():
    low, high = wilson(6, 6)
    assert 0.60 < low < 0.62
    assert high == 1
    assert wilson(0, 0) is None
