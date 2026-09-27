"""Baseline channel."""

from .model import Message, Payload


class ConsoleChannel:
    name = "console"

    def prepare(self, message: Message) -> Payload:
        body = f"{message.subject}: {message.body}".encode("utf-8")
        return Payload(self.name, message.destination, body)
