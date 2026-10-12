# Persistent MCP and Rust admission benchmark

Five counterbalanced repetitions of five equivalent software workloads passed
all frozen content, delivery, budget and durable-state checks. The final Lab
path used one MCP server and one persistent Rust codec per workload, reducing
the median paired useful-cycle time by **22.07×** compared with the frozen
per-operation implementation.

This is a deterministic transport measurement on one local host. No model
inference, task-output accuracy, token consumption or provider billing was
measured. The wire grammar remains the Lab envelope version `1`; benchmark
payloads identify `EAL/MAS-coordination/3`.

## Measured stages

All times are milliseconds. Each row is the median of five workload samples.

| Arm | Useful cycle | Cold first MCP/create operation | Operations after create | Actual process starts |
| --- | ---: | ---: | ---: | ---: |
| Frozen per-operation MCP and codec | 10,758.669 | 472.597 | 10,273.283 | 61 |
| Persistent MCP, one-shot codec | 629.583 | 398.252 | 225.723 | 37 |
| Persistent MCP and codec, round-trip admission | 518.846 | 398.952 | 117.832 | 2 |
| Persistent MCP and codec, Rust admission | 486.493 | 396.542 | 87.534 | 2 |
| JSON/SQLite semantic control | 20.482 | 1.305 | 18.752 | 0 |

The useful-cycle timer includes creation, reservation/completion, delivery
operations, correctness assertions and launch-log accounting. It excludes
construction, the final diagnostic call and shutdown, which have separate raw
fields. Per-operation timers exclude launch-log accounting. JSON remains
faster in this workload and does not perform the Rust wire-parser checks.

Operations after create include lazy startup of the persistent codec on its
first send. Raw samples label that codec first use separately, and the
per-operation `excluding_first_use` summaries omit it. These post-create totals
are not labelled pure steady-state timings.
First-use-excluded send summaries contain different payload-size subsets
across arms; matched comparisons use complete-cycle or post-create totals.

The median paired useful-cycle ratios were:

| Comparison | Before / after |
| --- | ---: |
| Per-operation implementation / persistent MCP | 17.089× |
| Persistent MCP / persistent MCP and codec | 1.212× |
| Persistent codec round-trip admission / Rust admission | 1.052× |
| Per-operation implementation / final Rust admission path | 22.070× |

For operations after create, the five round-trip/Rust-admission ratios were
`[1.3540, 1.3930, 1.2990, 1.3206, 1.4142]`, with median **1.3540×**. Cold MCP
initialization dominates the full persistent workload, so admission's effect
on the complete cold cycle is smaller.

## What justified the Rust change

The preliminary profile identified repeated server/session startup as the
largest original cost. After persistence, the server still performed 18 Rust
encode and 18 parse operations for nine sends, plus a separate encoding MCP
call for every send. The final admission path performs nine Rust `admit`
operations and combines encoding/admission into one MCP request per send.
Rust retains the canonical typed representation obtained during validation.

This comparison measures Rust admission **and pipeline batching**. It does
not isolate programming-language speed. SQLite continues to own durable
mailbox transactions and budgets; EAL reasoning semantics remain unchanged.

Actual launch logs substantiate the process counts: the frozen workload
started 23 MCP servers, two CLI processes and 36 codecs; the final workload
started one MCP server and one codec. The final server's runtime diagnostics
record one codec start, zero separate encode/parse calls and nine admit calls.

The median CPU totals were 10.5685 seconds for the frozen path and 0.5403
seconds for the final path. CPU accounting includes construction, the
diagnostic call and shutdown, using parent plus reaped-child CPU; its scope is
broader than the useful-cycle timer.

## Workload and evidence

Each sample uses the same run/message identities, fixed payloads with 256,
4,096 and 61,440 padding bytes, and a fresh SQLite database. It checks new
delivery, identical duplicates, changed-content rejection, premature ACK
rejection, wrong-recipient ACK rejection after receive, redelivery, correct
ACK, empty pending delivery, and one immutable completed call reservation.
Every sample ends with three received/ACKed messages, 67,013 canonical JSON
bytes, one completed reservation and identical evidence. A five-position
cyclic Latin square balances each arm's order position once; it does not
balance every adjacent carryover pair.

The [raw samples](raw-samples.json), [report](report.json), [plan](plan.json)
and [manifest](manifest.json) retain all 25 outcomes. Individual sample
directories contain accepted envelopes, final status and actual process
launch logs. The [source-stability check](source-stability.json) confirms that
all 24 hashed source/executable inputs remained unchanged during execution.
The benchmark's current `PATH` did not expose Cargo/Rustc, which the manifest
records as unavailable; build verification is recorded separately by the
implementation validation.

[Codec-only measurements](codec-microbench/report.json) compare one-shot and
persistent execution of the exact same compiled binary. Twelve encode/parse
round trips per size passed. Warm median encode times changed from 1.507 to
0.106 ms for 256-byte padding, and from 1.996 to 0.576 ms near the byte bound.
Those measurements exclude MCP, SQLite and model inference. Separate parent
and server main-thread profiles are retained under `profiles/`; their
cumulative timings include import/startup and waiting and are not labelled
parser CPU.

No final sample failed. The development run in
[transport-004](../transport-004/README.md) is retained as preliminary because
Rust source/executable hashes changed during that run. It is not used for
the final speed ratios. These finite paired results support this workload;
they do not establish general MAS accuracy or population performance.

The [implementation validation](validation.json) records correctness and
installed-package checks, including the separately verified Rust toolchain.
After timing completed, two fresh host-agent contexts performed a separate
[native audit exchange](native-audit/result.json): the reporter authored its
findings, Rust admitted the message, and the checker consumed, independently
verified and acknowledged it. Both actual execution identities and receipts
are retained. Shared report/raw-artifact reads were declared in the audit plan.
This demonstrates a genuine exchange through the new transport; it measures
no inference speed or model accuracy, and tokens/billing remain unknown.

Reproduce from the repository root after building the documented Rust codec
and installing the isolated Lab runtime:

```sh
.venv/bin/python -m experiments.mas_coordination.transport_benchmark \
  --output /tmp/eal-transport-benchmark \
  --repetitions 5 --profile --codec-microbench
```
