"""Small notification fixture for the architecture extension experiment."""

from .bootstrap import make_service
from .model import Message, Payload, Receipt
from .service import NotificationService

__all__ = ["Message", "Payload", "Receipt", "NotificationService", "make_service"]
