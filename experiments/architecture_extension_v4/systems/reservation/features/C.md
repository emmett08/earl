# C: move a room bundle without dropping its identity

Add `ReservationService.move_bundle(customer_id, bundle_request_id,
new_start, new_end, request_id) -> BundleReceipt`. The first request ID
identifies a completed `reserve_bundle` for this customer; the second is
this move's new command ID. Every bundle booking must still be active and
owned by the customer. Move all of them to the new half-open interval in
one locked operation, retaining their booking IDs and room order. When
checking availability, exclude exactly these bundle bookings. Reject a
conflict with any *other* booking, invalid or unchanged interval, missing
bundle, reused ID with different payload, or partially inactive bundle
without changing bookings, commands or events.

Return a new `BundleReceipt` with `request_id` equal to the move command ID
and the moved times. Append one `Event("BundleMoved", customer_id,
request_id, booking_ids)`. Identical retries return that original receipt
without moving again, even if the bundle subsequently changes. The earlier
reservation receipt also remains a historical result; reading current
booking times requires `calendar.bookings`. Preserve baseline and B.
