"""Software fault checks for lifecycle accounting and immutable first attempts.

Receipt values here are synthetic fixtures, including tests of the provider and
host receipt admission branches. No model or provider executes. A deliberately
mismatched workload makes assessment terminate before any MCP acquisition.
"""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import sys
from threading import Barrier

import pytest

from eal.coordination import Coordinator
from eal.coordination.bus import JsonBus
from eal.coordination.workers import CommandWorker
from experiments.mas_coordination.coordinator_demo import prepare_demo


def encoded(value):
    return json.dumps(value, allow_nan=False, sort_keys=True).encode("utf-8") + b"\n"


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    spec = prepare_demo(tmp_path_factory.mktemp("lifecycle-demo") / "workspace")
    spec = deepcopy(spec)
    spec["tasks"][0]["requirements"]["workload"]["run_id"] = "unavailable-lifecycle-run"
    return spec


@pytest.fixture(autouse=True)
def forbid_mcp(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Lifecycle mismatch fixture must not launch an MCP server")
    monkeypatch.setattr("eal.coordination.gateway.stdio_client", forbidden)


@pytest.fixture
def coord(tmp_path, demo):
    return Coordinator.start(tmp_path / "run", demo["server"], demo["tasks"][0])


def assessor(coord, mode="software_test"):
    reserved = coord.reserve_worker("assessor", execution_mode=mode)
    finding = coord.query(reserved["call_id"])
    assert finding["check"]["code"] == "workload_mismatch"
    assert finding["mcp"]["calls"] == []
    request = reserved["context"]["received_messages"][0]
    frame = {"message": {
        "schema": "EAL/MAS-coordination/3", "kind": "disposition",
        "message_id": "mismatched-sample", "task_id": request["task_id"],
        "task_digest": finding["task_digest"], "sender": "assessor", "recipient": "reviewer",
        "reply_to": request["message_id"], "attempt": 0, "finding_id": finding["finding_id"],
        "outcome": "rejected", "code": "workload_mismatch",
    }, "consumed_message_ids": [request["message_id"]]}
    return reserved, frame


class NeverExecute:
    execution_mode = "software_test"
    max_output_bytes = 65536

    def execute(self, *args, **kwargs):
        pytest.fail("An unresolved reservation must never launch another worker")


@pytest.mark.parametrize("remote_reserved", [False, True])
def test_transport_reservation_loss_reconciles_accounting_without_new_execution(coord, monkeypatch, remote_reserved):
    original = coord.bus.reserve

    def confirmation_lost(*args, **kwargs):
        if remote_reserved:
            original(*args, **kwargs)
        raise RuntimeError("Transport reservation confirmation lost")

    monkeypatch.setattr(coord.bus, "reserve", confirmation_lost)
    with pytest.raises(RuntimeError, match="confirmation lost"):
        coord.reserve_worker("assessor", execution_mode="software_test")
    worker = coord.state.effect("worker:assessor")
    assert worker["status"] == "unknown"
    assert coord.bus.status(coord.config["run_id"])["usage"]["calls"] == int(remote_reserved)

    restarted = Coordinator(coord.directory)
    assert restarted.resume()["status"] == "awaiting_worker_result"
    calls = restarted.bus.status(restarted.config["run_id"])["calls"]
    assert len(calls) == 1
    assert calls[0]["id"] == worker["payload"]["call_id"]
    assert calls[0]["actor"] == "assessor" and calls[0]["state"] == "reserved"
    assert restarted.reserve_worker("assessor", execution_mode="software_test")["new"] is False
    assert restarted.run(NeverExecute())["status"] == "awaiting_worker_result"
    assert restarted.bus.status(restarted.config["run_id"])["usage"]["calls"] == 1
    assert restarted.state.effect("worker:assessor")["result"] is None


@pytest.mark.parametrize("invalid_evidence", [
    {"measurement": float("nan")}, {"unsupported": {1, 2}}, ["not an object"],
    {"too_large": "x" * 65536},
])
def test_malformed_evidence_retains_rejected_first_raw_response(coord, invalid_evidence):
    reserved, frame = assessor(coord)
    raw = encoded(frame)
    recorded = coord.record(reserved["call_id"], raw, "synthetic-fixture/assessor",
                            execution_mode="software_test", evidence=invalid_evidence)
    assert recorded["accepted"] is False and recorded["outcome"] == "rejected"
    assert recorded["evidence"] == {}
    assert "execution evidence" in recorded["diagnostics"][0]["detail"]
    retained = Coordinator(coord.directory).state.effect("worker:assessor")
    assert retained["status"] == "committed"
    assert base64.b64decode(retained["result"]["raw_base64"]) == raw
    assert retained["acknowledged"] is True

    replacement = deepcopy(frame)
    replacement["message"]["message_id"] = "repaired-attempt"
    with pytest.raises(ValueError, match="First response cannot be replaced"):
        coord.record(reserved["call_id"], encoded(replacement), "synthetic-fixture/assessor",
                     execution_mode="software_test", evidence={"software_fixture": True})
    assert Coordinator(coord.directory).state.effect("worker:assessor")["result"] == recorded


@pytest.mark.parametrize("mode", ["provider", "actual_host_agent"])
@pytest.mark.parametrize("receipt,diagnostic", [
    ({"execution_id": "other-synthetic-id", "model": None, "usage": None}, "recorded identity"),
    ({"execution_id": "synthetic-external-id", "model": {}, "usage": None}, "model identity"),
    ({"execution_id": "synthetic-external-id", "model": None, "usage": {"input_tokens": True}}, "usage receipt"),
    ({"execution_id": "synthetic-external-id", "model": None, "usage": {"output_tokens": -1}}, "usage receipt"),
    ({"execution_id": "synthetic-external-id", "model": None, "usage": {"cost_usd": 0}}, "usage receipt"),
    ({"execution_id": "command:synthetic-external-id:42", "model": None, "usage": None}, "external execution identity"),
])
def test_wrapped_live_receipt_validation_is_enforced_for_external_recording(coord, mode, receipt, diagnostic):
    reserved = coord.reserve_worker("assessor", execution_mode=mode)
    # Receipt validation precedes domain admission, so no gateway call is needed
    # to demonstrate the reason this deliberately malformed receipt is rejected.
    raw = encoded({"response": {}, "execution": receipt})
    recorded = coord.record(reserved["call_id"], raw, "synthetic-external-id",
                            execution_mode=mode, evidence={"software_fixture": True})
    assert recorded["accepted"] is False
    assert diagnostic in recorded["diagnostics"][0]["detail"]
    assert base64.b64decode(recorded["raw_base64"]) == raw
    assert coord.state.effect("worker:assessor")["status"] == "committed"


@pytest.mark.parametrize("mode", ["provider", "actual_host_agent"])
def test_matching_wrapped_receipt_can_admit_synthetic_scoped_response(coord, mode):
    reserved, frame = assessor(coord, mode)
    raw = encoded({"response": frame, "execution": {
        "execution_id": "synthetic-receipt/assessor", "model": None, "usage": None,
    }})
    recorded = coord.record(reserved["call_id"], raw, "synthetic-receipt/assessor",
                            execution_mode=mode, evidence={"software_fixture": True})
    assert recorded["accepted"] is True
    assert recorded["response"] == frame
    assert recorded["evidence"]["software_fixture"] is True
    assert base64.b64decode(recorded["raw_base64"]) == raw


@pytest.mark.parametrize("mode,accepted", [("actual_host_agent", True), ("provider", False)])
def test_external_host_direct_frame_is_allowed_but_provider_requires_receipt(coord, mode, accepted):
    reserved, frame = assessor(coord, mode)
    result = coord.record(reserved["call_id"], encoded(frame), "synthetic-host/assessor",
                          execution_mode=mode, evidence={"software_fixture": True})
    assert result["accepted"] is accepted
    if not accepted:
        assert "external receipt" in result["diagnostics"][0]["detail"]


def test_run_rejects_incompatible_command_output_cap_before_any_worker_reservation(coord, tmp_path):
    marker = tmp_path / "executed"
    command = CommandWorker((sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"),
                            execution_mode="software_test", timeout_seconds=2,
                            max_output_bytes=coord.config["budgets"]["max_worker_output_bytes"] + 1)
    with pytest.raises(ValueError, match="output limit exceeds"):
        coord.run(command)
    assert not marker.exists()
    assert coord.state.effect("worker:assessor") is None
    assert coord.state.effect("worker:reviewer") is None
    assert coord.bus.status(coord.config["run_id"])["usage"]["calls"] == 0


def test_expired_unknown_worker_reports_expired_without_automatic_reexecution(coord, monkeypatch):
    reserved = coord.reserve_worker("assessor", execution_mode="software_test")
    monkeypatch.setattr("eal.coordination.service.time.time", lambda: coord.config["deadline"] + 1)
    restarted = Coordinator(coord.directory)
    assert restarted.resume()["status"] == "expired"
    assert restarted.state.effect("worker:assessor")["status"] == "unknown"
    assert restarted.state.effect("worker:assessor")["payload"]["call_id"] == reserved["call_id"]
    with pytest.raises(ValueError, match="wall-clock budget"):
        restarted.reserve_worker("assessor", execution_mode="software_test")
    assert restarted.run(NeverExecute())["status"] == "expired"


def test_initial_send_failure_reports_pending_and_resumes_without_workers(tmp_path, demo, monkeypatch):
    def failure(*args, **kwargs):
        raise RuntimeError("Initial delivery interrupted")

    with monkeypatch.context() as fault:
        fault.setattr(JsonBus, "send", failure)
        with pytest.raises(RuntimeError, match="Initial delivery interrupted"):
            Coordinator.start(tmp_path / "run", demo["server"], demo["tasks"][0])
    restarted = Coordinator(tmp_path / "run")
    assert restarted.state.effect("initial")["status"] == "committed"
    assert restarted.state.effect("initial")["acknowledged"] is False
    assert restarted.bus.status(restarted.config["run_id"])["usage"]["messages"] == 0
    assert restarted.status()["status"] == "delivery_pending"
    assert restarted.resume()["status"] == "ready_assessor"
    assert restarted.bus.status(restarted.config["run_id"])["usage"]["messages"] == 1
    assert restarted.state.effect("initial")["acknowledged"] is True
    assert restarted.state.effect("worker:assessor") is None
    assert restarted.bus.status(restarted.config["run_id"])["usage"]["calls"] == 0


def test_concurrent_coordinators_authorize_only_one_new_worker(coord):
    barrier = Barrier(2)

    def reserve():
        contender = Coordinator(coord.directory)
        barrier.wait(timeout=5)
        return contender.reserve_worker("assessor", execution_mode="software_test")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: reserve(), range(2)))
    assert sorted(result["new"] for result in results) == [False, True]
    assert results[0]["call_id"] == results[1]["call_id"]
    assert results[0]["context"] == results[1]["context"]
    assert coord.bus.status(coord.config["run_id"])["usage"]["calls"] == 1
    assert coord.state.effect("worker:assessor")["status"] == "unknown"
