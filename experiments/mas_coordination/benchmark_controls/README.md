# Frozen transport controls

The `snapshot` Python sources are byte-identical copies from commit
`2c76dcedfc19a59445c7b39478b812b3b09d7cda`. `source-map.json` maps their
original paths and SHA-256 hashes to the retained copies and the original
`results/transport-005/manifest.json`. The original evidence remains unchanged;
its source hashes describe that measured implementation, not current production.

`make_control` selects the intermediate persistent-MCP/one-shot-codec or
persistent-MCP/persistent-codec/round-trip-admission arms. They execute the frozen
server and supervisors, with an explicit codec executable. The legacy one-shot
MCP baseline remains in `benchmark_legacy`. The final Rust-admission arm always
uses the active `eal.coordination.lab_mcp.LabMCPTransport` implementation.

The copied `snapshot/transport_benchmark.py` records the original runner source;
run the maintained `experiments.mas_coordination.transport_benchmark` module to
exercise the frozen controls and current production together. Every new run
records both source sets and executable hashes in its own manifest. Do not relabel
historical results as measurements of the cleaned runtime.

These experiment adapters and CLI snapshots are not part of the installed EAL
package. Production has one persistent MCP/Rust-admission execution path; the
codec encode/parse inspection operations remain available there.
