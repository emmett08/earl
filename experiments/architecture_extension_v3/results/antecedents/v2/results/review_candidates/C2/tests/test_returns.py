"""Partial returns across shipments and failure boundaries."""

import json
import unittest
from decimal import Decimal

from fulfilment import (
    CheckoutRequest, CheckoutService, IdempotencyConflict, InMemoryEventSink,
    InMemoryOrderStore, InMemoryPayments, InMemoryPricing, InMemoryShipping,
    InMemoryStock, RequestedLine, ReturnLine,
)


class ReturnTest(unittest.TestCase):
    def setUp(self):
        self.stock = InMemoryStock({"north": {"lamp": 2}, "south": {"lamp": 1}},
                                   priorities=("north", "south"))
        self.payments = InMemoryPayments()
        self.orders = InMemoryOrderStore()
        self.events = InMemoryEventSink()
        self.service = CheckoutService(InMemoryPricing({"lamp": Decimal("10.00")}),
                                       self.stock, self.payments, InMemoryShipping(),
                                       self.orders, self.events)
        self.order = self.service.checkout(CheckoutRequest(
            "order", "customer", (RequestedLine("lamp", 3),), "address", "token"))
        self.north, self.south = (s.shipment_id for s in self.order.shipments)

    def test_split_return_replay_and_remaining_capacity(self):
        lines = (ReturnLine(self.north, "lamp", 1), ReturnLine(self.south, "lamp", 1))
        receipt = self.service.return_items("order", "first", lines)
        self.assertEqual(receipt.refunded_amount, Decimal("24.00"))
        self.assertEqual(self.stock.on_hand, {"north": {"lamp": 1}, "south": {"lamp": 1}})
        self.assertIs(self.service.return_items("order", "first", lines), receipt)
        self.assertEqual(len(self.payments.refunds), 1)
        self.assertEqual(len(self.events.events), 2)
        event = list(self.events.events.values())[1]
        self.assertEqual(event.name, "ItemsReturned")
        self.assertEqual(dict(event.data)["return_request_id"], "first")
        self.assertEqual(json.loads(dict(event.data)["allocations"])[0]["warehouse_id"], "north")
        self.service.return_items("order", "second", (ReturnLine(self.north, "lamp", 1),))
        self.assertEqual(self.payments.refunded[self.order.charge.charge_id], Decimal("36.00"))
        self.assertEqual(self.orders.get("order"), self.order)

    def test_invalid_requests_do_not_change_effects(self):
        before = {name: dict(stock) for name, stock in self.stock.on_hand.items()}
        for order_id, lines in (
            ("missing", (ReturnLine(self.north, "lamp", 1),)),
            ("order", (ReturnLine("missing", "lamp", 1),)),
            ("order", (ReturnLine(self.north, "cord", 1),)),
            ("order", (ReturnLine(self.north, "lamp", 2), ReturnLine(self.north, "lamp", 1))),
        ):
            with self.assertRaises(ValueError):
                self.service.return_items(order_id, "invalid", lines)
        with self.assertRaises(ValueError):
            ReturnLine(self.north, "lamp", 0)
        self.assertEqual(self.stock.on_hand, before)
        self.assertFalse(self.payments.refunds)
        self.assertEqual(len(self.events.events), 1)
        self.service.return_items("order", "valid", (ReturnLine(self.north, "lamp", 2),))
        with self.assertRaises(ValueError):
            self.service.return_items("order", "over", (ReturnLine(self.north, "lamp", 1),))
        with self.assertRaises(IdempotencyConflict):
            self.service.return_items("order", "valid", (ReturnLine(self.south, "lamp", 1),))

    def test_refund_failure_and_later_failures_retry_once(self):
        lines = (ReturnLine(self.north, "lamp", 1),)
        self.payments.fail_refund = True
        with self.assertRaisesRegex(RuntimeError, "refund failed"):
            self.service.return_items("order", "retry", lines)
        self.assertEqual(self.stock.on_hand["north"]["lamp"], 0)
        self.assertFalse(self.orders.returns)
        self.assertFalse(self.payments.refunds)
        self.payments.fail_refund = False
        self.stock.fail_restore = True
        with self.assertRaisesRegex(RuntimeError, "restoration failed"):
            self.service.return_items("order", "retry", lines)
        self.assertEqual(self.payments.refunded[self.order.charge.charge_id], Decimal("12.00"))
        self.stock.fail_restore = False
        self.orders.fail_save = True
        with self.assertRaisesRegex(RuntimeError, "transaction failed"):
            self.service.return_items("order", "retry", lines)
        self.assertEqual(self.stock.on_hand["north"]["lamp"], 1)
        self.orders.fail_save = False
        self.events.fail_publish = True
        receipt = self.service.return_items("order", "retry", lines)
        self.assertEqual(receipt.refunded_amount, Decimal("12.00"))
        self.assertEqual(len(self.payments.refunds), 1)
        self.assertEqual(len(self.stock.return_restorations), 1)
        self.assertEqual(len(self.orders.pending_events()), 1)
        self.events.fail_publish = False
        self.assertIs(self.service.return_items("order", "retry", lines), receipt)
        self.assertFalse(self.orders.pending_events())
        self.assertEqual(len(self.events.events), 2)


if __name__ == "__main__":
    unittest.main()
