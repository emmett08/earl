"""Real isolated Lab MCP delivery and strict response/codec checks.

These are software integration tests, not language-model executions. Lab's
optional installed runtime and compiled Rust codec must actually be available.
"""
import json
import os
from pathlib import Path

from mcp.types import CallToolResult, TextContent
import pytest

from eal.coordination.lab import LabTransport
from eal.coordination.lab_mcp import LabMCPTransport


@pytest.fixture
def bus(tmp_path):
    configured = os.environ.get("MAS_PROTOCOL_LAB_RUNTIME")
    runtime = Path(configured or "/workspace/mas-protocol-lab")
    required = (runtime / "runtime/mas_protocol/mcp_server.py", runtime / ".venv/bin/python",
                runtime / "rust-protocol/target/release/mas-protocol-codec")
    if not all(path.is_file() for path in required):
        if configured:
            pytest.fail("Configured MAS Protocol Lab runtime is not installed and built")
        pytest.skip("Optional MAS Protocol Lab runtime is not installed and built")
    return LabMCPTransport(runtime, tmp_path / "mailbox.sqlite")


def message(message_id="request"):
    return {"schema": "EAL/MAS-coordination/3", "kind": "request", "message_id": message_id,
            "task_id": "synthetic_task", "task_digest": "a" * 64,
            "sender": "reviewer", "recipient": "assessor", "reply_to": None, "attempt": 0,
            "candidate_entry_id": "synthetic_entry"}


def test_actual_mcp_multi_message_delivery_redelivery_ack_and_stable_identity(bus):
    initial = bus.create("run", "reviewer", "assessor", max_messages=3)
    assert initial["active_protocol"] == "1"
    assert initial["config"]["max_messages"] == 3
    original = [message("second"), message("first"), message("third")]
    for item in original:
        assert bus.send("run", item, actor="reviewer")["duplicate"] is False
    retry = LabMCPTransport(bus.runtime, bus.database)
    assert retry.send("run", original[0], actor="reviewer")["duplicate"] is True
    with pytest.raises(ValueError, match="different content"):
        retry.send("run", {**original[0], "task_digest": "b" * 64}, actor="reviewer")
    with pytest.raises(ValueError, match="communication budget"):
        retry.send("run", message("extra"), actor="reviewer")
    with pytest.raises(ValueError, match="not been received"):
        retry.acknowledge("run", "second", "assessor")
    first = retry.receive("run", "assessor", limit=2)
    assert [item["message"]["payload"] for item in first] == original[:2]
    assert [item["redelivered"] for item in first] == [False, False]
    rows = bus.receive("run", "assessor")
    assert [item["message"]["payload"] for item in rows] == original
    assert [item["redelivered"] for item in rows] == [True, True, False]
    assert all(set(item) == {"message", "sequence", "redelivered"} for item in rows)
    assert all(set(item["message"]) == {"message_id", "run_id", "sender", "recipient", "version", "kind", "payload"}
               for item in rows)
    assert [item["sequence"] for item in rows] == sorted(item["sequence"] for item in rows)
    with pytest.raises(ValueError, match="not addressed"):
        bus.acknowledge("run", "second", "reviewer")
    for item in original:
        assert bus.acknowledge("run", item["message_id"], "assessor")["acknowledged"] is True
    assert retry.acknowledge("run", "second", "assessor")["acknowledged"] is True
    assert retry.receive("run", "assessor") == []
    assert retry.status("run")["usage"]["messages"] == 3


def test_native_accounting_uses_supplied_cli_and_mcp_status_reads_same_store(bus, monkeypatch):
    bus.create("run", "reviewer", "assessor", max_calls=1)
    operations = []
    command = LabTransport.command

    def recorded_command(self, *args):
        operations.append(args[0])
        return command(self, *args)

    monkeypatch.setattr(LabMCPTransport, "command", recorded_command)
    assert bus.reserve("run", "assessor", "worker-call")["reserved"] is True
    evidence = {"execution_mode": "software_test", "execution_id": "test/turn1",
                "actual_agent_execution": False, "elapsed_ms": 10, "tokens": None, "cost_usd": None}
    assert bus.finish("run", "assessor", "worker-call", evidence)["recorded"] is True
    with pytest.raises(ValueError, match="budget"):
        bus.reserve("run", "reviewer", "extra-call")
    status = bus.status("run")
    assert status["usage"]["calls"] == 1
    assert status["calls"][0]["state"] == "recorded"
    assert status["calls"][0]["evidence"] == evidence
    assert operations == ["reserve", "finish", "reserve"]


@pytest.mark.parametrize("bad", [1.5, {"fraction": 0.25}, {1: "changed key"}])
def test_actual_codec_rejects_inexact_numbers_and_object_key_conversion(bus, bad):
    item = message()
    item["data"] = bad
    with pytest.raises(ValueError):
        bus.send("unused", item, actor="reviewer")
    assert not bus.database.is_file()  # Rejection precedes server routing.


def test_actual_rust_encoder_preserves_exact_payload_values(bus):
    item = message()
    item["data"] = [10**100, True, None, "λ exact", {"numerator": 1, "denominator": 3}]
    envelope = {"message_id": "request", "run_id": "run", "sender": "reviewer", "recipient": "assessor",
                "version": "1", "kind": "request", "payload": item}
    assert bus.validate_wire(bus._encode(envelope)) == envelope


def test_adapter_fails_unknown_operations_without_cli_or_json_fallback(bus, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Unknown MCP operation attempted a fallback")

    monkeypatch.setattr(bus, "command", unexpected)
    monkeypatch.setattr(bus, "_call", unexpected)
    with pytest.raises(ValueError, match="not exposed"):
        bus.mcp_call("mas_reserve", {})
    assert not bus.database.is_file()


@pytest.mark.parametrize("structured", [True, False])
def test_result_accepts_actual_sdk_structured_and_text_envelopes(structured):
    value = {"ok": True, "result": [{"message": {}, "sequence": 1, "redelivered": False}]}
    result = CallToolResult(content=[TextContent(type="text", text=json.dumps(value))],
                            structured_content=value if structured else None)
    assert LabMCPTransport._result(result) == value["result"]


@pytest.mark.parametrize("value", [[], {"ok": 1, "result": {}}, {"ok": True},
                                   {"ok": True, "result": {}, "extra": 1},
                                   {"ok": False, "error": "failure"},
                                   {"ok": False, "error": {"code": 1, "message": "failure"}}])
def test_result_rejects_malformed_or_extended_response_envelopes(value):
    result = CallToolResult(content=[], structured_content=value)
    with pytest.raises(RuntimeError):
        LabMCPTransport._result(result)


def test_operation_rejection_remains_an_ordinary_diagnostic():
    result = CallToolResult(content=[], structured_content={"ok": False, "error": {
        "code": "operation_rejected", "message": "Unknown recipient"}})
    with pytest.raises(ValueError, match="operation_rejected: Unknown recipient"):
        LabMCPTransport._result(result)


def test_inherited_environment_cannot_select_another_sdk_database_or_leak_credentials(bus, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/unrelated/imports")
    monkeypatch.setenv("MAS_STATE_DB", "/unrelated/state.sqlite")
    monkeypatch.setenv("EXAMPLE_API_KEY", "synthetic-private-value")
    env = bus._environment()
    assert env["PYTHONPATH"] == str(bus.runtime / "runtime")
    assert env["MAS_STATE_DB"] == str(bus.database)
    assert env["MAS_PROTOCOL_BIN"] == str(bus.binary)
    assert "EXAMPLE_API_KEY" not in env
