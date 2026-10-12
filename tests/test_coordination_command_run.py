"""Scripted fresh command workers exercising actual registered EAL MCP.

The supplied helper computes responses mechanically and provides no live
receipt. These checks establish command-adapter integration, not model trials.
"""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

from eal.coordination import Coordinator
from eal.coordination.lab_mcp import LabMCPTransport
from eal.coordination.workers import CommandWorker
from experiments.mas_coordination.coordinator_demo import prepare_demo


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "mas_coordination" / "coordinator_worker.py"


def lab_configuration():
    configured = os.environ.get("MAS_PROTOCOL_LAB_RUNTIME")
    runtime = Path(configured or "/workspace/mas-protocol-lab")
    required = (runtime / "runtime/mas_protocol/cli.py", runtime / "runtime/mas_protocol/mcp_server.py",
                runtime / ".venv/bin/python", runtime / "rust-protocol/target/release/mas-protocol-codec")
    if not all(path.is_file() for path in required):
        if configured:
            pytest.fail("Configured MAS Protocol Lab runtime is not installed and built")
        pytest.skip("Optional MAS Protocol Lab runtime is not installed and built")
    return {"kind": "lab", "runtime": str(runtime)}


@pytest.mark.parametrize("profile,kind,expected", [
    (0, "json", {"performance_criteria_met": "supported", "performance_criteria_failed": "unsupported"}),
    (1, "lab", {"sample_endpoint_available": "contested", "sample_quorum_present": "supported"}),
])
def test_fresh_scripted_command_workers_complete_mcp_workflow_and_replay_without_effects(
        tmp_path, monkeypatch, profile, kind, expected):
    selected_transport = {"kind": "json"} if kind == "json" else lab_configuration()
    spec = prepare_demo(tmp_path / "workspace")
    task = spec["tasks"][profile]
    coordinator = Coordinator.start(tmp_path / "run", spec["server"], task,
                                    transport=selected_transport)
    if kind == "lab":
        assert isinstance(coordinator.bus, LabMCPTransport)
    published_commits = []
    authored_outputs = {}
    original_send = coordinator.bus.send

    def observe_committed_publication(run_id, payload, *, actor):
        if payload["kind"] == "outcome":
            effect = coordinator.state.effect("worker:assessor")
            # Exact bytes, admission and the complete reply coexist durably
            # before publishing the assessor's first output over either bus.
            assert effect["status"] == "committed" and effect["result"]["accepted"] is True
            assert effect["outbox"] == [payload]
            assert effect["result"]["response"]["message"] == payload
            raw = base64.b64decode(effect["result"]["raw_base64"])
            assert raw == authored_outputs["assessor"].raw_response
            published_commits.append(deepcopy(effect))
        return original_send(run_id, payload, actor=actor)

    monkeypatch.setattr(coordinator.bus, "send", observe_committed_publication)
    worker = CommandWorker([sys.executable, str(SCRIPT)], execution_mode="software_test",
                           timeout_seconds=180, max_output_bytes=65536,
                           workspace=spec["server"]["workspace"])
    original_execute = worker.execute

    def capture_authored_bytes(context, *args, **kwargs):
        output = original_execute(context, *args, **kwargs)
        assert context["role"] not in authored_outputs
        authored_outputs[context["role"]] = output
        return output

    monkeypatch.setattr(worker, "execute", capture_authored_bytes)
    result = coordinator.run(worker)
    assert result["status"] == "completed"
    assert {claim: row["status"] for claim, row in result["answer"]["claims"].items()} == expected
    assert result["answer"]["scope"] == {"context": task["requirements"]["context"],
                                         "requirements": task["requirements"]}
    assert result["answer"]["qualification"] == "conditional_on_registered_argument"
    assert len(published_commits) == 1

    # Reopening uses authoritative committed state rather than in-memory views.
    reopened = Coordinator(tmp_path / "run")
    assessor = reopened.state.effect("worker:assessor")
    reviewer = reopened.state.effect("worker:reviewer")
    assert assessor["outbox"] == [assessor["result"]["response"]["message"]]
    assert reviewer["outbox"] == []
    assert assessor["acknowledged"] is reviewer["acknowledged"] is True
    assert assessor["result"]["response"]["consumed_message_ids"] == ["request"]
    assert reviewer["result"]["response"]["consumed_message_ids"] == [
        assessor["result"]["response"]["message"]["message_id"]]
    executions = []
    pids = []
    for effect in (assessor, reviewer):
        stored = effect["result"]
        original = authored_outputs[effect["payload"]["role"]]
        assert stored["accepted"] is True and stored["execution_mode"] == "software_test"
        raw = base64.b64decode(stored["raw_base64"])
        assert raw == original.raw_response
        assert stored["execution_id"] == original.execution_id
        assert stored["raw_digest"] == hashlib.sha256(raw).hexdigest()
        assert json.loads(raw) == stored["response"]
        assert "execution" not in json.loads(raw)
        assert stored["execution_id"].startswith("command:" + effect["payload"]["call_id"] + ":")
        receipt = stored["evidence"]
        assert receipt["returncode"] == 0 and receipt["receipt_verification"] is None
        assert receipt["model"] is receipt["usage"] is None
        assert type(receipt["supervisor_pid"]) is int and receipt["supervisor_pid"] > 0
        executions.append(stored["execution_id"])
        pids.append(receipt["supervisor_pid"])
    assert len(set(executions)) == len(set(pids)) == 2

    assessment = reopened.state.effect("assessment")["result"]
    calls = assessment["mcp"]["calls"]
    assert calls[0]["name"] == "eal_sources" and calls[0]["exposure"] == "registered"
    acquisitions = [row for row in calls if row["name"] == "eal_assess_known"]
    assert {row["arguments"]["claim"] for row in acquisitions} == set(task["claims"])
    assert all(row["outcome"] == "success" and set(row["arguments"]) == {"entry_id", "claim"}
               for row in acquisitions)
    assert {row["name"] for row in calls} == {"eal_sources", "eal_assess_known", "eal_packet", "eal_explain"}
    assert all(row["outcome"] == "success" for row in calls)
    assert any(event["kind"] == "lookup" and event["data"]["calls"]
               for event in reopened.state.events())
    before_calls = reopened.status()["calls"]
    before_transport = reopened.bus.status(reopened.config["run_id"])
    before_effects = reopened.state.effects()

    def no_worker_execution(*args, **kwargs):
        pytest.fail("Completed run launched another scripted worker")

    monkeypatch.setattr(worker, "execute", no_worker_execution)
    assert reopened.resume()["status"] == "completed"
    assert reopened.run(worker)["status"] == "completed"
    assert reopened.status()["calls"] == before_calls
    assert reopened.state.effects() == before_effects
    assert reopened.bus.status(reopened.config["run_id"])["usage"] == before_transport["usage"]
    assert before_transport["usage"]["calls"] == 2
    assert before_transport["usage"]["messages"] == 2
