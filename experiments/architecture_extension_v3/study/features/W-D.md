# Bounded ordered event delivery

The event sink imposes a batch limit. Extend `CheckoutService.retry_events` to
accept an optional positive integer `max_events`. Each call publishes at most
that many pending events and returns the number it published. Omission drains
the pending outbox as before. Deliver events in the order they were recorded
across ordinary and substituted orders, even when an earlier attempt failed.
If publication of an event fails, retain that event and every later one for a
subsequent call. A retry must never reissue payment, reserve stock or dispatch
shipments, and must never publish an already acknowledged event twice.

Reject zero, negative or non-integer limits without publishing anything.
For five pending orders and `max_events=2`, successive healthy calls return
`2`, `2`, `1`, then `0`. The same ordering and limit hold when a warehouse was
closed or a carrier substitution occurred. Preserve the earlier checkout,
availability, fallback, compensation and idempotency behaviour.
