"""Purchase orchestration, idempotency and durable event delivery."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from .domain import Allocation, ReturnLine, ReturnReceipt

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

    def return_items(
        self, order_request_id: str, return_request_id: str, lines: tuple[ReturnLine, ...],
    ) -> ReturnReceipt:
        if not order_request_id or not return_request_id or not isinstance(lines, tuple) or not lines:
            raise ValueError("return needs an order, request ID and nonempty tuple of lines")
        if any(not isinstance(line, ReturnLine) or type(line.quantity) is not int or line.quantity <= 0
               for line in lines):
            raise ValueError("return quantities must be positive whole units")
        fingerprint = hashlib.sha256(json.dumps(
            [order_request_id, [(line.shipment_id, line.sku, line.quantity) for line in lines]],
            separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()
        previous = self.orders.get_return(return_request_id)
        if previous is not None:
            if previous[:2] != (order_request_id, fingerprint):
                raise IdempotencyConflict(return_request_id)
            self.retry_events()
            return previous[2]

        order = self.orders.get(order_request_id)
        if order is None or order.status != "dispatched":
            raise ValueError("unknown or unfulfilled order")
        shipments = {shipment.shipment_id: shipment for shipment in order.shipments}
        quoted = {line.sku: line for line in order.quote.lines}
        requested: dict[tuple[str, str], int] = defaultdict(int)
        for line in lines:
            shipment = shipments.get(line.shipment_id)
            if shipment is None:
                raise ValueError("unknown shipment")
            if line.sku not in {a.sku for a in shipment.allocations}:
                raise ValueError("SKU does not match shipment")
            requested[(line.shipment_id, line.sku)] += line.quantity
        for (shipment_id, sku), quantity in requested.items():
            shipped = sum(a.quantity for a in shipments[shipment_id].allocations if a.sku == sku)
            returned = self.orders.returned_quantity(
                order_request_id, shipment_id, sku, excluding_request_id=return_request_id,
            )
            if returned + quantity > shipped:
                raise ValueError("return exceeds shipped quantity")

        amount = sum(
            ((quoted[line.sku].unit_price + quoted[line.sku].unit_tax) * line.quantity
             for line in lines),
            start=order.quote.total * 0,
        )
        receipt = ReturnReceipt(return_request_id, amount, lines)
        allocations = tuple(Allocation(sku, quantity, shipments[shipment_id].warehouse_id)
                            for (shipment_id, sku), quantity in requested.items())
        self.orders.begin_return(order_request_id, return_request_id, lines, fingerprint)
        operation_key = "return:" + hashlib.sha256(return_request_id.encode("utf-8")).hexdigest()
        # Each port deduplicates this operation key. In particular, a later stock
        # or store failure must never lead to a second payment refund.
        self.payments.refund(order.charge, amount, operation_key)
        self.orders.mark_refunded(return_request_id)
        self.stock.restore(allocations, operation_key)
        event = Event(
            event_id=f"{order.order_id}:return:{hashlib.sha256(return_request_id.encode()).hexdigest()}",
            name="ItemsReturned", order_id=order.order_id,
            data=(("return_request_id", return_request_id), ("refunded_amount", str(amount)),
                  ("allocations", json.dumps([
                      {"shipment_id": shipment_id,
                       "warehouse_id": shipments[shipment_id].warehouse_id,
                       "sku": sku, "quantity": quantity}
                      for (shipment_id, sku), quantity in requested.items()
                  ]))),
        )
        self.orders.save_return(order_request_id, fingerprint, receipt, event)
        self.retry_events()
        return receipt
