"""Independent black-box checks for the frozen fulfilment study.

The candidate package is imported in a fresh subprocess.  Each case constructs
new in-memory ports.  A failed probe is retained as a failed finding; no
candidate test is used as the oracle.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def request(f: Any, key: str = "order-1", count: int = 3) -> Any:
    return f.CheckoutRequest(
        key, "customer-1", (f.RequestedLine("widget", count),),
        "1 Market Road", "test-payment-token",
    )


def rig(f: Any, *, split: bool = False) -> tuple[Any, Any, Any, Any, Any, Any]:
    pricing = f.InMemoryPricing({"widget": Decimal("10.00")})
    if split:
        stock = f.InMemoryStock(
            {"north": {"widget": 2}, "south": {"widget": 2}},
            priorities=("north", "south"),
        )
    else:
        stock = f.InMemoryStock({"widget": 4})
    payments = f.InMemoryPayments()
    shipping = f.InMemoryShipping()
    orders = f.InMemoryOrderStore()
    events = f.InMemoryEventSink()
    service = f.CheckoutService(pricing, stock, payments, shipping, orders, events)
    return service, stock, payments, shipping, orders, events


def quantity(stock: Any, warehouse: str, sku: str) -> int:
    value = stock.on_hand
    if warehouse in value and isinstance(value[warehouse], dict):
        return value[warehouse].get(sku, 0)
    check(getattr(stock, "warehouse_id", "main") == warehouse, "warehouse stock is not addressable")
    return value.get(sku, 0)


def active_shipments(shipping: Any) -> list[Any]:
    return [
        shipment for shipment_id, shipment in shipping.shipments.items()
        if shipment_id not in shipping.cancelled
    ]


def event_text(event: Any) -> str:
    return json.dumps(
        {"name": event.name, "order_id": event.order_id, "data": event.data},
        sort_keys=True, default=str,
    )


def baseline_success(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig(f)
    order = service.checkout(request(f, count=2))
    check(order.quote.total == Decimal("24.00"), "quoted total differs from unit price plus tax")
    check(len(order.shipments) == 1, "single warehouse should produce one shipment")
    check(tuple((a.sku, a.quantity, a.warehouse_id) for a in order.shipments[0].allocations)
          == (("widget", 2, "main"),), "shipment has wrong source allocation")
    check(quantity(stock, "main", "widget") == 2, "reserved stock is wrong")
    check(len(payments.captures) == 1 and len(shipping.dispatches) == 1,
          "checkout repeated a payment capture or dispatch")
    check(len(orders.orders) == 1 and len(events.events) == 1, "order/event missing")
    check(order.order_id in event_text(next(iter(events.events.values()))), "event does not identify order")


def baseline_idempotency(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig(f)
    first = service.checkout(request(f, count=2))
    check(service.checkout(request(f, count=2)) == first, "same key did not return original order")
    check((quantity(stock, "main", "widget"), len(payments.captures),
           len(shipping.dispatches), len(events.events)) == (2, 1, 1, 1),
          "same key repeated an external effect")
    try:
        service.checkout(request(f, count=1))
    except f.IdempotencyConflict:
        pass
    else:
        raise AssertionError("changed request accepted with reused key")
    check(len(orders.orders) == 1, "conflicting retry changed order history")


def baseline_failure(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig(f)
    try:
        service.checkout(request(f, count=5))
    except f.OutOfStock:
        pass
    else:
        raise AssertionError("insufficient stock was accepted")
    check(quantity(stock, "main", "widget") == 4, "failed order changed stock")
    check(not payments.captures and not shipping.shipments and not orders.orders and not events.events,
          "failed order produced an external effect")
    payments.fail_capture = True
    try:
        service.checkout(request(f, key="payment-fail", count=2))
    except RuntimeError:
        pass
    else:
        raise AssertionError("payment failure was swallowed")
    check(quantity(stock, "main", "widget") == 4 and not orders.orders,
          "failed capture left reserved stock or an order")
    payments.fail_capture = False
    check(service.checkout(request(f, key="payment-fail", count=2)).status == "dispatched",
          "compensated order cannot be retried")


def baseline_event_retry(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig(f)
    events.fail_publish = True
    original = service.checkout(request(f, count=2))
    check(not events.events and len(orders.pending_events()) == 1,
          "transient event failure did not retain a pending event")
    snapshot = (quantity(stock, "main", "widget"), len(payments.captures), len(shipping.dispatches))
    events.fail_publish = False
    check(service.retry_events() == 1 and len(events.events) == 1, "pending event did not publish once")
    check(service.checkout(request(f, count=2)) == original, "retry did not recover original order")
    check((quantity(stock, "main", "widget"), len(payments.captures), len(shipping.dispatches))
          == snapshot, "event retry repeated fulfilment")


def baseline_save_failure(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig(f)
    orders.fail_save = True
    try:
        service.checkout(request(f, key="save-fail", count=2))
    except RuntimeError:
        pass
    else:
        raise AssertionError("order-store failure was swallowed")
    check(quantity(stock, "main", "widget") == 4, "failed save retained reserved stock")
    check(not active_shipments(shipping), "failed save left an active shipment")
    check(len(payments.refunds) == 1 and not orders.orders and not events.events,
          "failed save was not financially compensated or incorrectly published")
    orders.fail_save = False
    check(service.checkout(request(f, key="save-fail", count=2)).status == "dispatched",
          "compensated save failure cannot retry")


def split_priority_and_event(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig(f, split=True)
    order = service.checkout(request(f))
    expected = {("north", "widget", 2), ("south", "widget", 1)}
    actual = {
        (allocation.warehouse_id, allocation.sku, allocation.quantity)
        for shipment in order.shipments for allocation in shipment.allocations
    }
    check(actual == expected and len(order.shipments) == 2, "split allocations differ from priority order")
    check({tuple(a.warehouse_id for a in shipment.allocations) for shipment in order.shipments}
          == {("north",), ("south",)}, "a shipment spans warehouses")
    check(quantity(stock, "north", "widget") == 0 and quantity(stock, "south", "widget") == 1,
          "stock was not reserved at its source warehouse")
    check(len(payments.captures) == 1 and len(active_shipments(shipping)) == 2,
          "split order did not charge once and dispatch twice")
    check(len(orders.orders) == 1 and len(events.events) == 1, "split order/event not recorded")
    described = event_text(next(iter(events.events.values())))
    for marker in ("north", "south", "widget"):
        check(marker in described, f"final event omitted {marker}")
    for shipment in order.shipments:
        check(shipment.shipment_id in described, "final event omitted actual shipment ID")


def split_insufficient(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig(f, split=True)
    try:
        service.checkout(request(f, count=5))
    except f.OutOfStock:
        pass
    else:
        raise AssertionError("insufficient aggregate stock was accepted")
    check(quantity(stock, "north", "widget") == 2 and quantity(stock, "south", "widget") == 2,
          "aggregate failure modified warehouse stock")
    check(not payments.captures and not shipping.shipments and not orders.orders and not events.events,
          "aggregate failure produced effects")


def split_later_dispatch_failure(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig(f, split=True)
    shipping.fail_on_shipment_number = 2
    try:
        service.checkout(request(f))
    except Exception:
        pass
    else:
        raise AssertionError("injected second shipment failure was swallowed")
    check(not active_shipments(shipping), "first shipment remains active after second failed")
    check(quantity(stock, "north", "widget") == 2 and quantity(stock, "south", "widget") == 2,
          "failed split dispatch did not release all stock")
    check(len(payments.captures) == 1 and len(payments.refunds) == 1,
          "failed split dispatch did not capture and refund exactly once")
    check(not orders.orders and not events.events and not orders.pending_events(),
          "failed split dispatch committed an order or event")
    shipping.fail_on_shipment_number = None
    check(len(service.checkout(request(f)).shipments) == 2, "compensated split order could not retry")


def split_idempotency(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig(f, split=True)
    original = service.checkout(request(f))
    totals = (quantity(stock, "north", "widget"), quantity(stock, "south", "widget"),
              len(payments.captures), len(shipping.dispatches), len(events.events))
    check(service.checkout(request(f)) == original, "same split request did not return original")
    check((quantity(stock, "north", "widget"), quantity(stock, "south", "widget"),
           len(payments.captures), len(shipping.dispatches), len(events.events)) == totals,
          "split retry repeated effects")
    try:
        service.checkout(request(f, count=2))
    except f.IdempotencyConflict:
        pass
    else:
        raise AssertionError("split request key reused with changed content")


def split_event_retry(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig(f, split=True)
    events.fail_publish = True
    original = service.checkout(request(f))
    check(not events.events and len(orders.pending_events()) == 1, "split event was lost")
    effects = (len(payments.captures), len(shipping.dispatches),
               quantity(stock, "north", "widget"), quantity(stock, "south", "widget"))
    events.fail_publish = False
    check(service.retry_events() == 1, "split event not published on retry")
    check(service.checkout(request(f)) == original, "split event retry changed order")
    check((len(payments.captures), len(shipping.dispatches),
           quantity(stock, "north", "widget"), quantity(stock, "south", "widget")) == effects,
          "split event retry repeated fulfilment")


def return_lines(f: Any, order: Any) -> tuple[Any, ...]:
    by_warehouse = {
        allocation.warehouse_id: (shipment.shipment_id, allocation)
        for shipment in order.shipments for allocation in shipment.allocations
    }
    return (
        f.ReturnLine(by_warehouse["north"][0], "widget", 1),
        f.ReturnLine(by_warehouse["south"][0], "widget", 1),
    )


def partial_return(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig(f, split=True)
    order = service.checkout(request(f))
    lines = return_lines(f, order)
    receipt = service.return_items(order.request_id, "return-1", lines)
    check(receipt.return_request_id == "return-1", "receipt has wrong return request ID")
    check(receipt.refunded_amount == Decimal("24.00"), "refund omits original unit tax/price")
    check(tuple(receipt.lines) == lines, "receipt has wrong accepted lines")
    check(quantity(stock, "north", "widget") == 1 and quantity(stock, "south", "widget") == 2,
          "returned units did not restore their source warehouse")
    check(payments.refunded[order.charge.charge_id] == Decimal("24.00"),
          "payment refund differs from receipt")
    history = orders.get(order.request_id)
    check(history is not None, "original order history was lost")
    check((history.order_id, history.request_id, history.quote, history.reservation,
           history.charge, history.shipments)
          == (order.order_id, order.request_id, order.quote, order.reservation,
              order.charge, order.shipments),
          "original price, allocation, payment or shipment history was replaced")
    described = [event_text(e) for e in events.events.values()]
    check(any("return-1" in event and "24.00" in event and "north" in event and "south" in event
              for event in described), "return event lacks ID, amount or source allocations")
    north = lines[0]
    second = service.return_items(order.request_id, "return-2", (north,))
    check(second.refunded_amount == Decimal("12.00"), "later eligible north unit cannot return")


def return_rejection(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig(f, split=True)
    order = service.checkout(request(f))
    north, south = return_lines(f, order)
    cases = (
        ("missing-order", "unknown-order", lambda: (north,)),
        ("missing-shipment", order.request_id,
         lambda: (f.ReturnLine("unknown-shipment", "widget", 1),)),
        ("wrong-sku", order.request_id,
         lambda: (f.ReturnLine(north.shipment_id, "wrong", 1),)),
        ("zero", order.request_id,
         lambda: (f.ReturnLine(north.shipment_id, "widget", 0),)),
        ("over", order.request_id,
         lambda: (f.ReturnLine(south.shipment_id, "widget", 2),)),
    )
    for key, order_id, make_lines in cases:
        before = (quantity(stock, "north", "widget"), quantity(stock, "south", "widget"),
                  dict(payments.refunds), dict(events.events))
        try:
            service.return_items(order_id, key, make_lines())
        except Exception:
            pass
        else:
            raise AssertionError(f"{key} return was accepted")
        after = (quantity(stock, "north", "widget"), quantity(stock, "south", "widget"),
                 dict(payments.refunds), dict(events.events))
        check(after == before, f"{key} rejection changed stock, payment or events")
    service.return_items(order.request_id, "accepted", (north,))
    before = (quantity(stock, "north", "widget"), len(payments.refunds), len(events.events))
    try:
        service.return_items(order.request_id, "over-after", (f.ReturnLine(north.shipment_id, "widget", 2),))
    except Exception:
        pass
    else:
        raise AssertionError("cumulative over-return was accepted")
    check((quantity(stock, "north", "widget"), len(payments.refunds), len(events.events)) == before,
          "cumulative over-return had side effects")


def return_idempotency(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig(f, split=True)
    order = service.checkout(request(f))
    lines = return_lines(f, order)
    first = service.return_items(order.request_id, "return-1", lines)
    effects = (quantity(stock, "north", "widget"), quantity(stock, "south", "widget"),
               len(payments.refunds), len(events.events))
    check(service.return_items(order.request_id, "return-1", lines) == first,
          "return retry did not return original receipt")
    check((quantity(stock, "north", "widget"), quantity(stock, "south", "widget"),
           len(payments.refunds), len(events.events)) == effects, "return retry repeated effects")
    try:
        service.return_items(order.request_id, "return-1", (lines[0],))
    except f.IdempotencyConflict:
        pass
    else:
        raise AssertionError("return key reused with changed content")
    check(len(payments.refunds) == effects[2], "conflicting return issued another refund")


def return_refund_failure(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig(f, split=True)
    order = service.checkout(request(f))
    lines = return_lines(f, order)
    payments.fail_refund = True
    before = (quantity(stock, "north", "widget"), quantity(stock, "south", "widget"), len(events.events))
    try:
        service.return_items(order.request_id, "return-1", lines)
    except RuntimeError:
        pass
    else:
        raise AssertionError("payment refund failure was swallowed")
    check((quantity(stock, "north", "widget"), quantity(stock, "south", "widget"), len(events.events))
          == before and not payments.refunds, "failed refund changed stock, record or events")
    payments.fail_refund = False
    check(service.return_items(order.request_id, "return-1", lines).refunded_amount
          == Decimal("24.00"), "failed refund cannot be retried")


def return_event_retry(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig(f, split=True)
    order = service.checkout(request(f))
    lines = return_lines(f, order)
    events.fail_publish = True
    original = service.return_items(order.request_id, "return-1", lines)
    check(len(orders.pending_events()) == 1 and len(events.events) == 1,
          "transient return event was not queued")
    effects = (len(payments.refunds), quantity(stock, "north", "widget"),
               quantity(stock, "south", "widget"))
    events.fail_publish = False
    check(service.retry_events() == 1, "return event not published on retry")
    check(service.return_items(order.request_id, "return-1", lines) == original,
          "return event retry changed receipt")
    check((len(payments.refunds), quantity(stock, "north", "widget"),
           quantity(stock, "south", "widget")) == effects, "event retry repeated refund or restock")


BASELINE = {
    "baseline_success": baseline_success,
    "baseline_idempotency": baseline_idempotency,
    "baseline_failure": baseline_failure,
    "baseline_event_retry": baseline_event_retry,
    "baseline_save_failure": baseline_save_failure,
}
A = {
    "split_priority_and_event": split_priority_and_event,
    "split_insufficient": split_insufficient,
    "split_later_dispatch_failure": split_later_dispatch_failure,
    "split_idempotency": split_idempotency,
    "split_event_retry": split_event_retry,
}
B = {
    "partial_return": partial_return,
    "return_rejection": return_rejection,
    "return_idempotency": return_idempotency,
    "return_refund_failure": return_refund_failure,
    "return_event_retry": return_event_retry,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--stage", choices=("baseline", "a", "b"), required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.candidate.resolve()))
    tests: dict[str, Callable[[Any], None]] = dict(BASELINE)
    if args.stage in ("a", "b"):
        tests.update(A)
    if args.stage == "b":
        tests.update(B)
    try:
        f = importlib.import_module("fulfilment")
    except BaseException as exc:
        print(json.dumps({"findings": {
            name: {"status": "invalid", "detail": f"candidate import failed: {type(exc).__name__}: {exc}"}
            for name in tests
        }}, sort_keys=True))
        return
    findings = {}
    case_effect_calls: dict[str, dict[str, int]] = {}
    calls: Counter[str] = Counter()
    package_root = (args.candidate.resolve() / "fulfilment")

    def record_call(frame: Any, event: str, unused: Any) -> None:
        if event != "call":
            return
        try:
            path = Path(frame.f_code.co_filename).resolve().relative_to(package_root)
        except ValueError:
            return
        calls[f"{path}:{frame.f_code.co_qualname}"] += 1

    sys.setprofile(record_call)
    for name, probe in tests.items():
        before = calls.copy()
        try:
            probe(f)
        except BaseException as exc:
            findings[name] = {"status": "fail", "detail": f"{type(exc).__name__}: {exc}"}
        else:
            findings[name] = {"status": "pass", "detail": "independent probe passed"}
        increments = calls - before
        case_effect_calls[name] = {
            qualname: count for qualname, count in increments.items()
            if qualname.rsplit(".", 1)[-1] in {
                "reserve", "release", "restore", "restock", "capture", "refund",
                "dispatch", "cancel", "publish", "save", "record_return",
            }
        }
    sys.setprofile(None)
    print(json.dumps({
        "findings": findings, "executed_functions": dict(calls),
        "case_effect_calls": case_effect_calls,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
