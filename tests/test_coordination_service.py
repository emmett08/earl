"""Real MCP coordination with scripted responses, finite budgets and recovery.

These are software integration checks, not model-quality measurements. Every
worker record is explicitly software_test; the registered EAL acquisitions,
packet retrievals and explanation retrievals use actual subprocess MCP.
"""
from copy import deepcopy
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from eal.coordination import Coordinator
from eal.coordination.gateway import MCPGateway
from eal.coordination.workers import CommandWorker
from experiments.mas_coordination.coordinator_demo import prepare_demo


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")


def started(tmp_path, profile=0, **kwargs):
    spec = prepare_demo(tmp_path / "workspace")
    task = spec["tasks"][profile]
    coord = Coordinator.start(tmp_path / "run", spec["server"], task, **kwargs)
    return coord, spec, task


def received(reservation):
    return reservation["context"]["received_messages"]


def assessor_response(reservation, finding, task):
    request = received(reservation)[0]
    message = {
        "schema": "EAL/MAS-coordination/3", "message_id": "assessor-outcome",
        "task_id": task["task_id"], "task_digest": finding["task_digest"],
        "sender": "assessor", "recipient": "reviewer", "reply_to": request["message_id"],
        "attempt": 0, "finding_id": finding["finding_id"],
    }
    if finding["check"]["ok"]:
        message.update(kind="outcome", assessment_refs={
            claim: row["assessment_id"] for claim, row in finding["assessments"].items()})
    else:
        code = finding["check"]["code"]
        message.update(kind="disposition", code=code,
                       outcome="rejected" if code in {"source_changed", "context_mismatch",
                           "workload_mismatch", "criteria_mismatch"} else "incomplete")
    return {"message": message, "consumed_message_ids": [request["message_id"]]}


def reviewer_response(reservation, finding, task):
    rows = finding["assessments"]
    conclusion = "assessed" if finding["check"]["ok"] else (
        "out_of_scope" if finding["check"]["code"] in {"source_changed", "context_mismatch",
            "workload_mismatch", "criteria_mismatch"} else "unresolved")
    answer = {"task_digest": finding["task_digest"], "finding_id": finding["finding_id"],
              "claims": {claim: {key: rows[claim][key] if claim in rows else None
                  for key in ("assessment_id", "status", "assessed_at")} for claim in task["claims"]},
              "scope": {"context": task["requirements"]["context"], "requirements": task["requirements"]},
              "conclusion": conclusion, "qualification": "conditional_on_registered_argument"}
    return {"answer": answer,
            "consumed_message_ids": [item["message_id"] for item in received(reservation)]}


def record(coord, reservation, response, label):
    return coord.record(reservation["call_id"], encoded(response),
                        execution_id="scripted-integration/" + label,
                        execution_mode="software_test",
                        evidence={"actual_agent_execution": False})


def bus_status(coord):
    return coord.bus.status(coord.config["run_id"])


def assessed_assessor(coord, task):
    reservation = coord.reserve_worker("assessor", execution_mode="software_test")
    assert reservation["new"] is True
    finding = coord.query(reservation["call_id"])
    response = assessor_response(reservation, finding, task)
    record(coord, reservation, response, "assessor")
    return reservation, finding, response


@pytest.mark.parametrize("profile,expected", [
    (0, {"performance_criteria_met": "supported", "performance_criteria_failed": "unsupported"}),
    (1, {"sample_endpoint_available": "contested", "sample_quorum_present": "supported"}),
])
def test_two_role_mcp_workflow_for_multiple_registered_claims(tmp_path, profile, expected):
    coord, spec, task = started(tmp_path, profile)
    assessor = coord.reserve_worker("assessor", execution_mode="software_test")
    finding = coord.query(assessor["call_id"])
    assert finding["check"]["ok"] is True
    assert {claim: row["status"] for claim, row in finding["assessments"].items()} == expected
    assert set(finding["packets"]) == set(task["claims"]) == set(finding["explanations"])
    calls = finding["mcp"]["calls"]
    actual_assessments = [row for row in calls if row["name"] == "eal_assess_known"]
    assert len(actual_assessments) == len(task["claims"])
    assert all(row["exposure"] == "registered" and row["outcome"] == "success"
               and set(row["arguments"]) == {"entry_id", "claim"} for row in actual_assessments)
    assert {row["name"] for row in calls} == {"eal_sources", "eal_assess_known", "eal_packet", "eal_explain"}
    assert calls[0]["name"] == "eal_sources" and calls[0]["arguments"] == {}
    assert calls[0]["exposure"] == "registered" and calls[0]["outcome"] == "success"
    assert finding["collected_count"] > 0 and finding["reused_count"] >= 0
    if profile == 0:
        assert finding["reused_count"] > 0
    response = assessor_response(assessor, finding, task)
    record(coord, assessor, response, "assessor")

    # Opening a new coordinator process/session uses the same frozen run.
    restarted = Coordinator(tmp_path / "run")
    reviewer = restarted.reserve_worker("reviewer", execution_mode="software_test")
    assert reviewer["new"] is True
    assert received(reviewer) == [response["message"]]
    looked_up = restarted.lookup(reviewer["call_id"], finding["finding_id"])
    assert looked_up == finding
    final = reviewer_response(reviewer, looked_up, task)
    record(restarted, reviewer, final, "reviewer")
    finished = restarted.status()
    assert finished["status"] == "completed"
    assert finished["answer"] == final["answer"]
    delivered = bus_status(restarted)
    assert delivered["usage"]["calls"] == 2
    assert delivered["usage"]["messages"] == 2
    assert all(item["acked"] for item in delivered["messages"])
    assert all(item["evidence"]["execution_mode"] == "software_test" for item in delivered["calls"])
    exported = restarted.export(tmp_path / "evidence.json")
    assert exported["status"]["answer"] == final["answer"]
    worker_effects = {item["payload"]["role"]: item for item in exported["effects"]
                     if item["key"].startswith("worker:")}
    for role, authored in (("assessor", response), ("reviewer", final)):
        retained = worker_effects[role]["result"]
        assert base64.b64decode(retained["raw_base64"]) == encoded(authored)
        assert retained["raw_digest"] == hashlib.sha256(encoded(authored)).hexdigest()
    assert "binding_key" not in json.dumps(exported)


def test_duplicate_queries_and_worker_records_preserve_exact_issued_result(tmp_path):
    coord, _, task = started(tmp_path)
    assessor = coord.reserve_worker("assessor", execution_mode="software_test")
    first = coord.query(assessor["call_id"])
    assert Coordinator(tmp_path / "run").query(assessor["call_id"]) == first
    response = assessor_response(assessor, first, task)
    record(coord, assessor, response, "assessor")
    repeated = coord.reserve_worker("assessor", execution_mode="software_test")
    assert repeated["new"] is False and repeated["call_id"] == assessor["call_id"]
    record(Coordinator(tmp_path / "run"), repeated, response, "assessor")
    status = bus_status(coord)
    assert status["usage"]["calls"] == 1
    assert status["usage"]["messages"] == 2
    changed = deepcopy(response)
    changed["message"]["message_id"] = "replacement"
    with pytest.raises(ValueError):
        record(coord, repeated, changed, "assessor")


def test_current_source_change_cannot_substitute_for_pinned_task(tmp_path):
    coord, spec, task = started(tmp_path)
    source = Path(spec["server"]["workspace"]) / "api-load.eal"
    source.write_text(source.read_text() + "\n// Changed after the task pin.\n")
    assessor = coord.reserve_worker("assessor", execution_mode="software_test")
    finding = coord.query(assessor["call_id"])
    assert finding["check"]["code"] == "source_changed"
    assert finding["assessments"] == {} and finding["mcp"]["calls"] == []
    response = assessor_response(assessor, finding, task)
    record(coord, assessor, response, "assessor")
    reviewer = coord.reserve_worker("reviewer", execution_mode="software_test")
    looked_up = coord.lookup(reviewer["call_id"], finding["finding_id"])
    final = reviewer_response(reviewer, looked_up, task)
    record(coord, reviewer, final, "reviewer")
    assert coord.status()["answer"]["conclusion"] == "out_of_scope"
    assert all(row["status"] is None for row in coord.status()["answer"]["claims"].values())


def test_source_change_after_issuance_blocks_cached_query_and_review_lookup(tmp_path):
    coord, spec, task = started(tmp_path)
    assessor = coord.reserve_worker("assessor", execution_mode="software_test")
    finding = coord.query(assessor["call_id"])
    response = assessor_response(assessor, finding, task)
    record(coord, assessor, response, "assessor")
    source = Path(spec["server"]["workspace"]) / "api-load.eal"
    source.write_text(source.read_text() + "\n// Superseded registered source.\n")
    with pytest.raises(ValueError):
        coord.query(assessor["call_id"])
    reviewer = coord.reserve_worker("reviewer", execution_mode="software_test")
    with pytest.raises(ValueError):
        coord.lookup(reviewer["call_id"], finding["finding_id"])


def test_unknown_worker_reservation_never_authorizes_automatic_reexecution(tmp_path):
    coord, _, _ = started(tmp_path)
    reserved = coord.reserve_worker("assessor", execution_mode="software_test")
    assert reserved["new"] is True
    restarted = Coordinator(tmp_path / "run")
    restarted.resume()
    retry = restarted.reserve_worker("assessor", execution_mode="software_test")
    assert retry["new"] is False and retry["call_id"] == reserved["call_id"]
    assert bus_status(restarted)["usage"]["calls"] == 1
    assert bus_status(restarted)["calls"][0]["state"] == "reserved"
    assert restarted.status()["status"] == "awaiting_worker_result"


def test_query_interruption_keeps_external_effect_unknown_instead_of_repeating(tmp_path, monkeypatch):
    coord, _, task = started(tmp_path)
    reserved = coord.reserve_worker("assessor", execution_mode="software_test")
    calls = []
    original = MCPGateway.assess

    def after_effect(self):
        result = original(self)
        calls.append(result)
        raise RuntimeError("Process stopped after registered MCP effects")

    monkeypatch.setattr(MCPGateway, "assess", after_effect)
    first_unknown = coord.query(reserved["call_id"])
    assert first_unknown["check"]["code"] == "effect_outcome_unknown"
    assert len(calls) == 1
    restarted = Coordinator(tmp_path / "run")
    unknown = restarted.query(reserved["call_id"])
    assert unknown["check"]["code"] == "effect_outcome_unknown"
    assert unknown["assessments"] == {} and len(calls) == 1
    assert unknown["collected_count"] is unknown["reused_count"] is None


def test_cancelled_run_cannot_start_or_collect_another_effect(tmp_path, monkeypatch):
    coord, _, _ = started(tmp_path)
    reserved = coord.reserve_worker("assessor", execution_mode="software_test")
    coord.cancel()
    monkeypatch.setattr(MCPGateway, "assess", lambda _: pytest.fail("Cancelled run acquired evidence"))
    restarted = Coordinator(tmp_path / "run")
    with pytest.raises(ValueError):
        restarted.query(reserved["call_id"])
    with pytest.raises(ValueError):
        restarted.reserve_worker("assessor", execution_mode="software_test")
    assert restarted.resume()["status"] == "cancelled"


@pytest.mark.parametrize("profile", [0, 1])
def test_new_coordinator_session_reuses_observations_without_new_collectors(tmp_path, profile):
    first, spec, task = started(tmp_path, profile)
    first_worker = first.reserve_worker("assessor", execution_mode="software_test")
    original = first.query(first_worker["call_id"])
    second = Coordinator.start(tmp_path / "second-run", spec["server"], task)
    second_worker = second.reserve_worker("assessor", execution_mode="software_test")
    reused = second.query(second_worker["call_id"])
    assert reused["check"]["ok"] is True
    assert reused["collected_count"] == 0 and reused["reused_count"] > 0
    assert {claim: row["status"] for claim, row in reused["assessments"].items()} == {
        claim: row["status"] for claim, row in original["assessments"].items()}
    for packet in reused["packets"].values():
        assert all(row["observed_at"] == spec["created_at"] for row in packet["evidence"].values())


def transport(kind):
    if kind == "json":
        return {"kind": "json"}
    configured = os.environ.get("MAS_PROTOCOL_LAB_RUNTIME")
    runtime = Path(configured or "/workspace/mas-protocol-lab")
    if not all(path.is_file() for path in (
            runtime / "runtime/mas_protocol/cli.py", runtime / ".venv/bin/python",
            runtime / "rust-protocol/target/release/mas-protocol-codec")):
        if configured:
            pytest.fail("Configured MAS Protocol Lab runtime is not installed and built")
        pytest.skip("Optional MAS Protocol Lab runtime is not installed and built")
    return {"kind": "lab", "runtime": str(runtime)}


def mismatched_run(tmp_path, kind="json", **kwargs):
    spec = prepare_demo(tmp_path / "workspace")
    task = deepcopy(spec["tasks"][0])
    task["requirements"]["workload"]["run_id"] = "unavailable-synthetic-run"
    coord = Coordinator.start(tmp_path / "run", spec["server"], task,
                              transport=transport(kind), **kwargs)
    return coord, spec, task


@pytest.mark.parametrize("kind", ["json", "lab"])
@pytest.mark.parametrize("boundary", ["before_send", "after_send", "after_ack", "after_finish"])
def test_committed_worker_restarts_after_delivery_or_execution_receipt_loss(tmp_path, monkeypatch, kind, boundary):
    coord, _, task = mismatched_run(tmp_path, kind)
    reserved = coord.reserve_worker("assessor", execution_mode="software_test")
    finding = coord.query(reserved["call_id"])
    assert finding["check"]["code"] == "workload_mismatch"
    response = assessor_response(reserved, finding, task)
    operation = "send" if boundary.endswith("send") else "acknowledge" if boundary == "after_ack" else "finish"
    original = getattr(coord.bus, operation)
    fired = []

    def interrupted(*args, **kwargs):
        if fired:
            return original(*args, **kwargs)
        fired.append(True)
        if boundary != "before_send":
            original(*args, **kwargs)
        raise RuntimeError("Delivery confirmation lost")

    monkeypatch.setattr(coord.bus, operation, interrupted)
    with pytest.raises(RuntimeError, match="confirmation lost"):
        record(coord, reserved, response, "assessor")
    persisted = coord.state.effect("worker:assessor")
    assert persisted["status"] == "committed" and persisted["result"]["accepted"] is True
    assert base64.b64decode(persisted["result"]["raw_base64"]) == encoded(response)
    restarted = Coordinator(tmp_path / "run")
    restarted.resume()
    assert restarted.state.effect("worker:assessor")["acknowledged"] is True
    status = bus_status(restarted)
    assert status["usage"]["messages"] == 2 and status["usage"]["calls"] == 1
    assert status["calls"][0]["state"] == "recorded"
    reviewer = restarted.reserve_worker("reviewer", execution_mode="software_test")
    assert received(reviewer) == [response["message"]]
    assert restarted.lookup(reviewer["call_id"], finding["finding_id"]) == finding


@pytest.mark.parametrize("kind", ["json", "lab"])
def test_abrupt_process_exit_after_remote_send_preserves_committed_outbox(tmp_path, kind):
    coord, _, task = mismatched_run(tmp_path, kind)
    reserved = coord.reserve_worker("assessor", execution_mode="software_test")
    finding = coord.query(reserved["call_id"])
    response = assessor_response(reserved, finding, task)
    response_path = tmp_path / "response.json"
    response_path.write_bytes(encoded(response))
    crash_script = tmp_path / "crash.py"
    crash_script.write_text('''import os, sys
from pathlib import Path
from eal.coordination import Coordinator
c = Coordinator(sys.argv[1])
original = c.bus.send
def crash_after_send(*args, **kwargs):
    original(*args, **kwargs)
    os._exit(73)
c.bus.send = crash_after_send
c.record(sys.argv[2], Path(sys.argv[3]).read_bytes(), "scripted-integration/assessor",
         execution_mode="software_test", evidence={"actual_agent_execution": False})
''')
    exited = subprocess.run([sys.executable, str(crash_script), str(tmp_path / "run"),
                             reserved["call_id"], str(response_path)],
                            capture_output=True, timeout=30, check=False)
    assert exited.returncode == 73, exited.stderr.decode(errors="replace")
    restarted = Coordinator(tmp_path / "run")
    effect = restarted.state.effect("worker:assessor")
    assert effect["status"] == "committed" and effect["acknowledged"] is False
    assert base64.b64decode(effect["result"]["raw_base64"]) == encoded(response)
    restarted.resume()
    assert restarted.state.effect("worker:assessor")["acknowledged"] is True
    assert bus_status(restarted)["usage"]["messages"] == 2
    assert restarted.reserve_worker("assessor", execution_mode="software_test")["new"] is False


def test_gateway_and_mcp_budgets_are_counted_before_effects(tmp_path):
    coord, _, _ = mismatched_run(tmp_path, budgets={"max_gateway_calls_per_role": 1})
    reserved = coord.reserve_worker("assessor", execution_mode="software_test")
    coord.query(reserved["call_id"])
    with pytest.raises(ValueError, match="gateway call budget"):
        coord.query(reserved["call_id"])
    assert len(coord.status()["calls"]) == 1

    # One admitted MCP call leaves an incomplete external effect. Later queries
    # cannot recollect or fabricate the missing assessment/packet results.
    second, _, _ = started(tmp_path / "mcp", budgets={"max_mcp_calls_per_role": 1})
    worker = second.reserve_worker("assessor", execution_mode="software_test")
    unknown = second.query(worker["call_id"])
    assert unknown["check"]["code"] == "effect_outcome_unknown"
    assert unknown["assessments"] == {}
    assert len([row for row in second.status()["calls"] if row["category"] == "mcp"]) == 1
    second.query(worker["call_id"])
    assert len([row for row in second.status()["calls"] if row["category"] == "mcp"]) == 1


def test_worker_output_limit_rejects_and_retains_first_exact_bytes(tmp_path):
    coord, _, _ = started(tmp_path, budgets={"max_worker_output_bytes": 16})
    reserved = coord.reserve_worker("assessor", execution_mode="software_test")
    raw = b'{"oversized":"' + b'x' * 100 + b'"}'
    outcome = coord.record(reserved["call_id"], raw, "scripted-integration/oversized", execution_mode="software_test")
    assert outcome["accepted"] is False and "output budget" in outcome["diagnostics"][0]["detail"]
    assert base64.b64decode(outcome["raw_base64"]) == raw
    with pytest.raises(ValueError, match="cannot be replaced"):
        coord.record(reserved["call_id"], b'{}', "scripted-integration/repaired", execution_mode="software_test")


def test_coordinator_enforces_its_per_worker_deadline(tmp_path):
    coord, _, _ = started(tmp_path, budgets={"worker_seconds": 1})
    worker = CommandWorker([sys.executable, "-c", "import time; time.sleep(3)"],
                           execution_mode="software_test", timeout_seconds=3,
                           max_output_bytes=65536, workspace=tmp_path)
    began = time.monotonic()
    status = coord.run(worker)
    elapsed = time.monotonic() - began
    assert status["status"] == "failed"
    assert elapsed < 2.5
    effect = coord.state.effect("worker:assessor")
    assert effect["result"]["outcome"] == "interrupted"
    assert effect["result"]["diagnostics"] == [{"code": "timeout"}]


def test_worker_roles_cannot_call_each_others_gateway_or_invent_findings(tmp_path):
    coord, _, task = mismatched_run(tmp_path)
    assessor = coord.reserve_worker("assessor", execution_mode="software_test")
    with pytest.raises(ValueError, match="worker role"):
        coord.lookup(assessor["call_id"], "finding_" + "a" * 64)
    finding = coord.query(assessor["call_id"])
    record(coord, assessor, assessor_response(assessor, finding, task), "assessor")
    reviewer = coord.reserve_worker("reviewer", execution_mode="software_test")
    with pytest.raises(ValueError, match="worker role"):
        coord.query(reviewer["call_id"])
    with pytest.raises(ValueError, match="not issued"):
        coord.lookup(reviewer["call_id"], "finding_" + "a" * 64)


def test_null_unassessed_status_cannot_be_replaced_with_unsupported_evidence(tmp_path):
    coord, _, task = mismatched_run(tmp_path)
    _, finding, _ = assessed_assessor(coord, task)
    reviewer = coord.reserve_worker("reviewer", execution_mode="software_test")
    looked_up = coord.lookup(reviewer["call_id"], finding["finding_id"])
    response = reviewer_response(reviewer, looked_up, task)
    response["answer"]["claims"][task["claims"][0]]["status"] = "unsupported"
    outcome = record(coord, reviewer, response, "reviewer")
    assert outcome["accepted"] is False
    assert coord.status()["status"] == "failed" and coord.status()["answer"] is None
    fixed = reviewer_response(reviewer, looked_up, task)
    with pytest.raises(ValueError, match="cannot be replaced"):
        record(coord, reviewer, fixed, "reviewer")


def test_assessor_must_consume_its_exact_addressed_request(tmp_path):
    coord, _, task = mismatched_run(tmp_path)
    assessor = coord.reserve_worker("assessor", execution_mode="software_test")
    finding = coord.query(assessor["call_id"])
    response = assessor_response(assessor, finding, task)
    response["consumed_message_ids"] = []
    outcome = record(coord, assessor, response, "assessor")
    assert outcome["accepted"] is False
    assert base64.b64decode(outcome["raw_base64"]) == encoded(response)
    with pytest.raises(ValueError, match="accepted assessor handoff"):
        coord.reserve_worker("reviewer", execution_mode="software_test")


def test_malformed_non_utf8_response_bytes_survive_rejection_and_export(tmp_path):
    coord, _, _ = started(tmp_path)
    worker = coord.reserve_worker("assessor", execution_mode="software_test")
    raw = b'\xff\xfe{"invalid":"utf8"}'
    result = coord.record(worker["call_id"], raw, "scripted-integration/malformed", execution_mode="software_test")
    assert result["accepted"] is False and base64.b64decode(result["raw_base64"]) == raw
    exported = Coordinator(tmp_path / "run").export(tmp_path / "export.json")
    effect = next(row for row in exported["effects"] if row["key"] == "worker:assessor")
    assert base64.b64decode(effect["result"]["raw_base64"]) == raw
    assert effect["result"]["raw_digest"] == hashlib.sha256(raw).hexdigest()


def test_frozen_worker_call_limit_prevents_second_worker(tmp_path):
    coord, _, task = mismatched_run(tmp_path, budgets={"max_worker_calls": 1})
    assessed_assessor(coord, task)
    with pytest.raises(ValueError, match="Worker call budget"):
        coord.reserve_worker("reviewer", execution_mode="software_test")
    assert bus_status(coord)["usage"]["calls"] == 1
    assert coord.status()["workers"]["reviewer"] is None


def test_abrupt_exit_after_actual_mcp_acquisition_never_repeats_unknown_effect(tmp_path):
    coord, _, _ = started(tmp_path)
    worker = coord.reserve_worker("assessor", execution_mode="software_test")
    crash_script = tmp_path / "crash_after_acquisition.py"
    crash_script.write_text('''import os, sys
from eal.coordination import Coordinator
from eal.coordination.gateway import MCPGateway
original = MCPGateway.assess
def crash_after_assessment(self):
    original(self)
    os._exit(74)
MCPGateway.assess = crash_after_assessment
Coordinator(sys.argv[1]).query(sys.argv[2])
''')
    exited = subprocess.run([sys.executable, str(crash_script), str(tmp_path / "run"), worker["call_id"]],
                            capture_output=True, timeout=45, check=False)
    assert exited.returncode == 74, exited.stderr.decode(errors="replace")
    restarted = Coordinator(tmp_path / "run")
    assert restarted.state.effect("assessment")["status"] == "unknown"
    before = restarted.status()["calls"]
    assert len([row for row in before if row["category"] == "mcp"]) == 7
    finding = restarted.query(worker["call_id"])
    assert finding["check"]["code"] == "effect_outcome_unknown"
    assert finding["assessments"] == {} and finding["collected_count"] is None
    after = restarted.status()["calls"]
    assert [row for row in after if row["category"] == "mcp"] == [
        row for row in before if row["category"] == "mcp"]
