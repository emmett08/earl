"""SMS channel with a 160-byte UTF-8 content limit."""

from .model import Message, Payload


class SmsChannel:
    name = "sms"

    def prepare(self, message: Message) -> Payload:
        content = message.body.encode("utf-8")
        if len(content) > 160:
            raise ValueError("SMS body exceeds 160 bytes")
        return Payload(self.name, message.destination, content)
