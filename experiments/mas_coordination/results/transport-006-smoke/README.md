# Transport cleanup smoke

One actual software workload per arm passed after the production cleanup.
All five arms retained identical canonical envelopes and equivalent useful
mailbox states; [source stability](source-stability.json) found no changed
measured source during execution.

The maintained runner exercises the legacy one-shot baseline, frozen
persistent-MCP/one-shot-codec and persistent-codec/round-trip controls, current
persistent Rust admission, and durable JSON. Intermediate implementations now
live exclusively in [benchmark controls](../../benchmark_controls/README.md).
The production package excludes the deleted CLI transport and these snapshots.

[The manifest](manifest.json) hashes current production, frozen controls and
executables; [raw samples](raw-samples.json), per-arm launch logs, admitted
envelopes and final states retain the actual execution. This is a functional
cleanup check, not a new performance estimate or a model trial. The original
[transport-005 performance evidence](../transport-005/README.md) is unchanged.
