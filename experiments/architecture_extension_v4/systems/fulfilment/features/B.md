# Partial returns

After an order has been fulfilled, a customer may return a subset of units on
its shipments. Add `CheckoutService.return_items(order_request_id,
return_request_id, lines)`, where `lines` is a tuple of
`ReturnLine(shipment_id, sku, quantity)` records. Return a
`ReturnReceipt(return_request_id, refunded_amount, lines)` for accepted
positive quantities. Refund each accepted unit's original quoted unit price
plus unit tax and restore it to the warehouse that supplied it. Preserve the
original order and shipment history; later returns cannot exceed the units
shipped in aggregate.

For an order with two £10 plus £2 tax units from `north` and one from `south`,
returning one `north` and one `south` unit refunds £24 and restores one unit to
each source warehouse. Reject an unknown order or shipment, non-positive
quantities, SKU mismatch, and cumulative over-return with no financial,
inventory, order, or event effect.

The same return request ID and content yields the original receipt without
repeating effects. Reuse with different content is an error. A refund failure
must leave stock and completed returns unchanged; a later retry of that ID can
complete. A failure after refund must not cause a second refund on retry.
Record a return event containing the request ID, shipment allocations and
refunded amount. A transient publication failure leaves the event available
for retry without repeating the return. Preserve existing checkout behaviour.
