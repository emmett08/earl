# Preliminary transport profiling

This development run retains four repetitions of the original four arms and
their diagnostic profiles. All 16 samples passed the recorded equivalent
content and useful-state checks, and actual launch logs identified repeated
MCP startup and codec process invocation as costs worth removing.

Rust source and the compiled executable changed during execution when the
process-lifetime guard was added. The start manifest therefore does not
describe one unchanged executable throughout this run. Benchmark
instrumentation was also expanded after execution. These samples are
**preliminary profiling evidence**, and their ratios are not the final
performance result.

The source-frozen five-arm evaluation is retained in
[transport-005](../transport-005/README.md), including the Rust admission
candidate, explicit codec first-use labels, isolated premature/wrong-recipient
ACK rejection checks, and an end-of-run source-stability check.
