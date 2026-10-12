"""The optional agent payload cannot replace the scoped EAL host result."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

from eal.api_load_methods import registry as api_load_registry
from eal.knowledge import EALKnowledgeBase
from experiments.mas_coordination import (
    ProtocolError, Validator, decode_payload, make_anchor, make_message, proposal_fields,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/api-load-test"
CLAIM = "performance_criteria_met"
CONTEXT = {"service": "orders-api", "build_id": "demo-build-42", "dataset": "synthetic"}
AT = json.loads((EXAMPLE / "report.json").read_text())["observed_at"]
AFTER_EXPIRY = "2026-09-26T10:00:01Z"


@pytest.fixture
def case(tmp_path):
    """Use the maintained synthetic collector, real catalogue and private store."""
    source = tmp_path / "source.eal"
    source.write_text((EXAMPLE / "source.eal").read_text())
    tools = tmp_path / "tools.toml"
    tools.write_text(
        '[tools.load_test_report]\nkind="command"\nversion="1"\n'
        f'argv={json.dumps([sys.executable, str(EXAMPLE / "collect_results.py"), "--report", str(EXAMPLE / "report.json")])}\n'
        f'env={{PYTHONPATH={json.dumps(str(ROOT / "src"))}}}\n'
    )
    kb = EALKnowledgeBase(tmp_path, tools, tmp_path / "runs.sqlite3",
                          method_registry=api_load_registry())
    kb.register("source.eal", entry_id="api", context=CONTEXT, claims=[CLAIM])
    anchor = make_anchor(kb, task_id="synthetic-api", entry_id="api", claim=CLAIM, assessed_at=AT)
    assessment = kb.assess("api", CLAIM, now=AT)
    assert assessment["status"] == "supported"
    return kb, anchor, assessment, source


def messages(anchor, assessment):
    request = make_message(anchor, kind="assessment_request", message_id="request",
                           sender="reviewer", recipient="assessor")
    proposal = make_message(anchor, kind="proposal", message_id="proposal",
                            sender="assessor", recipient="reviewer", reply_to="request",
                            **proposal_fields(assessment))
    review = make_message(anchor, kind="review", message_id="review",
                          sender="reviewer", recipient="assessor", reply_to="proposal",
                          assessment_id=assessment["assessment_id"], verdict="accepted")
    return request, proposal, review


def start(case):
    kb, anchor, assessment, _ = case
    request, proposal, review = messages(anchor, assessment)
    validator = Validator(kb, anchor)
    assert validator.validate(request, actor="reviewer") is None
    return validator, proposal, review


def test_round_trip_returns_the_trusted_packet_and_preserves_qualifications(case):
    validator, proposal, review = start(case)
    payload = decode_payload(json.dumps(proposal))
    assert "packet" not in payload
    assert "age_seconds" not in json.dumps(payload)
    trusted = validator.validate(payload, actor="assessor")
    assert trusted == case[2]["packet"]
    assert trusted["claims"][CLAIM]["prose_verified"] is False
    assert trusted["evidence"]["load_test"]["age_status"] == "within_max_age"
    assert validator.validate(review, actor="reviewer") == trusted


@pytest.mark.parametrize("field,value", [
    ("assessment_id", "invented-assessment"),
    ("collection_id", "invented-collection"),
    ("status", "unsupported"),
    ("evidence_refs", {"load_test": "invented-observation"}),
    ("evidence_refs", {}),
])
def test_forged_reference_or_result_does_not_consume_the_request(case, field, value):
    validator, proposal, _ = start(case)
    forged = {**proposal, field: value}
    with pytest.raises(ProtocolError):
        validator.validate(forged, actor="assessor")
    assert validator.validate(proposal, actor="assessor")["assessment_id"] == proposal["assessment_id"]


@pytest.mark.parametrize("field,value", [
    ("entry_id", "other-entry"), ("claim", "performance_criteria_failed"),
    ("source_digest", "0" * 64), ("context_fingerprint", "0" * 64),
    ("method_registry_fingerprint", "0" * 64), ("assessed_at", AFTER_EXPIRY),
])
def test_changed_payload_scope_is_rejected(case, field, value):
    validator, proposal, _ = start(case)
    forged = copy.deepcopy(proposal)
    forged["scope"][field] = value
    with pytest.raises(ProtocolError, match="anchored task scope"):
        validator.validate(forged, actor="assessor")


def test_actual_source_revision_change_invalidates_pending_handoff(case):
    validator, proposal, _ = start(case)
    source = case[3]
    source.write_text(source.read_text().replace("The synthetic report", "This synthetic report"))
    with pytest.raises(ProtocolError, match="revision changed"):
        validator.validate(proposal, actor="assessor")


def test_registered_context_cannot_be_changed_in_place(case):
    validator, proposal, _ = start(case)
    with pytest.raises(ValueError, match="metadata differs"):
        case[0].register("source.eal", entry_id="api", context={**CONTEXT, "build_id": "another-build"},
                         claims=[CLAIM])
    assert validator.validate(proposal, actor="assessor")["assessment_id"] == proposal["assessment_id"]


def test_persisted_assessment_with_another_context_cannot_be_relabelled(case):
    validator, proposal, _ = start(case)
    other = case[0].assess("api", CLAIM, context={**CONTEXT, "build_id": "another-build"}, now=AT)
    forged = {**proposal, **proposal_fields(other)}
    with pytest.raises(ProtocolError, match="Assessment differs"):
        validator.validate(forged, actor="assessor")


def test_persisted_assessment_with_another_claim_cannot_be_relabelled(case):
    kb, anchor, _, _ = case
    (case[3].parent / "other.eal").write_text(case[3].read_text())
    kb.register("other.eal", entry_id="other", context=CONTEXT,
                claims=["performance_criteria_failed"])
    other = kb.assess("other", "performance_criteria_failed", now=AT)
    validator, proposal, _ = start(case)
    # Source and context are identical but that other claim's unsupported status
    # cannot replace the anchored claim's supported host result.
    forged = {**proposal, **proposal_fields(other)}
    with pytest.raises(ProtocolError, match="claim status"):
        validator.validate(forged, actor="assessor")


def test_collection_substitution_is_rejected_even_for_the_same_scope(case):
    validator, proposal, _ = start(case)
    other = case[0].assess("api", CLAIM, now=AT)
    assert other["assessment_id"] != proposal["assessment_id"]
    with pytest.raises(ProtocolError, match="Collection reference"):
        validator.validate({**proposal, "collection_id": other["collection_id"]}, actor="assessor")


def test_historical_supported_result_cannot_answer_a_later_time(case):
    kb, _, old_assessment, _ = case
    late = make_anchor(kb, task_id="late-api", entry_id="api", claim=CLAIM, assessed_at=AFTER_EXPIRY)
    request, replay, _ = messages(late, old_assessment)
    validator = Validator(kb, late)
    validator.validate(request, actor="reviewer")
    with pytest.raises(ProtocolError, match="assessment time"):
        validator.validate(replay, actor="assessor")


def test_stale_evidence_remains_unsupported_after_accepting_a_review(case):
    kb, _, _, _ = case
    late = make_anchor(kb, task_id="late-api", entry_id="api", claim=CLAIM, assessed_at=AFTER_EXPIRY)
    assessed = kb.assess("api", CLAIM, now=AFTER_EXPIRY)
    assert assessed["status"] == "unsupported"
    request, proposal, review = messages(late, assessed)
    validator = Validator(kb, late)
    validator.validate(request, actor="reviewer")
    packet = validator.validate(proposal, actor="assessor")
    assert packet["evidence"]["load_test"]["age_status"] == "stale"
    assert validator.validate(review, actor="reviewer")["claims"][CLAIM]["status"] == "unsupported"


def test_expired_assumption_is_not_extended_by_fresh_evidence_or_review(case):
    kb, _, _, source = case
    source.write_text(source.read_text().replace(
        '  reasoning passing_limits {',
        '  assumption applicable {\n'
        '    statement "The synthetic run remains applicable during this interval."\n'
        '    validate load_test\n'
        '    valid_from "2026-09-25T10:00:00Z"\n'
        '    valid_until "2026-09-25T10:00:10Z"\n'
        '  }\n\n  reasoning passing_limits {',
    ).replace('[evidence load_test] via passing_limits',
              '[evidence load_test, assumptions applicable] via passing_limits'))
    early = kb.assess("api", CLAIM, now=AT)
    assert early["status"] == "supported"
    at_expiry = "2026-09-25T10:00:10Z"
    anchor = make_anchor(kb, task_id="assumption-expiry", entry_id="api", claim=CLAIM, assessed_at=at_expiry)
    assessed = kb.assess("api", CLAIM, now=at_expiry)
    assert assessed["status"] == "unsupported"
    assert assessed["reused_count"] == 1
    request, proposal, review = messages(anchor, assessed)
    validator = Validator(kb, anchor)
    validator.validate(request, actor="reviewer")
    packet = validator.validate(proposal, actor="assessor")
    assert packet["evidence"]["load_test"]["age_status"] == "within_max_age"
    assert packet["assumptions"]["applicable"]["time_status"] == "expired"
    assert validator.validate(review, actor="reviewer")["claims"][CLAIM]["status"] == "unsupported"


def test_duplicate_and_conflicting_replies_are_rejected(case):
    validator, proposal, review = start(case)
    validator.validate(proposal, actor="assessor")
    with pytest.raises(ProtocolError, match="Duplicate"):
        validator.validate(proposal, actor="assessor")
    with pytest.raises(ProtocolError, match="already has"):
        validator.validate({**proposal, "message_id": "other-proposal"}, actor="assessor")
    validator.validate(review, actor="reviewer")
    with pytest.raises(ProtocolError, match="already has"):
        validator.validate({**review, "message_id": "other-review", "verdict": "rejected"}, actor="reviewer")


def test_missing_reply_wrong_actor_and_wrong_recipient_are_rejected(case):
    validator, proposal, _ = start(case)
    with pytest.raises(ProtocolError, match="no accepted prior"):
        validator.validate({**proposal, "reply_to": "missing"}, actor="assessor")
    with pytest.raises(ProtocolError, match="authenticated runner actor"):
        validator.validate(proposal, actor="reviewer")
    with pytest.raises(ProtocolError, match="do not reverse"):
        validator.validate({**proposal, "recipient": "intruder"}, actor="assessor")


def test_initial_request_requires_the_trusted_task_actors(case):
    validator = Validator(case[0], case[1])
    request, _, _ = messages(case[1], case[2])
    with pytest.raises(ProtocolError, match="not authorised"):
        validator.validate({**request, "sender": "intruder"}, actor="intruder")
    with pytest.raises(ProtocolError, match="authorised task actors"):
        validator.validate({**request, "recipient": "intruder"}, actor="reviewer")
    assert validator.validate(request, actor="reviewer") is None


def test_review_cannot_substitute_a_different_assessment(case):
    validator, proposal, review = start(case)
    validator.validate(proposal, actor="assessor")
    other = case[0].assess("api", CLAIM, now=AT)
    with pytest.raises(ProtocolError, match="substituted"):
        validator.validate({**review, "assessment_id": other["assessment_id"]}, actor="reviewer")


def test_objection_targets_an_existing_scoped_dependency(case):
    validator, proposal, _ = start(case)
    trusted = validator.validate(proposal, actor="assessor")
    objection = make_message(case[1], kind="objection", message_id="objection",
                             sender="reviewer", recipient="assessor", reply_to="proposal",
                             assessment_id=proposal["assessment_id"], target_kind="evidence",
                             target_id="missing_evidence", reason="Check the qualification.")
    with pytest.raises(ProtocolError, match="target is absent"):
        validator.validate(objection, actor="reviewer")
    assert validator.validate({**objection, "target_id": "load_test"}, actor="reviewer") == trusted


@pytest.mark.parametrize("mutation", [
    lambda p: {**p, "packet": {}},
    lambda p: {**p, "reply_to": None},
    lambda p: {**p, "evidence_refs": {"load_test": 1.5}},
    lambda p: {**p, "scope": {**p["scope"], "source": "injected source"}},
])
def test_schema_rejects_extra_fields_wrong_types_and_absent_reply(case, mutation):
    validator, proposal, _ = start(case)
    with pytest.raises(ProtocolError, match="discovery schema"):
        validator.validate(mutation(proposal), actor="assessor")


def test_json_decoder_rejects_duplicate_fields_and_nonfinite_numbers():
    with pytest.raises(ProtocolError):
        decode_payload('{"kind":"proposal","kind":"review"}')
    with pytest.raises(ProtocolError):
        decode_payload('{"measurement":NaN}')
