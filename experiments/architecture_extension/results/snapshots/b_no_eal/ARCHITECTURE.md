# Notification fixture architecture

`NotificationService` is the only application dispatch entry point. It resolves
one named `Channel` from its registry, calls `prepare`, and delivers the returned
`Payload` once through a `Gateway`. `prepare` validates and encodes before a
delivery side effect. Each medium lives in its own channel module. The
composition root `make_service` registers the available channels. Public
callers continue to use `send(name, Message)`.

The in-memory gateway records payloads for deterministic functional checks. It
does not model a real email or SMS provider, latency, retries, throughput or
delivery success. A size cap applies to the encoded UTF-8 byte count, not Python
characters, and must fail before calling the gateway.
