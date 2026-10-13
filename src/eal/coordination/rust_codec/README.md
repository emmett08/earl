# Persistent MAS codec

This crate preserves the supplied MAS Protocol Lab envelope version `1` and
compositional Rust `nom` parser. It changes execution lifetime, not the wire
grammar or EAL/3 reasoning semantics. `UPSTREAM.json` records the original
source digests; `LICENSE` retains the toolkit's MIT notice. The grammar,
validator and formatter in `src/lib.rs` retain the supplied implementation.
The encoder's validation path is factored to return its final typed result as
well as canonical wire text.

Build and test from this directory with the pinned Rust toolchain:

```sh
cargo test --locked
cargo build --release --locked
```

The binary is `target/release/mas-protocol-codec`. Existing `parse` and `encode`
commands read one bounded UTF-8 input and produce the supplied JSON response.
`admit` reads the same JSON envelope as `encode`, performs exactly the same
source recognition, typed validation, canonical formatting and final wire parse,
and returns that final canonical typed message directly. It removes an additional
encode/parse round trip by reusing work already performed inside Rust.
`serve` keeps the same implementation in one process and reads newline-delimited
JSON control requests from stdin:

```json
{"operation":"parse","source":"message \"m\" run \"r\" from \"a\" to \"b\" version \"1\" kind \"request\" payload {};","max_bytes":65536,"max_depth":32}
```

Each request has exactly these four fields. Duplicate or unknown fields, invalid
field types, trailing input, and unsupported operations are rejected. Successful
responses are `{"ok":true,"message":{...}}` for parsing or admission and
`{"ok":true,"text":"..."}` for encoding. Errors retain the codec response
shape `{"ok":false,"error":{"code":"...","message":"...","line":null,"column":null}}`;
syntax errors may include source locations.

Responses are flushed after every request. Ordinary request errors do not stop
the process. A control frame over `6 * (65536 + 256) + 1024` bytes is rejected
and the process stops, avoiding unbounded reads or ambiguous resynchronization.
This framing allowance covers JSON escaping; the original source and wire size,
depth, Unicode, integer, identity and duplicate-payload-key limits still apply.
The service owns no files, network connections, mailbox or subprocesses. On Linux,
`serve` registers `PR_SET_PDEATHSIG(SIGKILL)` and checks the parent ID around
registration. Parent death therefore terminates even a stopped codec. Other
platforms rely on stdin EOF for healthy-child exit and caller-owned process
termination; they do not provide the Linux stopped-grandchild guarantee.
