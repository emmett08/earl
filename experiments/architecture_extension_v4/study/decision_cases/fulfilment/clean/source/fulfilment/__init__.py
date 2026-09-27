"""An executable baseline for the architecture continuation experiment."""

from .domain import (
    Allocation, Charge, CheckoutRequest, CompensationFailure, DispatchFailure, Event,
    FulfilmentError, IdempotencyConflict, Order, OutOfStock, Quote, QuotedLine,
    RequestedLine, Reservation, Shipment,
)
from .memory import (
    InMemoryEventSink, InMemoryOrderStore, InMemoryPayments, InMemoryPricing,
    InMemoryShipping, InMemoryStock,
)
from .service import CheckoutService

__all__ = [
    "Allocation", "Charge", "CheckoutRequest", "CheckoutService", "CompensationFailure", "DispatchFailure",
    "Event", "FulfilmentError", "IdempotencyConflict", "InMemoryEventSink",
    "InMemoryOrderStore", "InMemoryPayments", "InMemoryPricing", "InMemoryShipping",
    "InMemoryStock", "Order", "OutOfStock", "Quote", "QuotedLine", "RequestedLine",
    "Reservation", "Shipment",
]
