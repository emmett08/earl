# B: atomic seat exchange

Add `EntitlementService.exchange(account_id, departing_user_id,
arriving_user_id, request_id) -> Assignment`. It replaces an existing
assigned user with a previously unassigned user in the same account, without
opening a temporary second seat. The returned assignment carries this
request ID. An exchange on a full account is valid. Reject unknown account,
empty identifiers, an absent departing user, an already assigned arriving
user, and identical departing and arriving users without effect.

One completed exchange emits one `Event("Exchanged", account_id, request_id,
arriving_user_id)`. The original assignment remains available only as
historical command data. Identical retries return the original result with
no repeated event or seat change; a reused request ID with different
operation or payload fails without effect. Keep account-scoped identity, and
preserve baseline assignment and release behaviour.
