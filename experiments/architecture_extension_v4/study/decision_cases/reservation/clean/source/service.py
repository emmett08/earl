"""Room reservations over half-open integer-minute intervals.

The baseline uses one active-booking index and a customer-scoped command
ledger. Later briefs add compound booking operations against the same index.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass
class Booking:
    booking_id: str
    room_id: str
    start: int
    end: int
    customer_id: str
    active: bool = True


@dataclass(frozen=True)
class BundleReceipt:
    customer_id: str
    request_id: str
    booking_ids: tuple[str, ...]
    room_ids: tuple[str, ...]
    start: int
    end: int


@dataclass(frozen=True)
class CancelReceipt:
    customer_id: str
    request_id: str
    booking_ids: tuple[str, ...]


@dataclass(frozen=True)
class Event:
    name: str
    customer_id: str
    request_id: str
    booking_ids: tuple[str, ...]


class InMemoryCalendar:
    def __init__(self) -> None:
        self.rooms: set[str] = set()
        self.bookings: dict[str, Booking] = {}
        self.commands: dict[tuple[str, str], tuple[tuple[object, ...], object]] = {}
        self.events: list[Event] = []
        self.lock = RLock()

    def conflicts(self, room_id: str, start: int, end: int,
                  excluding: frozenset[str] = frozenset()) -> bool:
        return any(booking.active and booking.room_id == room_id and
                   booking.booking_id not in excluding and
                   start < booking.end and booking.start < end
                   for booking in self.bookings.values())


class ReservationService:
    def __init__(self, calendar: InMemoryCalendar) -> None:
        self.calendar = calendar

    def add_room(self, room_id: str) -> None:
        if not room_id:
            raise ValueError("room ID required")
        with self.calendar.lock:
            if room_id in self.calendar.rooms:
                raise ValueError("room exists")
            self.calendar.rooms.add(room_id)

    @staticmethod
    def validate_interval(start: int, end: int) -> None:
        if type(start) is not int or type(end) is not int or start >= end:
            raise ValueError("integer half-open interval required")

    def reserve(self, room_id: str, start: int, end: int,
                customer_id: str, request_id: str) -> Booking:
        if not customer_id or not room_id or not request_id:
            raise ValueError("all IDs required")
        self.validate_interval(start, end)
        with self.calendar.lock:
            if room_id not in self.calendar.rooms:
                raise ValueError("unknown room")
            command = (customer_id, request_id)
            operation = ("reserve", room_id, start, end)
            if command in self.calendar.commands:
                previous, result = self.calendar.commands[command]
                if previous != operation:
                    raise ValueError("request ID reused with different content")
                return result  # type: ignore[return-value]
            if self.calendar.conflicts(room_id, start, end):
                raise ValueError("room occupied")
            booking_id = f"booking-{len(self.calendar.bookings) + 1}"
            booking = Booking(booking_id, room_id, start, end, customer_id)
            self.calendar.bookings[booking_id] = booking
            self.calendar.commands[command] = (operation, booking)
            self.calendar.events.append(Event("Reserved", customer_id, request_id, (booking_id,)))
            return booking

    def cancel(self, booking_id: str, customer_id: str, request_id: str) -> None:
        if not customer_id or not request_id:
            raise ValueError("customer and request IDs required")
        with self.calendar.lock:
            command = (customer_id, request_id)
            operation = ("cancel", booking_id)
            if command in self.calendar.commands:
                previous, _ = self.calendar.commands[command]
                if previous != operation:
                    raise ValueError("request ID reused with different content")
                return
            booking = self.calendar.bookings[booking_id]
            if booking.customer_id != customer_id or not booking.active:
                raise ValueError("not an active customer booking")
            booking.active = False
            self.calendar.commands[command] = (operation, None)
            self.calendar.events.append(Event("Cancelled", customer_id, request_id, (booking_id,)))
