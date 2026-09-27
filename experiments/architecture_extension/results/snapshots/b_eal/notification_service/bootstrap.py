"""Composition root for the sample application."""

from .channel import Gateway
from .console import ConsoleChannel
from .email import EmailChannel
from .service import NotificationService
from .sms import SmsChannel


def make_service(gateway: Gateway) -> NotificationService:
    service = NotificationService(gateway)
    service.register(ConsoleChannel())
    service.register(EmailChannel())
    service.register(SmsChannel())
    return service
