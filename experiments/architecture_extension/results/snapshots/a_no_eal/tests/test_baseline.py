import unittest

from notification_service import Message, make_service
from notification_service.channel import MemoryGateway


class BaselineTest(unittest.TestCase):
    def test_console_uses_registered_dispatch(self):
        gateway = MemoryGateway()
        service = make_service(gateway)
        self.assertEqual(service.available_channels(), ("console", "email"))
        receipt = service.send("console", Message("terminal", "Ready", "ok"))
        self.assertEqual(receipt.content, b"Ready: ok")
        self.assertEqual(len(gateway.sent), 1)

    def test_unknown_channel_fails_before_delivery(self):
        gateway = MemoryGateway()
        with self.assertRaises(ValueError):
            make_service(gateway).send("missing", Message("x", "s", "b"))
        self.assertEqual(gateway.sent, [])


if __name__ == "__main__":
    unittest.main()
