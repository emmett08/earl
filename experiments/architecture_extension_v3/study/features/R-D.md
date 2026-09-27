# Reconcile a refund acknowledgement loss

A payment provider can apply a refund and then lose the acknowledgement. Add
a deterministic in-memory failure mode `InMemoryPayments.fail_after_refund`:
when enabled for a new refund key, the provider applies and records the refund
once, then raises a `RuntimeError`. The provider must make the status of that
key available as `refund_status(key)`, returning `"applied"`, `"not_applied"`,
or `"unknown"`. Repeating an applied key never moves money again. `unknown`
may be simulated without assuming that the refund happened or did not happen.

Checkout rollback, partial return and cancellation must remain safe under
acknowledgement loss. A retry using the same request ID must reconcile an
applied refund, finish the remaining inventory and record/event transitions
once, and must not issue another refund. If status is `not_applied`, retry may
attempt it once using the same stable key. While the status is `unknown`, the
operation must remain unresolved and visible to the caller; neither a fresh
conflicting request nor an event may assume it completed. A subsequent known
status allows the original request to finish. Preserve the earlier successful
paths and the total-refund ceiling.
