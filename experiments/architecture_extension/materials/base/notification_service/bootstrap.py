"""Composition root for the sample application."""

from .channel import Gateway
from .console import ConsoleChannel
from .service import NotificationService


def make_service(gateway: Gateway) -> NotificationService:
    service = NotificationService(gateway)
    service.register(ConsoleChannel())
    return service
