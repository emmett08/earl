"""Email channel with escaped subject and body."""

from html import escape

from .model import Message, Payload


class EmailChannel:
    name = "email"

    def prepare(self, message: Message) -> Payload:
        content = (
            f"Subject: {escape(message.subject, quote=True)}\n\n"
            f"{escape(message.body, quote=True)}"
        ).encode("utf-8")
        return Payload(self.name, message.destination, content)
