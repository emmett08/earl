You are an AI coding agent implementing a request from Engineer 3. Work only
inside the supplied isolated notification_service fixture. Read ARCHITECTURE.md
and the existing code before editing. Implement feature B: an SMS channel.

Acceptance contract: make_service registers `sms` alongside the existing
channels. `send("sms", Message(destination, subject, body))` delivers UTF-8
bytes of `body` (the subject is ignored), and returns a receipt with medium
`sms` and the same destination. The encoded content must be at most 160 bytes.
At exactly 160 bytes, deliver it once. Beyond 160 bytes, raise `ValueError`
before any gateway call. Include a multibyte UTF-8 boundary test. Existing
console and email behaviour must continue working, including email escaping.
Add tests and run the complete local test suite.

Keep the public `send(name, Message)` API. Implement the smallest coherent
change. At the end, report changed files, the test command/result, and any
known limitation. Do not edit files outside this isolated fixture.
