# Pre-continuation amendment 0.1.2 — independent terminal failures

**Date:** 24 September 2026 UTC. **Status:** fixed after one 0.1.1 pilot call
and before any further call. This amendment changes execution control, not the
cases, prompts, model requests, scoring rules, schedule, arms or cost ceilings.
The first response and the reason it was invalid were inspected before this
amendment; consequently the continued Stage A run is developmental and cannot
be described as a prospectively untouched experiment.

An assigned call that reaches a terminal outcome no longer stops independent
scheduled assignments merely because its response is refused, malformed,
invalid against closed identifiers, returned by an unexpected model identity,
or lacks provider usage. It remains in the denominator with its exact failure
code and is never retried. The conservative reservation remains charged to the
study budget when usage is unknown. This matches the protocol's requirement
to analyse system success including failures rather than selecting only valid
answers.

Execution still stops before another request when there is an unresolved
write-ahead `pending` event, because sending that assignment again could
duplicate a billed call. It also stops before a request that would exceed the
frozen cumulative cap. The full schedule remains dependent on all 72 pilot
assignments having terminal outcomes, but it does not require all 72 outcomes
to be valid. Calls within the pilot and calls remaining in the full schedule
are otherwise independent.

The earlier 0.1.1 freeze and stopped ledger remain unchanged. A continuation
may copy that ledger, verify the first call's request identifier and request
hash against the new 0.1.2 freeze, and append the remaining assignments under
the new freeze digest. This is an explicit provenance transition, not a retry.
The completed composite pilot ledger is then the prior ledger for the 0.1.2
full freeze. Freeze schema `eal2-bias-freeze/2` declares execution policy
`continue_after_terminal_outcome/1` so the changed stopping contract cannot be
confused with the historical plan.
