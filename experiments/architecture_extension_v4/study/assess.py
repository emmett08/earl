"""Version 4 host-only assessor; the version 3 instrument remains immutable.

Each invocation imports one candidate in a new process. The inherited cases are
the frozen v3 cases, while the refund probes below replace ambiguous expectations
and cover a split-dispatch rollback omission. V4 scores must never overwrite v3
measurements, even when replayed against the same retained candidate sources.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable


_V3_PATH = Path(__file__).resolve().parents[2] / "architecture_extension_v3/study/assess.py"
_V2_PATH = Path(__file__).resolve().parents[2] / "architecture_extension_v2/materials/assessor/probe.py"
_FROZEN_DEPS = {
    _V3_PATH: "4d5e6ce89801d7c2c66886ec3063b75711ca8a2cf459d53cd177e5664f20429e",
    _V2_PATH: "c83151aab8600551cf5f5949080b0d16557f07616f754144736c097fee8fbb68",
}
for _path, _expected in _FROZEN_DEPS.items():
    if hashlib.sha256(_path.read_bytes()).hexdigest() != _expected:
        raise RuntimeError(f"frozen assessor dependency changed: {_path}")
_spec = importlib.util.spec_from_file_location("architecture_extension_v3_assessor", _V3_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot load the frozen v3 assessor: {_V3_PATH}")
V3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V3)
P = V3.P
check = P.check
quantity = P.quantity
request = P.request
active_shipments = P.active_shipments
source_digest = V3.source_digest


def _refund_calls(payments: Any) -> list[tuple[str, Decimal, str]]:
    """Count attempts at the payment boundary, separately from applied effects."""
    calls: list[tuple[str, Decimal, str]] = []
    original_refund = payments.refund

    def record(charge: Any, amount: Decimal, key: str) -> Any:
        calls.append((charge.charge_id, amount, key))
        return original_refund(charge, amount, key)

    payments.refund = record
    return calls


def _unresolved(call: Callable[[], Any], phase: str, *, allow_ack_loss: bool = False) -> None:
    try:
        provisional = call()
    except Exception as error:
        nested = getattr(error, "errors", ())
        description = " ".join(
            (type(item).__name__ + " " + str(item)).lower()
            for item in (error, *nested)
        )
        check(any(marker in description for marker in ("unknown", "unresolved", "pending")) or
              (allow_ack_loss and "acknowledg" in description and "lost" in description),
              f"{phase}: unrelated failure was presented as an unresolved refund")
    else:
        check(getattr(provisional, "status", None) in {"unknown", "unresolved", "pending"},
              f"{phase}: unknown payment outcome was presented as complete")


def _no_return_effects(stock: Any, payments: Any, shipping: Any,
                       events: Any, order: Any, phase: str) -> None:
    check(quantity(stock, "north", "widget") == 0 and quantity(stock, "south", "widget") == 1,
          f"{phase}: stock was restored before refund status was known")
    check(len(events.events) == 1 and not any(
        "return" in event.name.lower() for event in events.events.values()
    ), f"{phase}: a return completion event was published while status was unknown")
    check(len(payments.captures) == 1 and order.charge.charge_id in payments.refunded,
          f"{phase}: original payment capture was changed")
    check(len(active_shipments(shipping)) == 2 and not shipping.cancelled,
          f"{phase}: a shipment was cancelled while the refund remained unresolved")


def _reject_conflicts(f: Any, service: Any, order: Any, north: Any,
                      stock: Any, payments: Any, shipping: Any, events: Any,
                      calls: list[tuple[str, Decimal, str]]) -> None:
    before = (tuple(calls), dict(payments.refunds), dict(payments.refunded),
              quantity(stock, "north", "widget"), quantity(stock, "south", "widget"),
              set(shipping.cancelled), dict(events.events))
    conflicts = (
        lambda: service.return_items(order.request_id, "conflicting-return",
                                     (f.ReturnLine(north.shipment_id, "widget", 2),)),
        lambda: service.cancel_order(order.request_id, "conflicting-cancellation"),
    )
    for conflicting in conflicts:
        try:
            result = conflicting()
        except Exception:
            pass
        else:
            check(getattr(result, "status", None) in {"unknown", "unresolved", "pending"},
                  "conflicting request was treated as complete while original refund was unknown")
        check((tuple(calls), dict(payments.refunds), dict(payments.refunded),
               quantity(stock, "north", "widget"), quantity(stock, "south", "widget"),
               set(shipping.cancelled), dict(events.events)) == before,
              "conflicting request changed a refund call, effect, stock, carrier or event")


def _complete_return(service: Any, order: Any, north: Any, stock: Any,
                     payments: Any, events: Any,
                     calls: list[tuple[str, Decimal, str]], key: str) -> None:
    perform = lambda: service.return_items(order.request_id, key, (north,))
    receipt = perform()
    check(receipt.refunded_amount == Decimal("12.00"), "resolved return receipt has wrong amount")
    check(len(calls) == 1, "known status issued an additional refund call")
    check(len(payments.refunds) == 1, "known status produced more than one refund effect")
    check(payments.refunded[order.charge.charge_id] == Decimal("12.00"),
          "known status did not settle exactly £12")
    check(quantity(stock, "north", "widget") == 1 and quantity(stock, "south", "widget") == 1,
          "known status did not restore exactly one north unit")
    check(sum("return" in event.name.lower() for event in events.events.values()) == 1,
          "known status did not publish exactly one return completion event")
    after = (tuple(calls), dict(payments.refunds), dict(payments.refunded),
             quantity(stock, "north", "widget"), quantity(stock, "south", "widget"),
             dict(events.events))
    check(perform() == receipt, "same-ID return retry changed receipt")
    check((tuple(calls), dict(payments.refunds), dict(payments.refunded),
           quantity(stock, "north", "widget"), quantity(stock, "south", "widget"),
           dict(events.events)) == after, "same-ID return retry repeated an external effect")


def r_unknown_before_request(f: Any) -> None:
    """The status is unknown before any refund request; no first call is assumed."""
    service, stock, payments, shipping, orders, events = P.rig(f, split=True)
    order = service.checkout(request(f))
    north = V3.north_south_lines(f, order)[0]
    calls = _refund_calls(payments)
    original_status = payments.refund_status
    payments.refund_status = lambda key: "unknown"
    payments.fail_after_refund = True
    perform = lambda: service.return_items(order.request_id, "unknown-before", (north,))
    for attempt in range(2):
        # The first call may encounter the injected lost acknowledgement if
        # the implementation does not ask for status before submitting it.
        _unresolved(perform, f"unknown-before attempt {attempt + 1}",
                    allow_ack_loss=attempt == 0)
        check(len(calls) <= 1, "unknown-before repeated a refund method call")
        check(len(payments.refunds) == len(calls),
              "unknown-before refund calls and applied effects disagree")
        check(payments.refunded[order.charge.charge_id] == Decimal("12.00") * len(calls),
              "unknown-before applied a wrong or duplicate refund amount")
        _no_return_effects(stock, payments, shipping, events, order, "unknown-before")
    _reject_conflicts(f, service, order, north, stock, payments, shipping, events, calls)
    payments.refund_status = original_status
    payments.fail_after_refund = False
    _complete_return(service, order, north, stock, payments, events, calls, "unknown-before")


def r_applied_then_unknown(f: Any) -> None:
    """A refund definitely applies, then acknowledgement and status are hidden."""
    service, stock, payments, shipping, orders, events = P.rig(f, split=True)
    order = service.checkout(request(f))
    north = V3.north_south_lines(f, order)[0]
    calls = _refund_calls(payments)
    original_refund = payments.refund
    original_status = payments.refund_status
    hidden = {"status": False}

    def apply_then_hide(charge: Any, amount: Decimal, key: str) -> Any:
        try:
            return original_refund(charge, amount, key)
        finally:
            hidden["status"] = True

    payments.refund = apply_then_hide
    payments.refund_status = lambda key: "unknown" if hidden["status"] else original_status(key)
    payments.fail_after_refund = True
    perform = lambda: service.return_items(order.request_id, "applied-hidden", (north,))
    _unresolved(perform, "applied then unknown first attempt", allow_ack_loss=True)
    check(hidden["status"] and len(calls) == 1,
          "applied then unknown did not attempt exactly one initial refund")
    check(len(payments.refunds) == 1 and
          payments.refunded[order.charge.charge_id] == Decimal("12.00"),
          "applied then unknown did not apply exactly one £12 refund")
    _no_return_effects(stock, payments, shipping, events, order, "applied then unknown")
    for attempt in range(2):
        _unresolved(perform, f"applied then unknown retry {attempt + 1}")
        check(len(calls) == 1, "unknown applied refund caused another refund method call")
        check(len(payments.refunds) == 1 and
              payments.refunded[order.charge.charge_id] == Decimal("12.00"),
              "unknown applied refund repeated the financial effect")
        _no_return_effects(stock, payments, shipping, events, order, "applied then unknown")
    _reject_conflicts(f, service, order, north, stock, payments, shipping, events, calls)
    hidden["status"] = False
    payments.fail_after_refund = False
    _complete_return(service, order, north, stock, payments, events, calls, "applied-hidden")


def r_not_applied_retry(f: Any) -> None:
    """A failed-before-effect call may be retried once using the same key."""
    service, stock, payments, shipping, orders, events = P.rig(f, split=True)
    order = service.checkout(request(f))
    north = V3.north_south_lines(f, order)[0]
    calls = _refund_calls(payments)
    payments.fail_refund = True
    perform = lambda: service.return_items(order.request_id, "not-applied", (north,))
    try:
        result = perform()
    except Exception:
        pass
    else:
        check(getattr(result, "status", None) in {"pending", "unresolved"},
              "failed-before-effect refund was treated as completed")
    check(len(calls) == 1 and not payments.refunds,
          "failed-before-effect fixture did not cause exactly one unsuccessful call")
    check(payments.refunded[order.charge.charge_id] == Decimal("0.00"),
          "failed-before-effect refund moved money")
    _no_return_effects(stock, payments, shipping, events, order, "not-applied")
    payments.fail_refund = False
    receipt = perform()
    check(receipt.refunded_amount == Decimal("12.00"), "not-applied retry did not complete return")
    check(len(calls) == 2 and calls[0] == calls[1],
          "not-applied retry changed the refund key, charge or amount")
    check(len(payments.refunds) == 1 and
          payments.refunded[order.charge.charge_id] == Decimal("12.00"),
          "not-applied retry did not cause exactly one refund effect")
    check(quantity(stock, "north", "widget") == 1 and
          sum("return" in e.name.lower() for e in events.events.values()) == 1,
          "not-applied retry did not restore stock and emit one return event")
    check(perform() == receipt and len(calls) == 2 and len(payments.refunds) == 1,
          "completed not-applied retry repeated a refund call or effect")


def _rollback(f: Any, *, lost_acknowledgement: bool) -> None:
    service, stock, payments, shipping, orders, events = P.rig(f, split=True)
    calls = _refund_calls(payments)
    checkout = lambda: service.checkout(request(f, key="split-save-rollback"))
    orders.fail_save = True
    payments.fail_after_refund = lost_acknowledgement
    try:
        checkout()
    except Exception:
        pass
    else:
        raise AssertionError("injected order-store failure was swallowed")
    check(len(payments.captures) == 1, "failed split checkout did not capture once")
    check(len(calls) == 1, "failed split checkout did not attempt one refund")
    check(len(payments.refunds) == 1 and
          sum(payments.refunded.values(), Decimal("0.00")) == Decimal("36.00"),
          "failed split checkout did not apply exactly one £36 refund")
    check(not orders.orders and not events.events and not orders.pending_events(),
          "failed split checkout committed an order or completion event")
    if not lost_acknowledgement:
        check(not active_shipments(shipping),
              "known-status split rollback left an active old shipment")
        check(quantity(stock, "north", "widget") == 2 and
              quantity(stock, "south", "widget") == 2,
              "known-status split rollback did not restore source stock")
    # An applied refund with lost acknowledgement may hold stock and postpone
    # carrier cancellation until the permitted same-ID retry.
    orders.fail_save = False
    payments.fail_after_refund = False
    try:
        result = checkout()
    except Exception as error:
        raise AssertionError(
            f"same-ID retry could not resolve split rollback: {type(error).__name__}: {error}"
        ) from error
    check(len(result.shipments) == 2 and len(active_shipments(shipping)) == 2,
          "same-ID retry did not produce exactly two active new shipments")
    check({s.shipment_id for s in active_shipments(shipping)} ==
          {s.shipment_id for s in result.shipments},
          "same-ID retry retained an orphan shipment from the failed attempt")
    check(quantity(stock, "north", "widget") == 0 and
          quantity(stock, "south", "widget") == 1,
          "same-ID retry did not restore then reserve original source stock")
    check(len(calls) == 1 and len(payments.refunds) == 1 and
          sum(payments.refunded.values(), Decimal("0.00")) == Decimal("36.00"),
          "same-ID retry repeated rollback refund call or effect")
    check(len(payments.captures) == 2 and len(orders.orders) == 1 and
          len(events.events) == 1 and
          sum(e.name == "OrderDispatched" for e in events.events.values()) == 1,
          "same-ID retry did not make exactly one new capture, order and event")
    after = (tuple(calls), dict(payments.refunds), dict(payments.refunded),
             dict(payments.captures), dict(shipping.shipments), set(shipping.cancelled),
             quantity(stock, "north", "widget"), quantity(stock, "south", "widget"),
             dict(orders.orders), dict(events.events))
    check(checkout() == result, "completed same-ID checkout changed result")
    check((tuple(calls), dict(payments.refunds), dict(payments.refunded),
           dict(payments.captures), dict(shipping.shipments), set(shipping.cancelled),
           quantity(stock, "north", "widget"), quantity(stock, "south", "widget"),
           dict(orders.orders), dict(events.events)) == after,
          "completed same-ID checkout repeated a stock, carrier, payment or event effect")


def r_split_save_failure(f: Any) -> None:
    """Detect a cancellation-key collision without injecting payment failure."""
    _rollback(f, lost_acknowledgement=False)


def r_acknowledgement_loss_checkout_rollback(f: Any) -> None:
    _rollback(f, lost_acknowledgement=True)


def cases_for(family: str, stage: str) -> dict[str, Callable[[Any], None]]:
    cases = V3.cases_for(family, stage)
    if family == "R" and stage in ("C", "D"):
        cases["split_dispatch_save_failure"] = r_split_save_failure
    if family == "R" and stage == "D":
        del cases["unknown_refund_outcome"]
        cases["unknown_before_refund_request"] = r_unknown_before_request
        cases["applied_refund_status_unknown"] = r_applied_then_unknown
        cases["not_applied_refund_retry"] = r_not_applied_retry
        cases["checkout_rollback_acknowledgement_loss"] = r_acknowledgement_loss_checkout_rollback
    return cases


def assess(candidate: Path, family: str = "R", stage: str = "D") -> dict[str, Any]:
    """Assess one candidate in an isolated interpreter and return the JSON record."""
    if family not in {"R", "W"} or stage not in {"B", "C", "D"}:
        raise ValueError("family and stage must identify an available frozen case set")
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--candidate", str(candidate.resolve()),
         "--family", family, "--stage", stage],
        capture_output=True, text=True, check=True,
    )
    return json.loads(completed.stdout)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--family", required=True, choices=("R", "W"))
    parser.add_argument("--stage", required=True, choices=("B", "C", "D"))
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    cases = cases_for(args.family, args.stage)
    digest = source_digest(candidate)
    sys.path.insert(0, str(candidate))
    try:
        f = importlib.import_module("fulfilment")
    except BaseException as error:
        findings = {name: {"status": "invalid", "detail": f"candidate import failed: {type(error).__name__}: {error}"}
                    for name in cases}
    else:
        findings = {}
        for name, case in cases.items():
            try:
                case(f)
            except BaseException as error:
                findings[name] = {"status": "fail", "detail": f"{type(error).__name__}: {error}"}
            else:
                findings[name] = {"status": "pass", "detail": "independent probe passed"}
    print(json.dumps({
        "schema_version": "architecture-extension-v4/assessor/1",
        "family": args.family, "stage": args.stage,
        "source_sha256": digest,
        "source_digest_recipe": "sorted relative Python paths and ARCHITECTURE.md; path UTF-8,NUL,SHA-256 hex,LF",
        "findings": findings,
        "passed": sum(x["status"] == "pass" for x in findings.values()),
        "failed": sum(x["status"] == "fail" for x in findings.values()),
        "invalid": sum(x["status"] == "invalid" for x in findings.values()),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
