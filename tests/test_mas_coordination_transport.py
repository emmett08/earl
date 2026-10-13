"""Optional integration checks against the supplied Lab Rust codec and CLI.

Set MAS_PROTOCOL_LAB_RUNTIME to an installed, built bundle. These tests use real
subprocesses and SQLite mailboxes; missing optional runtime capability is a skip,
not a simulated pass or a claim that separate agents executed.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess

import pytest

from experiments.mas_coordination.protocol import ScopeAnchor, make_message
from experiments.mas_coordination.transport import LabTransport


@pytest.fixture
def bus(tmp_path):
    configured = os.environ.get("MAS_PROTOCOL_LAB_RUNTIME")
    runtime = Path(configured or "/workspace/mas-protocol-lab")
    required = (runtime / "runtime/mas_protocol/cli.py", runtime / ".venv/bin/python",
                runtime / "rust-protocol/target/release/mas-protocol-codec")
    if not all(path.is_file() for path in required):
        if configured:
            pytest.fail("Configured MAS Protocol Lab runtime is not installed and built")
        pytest.skip("Optional MAS Protocol Lab runtime is not installed and built")
    return LabTransport(runtime, tmp_path / "mailbox.sqlite")


def payload(message_id="request"):
    anchor = ScopeAnchor(task_id="synthetic-task", entry_id="synthetic_entry", claim="claim",
                         source_digest="0" * 64, context_fingerprint="1" * 64,
                         method_registry_fingerprint="2" * 64,
                         assessed_at="2026-09-25T10:00:00Z")
    return make_message(anchor, kind="assessment_request", message_id=message_id,
                        sender="reviewer", recipient="assessor")


def envelope(message, run_id="run"):
    return {"message_id": message["message_id"], "run_id": run_id,
            "sender": message["sender"], "recipient": message["recipient"],
            "version": "1", "kind": message["kind"], "payload": message}


def actual_encode(bus, message):
    """Execute the authoritative Rust encoder, without a local parser substitute."""
    result = subprocess.run([str(bus.binary), "encode"], input=json.dumps(message),
                            capture_output=True, text=True, timeout=15, check=False)
    value = json.loads(result.stdout)
    assert result.returncode == 0 and value["ok"] is True
    return value["text"]


def test_actual_codec_cli_round_trip_and_isolated_runtime(bus):
    original = envelope(payload())
    text = actual_encode(bus, original)
    assert bus.validate_wire(text) == original
    # Verify the interpreter's actual package contract, rather than inspecting
    # its pathname alone or importing Lab's MCP SDK into the EAL test process.
    installed = subprocess.run(
        [bus.python, "-c", "import importlib.metadata; print(importlib.metadata.version('mcp'))"],
        capture_output=True, text=True, timeout=15, check=True,
    )
    assert installed.stdout.strip() == "1.26.0"
    bus.create("run", "reviewer", "assessor")
    assert bus.command("send", "--actor", "reviewer", "--text", text)["accepted"] is True
    receipt = bus.receive("run", "assessor")[0]
    assert receipt["message"] == original


@pytest.mark.parametrize("mutation", [
    lambda text: text.rstrip().removesuffix(";"),
    lambda text: text + " trailing input",
    lambda text: text.replace('version "1"', 'version "2"'),
    lambda text: text.replace('payload {', 'payload {"duplicate":1,"duplicate":2,', 1),
    lambda text: text.replace('payload {', 'payload {"decimal":1.5,', 1),
])
def test_actual_cli_rejects_malformed_or_incompatible_wire(bus, mutation):
    original = actual_encode(bus, envelope(payload()))
    with pytest.raises(ValueError):
        bus.validate_wire(mutation(original))


def test_mailbox_order_redelivery_ack_and_restart(bus):
    initial = bus.create("run", "reviewer", "assessor")
    assert initial["config"]["max_messages"] == 8
    assert initial["config"]["max_calls"] == 2
    assert initial["config"]["max_bytes"] == 65536
    assert initial["config"]["wall_seconds"] == 3600
    ids = ["request-2", "request-1", "request-3"]
    for message_id in ids:
        bus.send("run", payload(message_id), actor="reviewer")
    with pytest.raises(ValueError, match="not been received"):
        bus.acknowledge("run", ids[0], "assessor")
    first = bus.receive("run", "assessor", limit=2)
    assert [row["message"]["message_id"] for row in first] == ids[:2]
    assert all(set(row) == {"message", "sequence", "redelivered"} for row in first)
    assert all(type(row["sequence"]) is int and row["redelivered"] is False for row in first)
    restarted = LabTransport(bus.runtime, bus.database)
    redelivered = restarted.receive("run", "assessor")
    assert [row["message"]["message_id"] for row in redelivered] == ids
    assert [row["redelivered"] for row in redelivered] == [True, True, False]
    assert [row["sequence"] for row in redelivered] == sorted(row["sequence"] for row in redelivered)
    with pytest.raises(ValueError, match="not addressed"):
        restarted.acknowledge("run", ids[0], "reviewer")
    for message_id in ids:
        assert restarted.acknowledge("run", message_id, "assessor")["acknowledged"] is True
    assert restarted.receive("run", "assessor") == []


def test_duplicate_does_not_spend_budget_but_changed_content_is_rejected(bus):
    bus.create("run", "reviewer", "assessor", max_messages=1)
    message = payload()
    first = bus.send("run", message, actor="reviewer")
    duplicate = bus.send("run", message, actor="reviewer")
    assert first["duplicate"] is False and duplicate["duplicate"] is True
    assert first["sequence"] == duplicate["sequence"]
    changed = copy.deepcopy(message)
    changed["scope"]["claim"] = "other_claim"
    with pytest.raises(ValueError, match="different content"):
        bus.send("run", changed, actor="reviewer")
    with pytest.raises(ValueError, match="communication budget"):
        bus.send("run", payload("second"), actor="reviewer")
    assert bus.status("run")["usage"]["messages"] == 1


def test_byte_budget_identity_and_frozen_configuration(bus):
    bus.create("tiny", "reviewer", "assessor", max_bytes=1)
    with pytest.raises(ValueError, match="communication budget"):
        bus.send("tiny", payload(), actor="reviewer")
    assert bus.status("tiny")["usage"]["messages"] == 0
    bus.create("run", "reviewer", "assessor")
    with pytest.raises(ValueError, match="configuration differs"):
        bus.create("run", "reviewer", "assessor", max_calls=3)
    with pytest.raises(ValueError, match="host worker identity"):
        bus.send("run", payload(), actor="assessor")
    with pytest.raises(ValueError, match="unregistered worker"):
        bus.send("run", payload(), actor="intruder")
    with pytest.raises(ValueError, match="unregistered recipient"):
        bus.send("run", {**payload(), "recipient": "intruder"}, actor="reviewer")
    assert bus.status("run")["usage"]["messages"] == 0


def test_calls_reserve_before_execution_and_preserve_ownership_and_budget(bus):
    bus.create("run", "reviewer", "assessor")
    assert bus.reserve("run", "assessor", "assessor-turn")["reserved"] is True
    restarted = LabTransport(bus.runtime, bus.database)
    with pytest.raises(ValueError, match="already reserved"):
        restarted.reserve("run", "assessor", "assessor-turn")
    with pytest.raises(ValueError, match="another worker"):
        restarted.finish("run", "reviewer", "assessor-turn", {"external_record": "synthetic-reference"})
    evidence = {"execution_mode": "test-reference", "external_record": "synthetic-reference",
                "elapsed_ms": 10, "actual_agent_execution": False}
    assert restarted.finish("run", "assessor", "assessor-turn", evidence)["recorded"] is True
    with pytest.raises(ValueError, match="already completed"):
        restarted.finish("run", "assessor", "assessor-turn", evidence)
    restarted.reserve("run", "reviewer", "reviewer-turn")
    with pytest.raises(ValueError, match="call budget"):
        restarted.reserve("run", "reviewer", "extra-turn")
    state = restarted.status("run")
    assert state["usage"]["calls"] == 2
    assert state["calls"][0]["evidence"] == evidence
    assert state["calls"][0]["state"] == "recorded"


def test_finish_rejects_float_evidence_without_spending_another_call(bus):
    bus.create("run", "reviewer", "assessor")
    bus.reserve("run", "assessor", "turn")
    with pytest.raises(ValueError, match="floating JSON numbers"):
        bus.finish("run", "assessor", "turn", {"latency_seconds": 0.1})
    assert bus.status("run")["calls"][0]["state"] == "reserved"
    assert bus.finish("run", "assessor", "turn", {"latency_ms": 100})["recorded"] is True
    assert bus.status("run")["usage"]["calls"] == 1
