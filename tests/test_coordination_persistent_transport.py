"""Real persistent MCP/Rust execution, lifecycle and uncertain-operation checks.

These are software integration checks. They do not execute language models or
establish model accuracy, token savings or parser throughput.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys
import time

import pytest

from eal.coordination.bus import envelope
from eal.coordination.codec_process import CodecProcess, CodecUnavailable
from eal.coordination.lab_mcp import LabMCPTransport


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def runtime_and_binary():
    configured = os.environ.get("MAS_PROTOCOL_LAB_RUNTIME")
    runtime = Path(configured or "/workspace/mas-protocol-lab")
    binary = ROOT / "src/eal/coordination/rust_codec/target/release/mas-protocol-codec"
    required = (runtime / "runtime/mas_protocol/mcp_server.py", runtime / "runtime/mas_protocol/cli.py",
                runtime / ".venv/bin/python", binary)
    if not all(path.is_file() for path in required):
        if configured:
            pytest.fail("Configured Lab runtime and EAL persistent Rust codec must be installed and built")
        pytest.skip("Optional Lab runtime and EAL persistent Rust codec are not installed and built")
    return runtime, binary


@pytest.fixture
def bus(runtime_and_binary, tmp_path):
    runtime, binary = runtime_and_binary
    with LabMCPTransport(runtime, tmp_path / "mailbox.sqlite", binary=binary) as value:
        yield value


@pytest.fixture
def admission_pair(runtime_and_binary, tmp_path):
    runtime, binary = runtime_and_binary
    with LabMCPTransport(runtime, tmp_path / "roundtrip.sqlite", binary=binary,
                         admission_mode="roundtrip") as roundtrip:
        with LabMCPTransport(runtime, tmp_path / "rust.sqlite", binary=binary,
                             admission_mode="rust") as native:
            yield roundtrip, native


def message(message_id="request"):
    return {"schema": "EAL/MAS-coordination/3", "kind": "request", "message_id": message_id,
            "task_id": "synthetic_task", "task_digest": "a" * 64,
            "sender": "reviewer", "recipient": "assessor", "reply_to": None, "attempt": 0,
            "candidate_entry_id": "synthetic_entry"}


def runtime_info(bus):
    return bus.mcp_call("mas_runtime_info", {})


def equal_store_states(pair, run_id="run"):
    states = [client.status(run_id) for client in pair]
    # Creation time is the sole expected difference between independent runs.
    for state in states:
        state.pop("deadline")
    assert states[0] == states[1]
    return states[0]


def send_envelope(client, value, actor="reviewer"):
    if client.admission_mode == "rust":
        return client.mcp_call("mas_send_envelope", {"envelope": value, "actor": actor})
    return client.mcp_call("mas_send", {"text": client._encode(value), "actor": actor})


def matching_rejection(pair, value, *, actor="reviewer", run_id="run"):
    before = equal_store_states(pair, run_id)
    for client in pair:
        with pytest.raises(ValueError):
            send_envelope(client, value, actor)
    assert equal_store_states(pair, run_id) == before
    assert all(not client.diagnostics()["closed"] for client in pair)


def assert_process_gone(pid, *, allow_defunct=False):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        if allow_defunct:
            # A forcibly killed server cannot wait() its codec child. Container
            # PID1 may retain the orphan's dead process entry until it reaps it.
            try:
                if Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z":
                    return
            except FileNotFoundError:
                return
        time.sleep(0.02)
    pytest.fail(f"Owned runtime process {pid} survived transport cleanup")


def test_persistent_session_reuses_server_and_codec_and_closes_both(bus):
    assert bus.diagnostics()["server_starts"] == 0
    bus.create("run", "reviewer", "assessor")
    bus.send("run", message(), actor="reviewer")
    initial = runtime_info(bus)
    assert initial["server_pid"] > 0 and initial["codec_pid"] > 0
    assert initial["codec_starts"] == 1
    assert bus.receive("run", "assessor")[0]["message"]["payload"] == message()
    bus.acknowledge("run", "request", "assessor")
    assert bus.receive("run", "assessor") == []
    bus.status("run")
    current = runtime_info(bus)
    assert {key: current[key] for key in ("server_pid", "codec_pid", "codec_starts")} == {
        key: initial[key] for key in ("server_pid", "codec_pid", "codec_starts")}
    assert bus.diagnostics()["server_starts"] == 1
    thread = bus._session.thread
    assert thread.is_alive()
    bus.close()
    bus.close()
    assert bus.diagnostics()["closed"] is True
    assert not thread.is_alive()
    assert_process_gone(initial["server_pid"])
    assert_process_gone(initial["codec_pid"])
    with pytest.raises(RuntimeError):
        bus.status("run")


def test_close_before_first_call_is_lazy_and_terminal(bus):
    bus.close()
    assert bus.diagnostics()["server_starts"] == 0
    assert bus.diagnostics()["closed"] is True
    with pytest.raises(RuntimeError):
        bus.create("run", "reviewer", "assessor")
    assert not bus.database.exists()


def test_context_exit_after_exception_reaps_owned_processes(runtime_and_binary, tmp_path):
    runtime, binary = runtime_and_binary
    with pytest.raises(ValueError, match="operator stopped"):
        with LabMCPTransport(runtime, tmp_path / "mailbox.sqlite", binary=binary) as bus:
            bus.create("run", "reviewer", "assessor")
            bus.send("run", message(), actor="reviewer")
            info = runtime_info(bus)
            raise ValueError("operator stopped")
    assert not bus._session.thread.is_alive()
    assert_process_gone(info["server_pid"])
    assert_process_gone(info["codec_pid"])


def test_concurrent_callers_share_one_session_and_stable_identity(bus):
    bus.create("run", "reviewer", "assessor", max_messages=8)
    inputs = [message(f"request-{index}") for index in range(8)]
    with ThreadPoolExecutor(max_workers=8) as clients:
        results = list(clients.map(lambda item: bus.send("run", item, actor="reviewer"), inputs))
    assert all(result["accepted"] and not result["duplicate"] for result in results)
    with ThreadPoolExecutor(max_workers=8) as clients:
        results = list(clients.map(lambda item: bus.send("run", item, actor="reviewer"), inputs))
    assert all(result["duplicate"] for result in results)
    assert bus.status("run")["usage"]["messages"] == 8
    assert bus.diagnostics()["server_starts"] == runtime_info(bus)["codec_starts"] == 1
    received = bus.receive("run", "assessor")
    assert {item["message"]["message_id"] for item in received} == {item["message_id"] for item in inputs}
    assert [item["sequence"] for item in received] == sorted(item["sequence"] for item in received)


def test_independent_clients_share_store_without_duplicate_quota(bus):
    bus.create("run", "reviewer", "assessor", max_messages=1)
    with LabMCPTransport(bus.runtime, bus.database, binary=bus.binary) as other:
        with ThreadPoolExecutor(max_workers=2) as clients:
            results = list(clients.map(lambda client: client.send("run", message(), actor="reviewer"),
                                       [bus, other]))
        assert sorted(result["duplicate"] for result in results) == [False, True]
        assert results[0]["sequence"] == results[1]["sequence"]
        changed = {**message(), "task_digest": "b" * 64}
        with pytest.raises(ValueError, match="different content"):
            other.send("run", changed, actor="reviewer")
        assert other.status("run")["usage"]["messages"] == 1
        assert other.receive("run", "assessor")[0]["message"]["payload"] == message()
        assert runtime_info(bus)["server_pid"] != runtime_info(other)["server_pid"]


def test_reservation_and_completion_share_mcp_session_without_cli(bus, monkeypatch):
    def unexpected_cli(*args, **kwargs):
        pytest.fail("Persistent transport used a per-operation CLI process")

    monkeypatch.setattr(bus, "command", unexpected_cli)
    bus.create("run", "reviewer", "assessor", max_calls=1)
    assert bus.reserve("run", "assessor", "worker-call")["reserved"] is True
    evidence = {"execution_id": "software/turn1", "execution_mode": "software_test",
                "tokens": None, "cost_usd": None}
    assert bus.finish("run", "assessor", "worker-call", evidence)["recorded"] is True
    status = bus.status("run")
    assert status["calls"][0]["state"] == "recorded"
    assert status["calls"][0]["evidence"] == evidence
    assert bus.diagnostics()["server_starts"] == 1


@pytest.mark.parametrize("bad", [1.5, {1: "converted key"}, "x" * 65537],
                         ids=["fraction", "nonstring_key", "oversize"])
def test_invalid_payload_cannot_route_or_poison_persistent_session(bus, bad):
    bus.create("run", "reviewer", "assessor")
    item = message()
    item["data"] = bad
    with pytest.raises(ValueError):
        bus.send("run", item, actor="reviewer")
    assert bus.status("run")["usage"]["messages"] == 0
    bus.send("run", message(), actor="reviewer")
    assert bus.status("run")["usage"]["messages"] == 1
    assert bus.diagnostics()["server_starts"] == 1


def test_depth_and_malformed_wire_rejections_preserve_mailbox_and_session(bus):
    bus.create("run", "reviewer", "assessor")
    nested = {}
    for _ in range(33):
        nested = {"nested": nested}
    item = message()
    item["data"] = nested
    with pytest.raises(ValueError):
        bus.send("run", item, actor="reviewer")
    wire = bus._encode(envelope("run", message()))
    for tampered in [wire + " garbage", wire.replace("payload {", 'payload {"attempt":0,', 1)]:
        assert tampered != wire
        with pytest.raises(ValueError):
            bus.mcp_call("mas_send", {"text": tampered, "actor": "reviewer"})
    assert bus.status("run")["usage"]["messages"] == 0
    assert bus.send("run", message(), actor="reviewer")["accepted"] is True


@pytest.mark.parametrize("near_wire_bound", [False, True])
def test_native_admission_preserves_exact_roundtrip_content_statuses_and_bytes(admission_pair, near_wire_bound):
    for client in admission_pair:
        client.create("run", "reviewer", "assessor", max_bytes=100000)
    item = message()
    if near_wire_bound:
        item["data"] = ""
        empty_wire = admission_pair[0]._encode(envelope("run", item))
        item["data"] = "x" * (65536 - len(empty_wire.encode("utf-8")))
        assert len(admission_pair[0]._encode(envelope("run", item)).encode("utf-8")) == 65536
    else:
        item["data"] = {"text": "∀x: 🧠 λ\n\\\"", "positive": 10**1023, "negative": -(10**1023),
                        "rational": {"numerator": 1, "denominator": 3}, "bool": True, "null": None,
                        "statuses": {"supported": "supported", "contested": "contested",
                                     "unsupported": "unsupported", "scope": "out_of_scope"}}
    traces = []
    results = []
    for client in admission_pair:
        before = runtime_info(client)
        results.append(client.send("run", item, actor="reviewer"))
        after = runtime_info(client)
        traces.append({key: after[key] - before[key] for key in ("encode_calls", "parse_calls", "admit_calls")})
    assert results[0] == results[1] == {"accepted": True, "duplicate": False, "sequence": 1}
    assert traces == [{"encode_calls": 2, "parse_calls": 2, "admit_calls": 0},
                      {"encode_calls": 0, "parse_calls": 0, "admit_calls": 1}]
    states = equal_store_states(admission_pair)
    exact_bytes = len(json.dumps(envelope("run", item), sort_keys=True, separators=(",", ":"),
                                ensure_ascii=False, allow_nan=False).encode("utf-8"))
    assert states["usage"] == {"messages": 1, "bytes": exact_bytes, "calls": 0}
    receipts = [client.receive("run", "assessor") for client in admission_pair]
    assert receipts[0] == receipts[1]
    assert receipts[0][0]["message"] == envelope("run", item)
    for client in admission_pair:
        client.acknowledge("run", "request", "assessor")
    assert equal_store_states(admission_pair)["messages"][0]["acked"] == 1


@pytest.mark.parametrize("changed,actor", [
    ({"sender": "assessor"}, "reviewer"),
    ({"recipient": "intruder"}, "reviewer"),
    ({}, "intruder"),
    ({"run_id": "missing"}, "reviewer"),
    ({"version": "2"}, "reviewer"),
    ({"message_id": "bad identity"}, "reviewer"),
    ({"kind": None}, "reviewer"),
    ({"payload": []}, "reviewer"),
    ({"validated": True}, "reviewer"),
])
def test_native_admission_matches_roundtrip_rejections_without_mutating_store(admission_pair, changed, actor):
    for client in admission_pair:
        client.create("run", "reviewer", "assessor")
    matching_rejection(admission_pair, {**envelope("run", message()), **changed}, actor=actor)
    for client in admission_pair:
        assert client.send("run", message(), actor="reviewer")["accepted"] is True
    equal_store_states(admission_pair)


@pytest.mark.parametrize("bad", [0.25, 10**1024, "x" * 65537],
                         ids=["fraction", "overlong_integer", "oversize"])
def test_native_admission_matches_invalid_typed_payload_rejections(admission_pair, bad):
    for client in admission_pair:
        client.create("run", "reviewer", "assessor")
    item = message()
    item["data"] = bad
    matching_rejection(admission_pair, envelope("run", item))


@pytest.mark.parametrize("depth,accepted", [(31, True), (32, False)])
def test_native_admission_matches_roundtrip_payload_depth_boundary(admission_pair, depth, accepted):
    for client in admission_pair:
        client.create("run", "reviewer", "assessor")
    value = None
    for _ in range(depth):
        value = {"nested": value}
    item = message()
    item["data"] = value
    if accepted:
        results = [client.send("run", item, actor="reviewer") for client in admission_pair]
        assert results[0] == results[1] == {"accepted": True, "duplicate": False, "sequence": 1}
        equal_store_states(admission_pair)
    else:
        matching_rejection(admission_pair, envelope("run", item))


def test_native_admission_preserves_duplicate_collision_and_expired_run_rules(admission_pair):
    for client in admission_pair:
        client.create("run", "reviewer", "assessor", max_messages=1)
        client.send("run", message(), actor="reviewer")
    changed = deepcopy(message())
    changed["task_digest"] = "b" * 64
    matching_rejection(admission_pair, envelope("run", changed))
    matching_rejection(admission_pair, envelope("run", message("message-budget-exhausted")))
    # A lost send receipt is still safely reconciled after the run's deadline;
    # an unseen identity cannot create a new effect after that deadline.
    for client in admission_pair:
        with sqlite3.connect(client.database) as db:
            db.execute("UPDATE runs SET deadline=0 WHERE id='run'")
    results = [client.send("run", message(), actor="reviewer") for client in admission_pair]
    assert results[0] == results[1] == {"accepted": True, "duplicate": True, "sequence": 1}
    matching_rejection(admission_pair, envelope("run", message("expired-new-message")))


def test_native_admission_preserves_exact_byte_budget_and_worker_call_state(admission_pair):
    item = message()
    size = len(json.dumps(envelope("run", item), ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")).encode("utf-8"))
    for client in admission_pair:
        client.create("run", "reviewer", "assessor", max_bytes=size, max_messages=2, max_calls=1)
        client.send("run", item, actor="reviewer")
        client.reserve("run", "assessor", "worker-call")
        client.finish("run", "assessor", "worker-call", {"execution_id": "software/turn1"})
    state = equal_store_states(admission_pair)
    assert state["usage"] == {"messages": 1, "bytes": size, "calls": 1}
    assert state["calls"][0]["state"] == "recorded"
    matching_rejection(admission_pair, envelope("run", message("byte-budget-exhausted")))
    for client in admission_pair:
        with pytest.raises(ValueError, match="budget"):
            client.reserve("run", "reviewer", "extra-worker-call")
    assert equal_store_states(admission_pair) == state


def test_caller_validation_flags_cannot_bypass_rust_admission(bus):
    bus.create("run", "reviewer", "assessor")
    invalid = envelope("run", message())
    invalid["payload"]["validated"] = True
    invalid["payload"]["fraction"] = 0.5
    # The only input is an ordinary envelope; neither an outer assertion nor a
    # payload assertion can substitute for admission by the actual Rust codec.
    with pytest.raises(ValueError):
        bus.mcp_call("mas_send_envelope", {"envelope": invalid, "actor": "reviewer", "validated": True})
    assert runtime_info(bus)["admit_calls"] == 1
    assert bus.status("run")["usage"]["messages"] == 0
    valid = envelope("run", message())
    assert bus.mcp_call("mas_send_envelope", {"envelope": valid, "actor": "reviewer"})["accepted"] is True
    assert runtime_info(bus)["admit_calls"] == 2


@pytest.mark.skipif(os.name != "posix", reason="Real process death check requires POSIX")
def test_dead_server_is_terminal_without_automatic_restart_or_send_replay(bus):
    bus.operation_timeout = 3
    bus.create("run", "reviewer", "assessor")
    bus.send("run", message(), actor="reviewer")
    info = runtime_info(bus)
    os.kill(info["server_pid"], signal.SIGKILL)
    with pytest.raises((RuntimeError, TimeoutError)):
        bus.send("run", message("never-replayed"), actor="reviewer")
    with pytest.raises(RuntimeError):
        bus.status("run")
    assert bus.diagnostics()["server_starts"] == 1
    assert bus.diagnostics()["closed"] is True
    # A new explicitly owned connection may inspect the durable outcome.
    with LabMCPTransport(bus.runtime, bus.database, binary=bus.binary) as reopened:
        assert reopened.status("run")["usage"]["messages"] == 1
    assert_process_gone(info["codec_pid"], allow_defunct=True)


@pytest.mark.skipif(os.name != "posix", reason="Real codec death check requires POSIX")
def test_dead_codec_is_terminal_without_replacement_or_routing(bus):
    bus.operation_timeout = 3
    bus.create("run", "reviewer", "assessor")
    bus.send("run", message(), actor="reviewer")
    info = runtime_info(bus)
    os.kill(info["codec_pid"], signal.SIGKILL)
    with pytest.raises((RuntimeError, TimeoutError)):
        bus.send("run", message("never-routed"), actor="reviewer")
    with pytest.raises(RuntimeError):
        bus.status("run")
    assert bus.diagnostics()["server_starts"] == 1
    assert bus.diagnostics()["closed"] is True
    assert_process_gone(info["server_pid"])
    with LabMCPTransport(bus.runtime, bus.database, binary=bus.binary) as reopened:
        assert reopened.status("run")["usage"]["messages"] == 1


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Parent-death cleanup requires Linux")
def test_hung_codec_times_out_terminally_and_cannot_survive_its_server(bus):
    bus.operation_timeout = 3
    bus.create("run", "reviewer", "assessor")
    bus.send("run", message(), actor="reviewer")
    info = runtime_info(bus)
    bus.operation_timeout = bus._session.timeout = 1
    os.kill(info["codec_pid"], signal.SIGSTOP)
    started = time.monotonic()
    try:
        with pytest.raises((RuntimeError, TimeoutError)):
            bus.send("run", message("never-replayed"), actor="reviewer")
        assert time.monotonic() - started < 10
        assert bus.diagnostics()["closed"] is True
        assert bus.diagnostics()["server_starts"] == 1
        assert not bus._session.thread.is_alive()
        assert_process_gone(info["server_pid"])
        assert_process_gone(info["codec_pid"], allow_defunct=True)
    finally:
        bus.close()
        # Preserve safety even if this check finds an orphaned stopped process.
        try:
            os.kill(info["codec_pid"], signal.SIGKILL)
        except ProcessLookupError:
            pass
    with LabMCPTransport(bus.runtime, bus.database, binary=bus.binary) as reopened:
        assert reopened.status("run")["usage"]["messages"] == 1


@pytest.mark.parametrize("response,operation", [
    ("os.write(1, b'not-json\\n')", "encode"),
    ("os.write(1, b'{}\\n{}\\n')", "encode"),
    ("os.write(1, b'{\"ok\":true,\"text\":1}\\n')", "encode"),
    ("os.write(1, b'x' * 300000 + b'\\n')", "encode"),
    ("time.sleep(60)", "encode"),
    ("os.write(1, b'{\"ok\":true,\"message\":{\"x\":' + b'[' * 20000 + b'0' + b']' * 20000 + b'}}\\n')", "admit"),
    ("os.write(1, b'{\"ok\":true,\"ok\":true,\"text\":\"unchanged\"}\\n')", "encode"),
    ("os.write(1, b'{\"ok\":true,\"message\":{\"x\":NaN}}\\n')", "admit"),
], ids=["invalid_json", "multiple_frames", "bad_success_type", "oversize_output", "timeout",
        "excessive_depth", "duplicate_response_fields", "nonfinite_message_number"])
def test_broken_codec_frames_and_timeout_are_bounded_and_never_retried(tmp_path, response, operation):
    # A deliberately faulty executable exercises the process supervisor rather
    # than pretending to implement the Rust protocol.
    executable = tmp_path / "faulty-codec"
    executable.write_text(f"#!{sys.executable}\nimport os, sys, time\n"
                          "sys.stdin.buffer.readline()\n" + response + "\n")
    executable.chmod(0o755)
    codec = CodecProcess(executable, timeout=0.3)
    with pytest.raises(CodecUnavailable):
        codec.call(operation, "{}")
    assert codec.closed is True
    assert codec.starts == 1
    assert codec.process.poll() is not None
    with pytest.raises(CodecUnavailable):
        codec.call(operation, "{}")
    assert codec.starts == 1
    codec.close()
