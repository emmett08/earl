# D: cancel a whole bundle after movement

Add `ReservationService.cancel_bundle(customer_id, bundle_request_id,
request_id) -> CancelReceipt`. Find the completed original bundle by its
customer-scoped reservation request ID. If *every* constituent booking is
active and owned by this customer, deactivate all of them atomically,
record one `Event("BundleCancelled", customer_id, request_id,
booking_ids)`, and return `CancelReceipt(customer_id, request_id,
booking_ids)`. The cancellation must operate on the booking IDs, including
after a move; the original reservation receipt is historical and its
interval may be stale.

Reject a missing bundle, partial prior cancellation, wrong customer or a
request collision without effect. A matching cancellation retry returns
the same receipt with no repeated effects. A subsequent new reservation may
occupy the released rooms and interval. Preserve all earlier behaviour,
including historical replay of reserve and move commands after cancellation.
