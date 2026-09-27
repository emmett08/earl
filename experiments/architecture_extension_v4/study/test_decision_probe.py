"""The registered cases drive the real EAL/2 and ASPIC+ decision path."""

from decimal import Decimal
import importlib
import importlib.util
from pathlib import Path
import sys
import json

import pytest

from experiments.architecture_extension_v4.study.decision_probe import generate, score


ROOT = Path(__file__).resolve().parent / "decision_cases"
EXPECTED = {
    ("fulfilment", "clean"): ("supported", "RECONCILE_COMPLETE"),
    ("fulfilment", "defeated"): ("contested", "HOLD_UNRESOLVED"),
    ("entitlement", "clean"): ("supported", "RETRY_SAME_KEY"),
    ("entitlement", "defeated"): ("contested", "RECONCILE_NO_REISSUE"),
    ("reservation", "clean"): ("supported", "MOVE_CURRENT_BUNDLE"),
    ("reservation", "defeated"): ("contested", "REJECT_NO_EFFECT"),
}


@pytest.mark.parametrize("system,case_id", EXPECTED)
def test_registered_state_pair_formal_and_plain_parity(system, case_id):
    source = ROOT / system / case_id / "source"
    p1 = generate(source, system, case_id, "P1", {})
    p2 = generate(source, system, case_id, "P2", {})
    p0 = generate(source, system, case_id, "P0", {})
    expected_status, expected_action = EXPECTED[(system, case_id)]
    assert p1["status"] == p2["status"] == p0["status"] == expected_status
    assert p1["expected_action"] == p2["expected_action"] == p0["expected_action"] == expected_action
    for field in ("facts", "guidance", "argument_content", "shared_material_digest",
                  "source_tree_sha256", "state_sha256", "selected_action"):
        assert p1[field] == p2[field], field
    assert "formal" not in p1 and p2["formal"]["status"] == expected_status
    assert p2["formal"]["grounded_status"] == ("accepted" if case_id == "clean" else "rejected")
    assert p2["formal"]["defeats"] if case_id == "defeated" else not p2["formal"]["defeats"]
    assert p2["prompt_text"].splitlines()[:2] == p1["prompt_text"].splitlines()[:2]
    assert "argument eligible_route" in p2["prompt_text"]
    assert expected_action not in p1["prompt_text"] or expected_action in p1["allowed_actions"]
    assert '"selected_action"' not in p1["prompt_text"]
    assert '"expected_action"' not in p2["prompt_text"]
    for packet in (p0, p1, p2):
        assert '"case_id"' not in packet["prompt_text"]
        assert '"clean"' not in packet["prompt_text"]
        assert '"defeated"' not in packet["prompt_text"]
    assert '"argument_content"' not in p0["prompt_text"]
    assert '"plain_conclusion"' not in p0["prompt_text"]
    assert score('{"action":"' + expected_action + '"}', expected_action, p1["allowed_actions"])["correct"]


def test_strict_scorer_classifies_wrong_and_malformed():
    assert score('{"action":"HOLD_UNRESOLVED"}', "RECONCILE_COMPLETE",
                 ["HOLD_UNRESOLVED", "RECONCILE_COMPLETE"])["status"] == "incorrect"
    assert score('```json\n{"action":"RECONCILE_COMPLETE"}\n```', "RECONCILE_COMPLETE")["status"] == "invalid"
    assert score('{"action":"RECONCILE_COMPLETE","reason":"guess"}',
                 "RECONCILE_COMPLETE")["status"] == "invalid"


def _public_module(source: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, source / "service.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("case_id", ("clean", "defeated"))
def test_entitlement_state_replays_against_public_issuer_source(case_id):
    root = ROOT / "entitlement" / case_id
    state = json.loads((root / "state.json").read_text())
    module = _public_module(root / "source", f"v4_public_issuer_{case_id}")
    issuer = module.InMemoryIssuer()
    setattr(issuer, "fail_before_issue" if case_id == "clean" else "lose_next_ack", True)
    request = state["request"]
    with pytest.raises(TimeoutError):
        issuer.issue(**request)
    actual = [{"account_id": receipt.account_id, "request_id": receipt.request_id,
               "user_id": receipt.user_id, "token_id": receipt.token_id}
              for receipt in issuer.lookup(request["account_id"], request["request_id"])]
    assert actual == state["lookup"]


@pytest.mark.parametrize("case_id", ("clean", "defeated"))
def test_reservation_state_uses_current_public_index(case_id):
    root = ROOT / "reservation" / case_id
    state = json.loads((root / "state.json").read_text())
    module = _public_module(root / "source", f"v4_public_calendar_{case_id}")
    calendar = module.InMemoryCalendar()
    for row in state["current_bookings"]:
        calendar.bookings[row["booking_id"]] = module.Booking(**row)
    request = state["request"]
    own = frozenset(request["own_booking_ids"])
    rooms = {calendar.bookings[booking_id].room_id for booking_id in own}
    conflict = any(calendar.conflicts(room, request["new_start"], request["new_end"],
                                      excluding=own) for room in rooms)
    assert conflict is (case_id == "defeated")
    assert state["historical_receipt"]["start"] == 10


def test_applied_refund_state_matches_public_payment_effect():
    root = ROOT / "fulfilment" / "clean"
    state = json.loads((root / "state.json").read_text())
    source = root / "source"
    saved = {key: value for key, value in sys.modules.items()
             if key == "fulfilment" or key.startswith("fulfilment.")}
    for key in saved:
        del sys.modules[key]
    sys.path.insert(0, str(source))
    try:
        payments = importlib.import_module("fulfilment.memory").InMemoryPayments()
        charge = payments.capture(Decimal("12.00"), "GBP", "token", "purchase-1")
        key = state["request"]["key"]
        payments.refund(charge, Decimal("12.00"), key)
        assert payments.refunds[key] == (charge.charge_id, Decimal("12.00"))
        assert state["provider"]["recorded_refunds"] == [{"key": key, "amount_pence": 1200}]
    finally:
        sys.path.remove(str(source))
        for key in [key for key in sys.modules if key == "fulfilment" or key.startswith("fulfilment.")]:
            del sys.modules[key]
        sys.modules.update(saved)
