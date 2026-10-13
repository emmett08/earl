# First paired coordination pilot

Sixteen actual native-agent contexts executed: an assessor and a fresh reviewer
for each of four synthetic cases in each arm. The host obtained packets through
actual EAL MCP processes. The protocol arm used the supplied Rust/nom codec and
SQLite mailbox; model-produced proposals entered subsequent reviewer contexts
only after reference and task-scope checks.

| Case | Structured JSON | EAL-aware protocol |
| --- | --- | --- |
| Passing synthetic sample | Exact answer | Exact answer |
| Stale observation | Exact justified-unresolved answer | Exact justified-unresolved answer |
| Requested build differs from report | Handoff rejected; safe null statuses, wrong conclusion label | Handoff rejected; safe null statuses, wrong conclusion label |
| Synthetic 2% failures | Exact measured-failure answer | Exact measured-failure answer |

Both arms scored **3/4 exact answers**. The build-mismatch reviewers used
`unresolved` instead of the frozen contract's `out_of_scope`. Their requested
build and null claim statuses were preserved, and neither asserted production
support. These first attempts were retained and scored as failures.

The pilot showed **no output improvement** from the additional protocol.
Structured JSON remains the default. The protocol prototype establishes the
tested durable delivery/reference path, rather than better reasoning or lower
total cost. Model token/billing receipts and development costs are unavailable.

The planned alternating arm order was not achieved: network provisioning forced
all baseline runs to precede all protocol runs. One pre-live method-worker
startup timeout was retained in [preparation-001.json](../preparation-001.json)
and setup succeeded when retried serially with unchanged limits. No live trial
was repeated or repaired. Six terminal review messages remain pending for their
completed assessor recipients; the claimed consumed model messages are the six
proposals delivered to subsequently executed protocol reviewers.

[report.json](report.json) retains all eight case-arm outcomes, actual external
execution identities, timing definitions, accounting gaps, file hashes, limits
and deviations. Each run directory retains worker inputs, exact native outputs
and coordinator state; protocol runs additionally retain mailbox receipts and
status. Host mediation and complete proposal/review templates make this a
handoff-preservation pilot, not an autonomous-discovery benchmark. Native
contexts were separate; shared filesystem isolation was enforced by role
instructions rather than an operating-system sandbox.

Validation passed: 67 repository checks across protocol, cases, recording and
transport; 25 Lab Python tests; five Rust parser tests; locked release build.
The Rust crate's binary and documentation targets have no tests and are not
included in the five-test count.
