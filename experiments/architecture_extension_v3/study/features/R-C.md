# Cancel a fulfilled order

Add `CheckoutService.cancel_order(order_request_id, cancellation_request_id)`.
For a dispatched order, cancel its still-active shipments, refund the amount
for units not already returned, restore only those units to their original
warehouses, retain the original order, shipment and return history, and record
one `OrderCancelled` event with the cancellation ID, affected allocations and
refunded amount. Return a `CancellationReceipt(cancellation_request_id,
refunded_amount)` exposing the cancellation ID and refunded amount. The order
must no longer accept new returns after cancellation.

For a three-unit order split `north=2`, `south=1`, after one `north` unit has
already been returned at £12, cancellation refunds the remaining £24 and
restores one unit to `north` and one to `south`. The cumulative refunds must
never exceed the original £36 capture. A cancelled order cannot be cancelled
again under a different ID. Retrying the same ID and content returns its
receipt without repeating a carrier, stock, refund or event effect; reuse of
the ID for a different order is an error. An unknown order is rejected without
effects.

If a carrier cancellation fails after another shipment has been cancelled,
the request remains recoverable under its original ID. Retrying it must
finish without repeating an earlier cancellation or financial/inventory
effect. Do not record a completed cancellation or publish its event until all
required external effects have completed. Transient event publication failure
remains retryable. Add the deterministic injection
`InMemoryShipping.fail_on_cancel_number`: when set to a positive call number,
that carrier cancellation call fails before mutating the shipment. This allows
recovery after one earlier cancellation to be checked. Preserve checkout and
return behaviour.
