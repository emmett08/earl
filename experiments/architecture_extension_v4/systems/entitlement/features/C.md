# C: shrink with explicit displacement

Add `EntitlementService.shrink(account_id, new_seats, displaced_user_ids,
request_id) -> tuple[str, ...]`. A successful call decreases the seat limit
to a positive integer. The caller passes `displaced_user_ids` as a tuple
that explicitly identifies exactly the current users to remove if the new
limit cannot hold the current assignment count. This tuple must have length
`max(0, current_assignments - new_seats)` and
contain distinct assigned users. Do not choose displaced users silently.
Remove those assignments, set the new limit, return the displaced IDs in
the caller's order, and emit one `Event("Shrunk", account_id, request_id,
",".join(displaced_user_ids))`.

Reject a limit that is unchanged or greater, non-positive or non-integer
limits, any incorrect or duplicate displacement, or a reused command ID
with different operation or payload. A rejected call has no account or
event effect. The same request and payload returns the original tuple
without repeating removal. Earlier exchange retries retain their recorded
result even after an account is shrunk. Preserve all earlier behaviour.
