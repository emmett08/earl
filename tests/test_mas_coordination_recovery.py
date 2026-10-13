"""Software integration checks of real EAL/MCP and Lab delivery boundaries.

Scripted payloads in these tests are not native model outcomes. No live-trial
records are read, and all run state lives in pytest's private temporary paths.
"""

from copy import deepcopy
from pathlib import Path
import sqlite3

import pytest

from eal.evaluator import canonical_digest
from eal.knowledge import EALKnowledgeBase
from experiments.mas_coordination import recovery
from experiments.mas_coordination.cases import CLAIMS, FAILED_CLAIM, MET_CLAIM
from experiments.mas_coordination.effect_ledger import EffectLedger
from experiments.mas_coordination.task_contract import CandidateCheck, TaskContract
from experiments.mas_coordination.transport import LabTransport


RUNTIME = Path("/workspace/mas-protocol-lab")


@pytest.fixture
def prepared(tmp_path):
    if (not (RUNTIME / "rust-protocol/target/release/mas-protocol-codec").is_file()
            or not (RUNTIME / ".venv/bin/python").is_file()):
        pytest.skip("Actual MAS Protocol Lab runtime is not installed")
    recovery.prepare(tmp_path / "runs", RUNTIME)
    return tmp_path / "runs"


def run_for(prepared, arm="checked_protocol", *, workload=False):
    return prepared / f"task{502 if workload else 501}-{arm}"


def authored_message(run, finding, *, message_id="handoff"):
    state, contract, _ = recovery.components(run)
    message = {"schema": "EAL/MAS-coordination/2", "message_id": message_id,
               "task_id": contract.task_id, "task_digest": contract.task_digest,
               "sender": "assessor", "recipient": "reviewer", "reply_to": "request", "attempt": 0,
               "finding_id": finding["finding_id"]}
    check = CandidateCheck.from_dict(finding["check"])
    if check.ok:
        message.update(kind="outcome", assessment_refs=finding["assessment_refs"])
    else:
        message.update(kind="disposition", code=check.code,
                       outcome="incomplete" if check.code in {"evidence_unavailable", "effect_outcome_unknown"} else "rejected")
    return message


def response_file(run, actor, value):
    path = run / f"test-{actor}-response.json"
    recovery.save(path, value)
    return path


def record_assessor(run, finding, *, fault=None):
    path = response_file(run, "assessor", {"message": authored_message(run, finding), "consumed_message_ids": ["request"]})
    return recovery.record(run, "assessor", path, "software-assessor", execution_mode="software_test", fault=fault)


def reviewer_answer(run, conclusion):
    _, contract, _ = recovery.components(run)
    # Independently known synthetic fixture answers; never supplied by the
    # production gateway or copied into worker contexts.
    statuses = ({MET_CLAIM: "unsupported", FAILED_CLAIM: "supported"}
                if conclusion == "sample_fail" else {claim: None for claim in CLAIMS})
    return {"statuses": statuses, "scope": dict(contract.requested_scope), "assessed_at": contract.assessed_at,
            "conclusion": conclusion, "production_supported": False}


def record_reviewer(run, conclusion):
    path = response_file(run, "reviewer", {"answer": reviewer_answer(run, conclusion), "consumed_message_ids": ["handoff"]})
    return recovery.record(run, "reviewer", path, "software-reviewer", execution_mode="software_test")


def test_initial_contexts_pin_semantics_without_results_or_templates(prepared):
    manifest = recovery.read(prepared / "manifest.json")
    assert manifest["implementation_digest"]["recovery-schema.json"]
    assert manifest["semantic_definitions_digest"]
    for name in manifest["runs"]:
        run = prepared / name
        context = recovery.read(run / "assessor-context.json")
        assert not {"answer", "assessments", "trusted_snapshots", "proposal_templates"} & set(context)
        contract = TaskContract.from_dict(context["contract"])
        assert context["received_messages"][0]["task_digest"] == contract.task_digest
        assert not (run / "findings").exists()
        assert not (run / "reviewer-context.json").exists()


@pytest.mark.parametrize("arm", ["plain_mcp", "checked_protocol"])
def test_real_checked_host_mcp_and_recipient_exchange_are_software_only(prepared, arm):
    run = run_for(prepared, arm)
    finding = recovery.query(run)
    assert finding["check"]["ok"]
    assert finding["mcp"]["transport"] == "actual_mcp_stdio"
    assert {row["name"] for row in finding["mcp"]["calls"]} >= {"eal_describe", "eal_packet", "eal_sources"}
    record_assessor(run, finding)
    context = recovery.read(run / "reviewer-context.json")
    assert "answer" not in context and "review_templates" not in context
    assert recovery.lookup(run, context["received_messages"][0]["finding_id"], track=True) == finding
    assert record_reviewer(run, "sample_fail")["score"]["correct"]
    state = recovery.read(run / "state.json")
    assert {row["execution_mode"] for row in state["executions"]} == {"software_test"}
    if arm == "checked_protocol":
        assert LabTransport(RUNTIME, run / "mailbox.sqlite").receive(state["run_id"], "reviewer") == []
        # Completed record replay must succeed after the reviewer ACK emptied
        # the inbox, and must not call a model or republish the handoff.
        assert record_assessor(run, finding)["replayed"]
        assert record_reviewer(run, "sample_fail")["replayed"]
        assert LabTransport(RUNTIME, run / "mailbox.sqlite").status(state["run_id"])["usage"]["messages"] == 2


@pytest.mark.parametrize("arm", ["plain_mcp", "checked_protocol"])
def test_other_run_and_client_workload_is_a_typed_unassessed_disposition(prepared, arm):
    run = run_for(prepared, arm, workload=True)
    finding = recovery.query(run)
    assert finding["check"]["code"] == "workload_mismatch"
    assert finding["assessment_refs"] == {} and finding["assessments"] == {}
    assert finding["collected_count"] == 0
    record_assessor(run, finding)
    assert recovery.read(run / "state.json")["message"]["outcome"] == "rejected"
    assert record_reviewer(run, "out_of_scope")["score"]["correct"]


def test_unknown_reserved_effect_gets_incomplete_handoff_without_reexecution(prepared, monkeypatch):
    run = run_for(prepared)
    _, contract, _ = recovery.components(run)
    key = "query:" + contract.task_digest
    ledger = EffectLedger(run / "effects.sqlite")
    payload = {"operation": "assess", "task_digest": contract.task_digest}
    assert ledger.reserve_effect(key, payload)["status"] == "new"

    def forbidden_effect(*args, **kwargs):
        pytest.fail("An unknown reservation must never automatically reacquire evidence")

    monkeypatch.setattr(EALKnowledgeBase, "assess", forbidden_effect)
    finding = recovery.query(run)
    assert finding["check"]["code"] == "effect_outcome_unknown"
    assert finding["assessment_refs"] == {}
    assert ledger.reserve_effect(key, payload)["status"] == "unknown"
    record_assessor(run, finding)
    assert recovery.read(run / "state.json")["message"]["outcome"] == "incomplete"
    assert record_reviewer(run, "unresolved")["score"]["correct"]


def test_view_tampering_and_unissued_negative_finding_are_rejected(prepared):
    # A scope mismatch avoids acquisition while exercising issuance integrity.
    run = run_for(prepared, workload=True)
    finding = recovery.query(run)
    path = run / "findings" / f"{finding['finding_id']}.json"
    changed = deepcopy(finding)
    changed["collected_count"] = 123
    recovery.save(path, changed)
    with pytest.raises(ValueError, match="immutable gateway-issued"):
        recovery.lookup(run, finding["finding_id"])
    recovery.save(path, finding)
    forged = deepcopy(finding)
    original = CandidateCheck.from_dict(forged["check"])
    forged["check"] = CandidateCheck(False, "evidence_unavailable", "Worker-invented diagnosis", original.task_digest,
                                     original.entry_id, original.source_digest, original.context_fingerprint,
                                     original.method_registry_fingerprint).to_dict()
    identity = {key: forged[key] for key in ("task_digest", "check", "assessment_refs")}
    forged["finding_id"] = "finding_" + canonical_digest(identity)
    recovery.save(run / "findings" / f"{forged['finding_id']}.json", forged)
    with pytest.raises(ValueError, match="immutable gateway-issued"):
        recovery.lookup(run, forged["finding_id"])


def test_cached_findings_cannot_survive_current_source_revision_change(prepared, monkeypatch):
    run = run_for(prepared)
    original = recovery.query(run)
    source = run / "workspace/source.eal"
    source.write_text(source.read_text().replace("The synthetic report", "This synthetic report"))
    with pytest.raises(ValueError, match="correspondence changed"):
        recovery.lookup(run, original["finding_id"])

    def forbidden_effect(*args, **kwargs):
        pytest.fail("Invalidated cached correspondence must not rerun the committed acquisition")

    monkeypatch.setattr(EALKnowledgeBase, "assess", forbidden_effect)
    invalidated = recovery.query(run)
    assert invalidated["check"]["code"] == "source_changed"
    assert invalidated["assessment_refs"] == {}
    assert recovery.lookup(run, invalidated["finding_id"])["check"]["code"] == "source_changed"
    record_assessor(run, invalidated)
    assert record_reviewer(run, "out_of_scope")["score"]["correct"]


def test_collision_is_retained_and_cannot_be_replaced_with_a_repair(prepared):
    run = run_for(prepared, "plain_mcp", workload=True)
    finding = recovery.query(run)
    message = authored_message(run, finding, message_id="request")
    path = response_file(run, "assessor", {"message": message, "consumed_message_ids": ["request"]})
    with pytest.raises(ValueError, match="collides"):
        recovery.record(run, "assessor", path, "software-first-attempt", execution_mode="software_test")
    state = recovery.read(run / "state.json")
    assert state["attempts"]["assessor"]["outcome"] == "rejected"
    assert (run / "assessor-attempt.raw").exists()
    assert state["message"] is None
    repaired = {"message": authored_message(run, finding), "consumed_message_ids": ["request"]}
    recovery.save(path, repaired)
    with pytest.raises(ValueError, match="already retained first attempt"):
        recovery.record(run, "assessor", path, "software-second-attempt", execution_mode="software_test")


def test_failed_lookup_calls_consume_durable_reviewer_budget(prepared):
    run = run_for(prepared, workload=True)
    for _ in range(4):
        with pytest.raises(ValueError, match="identifier"):
            recovery.lookup(run, "malformed", track=True)
    with pytest.raises(ValueError, match="budget exhausted"):
        recovery.lookup(run, "malformed", track=True)
    with sqlite3.connect(run / "gateway.sqlite") as db:
        rows = db.execute("SELECT actor,operation,outcome FROM gateway_calls").fetchall()
    assert rows == [("reviewer", "lookup", "failed")] * 4


def test_after_send_restart_replays_outbox_without_another_effect(prepared, monkeypatch):
    run = run_for(prepared)
    finding = recovery.query(run)
    with pytest.raises(recovery.DeliveryInterrupted) as interrupted:
        record_assessor(run, finding, fault="after_send")
    assert "after remote send" in str(interrupted.value.__cause__)
    state = recovery.read(run / "state.json")
    assert state["attempts"]["assessor"]["outcome"] == "delivery_interrupted"

    def forbidden_effect(*args, **kwargs):
        pytest.fail("Outbox recovery must not repeat the EAL acquisition")

    monkeypatch.setattr(EALKnowledgeBase, "assess", forbidden_effect)
    assert record_assessor(run, finding)["actor"] == "assessor"
    assert record_reviewer(run, "sample_fail")["score"]["correct"]
    status = LabTransport(RUNTIME, run / "mailbox.sqlite").status(state["run_id"])
    assert status["usage"]["messages"] == 2
    assert len(recovery.read(run / "state.json")["executions"]) == 2
    assert EffectLedger(run / "handoffs.sqlite").reserve_effect("request", state["request"])["acknowledged"]


def test_actual_transport_failure_is_retryable_without_a_fault_flag(prepared, monkeypatch):
    run = run_for(prepared, workload=True)
    finding = recovery.query(run)
    original_send = LabTransport.send
    calls = []

    def interrupted_send(self, *args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("Temporary transport interruption")
        return original_send(self, *args, **kwargs)

    monkeypatch.setattr(LabTransport, "send", interrupted_send)
    with pytest.raises(recovery.DeliveryInterrupted) as interrupted:
        record_assessor(run, finding)
    assert "transport interruption" in str(interrupted.value.__cause__)
    assert recovery.read(run / "state.json")["attempts"]["assessor"]["outcome"] == "delivery_interrupted"
    assert record_assessor(run, finding)["actor"] == "assessor"
    assert record_reviewer(run, "out_of_scope")["score"]["correct"]


def test_received_envelope_is_checked_before_its_payload_is_relayed(prepared, monkeypatch):
    run = run_for(prepared, workload=True)
    finding = recovery.query(run)
    original_receive = LabTransport.receive

    def wrong_envelope(self, *args, **kwargs):
        deliveries = original_receive(self, *args, **kwargs)
        deliveries[0]["message"]["run_id"] = "another-run"
        return deliveries

    monkeypatch.setattr(LabTransport, "receive", wrong_envelope)
    with pytest.raises(recovery.DeliveryInterrupted) as interrupted:
        record_assessor(run, finding)
    assert "wrongly addressed envelope" in str(interrupted.value.__cause__)
    assert not (run / "reviewer-context.json").exists()
    assert not recovery.read(run / "state.json")["received"].get("reviewer")
    monkeypatch.setattr(LabTransport, "receive", original_receive)
    assert record_assessor(run, finding)["actor"] == "assessor"
    assert record_reviewer(run, "out_of_scope")["score"]["correct"]
