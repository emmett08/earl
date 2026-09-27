# Interval reservation service

Each room has capacity one. Intervals are half-open, `[start, end)` in
integer minutes, so a booking ending at minute 60 and one starting at 60
do not conflict. The active booking index in `InMemoryCalendar.bookings` is
the authority for availability. `conflicts()` checks that index, with an
optional set of booking IDs excluded when changing an existing reservation.

The calendar lock protects the booking index, customer-scoped command
identity and completed events together. Failed commands have no effect.
`commands` retains historical results for identical request replay; a
different operation or payload cannot reuse the same customer/request pair.
The current feature brief supplies further constraints for compound changes.
