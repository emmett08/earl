import unittest

from notification_service import Message, make_service
from notification_service.channel import MemoryGateway


class SmsTest(unittest.TestCase):
    def test_body_is_delivered_as_utf8_once_and_subject_is_ignored(self):
        gateway = MemoryGateway()
        message = Message("+15551234567", "Ignored <&>", "Привет 🌍")

        receipt = make_service(gateway).send("sms", message)

        expected = message.body.encode("utf-8")
        self.assertEqual(receipt.medium, "sms")
        self.assertEqual(receipt.destination, message.destination)
        self.assertEqual(receipt.content, expected)
        self.assertEqual(len(gateway.sent), 1)
        self.assertEqual(gateway.sent[0].content, expected)

    def test_exactly_160_bytes_delivers_once(self):
        gateway = MemoryGateway()
        body = "a" * 158 + "é"
        self.assertEqual(len(body.encode("utf-8")), 160)

        receipt = make_service(gateway).send("sms", Message("phone", "", body))

        self.assertEqual(receipt.content, body.encode("utf-8"))
        self.assertEqual(len(gateway.sent), 1)

    def test_multibyte_character_beyond_byte_limit_fails_before_delivery(self):
        gateway = MemoryGateway()
        body = "a" * 159 + "é"
        self.assertEqual(len(body), 160)
        self.assertEqual(len(body.encode("utf-8")), 161)

        with self.assertRaises(ValueError):
            make_service(gateway).send("sms", Message("phone", "", body))

        self.assertEqual(gateway.sent, [])


if __name__ == "__main__":
    unittest.main()
