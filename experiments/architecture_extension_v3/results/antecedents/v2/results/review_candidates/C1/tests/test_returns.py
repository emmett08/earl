"""Partial returns across shipments and retry boundaries."""

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
            "purchase", "customer", (RequestedLine("lamp", 3),), "address", "token"))
        self.north, self.south = (s.shipment_id for s in self.order.shipments)

    def test_partial_return_restores_origin_and_replay_does_not_repeat_effects(self):
        lines = (ReturnLine(self.north, "lamp", 1), ReturnLine(self.south, "lamp", 1))
        receipt = self.service.return_items("purchase", "return-1", lines)
        self.assertEqual(receipt.refunded_amount, Decimal("24.00"))
        self.assertEqual(self.stock.on_hand, {"north": {"lamp": 1}, "south": {"lamp": 1}})
        self.assertEqual(self.payments.refunded[self.order.charge.charge_id], Decimal("24.00"))
        self.assertIs(self.service.return_items("purchase", "return-1", lines), receipt)
        self.assertEqual(len(self.payments.refunds), 1)
        self.assertEqual(len(self.stock.restorations), 1)
        event = list(self.events.events.values())[-1]
        self.assertEqual(event.name, "ItemsReturned")
        self.assertEqual(dict(event.data)["return_request_id"], "return-1")
        self.assertEqual([a["warehouse_id"] for a in json.loads(dict(event.data)["allocations"])],
                         ["north", "south"])
        self.assertIs(self.orders.get("purchase"), self.order)
        self.service.return_items("purchase", "return-2", (ReturnLine(self.north, "lamp", 1),))
        self.assertEqual(self.payments.refunded[self.order.charge.charge_id], self.order.charge.amount)
        self.assertEqual(self.orders.returned_quantities[("purchase", self.north, "lamp")], 2)

    def test_invalid_returns_have_no_effects(self):
        bad = (("absent", "x", (ReturnLine(self.north, "lamp", 1),)),
               ("purchase", "x", (ReturnLine("missing", "lamp", 1),)),
               ("purchase", "x", (ReturnLine(self.north, "cord", 1),)),
               ("purchase", "x", (ReturnLine(self.north, "lamp", 2),
                                  ReturnLine(self.north, "lamp", 1))))
        for args in bad:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.service.return_items(*args)
        self.assertEqual(self.stock.on_hand, {"north": {"lamp": 0}, "south": {"lamp": 0}})
        self.assertFalse(self.payments.refunds)
        self.assertFalse(self.orders.returns)
        self.assertEqual(len(self.events.events), 1)
        with self.assertRaises(ValueError):
            ReturnLine(self.north, "lamp", 0)

    def test_refund_failure_and_later_step_failure(self):
        line = (ReturnLine(self.north, "lamp", 1),)
        self.payments.fail_refund = True
        with self.assertRaisesRegex(RuntimeError, "refund failed"):
            self.service.return_items("purchase", "return-1", line)
        self.assertFalse(self.orders.returns)
        self.assertFalse(self.stock.restorations)
        self.assertEqual(self.stock.on_hand["north"]["lamp"], 0)
        self.payments.fail_refund = False
        self.orders.fail_save_return = True
        with self.assertRaisesRegex(RuntimeError, "return transaction failed"):
            self.service.return_items("purchase", "return-1", line)
        self.assertEqual(self.stock.on_hand["north"]["lamp"], 1)
        self.assertFalse(self.orders.returns)
        with self.assertRaises(ValueError):
            self.service.return_items("purchase", "return-2", (ReturnLine(self.north, "lamp", 2),))
        self.orders.fail_save_return = False
        self.assertEqual(self.service.return_items("purchase", "return-1", line).refunded_amount,
                         Decimal("12.00"))
        self.assertEqual(len(self.payments.refunds), 1)
        self.assertEqual(self.stock.on_hand["north"]["lamp"], 1)
        with self.assertRaises(IdempotencyConflict):
            self.service.return_items("purchase", "return-1", (ReturnLine(self.south, "lamp", 1),))

    def test_stock_failure_and_event_delivery_retry(self):
        line = (ReturnLine(self.south, "lamp", 1),)
        self.stock.fail_restore = True
        with self.assertRaisesRegex(RuntimeError, "restoration failed"):
            self.service.return_items("purchase", "return-1", line)
        self.assertEqual(self.stock.on_hand["south"]["lamp"], 0)
        self.assertEqual(len(self.payments.refunds), 1)
        self.stock.fail_restore = False
        self.events.fail_publish = True
        self.service.return_items("purchase", "return-1", line)
        self.assertEqual(len(self.orders.pending_events()), 1)
        self.events.fail_publish = False
        self.service.return_items("purchase", "return-1", line)
        self.assertEqual(len(self.payments.refunds), 1)
        self.assertEqual(len(self.stock.restorations), 1)
        self.assertFalse(self.orders.pending_events())
        self.assertEqual(len(self.events.events), 2)


if __name__ == "__main__":
    unittest.main()
