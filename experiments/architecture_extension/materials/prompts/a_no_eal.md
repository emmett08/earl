You are an AI coding agent implementing a request from Engineer 2. Work only
inside the supplied isolated notification_service fixture. Read ARCHITECTURE.md
and the existing code before editing. Implement feature A: an email channel.

Acceptance contract: make_service registers `email` alongside `console`.
`send("email", Message(destination, subject, body))` returns a receipt with
medium `email`, the same destination, and UTF-8 content exactly
`Subject: <escaped subject>\n\n<escaped body>`, where both fields use
`html.escape(text, quote=True)`. Delivery goes through the supplied gateway
once. Existing console and unknown-channel behaviour must continue working.
Add tests for the new behaviour and run the complete local test suite.

Keep the public `send(name, Message)` API. Implement the smallest coherent
change. At the end, report changed files, the test command/result, and any
known limitation. Do not edit files outside this isolated fixture.
