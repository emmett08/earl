"""Host-only positive control; not copied into a coding episode."""

from __future__ import annotations

from service import (Booking, BundleReceipt, CancelReceipt, Event,
                     ReservationService)


class ReferenceService(ReservationService):
    def reserve_bundle(self, room_ids, start, end, customer_id, request_id):
        if not customer_id or not request_id or type(room_ids) is not tuple:
            raise ValueError("identity and tuple of rooms required")
        self.validate_interval(start, end)
        with self.calendar.lock:
            key = (customer_id, request_id)
            operation = ("reserve_bundle", room_ids, start, end)
            if key in self.calendar.commands:
                previous, result = self.calendar.commands[key]
                if previous != operation:
                    raise ValueError("request collision")
                return result
            if (not room_ids or len(set(room_ids)) != len(room_ids) or
                any(room not in self.calendar.rooms or
                    self.calendar.conflicts(room, start, end) for room in room_ids)):
                raise ValueError("invalid or occupied rooms")
            ids = []
            for room in room_ids:
                booking_id = f"booking-{len(self.calendar.bookings) + 1}"
                self.calendar.bookings[booking_id] = Booking(booking_id, room, start, end, customer_id)
                ids.append(booking_id)
            receipt = BundleReceipt(customer_id, request_id, tuple(ids), room_ids, start, end)
            self.calendar.commands[key] = (operation, receipt)
            self.calendar.events.append(Event("BundleReserved", customer_id, request_id, tuple(ids)))
            return receipt

    def _bundle(self, customer_id, bundle_request_id):
        operation, receipt = self.calendar.commands[(customer_id, bundle_request_id)]
        if operation[0] != "reserve_bundle":
            raise ValueError("not a bundle command")
        bookings = [self.calendar.bookings[i] for i in receipt.booking_ids]
        if any(not booking.active or booking.customer_id != customer_id for booking in bookings):
            raise ValueError("bundle not wholly active")
        return receipt, bookings

    def move_bundle(self, customer_id, bundle_request_id, new_start, new_end, request_id):
        if not customer_id or not bundle_request_id or not request_id:
            raise ValueError("IDs required")
        self.validate_interval(new_start, new_end)
        with self.calendar.lock:
            key = (customer_id, request_id)
            operation = ("move_bundle", bundle_request_id, new_start, new_end)
            if key in self.calendar.commands:
                previous, result = self.calendar.commands[key]
                if previous != operation:
                    raise ValueError("request collision")
                return result
            original, bookings = self._bundle(customer_id, bundle_request_id)
            if all((b.start, b.end) == (new_start, new_end) for b in bookings):
                raise ValueError("unchanged interval")
            excluded = frozenset(original.booking_ids)
            if any(self.calendar.conflicts(b.room_id, new_start, new_end, excluded) for b in bookings):
                raise ValueError("room occupied")
            for booking in bookings:
                booking.start, booking.end = new_start, new_end
            receipt = BundleReceipt(customer_id, request_id, original.booking_ids,
                                    original.room_ids, new_start, new_end)
            self.calendar.commands[key] = (operation, receipt)
            self.calendar.events.append(Event("BundleMoved", customer_id, request_id, original.booking_ids))
            return receipt

    def cancel_bundle(self, customer_id, bundle_request_id, request_id):
        if not customer_id or not bundle_request_id or not request_id:
            raise ValueError("IDs required")
        with self.calendar.lock:
            key = (customer_id, request_id)
            operation = ("cancel_bundle", bundle_request_id)
            if key in self.calendar.commands:
                previous, result = self.calendar.commands[key]
                if previous != operation:
                    raise ValueError("request collision")
                return result
            original, bookings = self._bundle(customer_id, bundle_request_id)
            for booking in bookings:
                booking.active = False
            receipt = CancelReceipt(customer_id, request_id, original.booking_ids)
            self.calendar.commands[key] = (operation, receipt)
            self.calendar.events.append(Event("BundleCancelled", customer_id, request_id, original.booking_ids))
            return receipt
