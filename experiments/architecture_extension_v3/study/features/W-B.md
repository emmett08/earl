# Warehouse availability

Orders can be placed while a warehouse is temporarily unavailable. Add
`InMemoryStock.set_warehouse_open(warehouse_id, open)` to change its current
availability; reject an unknown warehouse. New reservations skip closed
warehouses and allocate from open warehouses in their configured priority
order. Do not alter the stock or historical shipments of an already completed
order when availability changes.

For `north=2`, `south=2`, `east=3` units of a SKU in that priority order, a
three-unit order with `north` closed takes two from `south` and one from
`east`, charges once, and emits an event with actual source allocations. If
open warehouses cannot supply all units, reject the request without changing
inventory, payment, shipments, order history or events. Reopening a warehouse
makes its stock available for later orders. Preserve split dispatch,
compensation, idempotency and event retry.
