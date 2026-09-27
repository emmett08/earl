"""One dispatch path. New media register a Channel implementation."""

from .channel import Channel, Gateway
from .model import Message, Receipt


class NotificationService:
    def __init__(self, gateway: Gateway) -> None:
        self._gateway = gateway
        self._channels: dict[str, Channel] = {}

    def register(self, channel: Channel) -> None:
        if channel.name in self._channels:
            raise ValueError(f"duplicate channel: {channel.name}")
        self._channels[channel.name] = channel

    def send(self, name: str, message: Message) -> Receipt:
        try:
            channel = self._channels[name]
        except KeyError as exc:
            raise ValueError(f"unknown channel: {name}") from exc
        return self._gateway.deliver(channel.prepare(message))

    def available_channels(self) -> tuple[str, ...]:
        return tuple(sorted(self._channels))
