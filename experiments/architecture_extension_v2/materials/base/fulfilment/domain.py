"""Immutable business records used across the fulfilment ports."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


CENT = Decimal("0.01")


class FulfilmentError(Exception):
    """A business operation cannot complete."""


class IdempotencyConflict(FulfilmentError):
    """A request key was reused with different inputs."""


class OutOfStock(FulfilmentError):
    """Inventory cannot cover every requested unit."""


class CompensationFailure(FulfilmentError):
    """A failed checkout left an external operation requiring reconciliation."""

    def __init__(self, original: Exception, errors: tuple[Exception, ...]):
        self.original = original
        self.errors = errors
        super().__init__(f"{original}; {len(errors)} compensation operation(s) failed")


@dataclass(frozen=True)
class RequestedLine:
    sku: str
    quantity: int

    def __post_init__(self) -> None:
        if not self.sku or type(self.quantity) is not int or self.quantity <= 0:
            raise ValueError("a line needs a SKU and a positive integer quantity")


@dataclass(frozen=True)
class CheckoutRequest:
    request_id: str
    customer_id: str
    lines: tuple[RequestedLine, ...]
    address: str
    payment_token: str

    def __post_init__(self) -> None:
        if not all((self.request_id, self.customer_id, self.address, self.payment_token)):
            raise ValueError("request, customer, address and payment token are required")
        if not self.lines or len({line.sku for line in self.lines}) != len(self.lines):
            raise ValueError("lines must be nonempty and have distinct SKUs")


@dataclass(frozen=True)
class QuotedLine:
    sku: str
    quantity: int
    unit_price: Decimal
    unit_tax: Decimal
    line_total: Decimal
    line_tax: Decimal


@dataclass(frozen=True)
class Quote:
    lines: tuple[QuotedLine, ...]
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    currency: str


@dataclass(frozen=True)
class Allocation:
    sku: str
    quantity: int
    warehouse_id: str


@dataclass(frozen=True)
class Reservation:
    reservation_id: str
    allocations: tuple[Allocation, ...]


@dataclass(frozen=True)
class Charge:
    charge_id: str
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class Shipment:
    shipment_id: str
    allocations: tuple[Allocation, ...]
    address: str


class DispatchFailure(FulfilmentError):
    """Carrier failure with every shipment created before the failure."""

    def __init__(self, message: str, partial_shipments: tuple[Shipment, ...] = ()):
        self.partial_shipments = partial_shipments
        super().__init__(message)


@dataclass(frozen=True)
class Order:
    order_id: str
    request_id: str
    request_fingerprint: str
    customer_id: str
    address: str
    quote: Quote
    reservation: Reservation
    charge: Charge
    shipments: tuple[Shipment, ...]
    status: str


@dataclass(frozen=True)
class Event:
    event_id: str
    name: str
    order_id: str
    data: tuple[tuple[str, str], ...]
