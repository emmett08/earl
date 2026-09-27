"""Business behaviour and failure boundaries that both continuation arms inherit."""

import unittest
import json
from decimal import Decimal

from fulfilment import (
    CheckoutRequest, CheckoutService, CompensationFailure, DispatchFailure, IdempotencyConflict,
    InMemoryEventSink, InMemoryOrderStore, InMemoryPayments, InMemoryPricing,
    InMemoryShipping, InMemoryStock, OutOfStock, RequestedLine,
)


class BaselineTest(unittest.TestCase):
    def setUp(self):
        self.pricing = InMemoryPricing({"lamp": Decimal("19.99"), "cord": Decimal("5.25")})
        self.stock = InMemoryStock({"lamp": 5, "cord": 3})
        self.payments = InMemoryPayments()
        self.shipping = InMemoryShipping()
        self.orders = InMemoryOrderStore()
        self.events = InMemoryEventSink()
        self.service = CheckoutService(
            self.pricing, self.stock, self.payments, self.shipping, self.orders, self.events,
        )

    def request(self, key="request-1", lines=None):
        return CheckoutRequest(
            request_id=key, customer_id="customer-1",
            lines=lines or (RequestedLine("lamp", 2), RequestedLine("cord", 1)),
            address="10 Test Street", payment_token="opaque-token",
        )

    def test_quote_reserve_capture_dispatch_and_event(self):
        order = self.service.checkout(self.request())
        self.assertEqual(order.status, "dispatched")
        self.assertEqual(order.quote.subtotal, Decimal("45.23"))
        self.assertEqual(order.quote.tax, Decimal("9.05"))
        self.assertEqual(order.quote.total, Decimal("54.28"))
        self.assertEqual(order.charge.amount, order.quote.total)
        self.assertEqual(order.quote.lines[0].unit_tax, Decimal("4.00"))
        self.assertEqual(order.quote.lines[1].unit_tax, Decimal("1.05"))
        self.assertEqual(self.stock.on_hand, {"lamp": 3, "cord": 2})
        self.assertEqual(order.shipments[0].allocations, order.reservation.allocations)
        self.assertEqual({a.warehouse_id for a in order.reservation.allocations}, {"main"})
        self.assertEqual([e.name for e in self.events.events.values()], ["OrderDispatched"])
        self.assertFalse(self.orders.pending_events())

    def test_successful_replay_has_no_duplicate_effects_and_conflict_is_rejected(self):
        first = self.service.checkout(self.request())
        second = self.service.checkout(self.request())
        self.assertIs(first, second)
        self.assertEqual(len(self.payments.charges), 1)
        self.assertEqual(len(self.shipping.shipments), 1)
        self.assertEqual(len(self.events.events), 1)
        with self.assertRaises(IdempotencyConflict):
            self.service.checkout(self.request(lines=(RequestedLine("lamp", 1),)))
        self.assertEqual(self.stock.on_hand, {"lamp": 3, "cord": 2})

    def test_atomic_out_of_stock_rejects_whole_order(self):
        with self.assertRaises(OutOfStock):
            self.service.checkout(self.request(lines=(RequestedLine("lamp", 1), RequestedLine("cord", 4))))
        self.assertEqual(self.stock.on_hand, {"lamp": 5, "cord": 3})
        self.assertFalse(self.payments.charges)

    def test_payment_failure_releases_inventory_then_retry_uses_new_attempt(self):
        self.payments.fail_capture = True
        with self.assertRaisesRegex(RuntimeError, "capture failed"):
            self.service.checkout(self.request())
        self.assertEqual(self.stock.on_hand, {"lamp": 5, "cord": 3})
        self.payments.fail_capture = False
        order = self.service.checkout(self.request())
        self.assertIn(":attempt:2", order.charge.charge_id)
        self.assertEqual(self.stock.on_hand, {"lamp": 3, "cord": 2})

    def test_carrier_failure_refunds_and_releases_then_retry_recaptures(self):
        self.shipping.fail_dispatch = True
        with self.assertRaisesRegex(DispatchFailure, "dispatch failed"):
            self.service.checkout(self.request())
        old_charge = next(iter(self.payments.charges.values()))
        self.assertEqual(self.payments.refunded[old_charge.charge_id], old_charge.amount)
        self.assertEqual(self.stock.on_hand, {"lamp": 5, "cord": 3})
        self.shipping.fail_dispatch = False
        order = self.service.checkout(self.request())
        self.assertNotEqual(order.charge.charge_id, old_charge.charge_id)
        self.assertEqual(self.payments.refunded[order.charge.charge_id], Decimal("0.00"))

    def test_transaction_failure_cancels_dispatch_refunds_and_releases(self):
        self.orders.fail_save = True
        with self.assertRaisesRegex(RuntimeError, "order transaction failed"):
            self.service.checkout(self.request())
        self.assertEqual(self.stock.on_hand, {"lamp": 5, "cord": 3})
        self.assertEqual(self.shipping.cancelled, set(self.shipping.shipments))
        charge = next(iter(self.payments.charges.values()))
        self.assertEqual(self.payments.refunded[charge.charge_id], charge.amount)
        self.assertFalse(self.orders.orders)
        self.assertFalse(self.orders.pending_events())

    def test_failed_event_delivery_keeps_order_and_preserves_event_order(self):
        self.events.fail_publish = True
        first = self.service.checkout(self.request("first"))
        self.assertEqual(self.orders.get("first"), first)
        self.assertEqual([e.order_id for e in self.orders.pending_events()], [first.order_id])
        self.events.fail_publish = False
        second = self.service.checkout(self.request("second", (RequestedLine("lamp", 1),)))
        self.assertEqual(
            [e.order_id for e in self.events.events.values()], [first.order_id, second.order_id],
        )
        self.assertEqual(self.service.retry_events(), 0)

    def test_unreconciled_refund_failure_is_explicit(self):
        self.shipping.fail_dispatch = True
        self.payments.fail_refund = True
        with self.assertRaises(CompensationFailure) as raised:
            self.service.checkout(self.request())
        self.assertEqual(len(raised.exception.errors), 1)
        self.assertEqual(self.stock.on_hand, {"lamp": 5, "cord": 3})

    def test_carrier_failure_injection_contract(self):
        self.shipping.fail_on_shipment_number = 1
        with self.assertRaises(DispatchFailure) as raised:
            self.service.checkout(self.request())
        self.assertEqual(raised.exception.partial_shipments, ())
        self.assertEqual(self.shipping.shipment_attempts, 1)
        self.assertEqual(self.stock.on_hand, {"lamp": 5, "cord": 3})

    def test_multi_depot_configuration_allocates_across_warehouses(self):
        stock = InMemoryStock(
            {"north": {"lamp": 1}, "south": {"lamp": 2}},
            priorities=("north", "south"),
        )
        self.assertEqual(stock.priorities, ("north", "south"))
        self.assertEqual(stock.on_hand_by_warehouse["south"]["lamp"], 2)
        reservation = stock.reserve((RequestedLine("lamp", 2),), "multi")
        self.assertEqual([(a.warehouse_id, a.sku, a.quantity) for a in reservation.allocations],
                         [("north", "lamp", 1), ("south", "lamp", 1)])
        self.assertEqual(stock.on_hand["north"]["lamp"], 0)
        self.assertEqual(stock.on_hand["south"]["lamp"], 1)
        self.assertIs(stock.reserve((RequestedLine("lamp", 2),), "multi"), reservation)
        with self.assertRaises(IdempotencyConflict):
            stock.reserve((RequestedLine("lamp", 1),), "multi")
        stock.release(reservation)
        self.assertEqual(stock.on_hand["north"]["lamp"], 1)
        self.assertEqual(stock.on_hand["south"]["lamp"], 2)

    def test_input_validation_and_canonical_request_scope(self):
        with self.assertRaises(ValueError):
            self.request(lines=(RequestedLine("lamp", 1), RequestedLine("lamp", 1)))
        with self.assertRaises(ValueError):
            RequestedLine("lamp", True)
        self.shipping.fail_dispatch = True
        with self.assertRaises(DispatchFailure):
            self.service.checkout(self.request())
        with self.assertRaises(IdempotencyConflict):
            self.service.checkout(self.request(lines=(RequestedLine("lamp", 1),)))


if __name__ == "__main__":
    unittest.main()
