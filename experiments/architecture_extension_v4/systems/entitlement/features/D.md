# D: issue a token across an uncertain acknowledgement

Add `EntitlementService.issue_access(account_id, user_id, request_id)
-> IssueReceipt`. Only a currently assigned user may receive a token.
An identical retry returns the recorded receipt, even if the seat was
later released. Reuse of a request ID for a different operation or user
must fail without issuer or account effects. Completed issue emits one
`Event("AccessIssued", account_id, request_id, user_id)`.

`InMemoryIssuer.issue` can raise `TimeoutError` before an effect or *after*
committing a token.
The service must reconcile an uncertain outcome with
`issuer.lookup(account_id, request_id)` before another issue call. If a
matching token exists, record and return it without producing a second
token. If no matching token exists after a timeout, propagate `TimeoutError`
without recording a completed command or event; a later call with the same
request ID can try again. Reject a lookup containing conflicting user IDs
or multiple tokens with `ValueError`, without another issue call or account
effect. Preserve prior features and atomic command identity. The issuer
implementation and `ARCHITECTURE.md` are source-derived evidence; a timeout
alone proves neither success nor failure.
