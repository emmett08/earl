# Architecture extension experiment, v2

This directory contains a separate, more demanding successor to the frozen [notification-channel case](../architecture_extension/). The [paper](paper.md) reports the completed local sequence: one EAL-assisted split-fulfilment change, followed by two partial-return implementations from an identical A snapshot. The [protocol](PROTOCOL.md), [feature briefs](materials/features/) and [pre-run manifest](materials/freeze.json) preceded the coding sessions. The observed B comparison is a tie on the 15 fixed probes; a condition-masked, post-run review found a narrower refund-failure distinction and labelled it exploratory.

Run the deterministic checks from the repository root:

```bash
python experiments/architecture_extension_v2/freeze.py verify
python experiments/architecture_extension_v2/replay.py
```

`replay.py` verifies retained hashes, reruns the frozen finite assessor and metric collector, and checks the exported ASPIC view. It does not recreate the stochastic coding sessions. The primary local runner requested `gpt-6-sol` at medium reasoning effort; the collaboration interface did not expose the internal model revision or raw agent tool transcript. Exact wrappers, final agent reports, source snapshots, patches, assessment JSON, metric JSON, MCP context packets and losslessly compressed host wire records are under [`results/`](results/). The [Cloud Browser screenshots](screenshots/) show the imported formal ASPIC graph.

The GitHub workflow is a separate, manually dispatched operational replication path. It is not the source of the local results in the paper. Its requested agent class/model and job logs must be reported with each new execution.
