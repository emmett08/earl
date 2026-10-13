"""Effect crash boundaries with pure callbacks and the actual optional Lab bus.

These are software recovery checks, not native model executions. Lab checks use
its built Rust codec, subprocess CLI, and SQLite mailbox, without a replacement
parser or a simulated transport.
"""

from concurrent.futures import ThreadPoolExecutor
import copy
import os
from pathlib import Path
import sqlite3

import pytest

from experiments.mas_coordination.effect_ledger import EffectLedger, LedgerError, canonical_json
from experiments.mas_coordination.transport import LabTransport


class SimulatedCrash(BaseException):
    """Abrupt interruption rather than a successful callback return."""


def incoming(message_id="request"):
    return {"message_id": message_id, "sender": "reviewer", "recipient": "assessor",
            "kind": "assessment_request", "question": "synthetic recovery check"}


def outgoing(message_id="reply"):
    return {"message_id": message_id, "sender": "assessor", "recipient": "reviewer",
            "kind": "proposal", "reply_to": "request", "synthetic": True}


RESULT = {"raw_response": '{"proposals":[]}', "admission": "accepted",
          "execution_mode": "software_test", "actual_agent_execution": False}
KEY = "run/assessor/request"


def state(path):
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        return {
            "effects": [dict(row) for row in db.execute("SELECT * FROM effects ORDER BY rowid")],
            "outbox": [dict(row) for row in db.execute("SELECT * FROM effect_outbox ORDER BY effect_key, position")],
        }


def test_canonical_identity_and_immutable_committed_output(tmp_path):
    ledger = EffectLedger(tmp_path / "ledger.sqlite")
    payload = {"nested": [1, 1.5, None, True], "scope": "synthetic"}
    first = ledger.reserve_effect(KEY, payload)
    assert first["status"] == "new"
    assert ledger.reserve_effect(KEY, {"scope": "synthetic", "nested": [1, 1.5, None, True]})["status"] == "unknown"
    result = copy.deepcopy(RESULT)
    messages = [outgoing()]
    committed = ledger.complete_effect(KEY, result, messages)
    result["raw_response"] = "changed by caller"
    messages[0]["synthetic"] = False
    committed["outbox"][0]["synthetic"] = False
    restarted = EffectLedger(ledger.path)
    replay = restarted.reserve_effect(KEY, payload)
    assert replay["status"] == "committed"
    assert replay["result"] == RESULT
    assert replay["outbox"] == [outgoing()]
    assert replay["payload_digest"] == first["payload_digest"]
    assert restarted.complete_effect(KEY, copy.deepcopy(RESULT), [outgoing()]) == replay
    with pytest.raises(LedgerError, match="cannot change"):
        restarted.complete_effect(KEY, {**RESULT, "admission": "rejected"}, [outgoing()])
    with pytest.raises(LedgerError, match="cannot change"):
        restarted.complete_effect(KEY, RESULT, [outgoing("other")])


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), {"n": float("-inf")},
                                     {1: "coerced key"}, (1, 2), {"bytes": b"raw"}, "\ud800"])
def test_rejects_non_json_without_reserving_effect(tmp_path, invalid):
    ledger = EffectLedger(tmp_path / "ledger.sqlite")
    with pytest.raises(LedgerError):
        ledger.reserve_effect(KEY, invalid)
    assert state(ledger.path)["effects"] == []


def test_rejects_cycles_and_preserves_json_number_types():
    cyclic = []
    cyclic.append(cyclic)
    with pytest.raises(LedgerError):
        canonical_json(cyclic)
    assert canonical_json({"n": 1}) != canonical_json({"n": 1.0})
    assert canonical_json({"n": True}) != canonical_json({"n": 1})


@pytest.mark.parametrize("completed", [False, True])
def test_inbound_collision_rejected_before_new_effect(tmp_path, completed):
    ledger = EffectLedger(tmp_path / "ledger.sqlite")
    assert ledger.reserve_effect(KEY, incoming())["status"] == "new"
    if completed:
        ledger.complete_effect(KEY, RESULT, [outgoing()])
    with pytest.raises(LedgerError, match="Inbound identity collision"):
        EffectLedger(ledger.path).reserve_effect(KEY, {**incoming(), "question": "different scope"})


def test_interrupted_external_effect_is_unknown_and_never_automatically_reexecuted(tmp_path):
    ledger = EffectLedger(tmp_path / "ledger.sqlite")
    external_calls = []
    reserved = ledger.reserve_effect(KEY, incoming())
    assert reserved["status"] == "new"
    external_calls.append("effect ran outside the ledger")
    # Crash after the external effect ran, before any output was committed.
    restarted = EffectLedger(ledger.path)
    replay = restarted.reserve_effect(KEY, incoming())
    if replay["status"] == "new":
        external_calls.append("unsafe automatic rerun")
    assert external_calls == ["effect ran outside the ledger"]
    assert replay["status"] == "unknown"
    assert replay["diagnosis"] == "effect_outcome_unknown"
    assert replay["result"] is None and replay["outbox"] == []
    assert restarted.drain_outbox(lambda _: pytest.fail("unknown effect must not send"),
                                  lambda _: pytest.fail("unknown effect must not ACK")) == {
        "confirmed_sends": [], "acknowledged_effects": [],
    }
    # An independently retained result may be reconciled, without reexecution.
    assert restarted.complete_effect(KEY, RESULT, [outgoing()])["status"] == "committed"


def test_concurrent_reservations_authorize_only_one_new_effect(tmp_path):
    ledger = EffectLedger(tmp_path / "ledger.sqlite")
    with ThreadPoolExecutor(max_workers=2) as workers:
        attempts = list(workers.map(lambda _: ledger.reserve_effect(KEY, incoming()), range(2)))
    assert sorted(row["status"] for row in attempts) == ["new", "unknown"]
    assert len(state(ledger.path)["effects"]) == 1


def test_result_and_outbox_rollback_together_on_interrupted_commit(tmp_path):
    ledger = EffectLedger(tmp_path / "ledger.sqlite")
    ledger.reserve_effect(KEY, incoming())
    with sqlite3.connect(ledger.path) as db:
        db.execute("""CREATE TRIGGER fail_outbox BEFORE INSERT ON effect_outbox
                      WHEN NEW.position = 1 BEGIN SELECT RAISE(ABORT, 'simulated commit failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="simulated commit failure"):
        ledger.complete_effect(KEY, RESULT, [outgoing("reply-1"), outgoing("reply-2")])
    persisted = state(ledger.path)
    assert persisted["effects"][0]["state"] == "reserved"
    assert persisted["effects"][0]["result"] is None
    assert persisted["outbox"] == []
    assert EffectLedger(ledger.path).reserve_effect(KEY, incoming())["diagnosis"] == "effect_outcome_unknown"


def test_invalid_completion_does_not_create_a_partial_commit(tmp_path):
    ledger = EffectLedger(tmp_path / "ledger.sqlite")
    with pytest.raises(LedgerError, match="existing effect reservation"):
        ledger.complete_effect(KEY, RESULT, [outgoing()])
    ledger.reserve_effect(KEY, incoming())
    for result, messages in [(float("nan"), [outgoing()]), (RESULT, [outgoing(), outgoing()]),
                             (RESULT, [{"message_id": ""}]), (RESULT, (outgoing(),))]:
        with pytest.raises(LedgerError):
            ledger.complete_effect(KEY, result, messages)
    assert state(ledger.path)["effects"][0]["state"] == "reserved"
    assert state(ledger.path)["outbox"] == []


def test_callbacks_observe_committed_output_and_execute_without_database_lock(tmp_path):
    ledger = EffectLedger(tmp_path / "ledger.sqlite")
    ledger.reserve_effect(KEY, incoming())
    messages = [outgoing("reply-1"), outgoing("reply-2")]
    ledger.complete_effect(KEY, RESULT, messages)
    delivered = []

    def send(message):
        assert EffectLedger(ledger.path).reserve_effect(KEY, incoming())["result"] == RESULT
        # A separate connection can write while an external send is in progress.
        EffectLedger(ledger.path).reserve_effect("side/" + message["message_id"], {"synthetic": True})
        delivered.append(message)

    def ack(key):
        assert key == KEY
        assert delivered == messages
        assert all(row["sent"] == 1 for row in state(ledger.path)["outbox"])

    drained = ledger.drain_outbox(send, ack)
    assert [row["message_id"] for row in drained["confirmed_sends"]] == ["reply-1", "reply-2"]
    assert drained["acknowledged_effects"] == [KEY]
    assert EffectLedger(ledger.path).reserve_effect(KEY, incoming())["acknowledged"] is True
    assert ledger.drain_outbox(lambda _: pytest.fail("no repeat after ACK"),
                              lambda _: pytest.fail("no repeat after ACK"))["confirmed_sends"] == []


def test_empty_rejected_outbox_acknowledges_only_persisted_response(tmp_path):
    ledger = EffectLedger(tmp_path / "ledger.sqlite")
    ledger.reserve_effect(KEY, incoming())
    result = {"raw_response": "invalid but retained", "admission": "rejected"}
    ledger.complete_effect(KEY, result, [])
    acknowledged = []

    def ack(key):
        assert ledger.reserve_effect(key, incoming())["result"] == result
        acknowledged.append(key)

    ledger.drain_outbox(lambda _: pytest.fail("rejected response has no reply"), ack)
    assert acknowledged == [KEY]


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


def prepare_inbound(bus, *, max_messages=2):
    bus.create("run", "reviewer", "assessor", max_messages=max_messages)
    bus.send("run", incoming(), actor="reviewer")
    received = bus.receive("run", "assessor")
    assert received[0]["message"]["payload"] == incoming()


@pytest.mark.parametrize("boundary", ["before_send", "after_send", "before_ack", "after_ack"])
def test_actual_lab_delivery_resumes_across_crash_boundaries(bus, tmp_path, boundary):
    prepare_inbound(bus)
    ledger = EffectLedger(tmp_path / "effects.sqlite")
    assert ledger.reserve_effect(KEY, incoming())["status"] == "new"
    ledger.complete_effect(KEY, RESULT, [outgoing()])

    def interrupted_send(message):
        if boundary == "before_send":
            raise SimulatedCrash()
        bus.send("run", message, actor="assessor")
        if boundary == "after_send":
            raise SimulatedCrash()

    def interrupted_ack(key):
        assert key == KEY
        if boundary == "before_ack":
            raise SimulatedCrash()
        bus.acknowledge("run", "request", "assessor")
        raise SimulatedCrash()

    with pytest.raises(SimulatedCrash):
        ledger.drain_outbox(interrupted_send, interrupted_ack)
    persisted = state(ledger.path)
    assert persisted["effects"][0]["state"] == "committed"
    assert persisted["effects"][0]["acknowledged"] == 0
    assert persisted["outbox"][0]["sent"] == int(boundary in {"before_ack", "after_ack"})
    restarted = EffectLedger(ledger.path)
    assert restarted.reserve_effect(KEY, incoming())["result"] == RESULT
    confirmations = []

    def send(message):
        confirmations.append(bus.send("run", message, actor="assessor"))

    restarted.drain_outbox(send, lambda key: bus.acknowledge("run", "request", "assessor"))
    assert len(confirmations) == int(boundary in {"before_send", "after_send"})
    if boundary == "after_send":
        assert confirmations[0]["duplicate"] is True
    assert bus.status("run")["usage"]["messages"] == 2
    assert bus.receive("run", "assessor") == []
    reply = bus.receive("run", "reviewer")
    assert len(reply) == 1 and reply[0]["message"]["payload"] == outgoing()
    assert restarted.reserve_effect(KEY, incoming())["acknowledged"] is True


def test_actual_lab_collision_keeps_result_pending_without_ack(bus, tmp_path):
    prepare_inbound(bus, max_messages=3)
    bus.send("run", {**outgoing(), "synthetic": False}, actor="assessor")
    ledger = EffectLedger(tmp_path / "effects.sqlite")
    ledger.reserve_effect(KEY, incoming())
    ledger.complete_effect(KEY, RESULT, [outgoing()])
    with pytest.raises(ValueError, match="different content"):
        ledger.drain_outbox(lambda message: bus.send("run", message, actor="assessor"),
                            lambda key: pytest.fail("colliding reply must not ACK input"))
    assert state(ledger.path)["outbox"][0]["sent"] == 0
    assert bus.receive("run", "assessor")[0]["redelivered"] is True
    assert EffectLedger(ledger.path).reserve_effect(KEY, incoming())["status"] == "committed"


def test_actual_lab_quota_failure_preserves_output_without_ack_or_new_execution(bus, tmp_path):
    prepare_inbound(bus, max_messages=1)
    ledger = EffectLedger(tmp_path / "effects.sqlite")
    ledger.reserve_effect(KEY, incoming())
    ledger.complete_effect(KEY, RESULT, [outgoing()])
    for current in [ledger, EffectLedger(ledger.path)]:
        assert current.reserve_effect(KEY, incoming())["status"] == "committed"
        with pytest.raises(ValueError, match="communication budget"):
            current.drain_outbox(lambda message: bus.send("run", message, actor="assessor"),
                                 lambda key: pytest.fail("undelivered output must not ACK input"))
    assert state(ledger.path)["outbox"][0]["sent"] == 0
    assert bus.status("run")["usage"]["messages"] == 1
    assert bus.receive("run", "assessor")[0]["redelivered"] is True


def test_actual_lab_partial_outbox_delivery_marks_only_confirmed_message(bus, tmp_path):
    prepare_inbound(bus, max_messages=2)
    ledger = EffectLedger(tmp_path / "effects.sqlite")
    ledger.reserve_effect(KEY, incoming())
    messages = [outgoing("reply-1"), outgoing("reply-2")]
    ledger.complete_effect(KEY, RESULT, messages)
    attempted = []

    def send(message):
        attempted.append(message["message_id"])
        return bus.send("run", message, actor="assessor")

    for current in [ledger, EffectLedger(ledger.path)]:
        with pytest.raises(ValueError, match="communication budget"):
            current.drain_outbox(send, lambda key: pytest.fail("partial outbox must not ACK input"))
    assert attempted == ["reply-1", "reply-2", "reply-2"]
    assert [row["sent"] for row in state(ledger.path)["outbox"]] == [1, 0]
    assert EffectLedger(ledger.path).reserve_effect(KEY, incoming())["outbox"] == messages
    assert bus.receive("run", "assessor")[0]["redelivered"] is True
    assert bus.status("run")["usage"]["messages"] == 2


def test_actual_lab_restart_after_interrupted_effect_keeps_input_unacknowledged(bus, tmp_path):
    prepare_inbound(bus)
    ledger = EffectLedger(tmp_path / "effects.sqlite")
    ledger.reserve_effect(KEY, incoming())
    # The external effect's outcome was lost; even redelivery cannot authorize a rerun.
    restarted = EffectLedger(ledger.path)
    assert bus.receive("run", "assessor")[0]["redelivered"] is True
    assert restarted.reserve_effect(KEY, incoming())["diagnosis"] == "effect_outcome_unknown"
    restarted.drain_outbox(lambda _: pytest.fail("unknown result must not be sent"),
                           lambda _: pytest.fail("unknown effect must not ACK input"))
    assert bus.status("run")["usage"]["messages"] == 1
    assert bus.receive("run", "assessor")[0]["redelivered"] is True
