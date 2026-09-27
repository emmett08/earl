"""Split warehouse allocation and checkout failure boundaries."""

import json
import unittest
from decimal import Decimal

from fulfilment import (
    CheckoutRequest, CheckoutService, DispatchFailure, IdempotencyConflict,
    InMemoryEventSink, InMemoryOrderStore, InMemoryPayments, InMemoryPricing,
    InMemoryShipping, InMemoryStock, OutOfStock, RequestedLine,
)


class SplitFulfilmentTest(unittest.TestCase):
    def setUp(self):
        self.stock = InMemoryStock(
            {"north": {"lamp": 2, "cord": 1}, "south": {"lamp": 2, "cord": 3}},
            priorities=("north", "south"),
        )
        self.payments = InMemoryPayments()
        self.shipping = InMemoryShipping()
        self.orders = InMemoryOrderStore()
        self.events = InMemoryEventSink()
        self.service = CheckoutService(
            InMemoryPricing({"lamp": Decimal("10.00"), "cord": Decimal("2.00")}),
            self.stock, self.payments, self.shipping, self.orders, self.events,
        )

    def request(self, key="split", lines=(RequestedLine("lamp", 3), RequestedLine("cord", 2))):
        return CheckoutRequest(key, "customer", lines, "10 Test Street", "token")

    def test_split_dispatch_groups_every_sku_by_warehouse_and_event_matches_order(self):
        order = self.service.checkout(self.request())
        self.assertEqual([(a.warehouse_id, a.sku, a.quantity) for a in order.allocations], [
            ("north", "lamp", 2), ("north", "cord", 1),
            ("south", "lamp", 1), ("south", "cord", 1),
        ])
        self.assertEqual([(s.warehouse_id, [(a.sku, a.quantity) for a in s.allocations])
                          for s in order.shipments], [
            ("north", [("lamp", 2), ("cord", 1)]),
            ("south", [("lamp", 1), ("cord", 1)]),
        ])
        self.assertEqual(len(self.payments.charges), 1)
        self.assertEqual(order.charge.amount, order.quote.total)
        data = dict(next(iter(self.events.events.values())).data)
        self.assertEqual(json.loads(data["allocations"]), [
            {"warehouse_id": a.warehouse_id, "sku": a.sku, "quantity": a.quantity}
            for a in order.allocations
        ])
        self.assertEqual([(s["warehouse_id"], s["allocations"]) for s in json.loads(data["shipments"])], [
            ("north", [{"sku": "lamp", "quantity": 2}, {"sku": "cord", "quantity": 1}]),
            ("south", [{"sku": "lamp", "quantity": 1}, {"sku": "cord", "quantity": 1}]),
        ])
        self.assertIs(self.service.checkout(self.request()), order)
        self.assertEqual(self.shipping.shipment_attempts, 2)
        with self.assertRaises(IdempotencyConflict):
            self.service.checkout(self.request(lines=(RequestedLine("lamp", 2),)))

    def test_aggregate_shortage_does_not_mutate_effects(self):
        before = {name: dict(stock) for name, stock in self.stock.on_hand.items()}
        with self.assertRaises(OutOfStock):
            self.service.checkout(self.request(lines=(RequestedLine("lamp", 3), RequestedLine("cord", 5))))
        self.assertEqual(self.stock.on_hand, before)
        self.assertFalse(self.stock.reservations)
        self.assertFalse(self.payments.charges)
        self.assertFalse(self.shipping.shipments)
        self.assertFalse(self.orders.orders)
        self.assertFalse(self.events.events)

    def test_shipment_order_follows_priority_even_when_first_sku_is_only_in_south(self):
        self.stock.on_hand["north"]["lamp"] = 0
        order = self.service.checkout(self.request(lines=(RequestedLine("lamp", 1), RequestedLine("cord", 1))))
        self.assertEqual([shipment.warehouse_id for shipment in order.shipments], ["north", "south"])
        self.assertEqual([a.sku for a in order.shipments[0].allocations], ["cord"])

    def test_second_dispatch_failure_cancels_first_and_refunds_once(self):
        self.shipping.fail_on_shipment_number = 2
        before = {name: dict(stock) for name, stock in self.stock.on_hand.items()}
        with self.assertRaises(DispatchFailure) as raised:
            self.service.checkout(self.request())
        self.assertEqual(len(raised.exception.partial_shipments), 1)
        self.assertEqual(self.shipping.cancelled, set(self.shipping.shipments))
        self.assertEqual(self.stock.on_hand, before)
        charge = next(iter(self.payments.charges.values()))
        self.assertEqual(self.payments.refunded[charge.charge_id], charge.amount)
        self.assertEqual(len(self.payments.refunds), 1)
        self.assertFalse(self.orders.orders)
        self.assertFalse(self.events.events)
        self.shipping.fail_on_shipment_number = None
        order = self.service.checkout(self.request())
        self.assertEqual(len(order.shipments), 2)
        self.assertEqual(len(self.payments.charges), 2)

    def test_event_failure_is_retried_without_refulfilment(self):
        self.events.fail_publish = True
        order = self.service.checkout(self.request())
        self.assertEqual(len(self.orders.pending_events()), 1)
        self.events.fail_publish = False
        self.assertIs(self.service.checkout(self.request()), order)
        self.assertEqual(self.shipping.shipment_attempts, 2)
        self.assertEqual(len(self.payments.charges), 1)
        self.assertEqual(len(self.events.events), 1)


if __name__ == "__main__":
    unittest.main()
