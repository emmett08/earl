"""Deterministic in-memory implementations for the independent experiment runs."""

from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal, ROUND_HALF_UP

from .domain import (
    CENT, Allocation, Charge, DispatchFailure, Event, IdempotencyConflict, Order, OutOfStock,
    Quote, QuotedLine, RequestedLine, Reservation, Shipment,
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
        self.fail_release = False

    def reserve(self, lines: tuple[RequestedLine, ...], key: str) -> Reservation:
        existing = self.reservations.get(key)
        if existing is not None:
            expected = tuple((line.sku, line.quantity) for line in lines)
            actual = tuple((a.sku, a.quantity) for a in existing.allocations)
            if expected != actual:
                raise IdempotencyConflict(key)
            return existing
        # Check the complete demand before mutating any SKU.
        primary = self.on_hand_by_warehouse[self.warehouse_id]
        for line in lines:
            if primary.get(line.sku, 0) < line.quantity:
                raise OutOfStock(line.sku)
        allocations = tuple(Allocation(line.sku, line.quantity, self.warehouse_id) for line in lines)
        reservation = Reservation(f"res:{key}", allocations)
        for allocation in allocations:
            primary[allocation.sku] -= allocation.quantity
        self.reservations[key] = reservation
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
        if amount <= 0 or amount != amount.quantize(CENT) or self.refunded[charge.charge_id] + amount > charge.amount:
            raise ValueError("refund exceeds captured amount or is not whole-cent positive")
        self.refunded[charge.charge_id] += amount
        self.refunds[key] = (charge.charge_id, amount)


class InMemoryShipping:
    def __init__(self) -> None:
        self.shipments: dict[str, Shipment] = {}
        self.dispatches: dict[str, tuple[str, Reservation, str]] = {}
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
            return (self.shipments[f"shipment:{key}"],)
        self.shipment_attempts += 1
        if self.fail_dispatch or self.fail_on_shipment_number == self.shipment_attempts:
            raise DispatchFailure("carrier dispatch failed")
        shipment = Shipment(f"shipment:{key}", reservation.allocations, address)
        self.shipments[shipment.shipment_id] = shipment
        self.dispatches[key] = parameters
        return (shipment,)

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
