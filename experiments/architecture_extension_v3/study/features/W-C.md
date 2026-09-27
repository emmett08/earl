# Carrier rejection and warehouse substitution

A carrier may reject dispatch from one warehouse for a particular order. Add
`InMemoryShipping.reject_warehouses`, a set of warehouse IDs whose dispatch
attempts fail for the current order; the rejection identifies the affected
warehouse. An order whose initial allocation includes a rejected warehouse
must seek unused stock from other currently open warehouses in priority order,
substitute those allocations and dispatch successfully if enough stock exists.
No final shipment or event may refer to the rejected source. Charge only once,
and leave final stock deducted only for the warehouses that actually supplied
the order. Preserve the original requested quantities and quoted price.

For `north=2`, `south=2`, `east=3` in priority order and a three-unit request,
rejection of `north` permits a two-unit `south` shipment and a one-unit `east`
shipment. When no open alternative can cover the rejected units, compensate
all partial shipments, release every reservation, refund the charge once and
record no completed order or event. A retry of a fully compensated request
may succeed after the carrier rejection clears. A successful request ID
remains idempotent, and an event publication retry never redispatches.
Preserve warehouse availability behaviour.
