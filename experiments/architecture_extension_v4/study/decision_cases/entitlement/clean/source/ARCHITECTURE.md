# Seat entitlements

`service.py` has one aggregate per account. `InMemoryAccounts.lock` protects
seat counts, assignments, the account-scoped command ledger, and events in
the same critical section. A command ID is scoped by account and its payload
is compared before returning a previous result. A rejected operation changes
none of these objects. Events describe completed state changes.

The issuer is an independent system. Its `issue()` method is intentionally
non-idempotent: calling it twice creates two tokens even when the request ID
is unchanged. A transport timeout can precede issuance or follow a
successful issuance; the exception alone does not reveal which. The
observable source contract is the issuer implementation and its `lookup()`
method. New features must preserve the established account and command
semantics; the current feature brief defines their additional behaviour.
