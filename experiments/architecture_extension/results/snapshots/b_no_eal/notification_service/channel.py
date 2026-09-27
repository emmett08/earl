"""Extension contract and a deterministic in-memory delivery gateway."""

from typing import Protocol

from .model import Message, Payload, Receipt


class Channel(Protocol):
    name: str

    def prepare(self, message: Message) -> Payload:
        """Validate and encode a message before any delivery side effect."""


class Gateway(Protocol):
    def deliver(self, payload: Payload) -> Receipt:
        """Deliver one prepared payload."""


class MemoryGateway:
    def __init__(self) -> None:
        self.sent: list[Payload] = []

    def deliver(self, payload: Payload) -> Receipt:
        self.sent.append(payload)
        return Receipt(payload.medium, payload.destination, payload.content)
