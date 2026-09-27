import unittest

from notification_service import Message, make_service
from notification_service.channel import MemoryGateway


class EmailTest(unittest.TestCase):
    def test_email_escapes_fields_and_delivers_once(self):
        gateway = MemoryGateway()
        message = Message("person@example.com", "Café <&>\"'", "Привет & <b>\"'\nDone")

        receipt = make_service(gateway).send("email", message)

        expected = (
            'Subject: Café &lt;&amp;&gt;&quot;&#x27;\n\n'
            'Привет &amp; &lt;b&gt;&quot;&#x27;\nDone'
        ).encode("utf-8")
        self.assertEqual(receipt.medium, "email")
        self.assertEqual(receipt.destination, "person@example.com")
        self.assertEqual(receipt.content, expected)
        self.assertEqual(len(gateway.sent), 1)
        self.assertEqual(gateway.sent[0].content, expected)


if __name__ == "__main__":
    unittest.main()
