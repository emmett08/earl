"""Durable addressed delivery over JSON and the actual optional Rust Lab bus."""
from copy import deepcopy
from contextlib import ExitStack
import os
from pathlib import Path

import pytest

from eal.coordination.bus import JsonBus, envelope
from eal.coordination.lab_mcp import LabMCPTransport


@pytest.fixture(params=("json", "lab"))
def bus(request, tmp_path):
    if request.param == "json":
        yield JsonBus(tmp_path / "mailbox.sqlite")
    else:
        configured = os.environ.get("MAS_PROTOCOL_LAB_RUNTIME")
        runtime = Path(configured or "/workspace/mas-protocol-lab")
        native = Path(__file__).resolve().parents[1] / "src/eal/coordination/rust_codec/target/release/mas-protocol-codec"
        required = (runtime / "runtime/mas_protocol/cli.py", runtime / ".venv/bin/python", native)
        if not all(path.is_file() for path in required):
            if configured:
                pytest.fail("Configured MAS Protocol Lab runtime is not installed and built")
            pytest.skip("Optional MAS Protocol Lab runtime is not installed and built")
        with ExitStack() as owners:
            transport = owners.enter_context(LabMCPTransport(runtime, tmp_path / "mailbox.sqlite", binary=native))
            transport._test_owners = owners
            yield transport


def reopened(bus):
    if isinstance(bus, JsonBus):
        return JsonBus(bus.database)
    return bus._test_owners.enter_context(LabMCPTransport(bus.runtime, bus.database, binary=bus.binary))


def message(message_id="request"):
    return {"schema": "EAL/MAS-coordination/3", "kind": "request", "message_id": message_id,
            "task_id": "synthetic_task", "task_digest": "a" * 64,
            "sender": "reviewer", "recipient": "assessor", "reply_to": None, "attempt": 0,
            "candidate_entry_id": "synthetic_entry"}


def test_addressed_delivery_preserves_envelope_order_and_acknowledged_receipts(bus):
    bus.create("run", "reviewer", "assessor")
    sent = [message("request-2"), message("request-1"), message("request-3")]
    for item in sent:
        bus.send("run", item, actor="reviewer")
    first = bus.receive("run", "assessor", limit=2)
    assert [item["message"] for item in first] == [envelope("run", item) for item in sent[:2]]
    assert all(set(item) == {"message", "sequence", "redelivered"} for item in first)
    assert all(type(item["sequence"]) is int and item["redelivered"] is False for item in first)
    restarted = reopened(bus)
    retry = restarted.receive("run", "assessor")
    assert [item["message"] for item in retry] == [envelope("run", item) for item in sent]
    assert [item["redelivered"] for item in retry] == [True, True, False]
    assert [item["sequence"] for item in retry] == sorted(item["sequence"] for item in retry)
    for item in sent:
        restarted.acknowledge("run", item["message_id"], "assessor")
    # Receipt loss after remote ACK is safely reconciled by repeat ACK.
    reopened(bus).acknowledge("run", sent[0]["message_id"], "assessor")
    assert reopened(bus).receive("run", "assessor") == []


def test_stable_message_retry_does_not_consume_another_quota_or_change_content(bus):
    bus.create("run", "reviewer", "assessor", max_messages=1)
    item = message()
    first = bus.send("run", item, actor="reviewer")
    retry = reopened(bus).send("run", item, actor="reviewer")
    assert first["duplicate"] is False and retry["duplicate"] is True
    assert first["sequence"] == retry["sequence"]
    changed = deepcopy(item)
    changed["task_digest"] = "b" * 64
    with pytest.raises(ValueError):
        bus.send("run", changed, actor="reviewer")
    with pytest.raises(ValueError):
        bus.send("run", message("extra"), actor="reviewer")
    assert bus.status("run")["usage"]["messages"] == 1


def test_ack_requires_received_message_and_exact_addressee(bus):
    bus.create("run", "reviewer", "assessor")
    bus.send("run", message(), actor="reviewer")
    with pytest.raises(ValueError):
        bus.acknowledge("run", "request", "assessor")
    assert bus.receive("run", "reviewer") == []
    bus.receive("run", "assessor")
    with pytest.raises(ValueError):
        bus.acknowledge("run", "request", "reviewer")
    with pytest.raises(ValueError):
        bus.acknowledge("run", "unknown", "assessor")
    assert len(bus.receive("run", "assessor")) == 1


def test_actor_and_recipient_must_belong_to_frozen_mailbox(bus):
    bus.create("run", "reviewer", "assessor")
    with pytest.raises(ValueError):
        bus.send("run", message(), actor="assessor")
    with pytest.raises(ValueError):
        bus.send("run", message(), actor="intruder")
    with pytest.raises(ValueError):
        bus.send("run", {**message(), "recipient": "intruder"}, actor="reviewer")
    with pytest.raises(ValueError):
        bus.receive("run", "intruder")
    assert bus.status("run")["usage"]["messages"] == 0


def test_bytes_and_frozen_configuration_survive_restart(bus):
    bus.create("run", "reviewer", "assessor", max_bytes=1)
    with pytest.raises(ValueError):
        bus.send("run", message(), actor="reviewer")
    restarted = reopened(bus)
    with pytest.raises(ValueError):
        restarted.create("run", "reviewer", "assessor", max_bytes=65536)
    assert restarted.status("run")["usage"]["messages"] == 0


def test_worker_reservations_and_actual_completion_evidence_persist(bus):
    bus.create("run", "reviewer", "assessor", max_calls=2)
    assert bus.reserve("run", "assessor", "assessor-call")["reserved"] is True
    restarted = reopened(bus)
    assert restarted.status("run")["calls"][0]["state"] == "reserved"
    with pytest.raises(ValueError):
        restarted.finish("run", "reviewer", "assessor-call", {"execution_id": "scripted"})
    evidence = {"execution_mode": "software_test", "execution_id": "scripted-check/turn1",
                "actual_agent_execution": False, "elapsed_ms": 10, "tokens": None, "cost_usd": None}
    assert restarted.finish("run", "assessor", "assessor-call", evidence)["recorded"] is True
    restarted.reserve("run", "reviewer", "reviewer-call")
    with pytest.raises(ValueError):
        restarted.reserve("run", "reviewer", "extra-call")
    status = reopened(bus).status("run")
    assert status["usage"]["calls"] == 2
    assert status["calls"][0]["evidence"] == evidence
    assert status["calls"][0]["state"] == "recorded"
