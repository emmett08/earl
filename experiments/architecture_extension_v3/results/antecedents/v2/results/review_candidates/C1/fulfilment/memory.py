"""Deterministic in-memory implementations for the independent experiment runs."""

from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal, ROUND_HALF_UP

from .domain import (
    CENT, Allocation, Charge, DispatchFailure, Event, IdempotencyConflict, Order, OutOfStock,
    Quote, QuotedLine, RequestedLine, Reservation, ReturnLine, ReturnReceipt, Shipment,
)


class InMemoryPricing:
    def __init__(self, prices: dict[str, Decimal], tax_rate: Decimal = Decimal("0.20")) -> None:
        if not Decimal("0") <= tax_rate <= Decimal("1"):
            raise ValueError("tax rate must be between zero and one")
        self.prices = dict(prices)
        self.tax_rate = tax_rate
        if any(price < 0 or price != price.quantize(CENT) for price in self.prices.values()):
            raise ValueError("prices must be nonnegative, whole-cent amounts")

    def quote(self, lines: tuple[RequestedLine, ...]) -> Quote:
        result = []
        for line in lines:
            unit_price = self.prices[line.sku]
            unit_tax = (unit_price * self.tax_rate).quantize(CENT, rounding=ROUND_HALF_UP)
            result.append(QuotedLine(
                line.sku, line.quantity, unit_price, unit_tax,
                unit_price * line.quantity, unit_tax * line.quantity,
            ))
        quoted = tuple(result)
        subtotal = sum((line.line_total for line in quoted), Decimal("0.00"))
        tax = sum((line.line_tax for line in quoted), Decimal("0.00"))
        return Quote(quoted, subtotal, tax, subtotal + tax, "GBP")


class InMemoryStock:
    def __init__(
        self,
        on_hand: dict[str, int] | dict[str, dict[str, int]],
        warehouse_id: str = "main",
        priorities: tuple[str, ...] | None = None,
    ) -> None:
        if not on_hand:
            raise ValueError("inventory needs at least one warehouse and SKU")
        first_value = next(iter(on_hand.values()))
        self.nested = isinstance(first_value, dict)
        if self.nested:
            if any(not isinstance(stock, dict) for stock in on_hand.values()):
                raise ValueError("warehouse inventory shapes cannot be mixed")
            nested = {name: dict(stock) for name, stock in on_hand.items()}
            selected = priorities or tuple(sorted(nested))
            if len(set(selected)) != len(selected) or set(selected) != set(nested):
                raise ValueError("priorities must list every warehouse exactly once")
            self.priorities = tuple(selected)
            self.warehouse_id = self.priorities[0]
            self.on_hand_by_warehouse = nested
            self.on_hand = nested
        else:
            if priorities not in (None, (warehouse_id,)):
                raise ValueError("flat inventory has one warehouse")
            self.priorities = (warehouse_id,)
            self.warehouse_id = warehouse_id
            self.on_hand = dict(on_hand)
            self.on_hand_by_warehouse = {warehouse_id: self.on_hand}
        if any(
            not name or any(type(n) is not int or n < 0 for n in stock.values())
            for name, stock in self.on_hand_by_warehouse.items()
        ):
            raise ValueError("stock needs named warehouses and nonnegative whole-unit counts")
        self.reservations: dict[str, Reservation] = {}
        self.reservation_lines: dict[str, tuple[RequestedLine, ...]] = {}
        self.fail_release = False
        self.fail_restore = False
        self.restorations: dict[str, tuple[Allocation, ...]] = {}

    def reserve(self, lines: tuple[RequestedLine, ...], key: str) -> Reservation:
        existing = self.reservations.get(key)
        if existing is not None:
            if tuple(lines) != self.reservation_lines[key]:
                raise IdempotencyConflict(key)
            return existing
        # Plan the entire reservation before changing any warehouse inventory.
        planned: dict[str, list[Allocation]] = {name: [] for name in self.priorities}
        for line in lines:
            remaining = line.quantity
            for name in self.priorities:
                available = self.on_hand_by_warehouse[name].get(line.sku, 0)
                taken = min(available, remaining)
                if taken:
                    planned[name].append(Allocation(line.sku, taken, name))
                    remaining -= taken
                if not remaining:
                    break
            if remaining:
                raise OutOfStock(line.sku)
        allocations = tuple(a for name in self.priorities for a in planned[name])
        reservation = Reservation(f"res:{key}", allocations)
        for allocation in allocations:
            self.on_hand_by_warehouse[allocation.warehouse_id][allocation.sku] -= allocation.quantity
        self.reservations[key] = reservation
        self.reservation_lines[key] = tuple(lines)
        return reservation

    def release(self, reservation: Reservation) -> None:
        if self.fail_release:
            raise RuntimeError("stock release failed")
        key = reservation.reservation_id.removeprefix("res:")
        held = self.reservations.get(key)
        if held is None:
            return
        if held != reservation:
            raise IdempotencyConflict(reservation.reservation_id)
        for allocation in reservation.allocations:
            warehouse = self.on_hand_by_warehouse[allocation.warehouse_id]
            warehouse[allocation.sku] += allocation.quantity
        del self.reservations[key]
        del self.reservation_lines[key]

    def restore(self, allocations: tuple[Allocation, ...], key: str) -> None:
        previous = self.restorations.get(key)
        if previous is not None:
            if previous != allocations:
                raise IdempotencyConflict(key)
            return
        if self.fail_restore:
            raise RuntimeError("stock restoration failed")
        if any(a.warehouse_id not in self.on_hand_by_warehouse or a.quantity <= 0
               or a.sku not in self.on_hand_by_warehouse[a.warehouse_id] for a in allocations):
            raise ValueError("unknown stock allocation")
        for allocation in allocations:
            warehouse = self.on_hand_by_warehouse[allocation.warehouse_id]
            warehouse[allocation.sku] += allocation.quantity
        self.restorations[key] = allocations


class InMemoryPayments:
    def __init__(self) -> None:
        self.charges: dict[str, Charge] = {}
        self.captures: dict[str, tuple[str, Decimal, str, str]] = {}
        self.refunded: dict[str, Decimal] = {}
        self.refunds: dict[str, tuple[str, Decimal]] = {}
        self.fail_capture = False
        self.fail_refund = False

    def capture(self, amount: Decimal, currency: str, token: str, key: str) -> Charge:
        if self.fail_capture:
            raise RuntimeError("payment capture failed")
        if amount <= 0 or amount != amount.quantize(CENT):
            raise ValueError("capture amount must be a positive whole-cent amount")
        parameters = (token, amount, currency, key)
        if key in self.captures:
            if self.captures[key] != parameters:
                raise IdempotencyConflict(key)
            return self.charges[f"charge:{key}"]
        charge = Charge(f"charge:{key}", amount, currency)
        self.charges[charge.charge_id] = charge
        self.captures[key] = parameters
        self.refunded[charge.charge_id] = Decimal("0.00")
        return charge

    def refund(self, charge: Charge, amount: Decimal, key: str) -> None:
        if self.fail_refund:
            raise RuntimeError("payment refund failed")
        prior = self.refunds.get(key)
        if prior is not None:
            if prior != (charge.charge_id, amount):
                raise IdempotencyConflict(key)
            return
        if charge.charge_id not in self.charges:
            raise ValueError("unknown charge")
        if amount < 0 or amount != amount.quantize(CENT) or self.refunded[charge.charge_id] + amount > charge.amount:
            raise ValueError("refund exceeds captured amount or is not a nonnegative whole-cent amount")
        self.refunded[charge.charge_id] += amount
        self.refunds[key] = (charge.charge_id, amount)


class InMemoryShipping:
    def __init__(self) -> None:
        self.shipments: dict[str, Shipment] = {}
        self.dispatches: dict[str, tuple[str, Reservation, str]] = {}
        self.dispatched_shipments: dict[str, tuple[Shipment, ...]] = {}
        self.cancelled: set[str] = set()
        self.fail_dispatch = False
        self.fail_on_shipment_number: int | None = None
        self.shipment_attempts = 0
        self.fail_cancel = False

    def dispatch(self, order_id: str, reservation: Reservation, address: str, key: str) -> tuple[Shipment, ...]:
        parameters = (order_id, reservation, address)
        if key in self.dispatches:
            if parameters != self.dispatches[key]:
                raise IdempotencyConflict(key)
            return self.dispatched_shipments[key]
        grouped: dict[str, list[Allocation]] = {}
        for allocation in reservation.allocations:
            grouped.setdefault(allocation.warehouse_id, []).append(allocation)
        completed: list[Shipment] = []
        for warehouse_id, allocations in grouped.items():
            self.shipment_attempts += 1
            if self.fail_dispatch or self.fail_on_shipment_number == self.shipment_attempts:
                raise DispatchFailure("carrier dispatch failed", tuple(completed))
            shipment_id = f"shipment:{key}" if len(grouped) == 1 else f"shipment:{key}:{warehouse_id}"
            shipment = Shipment(shipment_id, tuple(allocations), address, warehouse_id)
            self.shipments[shipment.shipment_id] = shipment
            completed.append(shipment)
        self.dispatches[key] = parameters
        self.dispatched_shipments[key] = tuple(completed)
        return tuple(completed)

    def cancel(self, shipment: Shipment, key: str) -> None:
        if self.fail_cancel:
            raise RuntimeError("carrier cancellation failed")
        if shipment.shipment_id not in self.shipments:
            raise ValueError("unknown shipment")
        self.cancelled.add(shipment.shipment_id)


class InMemoryOrderStore:
    def __init__(self) -> None:
        self.orders: dict[str, Order] = {}
        self.fingerprints: dict[str, str] = {}
        self.attempts: dict[str, int] = {}
        self.outbox: OrderedDict[str, Event] = OrderedDict()
        self.fail_save = False
        self.fail_save_return = False
        self.returns: dict[str, tuple[str, str, ReturnReceipt]] = {}
        self.return_intents: dict[str, tuple[str, str, tuple[ReturnLine, ...]]] = {}
        self.refunded_returns: set[str] = set()
        self.returned_quantities: dict[tuple[str, str, str], int] = {}

    def get(self, request_id: str) -> Order | None:
        return self.orders.get(request_id)

    def begin_attempt(self, request_id: str, fingerprint: str) -> int:
        previous = self.fingerprints.setdefault(request_id, fingerprint)
        if previous != fingerprint or request_id in self.orders:
            raise IdempotencyConflict(request_id)
        attempt = self.attempts.get(request_id, 0) + 1
        self.attempts[request_id] = attempt
        return attempt

    def save(self, order: Order, events: tuple[Event, ...]) -> None:
        if self.fail_save:
            raise RuntimeError("order transaction failed")
        if order.request_id in self.orders or self.fingerprints.get(order.request_id) != order.request_fingerprint:
            raise IdempotencyConflict(order.request_id)
        if len({event.event_id for event in events}) != len(events) or any(event.event_id in self.outbox for event in events):
            raise IdempotencyConflict("event identifier")
        self.orders[order.request_id] = order
        self.outbox.update((event.event_id, event) for event in events)

    def get_return(self, return_request_id: str) -> tuple[str, str, ReturnReceipt] | None:
        return self.returns.get(return_request_id)

    def begin_return(self, order_request_id: str, return_request_id: str,
                     lines: tuple[ReturnLine, ...], fingerprint: str) -> None:
        current = self.return_intents.get(return_request_id)
        if current is not None:
            if current != (order_request_id, fingerprint, lines):
                raise IdempotencyConflict(return_request_id)
            return
        self.return_intents[return_request_id] = (order_request_id, fingerprint, lines)

    def returned_quantity(self, order_request_id: str, shipment_id: str, sku: str,
                          excluding_request_id: str = "") -> int:
        key = (order_request_id, shipment_id, sku)
        committed = self.returned_quantities.get(key, 0)
        pending = sum(
            line.quantity
            for request_id in self.refunded_returns
            if request_id not in self.returns and request_id != excluding_request_id
            for intent_order, _, lines in (self.return_intents[request_id],)
            if intent_order == order_request_id
            for line in lines if (line.shipment_id, line.sku) == (shipment_id, sku)
        )
        return committed + pending

    def mark_refunded(self, return_request_id: str) -> None:
        self.refunded_returns.add(return_request_id)

    def save_return(self, order_request_id: str, fingerprint: str, receipt: ReturnReceipt,
                    event: Event) -> None:
        if self.fail_save or self.fail_save_return:
            raise RuntimeError("return transaction failed")
        request_id = receipt.return_request_id
        if (self.return_intents.get(request_id) != (order_request_id, fingerprint, receipt.lines)
                or request_id not in self.refunded_returns or request_id in self.returns
                or event.event_id in self.outbox):
            raise IdempotencyConflict(request_id)
        increments: dict[tuple[str, str, str], int] = {}
        for line in receipt.lines:
            key = (order_request_id, line.shipment_id, line.sku)
            increments[key] = increments.get(key, 0) + line.quantity
        for key, quantity in increments.items():
            self.returned_quantities[key] = self.returned_quantities.get(key, 0) + quantity
        self.returns[request_id] = (order_request_id, fingerprint, receipt)
        self.refunded_returns.remove(request_id)
        self.outbox[event.event_id] = event

    def pending_events(self) -> tuple[Event, ...]:
        return tuple(self.outbox.values())

    def ack(self, event_id: str) -> None:
        self.outbox.pop(event_id, None)


class InMemoryEventSink:
    def __init__(self) -> None:
        self.events: OrderedDict[str, Event] = OrderedDict()
        self.fail_publish = False

    def publish(self, event: Event) -> None:
        if self.fail_publish:
            raise RuntimeError("event delivery failed")
        previous = self.events.get(event.event_id)
        if previous is not None and previous != event:
            raise IdempotencyConflict(event.event_id)
        self.events[event.event_id] = event
