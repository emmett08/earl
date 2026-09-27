# Entitlement study fixture

Only `source/` and the current stage brief are copied to a coding episode.
`host/` contains independent, cumulative assessment and its positive
control. B exchanges seats without exceeding capacity, C shrinks capacity
with explicit displacements, and D reconciles access-token issuance.

Contested premise for the D decision test: “An issuer timeout tells whether
a token was committed.” Source-derived evidence in `source/service.py`
contains both `fail_before_issue`, which raises before append, and
`lose_next_ack`, which appends before raising. Either unconditional retry or
unconditional completion can be wrong. The safe choice is to query by
account and request ID, complete exactly once if a matching token exists,
leave an empty result retryable, and reject conflicting issuer outcomes.
This host note defines expected assessment; it is never copied to a coding
clone.
