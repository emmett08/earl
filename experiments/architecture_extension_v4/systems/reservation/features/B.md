# B: reserve a room bundle atomically

Add `ReservationService.reserve_bundle(room_ids, start, end, customer_id,
request_id) -> BundleReceipt`. `room_ids` is a nonempty tuple of distinct
registered rooms in caller order. Reserve the same half-open integer-minute
interval in every room, or reserve none. A conflict in any room, invalid
interval, duplicate or unknown room, or missing identity is rejected with no
booking, command, or event effect. Existing single-room reservations still
participate in conflict detection.

Return a `BundleReceipt(customer_id, request_id, booking_ids, room_ids,
start, end)` with one booking ID per room in the same order. Append one
`Event("BundleReserved", customer_id, request_id, booking_ids)` after the
whole reservation is committed. A matching request replay returns the
original receipt without repeated effects; a reused customer/request pair
with different operation or payload fails. Different customers may reuse
the same request ID. Preserve baseline behaviour.
