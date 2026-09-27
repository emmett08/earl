import unittest

from notification_service import Message, make_service
from notification_service.channel import MemoryGateway


class SmsTest(unittest.TestCase):
    def test_sms_delivers_body_as_utf8_and_ignores_subject(self):
        gateway = MemoryGateway()
        receipt = make_service(gateway).send("sms", Message("+15551234567", "ignored", "Café"))

        self.assertEqual(receipt.medium, "sms")
        self.assertEqual(receipt.destination, "+15551234567")
        self.assertEqual(receipt.content, "Café".encode("utf-8"))
        self.assertEqual(len(gateway.sent), 1)
        self.assertEqual(gateway.sent[0].content, receipt.content)

    def test_exactly_160_bytes_delivers_once(self):
        gateway = MemoryGateway()
        receipt = make_service(gateway).send("sms", Message("number", "subject", "x" * 160))

        self.assertEqual(receipt.content, b"x" * 160)
        self.assertEqual(len(gateway.sent), 1)

    def test_more_than_160_bytes_fails_before_delivery(self):
        gateway = MemoryGateway()
        with self.assertRaises(ValueError):
            make_service(gateway).send("sms", Message("number", "subject", "x" * 161))

        self.assertEqual(gateway.sent, [])

    def test_multibyte_utf8_boundary(self):
        gateway = MemoryGateway()
        service = make_service(gateway)
        valid_body = "é" * 79 + "ab"  # 160 UTF-8 bytes, 81 characters.
        receipt = service.send("sms", Message("number", "subject", valid_body))
        self.assertEqual(receipt.content, valid_body.encode("utf-8"))
        self.assertEqual(len(gateway.sent), 1)

        with self.assertRaises(ValueError):
            service.send("sms", Message("number", "subject", "é" * 80 + "x"))
        self.assertEqual(len(gateway.sent), 1)


if __name__ == "__main__":
    unittest.main()
