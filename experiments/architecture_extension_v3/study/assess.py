"""Independent, host-only behavioural assessor for both frozen task families.

Run in a fresh Python process for one immutable candidate. No assessor code,
future requirement, or result belongs in an agent's coding worktree.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable


def source_digest(candidate: Path) -> str:
    """SHA-256 of sorted relative path, NUL, file SHA-256, LF records.

    Include every Python source/test file and ARCHITECTURE.md. Runtime caches,
    environment packets and requirement briefs do not enter this source digest.
    """
    paths = sorted(
        (p for p in candidate.rglob("*.py") if
         not any(part in {"__pycache__", ".venv", ".pytest_cache"} for part in p.relative_to(candidate).parts)),
        key=lambda p: p.relative_to(candidate).as_posix(),
    )
    architecture = candidate / "ARCHITECTURE.md"
    if architecture.is_file():
        paths.append(architecture)
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.relative_to(candidate).as_posix()):
        digest.update(path.relative_to(candidate).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def load_v2_probes() -> Any:
    path = Path(__file__).resolve().parents[2] / "architecture_extension_v2/materials/assessor/probe.py"
    spec = importlib.util.spec_from_file_location("frozen_v2_assessor", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load frozen A assessor at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P = load_v2_probes()
check = P.check
quantity = P.quantity
request = P.request
active_shipments = P.active_shipments


def rig_three(f: Any) -> tuple[Any, Any, Any, Any, Any, Any]:
    pricing = f.InMemoryPricing({"widget": Decimal("10.00")})
    stock = f.InMemoryStock(
        {"north": {"widget": 2}, "south": {"widget": 2}, "east": {"widget": 3}},
        priorities=("north", "south", "east"),
    )
    payments, shipping = f.InMemoryPayments(), f.InMemoryShipping()
    orders, events = f.InMemoryOrderStore(), f.InMemoryEventSink()
    service = f.CheckoutService(pricing, stock, payments, shipping, orders, events)
    return service, stock, payments, shipping, orders, events


def north_south_lines(f: Any, order: Any, north_count: int = 1) -> tuple[Any, ...]:
    by_wh = {shipment.warehouse_id: shipment for shipment in order.shipments}
    return (f.ReturnLine(by_wh["north"].shipment_id, "widget", north_count),
            f.ReturnLine(by_wh["south"].shipment_id, "widget", 1))


def r_cancel_after_return(f: Any) -> None:
    service, stock, payments, shipping, orders, events = P.rig(f, split=True)
    order = service.checkout(request(f))
    north = north_south_lines(f, order)[0]
    service.return_items(order.request_id, "return-first", (north,))
    receipt = service.cancel_order(order.request_id, "cancel-first")
    check(receipt.cancellation_request_id == "cancel-first", "cancellation receipt ID differs")
    check(receipt.refunded_amount == Decimal("24.00"), "cancellation did not refund only unreturned units")
    check(payments.refunded[order.charge.charge_id] == Decimal("36.00"), "refund total differs from capture")
    check(quantity(stock, "north", "widget") == 2 and quantity(stock, "south", "widget") == 2,
          "cancellation and prior return did not restore original source stock exactly once")
    check(not active_shipments(shipping), "cancellation left active shipment")
    check(orders.get(order.request_id).shipments == order.shipments, "original order history was overwritten")
    check(any(e.name == "OrderCancelled" and "cancel-first" in P.event_text(e) and
              "24.00" in P.event_text(e) for e in events.events.values()),
          "completed cancellation event missing its ID or amount")


def r_cancel_idempotency_and_rejection(f: Any) -> None:
    service, stock, payments, shipping, orders, events = P.rig(f, split=True)
    order = service.checkout(request(f))
    before = (dict(payments.refunds), dict(shipping.shipments), dict(events.events))
    try:
        service.cancel_order("absent", "cancel-absent")
    except Exception:
        pass
    else:
        raise AssertionError("unknown order cancelled")
    check((dict(payments.refunds), dict(shipping.shipments), dict(events.events)) == before,
          "unknown-order rejection made an effect")
    receipt = service.cancel_order(order.request_id, "cancel-once")
    effects = (dict(payments.refunds), set(shipping.cancelled), dict(events.events),
               quantity(stock, "north", "widget"), quantity(stock, "south", "widget"))
    check(service.cancel_order(order.request_id, "cancel-once") == receipt,
          "same cancellation key did not return receipt")
    check((dict(payments.refunds), set(shipping.cancelled), dict(events.events),
           quantity(stock, "north", "widget"), quantity(stock, "south", "widget")) == effects,
          "cancellation retry repeated an effect")
    for action in (lambda: service.cancel_order(order.request_id, "cancel-twice"),
                   lambda: service.return_items(order.request_id, "late-return", north_south_lines(f, order)[:1])):
        try:
            action()
        except Exception:
            pass
        else:
            raise AssertionError("completed cancellation accepted new cancellation or return")
    check((dict(payments.refunds), set(shipping.cancelled), dict(events.events),
           quantity(stock, "north", "widget"), quantity(stock, "south", "widget")) == effects,
          "rejected post-cancellation request made an effect")


def r_partial_cancel_retry(f: Any) -> None:
    service, stock, payments, shipping, orders, events = P.rig(f, split=True)
    order = service.checkout(request(f))
    shipping.fail_on_cancel_number = 2
    try:
        provisional = service.cancel_order(order.request_id, "cancel-retry")
    except Exception:
        pass
    else:
        check(getattr(provisional, "status", None) in {"pending", "unresolved"},
              "injected second carrier failure was treated as completed")
    check(not any(e.name == "OrderCancelled" for e in events.events.values()),
          "incomplete cancellation event was published")
    check(len(shipping.cancelled) == 1, "first carrier cancellation was not retained")
    shipping.fail_on_cancel_number = None
    receipt = service.cancel_order(order.request_id, "cancel-retry")
    check(receipt.refunded_amount == Decimal("36.00"), "retry did not settle the outstanding refund")
    check(len(shipping.cancelled) == 2 and not active_shipments(shipping),
          "retry did not complete carrier cancellation")
    check(len(payments.refunds) == 1 and quantity(stock, "north", "widget") == 2 and
          quantity(stock, "south", "widget") == 2, "retry repeated refund or stock restoration")
    check(sum(e.name == "OrderCancelled" for e in events.events.values()) == 1,
          "retry did not publish exactly one completed cancellation")


def r_cancel_event_retry(f: Any) -> None:
    service, stock, payments, shipping, orders, events = P.rig(f, split=True)
    order = service.checkout(request(f))
    events.fail_publish = True
    receipt = service.cancel_order(order.request_id, "cancel-event")
    check(any(e.name == "OrderCancelled" for e in orders.pending_events()),
          "publication failure lost cancellation event")
    effects = (dict(payments.refunds), set(shipping.cancelled),
               quantity(stock, "north", "widget"), quantity(stock, "south", "widget"))
    events.fail_publish = False
    check(service.retry_events() >= 1, "cancellation event could not be retried")
    check(service.cancel_order(order.request_id, "cancel-event") == receipt, "replayed cancellation changed receipt")
    check((dict(payments.refunds), set(shipping.cancelled),
           quantity(stock, "north", "widget"), quantity(stock, "south", "widget")) == effects,
          "event retry repeated a payment, carrier or stock effect")


def r_acknowledgement_loss_return(f: Any) -> None:
    service, stock, payments, shipping, orders, events = P.rig(f, split=True)
    order = service.checkout(request(f))
    north = north_south_lines(f, order)[0]
    payments.fail_after_refund = True
    try:
        service.return_items(order.request_id, "lost-ack-return", (north,))
    except Exception:
        pass  # A service may surface the loss or reconcile it immediately.
    check(len(payments.refunds) == 1 and payments.refunded[order.charge.charge_id] == Decimal("12.00"),
          "provider did not apply the single refund before acknowledgement loss")
    payments.fail_after_refund = False
    receipt = service.return_items(order.request_id, "lost-ack-return", (north,))
    check(receipt.refunded_amount == Decimal("12.00"), "return could not reconcile applied refund")
    check(len(payments.refunds) == 1 and quantity(stock, "north", "widget") == 1,
          "reconciled return repeated refund or stock restoration")
    check(sum(e.name.lower().find("return") >= 0 for e in events.events.values()) == 1,
          "reconciled return event was not emitted once")


def r_acknowledgement_loss_cancel(f: Any) -> None:
    service, stock, payments, shipping, orders, events = P.rig(f, split=True)
    order = service.checkout(request(f))
    payments.fail_after_refund = True
    try:
        service.cancel_order(order.request_id, "lost-ack-cancel")
    except Exception:
        pass  # Immediate reconciliation is also allowed.
    check(len(payments.refunds) == 1 and payments.refunded[order.charge.charge_id] == Decimal("36.00"),
          "provider did not apply exactly one whole-order refund")
    payments.fail_after_refund = False
    receipt = service.cancel_order(order.request_id, "lost-ack-cancel")
    check(receipt.refunded_amount == Decimal("36.00") and len(payments.refunds) == 1,
          "cancellation retry did not reconcile one applied refund")
    check(quantity(stock, "north", "widget") == 2 and quantity(stock, "south", "widget") == 2,
          "cancellation retry restored source stock incorrectly")
    check(sum(e.name == "OrderCancelled" for e in events.events.values()) == 1,
          "cancellation retry emitted wrong number of events")


def r_acknowledgement_loss_checkout_rollback(f: Any) -> None:
    service, stock, payments, shipping, orders, events = P.rig(f, split=True)
    orders.fail_save = True
    payments.fail_after_refund = True
    try:
        service.checkout(request(f, key="save-ack-loss"))
    except Exception:
        pass
    else:
        raise AssertionError("order-store failure was swallowed")
    check(len(payments.refunds) == 1 and
          sum(payments.refunded.values(), Decimal("0.00")) == Decimal("36.00"),
          "rollback acknowledgement loss did not apply one refund")
    check(quantity(stock, "north", "widget") == 2 and quantity(stock, "south", "widget") == 2,
          "rollback acknowledgement loss retained stock")
    check(not active_shipments(shipping) and not orders.orders and not events.events,
          "rollback acknowledgement loss committed shipment, order or event")
    orders.fail_save = False
    payments.fail_after_refund = False
    check(len(service.checkout(request(f, key="save-ack-loss")).shipments) == 2,
          "reconciled rollback could not retry")
    check(len(payments.refunds) == 1, "retry issued a second rollback refund")


def r_unknown_outcome(f: Any) -> None:
    service, stock, payments, shipping, orders, events = P.rig(f, split=True)
    order = service.checkout(request(f))
    north = north_south_lines(f, order)[0]
    original_status = payments.refund_status
    payments.refund_status = lambda key: "unknown"
    payments.fail_after_refund = True
    for attempt in range(2):
        try:
            provisional = service.return_items(order.request_id, "unknown-refund", (north,))
        except Exception:
            pass
        else:
            check(getattr(provisional, "status", None) in {"pending", "unresolved", "unknown"},
                  f"unknown provider outcome treated as complete on attempt {attempt}")
    check(len(payments.refunds) == 1 and quantity(stock, "north", "widget") == 0,
          "unknown outcome repeated financial effect or restored stock early")
    check(not any("unknown-refund" in P.event_text(e) for e in events.events.values()),
          "unknown outcome published completion")
    payments.refund_status = original_status
    payments.fail_after_refund = False
    service.return_items(order.request_id, "unknown-refund", (north,))
    check(len(payments.refunds) == 1 and quantity(stock, "north", "widget") == 1,
          "resolved status did not complete exactly once")


def w_closed_warehouse(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig_three(f)
    stock.set_warehouse_open("north", False)
    order = service.checkout(request(f))
    allocation = {(a.warehouse_id, a.quantity) for a in order.allocations}
    check(allocation == {("south", 2), ("east", 1)}, "closed warehouse contributed stock")
    check(quantity(stock, "north", "widget") == 2 and quantity(stock, "south", "widget") == 0 and
          quantity(stock, "east", "widget") == 2, "stock changed at wrong warehouse")
    check(len(payments.captures) == 1 and len(order.shipments) == 2,
          "available depots did not produce one charge and two shipments")
    described = P.event_text(next(e for e in events.events.values() if e.order_id == order.order_id))
    check("south" in described and "east" in described and "north" not in described,
          "final event does not describe actual available depots")


def w_closed_shortage_and_reopen(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig_three(f)
    stock.set_warehouse_open("north", False)
    stock.set_warehouse_open("south", False)
    try:
        service.checkout(request(f, count=4))
    except Exception:
        pass
    else:
        raise AssertionError("insufficient open stock was accepted")
    check((quantity(stock, "north", "widget"), quantity(stock, "south", "widget"),
           quantity(stock, "east", "widget")) == (2, 2, 3), "shortage altered stock")
    check(not payments.captures and not shipping.shipments and not orders.orders and not events.events,
          "shortage produced external effects")
    stock.set_warehouse_open("north", True)
    order = service.checkout(request(f, count=4))
    check({a.warehouse_id for a in order.allocations} == {"north", "east"},
          "reopened warehouse did not participate in new reservation")
    try:
        stock.set_warehouse_open("absent", True)
    except Exception:
        pass
    else:
        raise AssertionError("unknown warehouse availability accepted")


def w_history_stability(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig_three(f)
    order = service.checkout(request(f))
    old = (order.allocations, order.shipments, orders.get(order.request_id))
    stock.set_warehouse_open("north", False)
    check((order.allocations, order.shipments, orders.get(order.request_id)) == old,
          "availability update rewrote a completed order")
    check(service.checkout(request(f)) == order and len(payments.captures) == 1,
          "availability update changed completed-request idempotency")


def w_carrier_substitution(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig_three(f)
    shipping.reject_warehouses.add("north")
    order = service.checkout(request(f))
    check({(a.warehouse_id, a.quantity) for a in order.allocations} ==
          {("south", 2), ("east", 1)}, "carrier rejection did not substitute priority warehouses")
    check(quantity(stock, "north", "widget") == 2 and quantity(stock, "south", "widget") == 0 and
          quantity(stock, "east", "widget") == 2, "rejected allocation was not restored or substitute stock wrong")
    check(len(payments.captures) == 1 and len(payments.refunds) == 0,
          "successful substitution issued more than one charge or a refund")
    check({s.warehouse_id for s in active_shipments(shipping)} == {"south", "east"},
          "carrier left a rejected or missing active shipment")
    event = next(e for e in events.events.values() if e.order_id == order.order_id)
    check("south" in P.event_text(event) and "east" in P.event_text(event) and
          "north" not in P.event_text(event), "event contains rejected rather than final allocation")


def w_carrier_no_alternative(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig_three(f)
    stock.set_warehouse_open("east", False)
    shipping.reject_warehouses.add("north")
    try:
        service.checkout(request(f))
    except Exception:
        pass
    else:
        raise AssertionError("rejection without alternative was accepted")
    check((quantity(stock, "north", "widget"), quantity(stock, "south", "widget"),
           quantity(stock, "east", "widget")) == (2, 2, 3), "failed substitution leaked stock")
    check(not active_shipments(shipping) and not orders.orders and not events.events and
          not orders.pending_events(), "failed substitution left order, shipment or event")
    check(len(payments.captures) == len(payments.refunds), "failed substitution retained charge")
    shipping.reject_warehouses.clear()
    check(len(service.checkout(request(f)).shipments) == 2, "compensated request cannot retry")


def w_substitution_retry(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig_three(f)
    shipping.reject_warehouses.add("north")
    events.fail_publish = True
    order = service.checkout(request(f))
    before = (len(payments.captures), len(shipping.dispatches),
              quantity(stock, "south", "widget"), quantity(stock, "east", "widget"))
    events.fail_publish = False
    check(service.retry_events() == 1 and service.checkout(request(f)) == order,
          "substituted order event retry failed")
    check((len(payments.captures), len(shipping.dispatches),
           quantity(stock, "south", "widget"), quantity(stock, "east", "widget")) == before,
          "event retry repeated payment, shipment or stock effect")


def w_bounded_delivery(f: Any) -> None:
    pricing = f.InMemoryPricing({"widget": Decimal("10.00")})
    stock = f.InMemoryStock({"north": {"widget": 20}, "south": {"widget": 20}},
                            priorities=("north", "south"))
    payments, shipping = f.InMemoryPayments(), f.InMemoryShipping()
    orders, events = f.InMemoryOrderStore(), f.InMemoryEventSink()
    service = f.CheckoutService(pricing, stock, payments, shipping, orders, events)
    events.fail_publish = True
    made = [service.checkout(request(f, key=f"order-{n}", count=1)) for n in range(5)]
    expected = [order.order_id for order in made]
    check(len(orders.pending_events()) == 5 and not events.events,
          "publication failure did not retain five ordered events")
    before = (len(payments.captures), len(shipping.dispatches), quantity(stock, "north", "widget"))
    events.fail_publish = False
    check([service.retry_events(max_events=2) for _ in range(4)] == [2, 2, 1, 0],
          "bounded deliveries differ from 2,2,1,0")
    check([e.order_id for e in events.events.values()] == expected,
          "outbox delivered events out of order or twice")
    check((len(payments.captures), len(shipping.dispatches), quantity(stock, "north", "widget")) == before,
          "delivery retry repeated fulfilment")


def w_invalid_limit_and_failure(f: Any) -> None:
    service, stock, payments, shipping, orders, events = rig_three(f)
    events.fail_publish = True
    order = service.checkout(request(f))
    pending = tuple(orders.pending_events())
    for invalid in (0, -1, 1.2, "2", True):
        try:
            service.retry_events(max_events=invalid)
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"invalid max_events={invalid!r} accepted")
        check(tuple(orders.pending_events()) == pending and not events.events,
              "invalid limit published or acknowledged an event")
    check(service.retry_events(max_events=2) == 0, "failed publication reported success")
    check(tuple(orders.pending_events()) == pending, "failed event was lost")
    events.fail_publish = False
    check(service.retry_events() == 1 and len(events.events) == 1 and
          next(iter(events.events.values())).order_id == order.order_id,
          "healthy retry did not publish retained event")


R_C = {"cancel_after_return": r_cancel_after_return,
       "cancel_idempotency_and_rejection": r_cancel_idempotency_and_rejection,
       "cancel_partial_carrier_failure_retry": r_partial_cancel_retry,
       "cancel_event_retry": r_cancel_event_retry}
R_D = {"return_acknowledgement_loss": r_acknowledgement_loss_return,
       "cancel_acknowledgement_loss": r_acknowledgement_loss_cancel,
       "checkout_rollback_acknowledgement_loss": r_acknowledgement_loss_checkout_rollback,
       "unknown_refund_outcome": r_unknown_outcome}
W_B = {"closed_warehouse_priority": w_closed_warehouse,
       "closed_shortage_and_reopen": w_closed_shortage_and_reopen,
       "completed_order_stability": w_history_stability}
W_C = {"carrier_substitution": w_carrier_substitution,
       "carrier_no_alternative": w_carrier_no_alternative,
       "substitution_event_retry": w_substitution_retry}
W_D = {"bounded_delivery": w_bounded_delivery,
       "invalid_limit_and_failure": w_invalid_limit_and_failure}


def cases_for(family: str, stage: str) -> dict[str, Callable[[Any], None]]:
    cases: dict[str, Callable[[Any], None]] = dict(P.BASELINE)
    cases.update(P.A)
    if family == "R":
        cases.update(P.B)
        if stage in ("C", "D"):
            cases.update(R_C)
        if stage == "D":
            cases.update(R_D)
    else:
        cases.update(W_B)
        if stage in ("C", "D"):
            cases.update(W_C)
        if stage == "D":
            cases.update(W_D)
    return cases


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
    findings: dict[str, dict[str, str]] = {}
    try:
        f = importlib.import_module("fulfilment")
    except BaseException as error:
        findings = {name: {"status": "invalid", "detail": f"candidate import failed: {type(error).__name__}: {error}"}
                    for name in cases}
    else:
        for name, case in cases.items():
            try:
                case(f)
            except BaseException as error:
                findings[name] = {"status": "fail", "detail": f"{type(error).__name__}: {error}"}
            else:
                findings[name] = {"status": "pass", "detail": "independent probe passed"}
    print(json.dumps({
        "schema_version": "architecture-extension-v3/assessor/1",
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
