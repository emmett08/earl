"""Actual EAL and optional Lab checks for software-only operational contrasts."""

import copy
import json
import os
from pathlib import Path

import pytest

from eal.knowledge import EALKnowledgeBase
from experiments.mas_coordination import operational


@pytest.fixture(scope="module")
def runtime():
    configured = os.environ.get("MAS_PROTOCOL_LAB_RUNTIME")
    path = Path(configured or "/workspace/mas-protocol-lab")
    required = (path / "runtime/mas_protocol/cli.py", path / ".venv/bin/python",
                path / "rust-protocol/target/release/mas-protocol-codec")
    if not all(item.is_file() for item in required):
        if configured:
            pytest.fail("Configured MAS Protocol Lab runtime is not installed and built")
        pytest.skip("Optional MAS Protocol Lab runtime is not installed and built")
    return path


@pytest.fixture(scope="module")
def measured(tmp_path_factory, runtime):
    output = tmp_path_factory.mktemp("operational") / "measured"
    return output, operational.run(output, runtime)


def episode(report, name, arm):
    return next(row for row in report["episodes"] if row["episode_id"] == name and row["arm"] == arm)


def test_correspondence_rejects_requested_run_and_client_mismatches_without_answers(tmp_path):
    result = operational.run_correspondence(tmp_path / "correspondence")
    assert result["outcome"] == "complete", result["errors"]
    assert result["eal_assessment_calls"] == 2
    rows = {row["case_id"]: row for row in result["cases"]}
    assert rows["nominal"]["legacy_context_only_admitted"] is True
    assert rows["nominal"]["v2_candidate_check"]["ok"] is True
    for name in ["changed_run", "changed_clients"]:
        assert rows[name]["legacy_false_admission"] is True
        assert rows[name]["v2_false_admission"] is False
        assert rows[name]["v2_candidate_check"]["code"] == "workload_mismatch"
        assert rows[name]["final_worker_answers"] is None
    assert rows["changed_build"]["legacy_context_only_admitted"] is False
    assert rows["changed_build"]["v2_candidate_check"]["code"] == "context_mismatch"
    assessments = json.loads((tmp_path / "correspondence/source-assessments.json").read_text())
    assert {row["status"] for row in assessments.values()} == {"supported", "unsupported"}


def test_actual_duplicate_eal_calls_reduce_independently_of_acquisition_reuse(measured):
    output, report = measured
    for arm, calls, reused in [("plain_retry", 3, 2), ("durable_json", 1, 0), ("durable_lab", 1, 0)]:
        row = episode(report, "duplicate_request", arm)
        assert row["outcome"] == "delivered", row["errors"]
        assert row["logical_effect_invocations"] == row["eal_assessment_calls"] == calls
        assert row["collected_count"] == 1
        assert row["reused_count"] == reused
        assert row["handler_deliveries"] == 3
        assert row["unique_replies"] == 1
        summaries = row["qualified_reply_summaries"]
        assert summaries[0]["status"] == "supported"
        assert summaries[0]["production_supported"] is False
        artifacts = list((output / row["artifact_directory"]).glob("assessment-*.json"))
        assert len(artifacts) == calls
        ids = {json.loads(path.read_text())["assessment_id"] for path in artifacts}
        assert len(ids) == calls
        events = json.loads((output / row["artifact_directory"] / "events.json").read_text())
        first_ack = next(index for index, event in enumerate(events) if event["operation"] == "ack_attempted")
        assert sum(event["operation"] == "inbound_received" for event in events[:first_ack]) == 3


def test_no_fault_controls_have_one_effect_and_equivalent_replies(measured):
    _, report = measured
    rows = [episode(report, "no_fault", arm) for arm in operational.ARMS]
    for row in rows:
        assert row["outcome"] == "delivered"
        assert row["logical_effect_invocations"] == 1
        assert row["unique_replies"] == 1
        assert row["local_completion_confirmed"] is True
    assert rows[0]["qualified_reply_summaries"] == rows[1]["qualified_reply_summaries"] == rows[2]["qualified_reply_summaries"]


@pytest.mark.parametrize("fault", ["commit_before_publish", "send_receipt_lost"])
def test_committed_delivery_faults_recover_without_reexecuting_durable_effect(measured, fault):
    output, report = measured
    for arm, calls in [("plain_retry", 2), ("durable_json", 1), ("durable_lab", 1)]:
        row = episode(report, fault, arm)
        assert row["outcome"] == "delivered"
        assert row["logical_effect_invocations"] == calls
        assert row["unique_replies"] == 1
        assert row["recovered_delivery"] is True
        assert row["eal_assessment_calls"] == 0
        assert row["effect_mode"] == "synthetic_counted_effect"
        events = json.loads((output / row["artifact_directory"] / "events.json").read_text())
        assert sum(event["operation"] == "fault_injected" for event in events) == 1
        if fault == "send_receipt_lost":
            sends = [event for event in events if event["operation"] == "remote_send_returned"]
            assert [event["duplicate"] for event in sends] == [False, True]


def test_successful_ack_has_no_manufactured_redelivery_or_plain_effect_penalty(measured):
    output, report = measured
    for arm in operational.ARMS:
        row = episode(report, "ack_confirmation_lost", arm)
        assert row["logical_effect_invocations"] == 1
        assert row["handler_deliveries"] == 1
        assert row["unique_replies"] == 1
        assert row["input_acknowledged"] is True
        assert row["local_completion_confirmed"] is (arm != "plain_retry")
        events = json.loads((output / row["artifact_directory"] / "events.json").read_text())
        polls = [event for event in events if event["operation"] == "recovery_inbox_polled"]
        assert polls == [{"sequence": polls[0]["sequence"], "operation": "recovery_inbox_polled", "pending_count": 0}]


def test_unknown_effect_remains_unresolved_and_avoids_automatic_rerun(measured):
    _, report = measured
    for arm in operational.ARMS:
        row = episode(report, "interrupted_effect", arm)
        if arm == "plain_retry":
            assert row["logical_effect_invocations"] == 2
            assert row["outcome"] == "delivered"
            assert row["automatic_reexecution_after_unknown"] is True
        else:
            assert row["logical_effect_invocations"] == 1
            assert row["outcome"] == "effect_outcome_unknown"
            assert row["safe_unknown"] is True
            assert row["recovered_delivery"] is False
            assert row["input_acknowledged"] is False
            assert row["unique_replies"] == 0
            assert row["automatic_reexecution_after_unknown"] is False


def test_json_and_actual_lab_share_logical_outcomes_and_budgets(measured):
    output, report = measured
    fields = ["outcome", "logical_effect_invocations", "eal_assessment_calls", "collected_count", "reused_count",
              "handler_deliveries", "send_attempts", "ack_attempts", "unique_replies", "input_acknowledged",
              "local_completion_confirmed", "recovered_delivery", "safe_unknown", "budgets"]
    for spec in operational.EPISODES:
        first = episode(report, spec["id"], "durable_json")
        second = episode(report, spec["id"], "durable_lab")
        assert {field: first[field] for field in fields} == {field: second[field] for field in fields}
    plan = json.loads((output / "plan.json").read_text())
    assert plan == operational.frozen_plan()
    assert len(report["episodes"]) == 18
    assert report["native_model_calls"] == report["actual_mcp_calls"] == 0
    assert report["model_tokens"] is report["model_cost_usd"] is None
    assert all(row["final_worker_answers"] is None for row in report["episodes"])
    with pytest.raises(FileExistsError, match="preserve all prior outcomes"):
        operational.run(output)


def test_json_mailbox_dedup_collision_quota_and_receive_before_ack(tmp_path):
    mailbox = operational.JsonMailbox(tmp_path / "mailbox.sqlite")
    mailbox.create("run", "reviewer", "assessor", max_messages=1)
    message = {"message_id": "message", "kind": "request", "sender": "reviewer", "recipient": "assessor"}
    assert mailbox.send("run", message, actor="reviewer")["duplicate"] is False
    assert mailbox.send("run", copy.deepcopy(message), actor="reviewer")["duplicate"] is True
    with pytest.raises(ValueError, match="different content"):
        mailbox.send("run", {**message, "extra": True}, actor="reviewer")
    with pytest.raises(ValueError, match="communication budget"):
        mailbox.send("run", {**message, "message_id": "second"}, actor="reviewer")
    with pytest.raises(ValueError, match="before ACK"):
        mailbox.acknowledge("run", "message", "assessor")
    assert mailbox.receive("run", "assessor")[0]["redelivered"] is False
    restarted = operational.JsonMailbox(mailbox.path)
    assert restarted.receive("run", "assessor")[0]["redelivered"] is True
    restarted.acknowledge("run", "message", "assessor")
    assert restarted.receive("run", "assessor") == []


def test_missing_lab_runtime_retains_incomplete_episode_without_substitution(tmp_path):
    row = operational.run_episode(tmp_path / "missing", "no_fault", "durable_lab", tmp_path / "missing-runtime")
    assert row["outcome"] == "incomplete"
    assert row["logical_effect_invocations"] == 0
    assert row["mailbox_usage"] is None
    assert row["errors"][0]["type"] == "FileNotFoundError"
    assert json.loads((tmp_path / "missing/result.json").read_text()) == row


def test_incomplete_actual_eal_result_is_retained_without_hidden_retry(tmp_path, monkeypatch):
    original = EALKnowledgeBase.assess

    def interrupted(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        next(iter(result["packet"]["arguments"].values()))["method_result"]["status"] = "incomplete"
        return result

    monkeypatch.setattr(EALKnowledgeBase, "assess", interrupted)
    row = operational.run_episode(tmp_path / "incomplete", "duplicate_request", "durable_json")
    assert row["outcome"] == "incomplete"
    assert row["eal_assessment_calls"] == row["logical_effect_invocations"] == 1
    assert row["unique_replies"] == 0
    assert row["errors"][0]["type"] == "ResourceIncomplete"
    assert (tmp_path / "incomplete/assessment-001.json").is_file()
    events = json.loads((tmp_path / "incomplete/events.json").read_text())
    assert events[-1]["operation"] == "episode_incomplete"
    assert events[-1]["automatic_retry"] is False


def test_exception_after_actual_acquisition_keeps_counts_unknown(tmp_path, monkeypatch):
    original = EALKnowledgeBase.assess

    def output_lost(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("Injected exception after actual acquisition; result unavailable")

    monkeypatch.setattr(EALKnowledgeBase, "assess", output_lost)
    row = operational.run_episode(tmp_path / "exception", "duplicate_request", "durable_json")
    assert row["outcome"] == "incomplete"
    assert row["eal_assessment_calls"] == 1
    assert row["collection_receipts_complete"] is False
    assert row["collected_count"] is row["reused_count"] is None
    assert row["recorded_collected_count"] == row["recorded_reused_count"] == 0
    assert row["input_acknowledged"] is False
    assert row["errors"][0]["type"] == "RuntimeError"
