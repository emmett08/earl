"""Purchase orchestration, idempotency and durable event delivery."""

from __future__ import annotations

import hashlib
import json

from .domain import (
    CheckoutRequest, CompensationFailure, DispatchFailure, Event, IdempotencyConflict, Order,
    Reservation, Charge, Shipment,
)
from .ports import EventSink, OrderStore, PaymentPort, PricingPort, ShippingPort, StockPort


def request_fingerprint(request: CheckoutRequest) -> str:
    # The token participates in the identity but is never written into an event.
    serialised = json.dumps(
        [request.customer_id, [(line.sku, line.quantity) for line in request.lines],
         request.address, request.payment_token],
        separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


class CheckoutService:
    def __init__(
        self, pricing: PricingPort, stock: StockPort, payments: PaymentPort,
        shipping: ShippingPort, orders: OrderStore, events: EventSink,
    ) -> None:
        self.pricing = pricing
        self.stock = stock
        self.payments = payments
        self.shipping = shipping
        self.orders = orders
        self.events = events

    def checkout(self, request: CheckoutRequest) -> Order:
        fingerprint = request_fingerprint(request)
        previous = self.orders.get(request.request_id)
        if previous is not None:
            if previous.request_fingerprint != fingerprint:
                raise IdempotencyConflict(request.request_id)
            self.retry_events()
            return previous

        quote = self.pricing.quote(request.lines)
        order_id = "ord-" + hashlib.sha256(request.request_id.encode()).hexdigest()[:20]
        attempt = self.orders.begin_attempt(request.request_id, fingerprint)
        operation_key = f"{request.request_id}:attempt:{attempt}"
        reservation: Reservation | None = None
        charge: Charge | None = None
        shipments: tuple[Shipment, ...] = ()
        try:
            reservation = self.stock.reserve(request.lines, operation_key)
            charge = self.payments.capture(quote.total, quote.currency, request.payment_token, operation_key)
            shipments = self.shipping.dispatch(order_id, reservation, request.address, operation_key)
            if not shipments:
                raise ValueError("dispatch returned no shipments")
            order = Order(
                order_id=order_id, request_id=request.request_id,
                request_fingerprint=fingerprint, customer_id=request.customer_id,
                address=request.address, quote=quote, reservation=reservation,
                charge=charge, shipments=shipments, status="dispatched",
            )
            event = Event(
                event_id=f"{order_id}:dispatched", name="OrderDispatched", order_id=order_id,
                data=(
                    ("customer_id", request.customer_id), ("shipment_count", str(len(shipments))),
                    ("allocations", json.dumps([
                        {"warehouse_id": a.warehouse_id, "sku": a.sku, "quantity": a.quantity}
                        for a in order.allocations
                    ])),
                    ("shipments", json.dumps([
                        {"shipment_id": shipment.shipment_id, "warehouse_id": shipment.warehouse_id,
                         "allocations": [{"sku": a.sku, "quantity": a.quantity} for a in shipment.allocations]}
                        for shipment in shipments
                    ])),
                ),
            )
            self.orders.save(order, (event,))
        except Exception as original:
            if isinstance(original, DispatchFailure):
                shipments = original.partial_shipments
            # Undo external operations in reverse order. A failed compensation is
            # explicit: the caller must reconcile it before retrying the key.
            compensation_errors: list[Exception] = []
            for shipment in reversed(shipments):
                try:
                    self.shipping.cancel(shipment, operation_key + ":rollback")
                except Exception as error:
                    compensation_errors.append(error)
            if charge is not None:
                try:
                    self.payments.refund(charge, charge.amount, operation_key + ":rollback")
                except Exception as error:
                    compensation_errors.append(error)
            if reservation is not None:
                try:
                    self.stock.release(reservation)
                except Exception as error:
                    compensation_errors.append(error)
            if compensation_errors:
                raise CompensationFailure(original, tuple(compensation_errors)) from original
            raise
        self.retry_events()
        return order

    def retry_events(self) -> int:
        """Send pending events, retaining any that the sink rejects for a later retry."""
        count = 0
        for event in self.orders.pending_events():
            try:
                self.events.publish(event)
            except Exception:
                break
            self.orders.ack(event.event_id)
            count += 1
        return count
