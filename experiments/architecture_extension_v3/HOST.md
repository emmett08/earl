# Current-source assessment host

`host.py` runs a bounded assessment of one immutable source snapshot before a
coding episode. The agent's direct user request is the selected requirement
brief. The host gives P0 no architecture packet, P1 a plain deterministic
packet and P2 an EAL/2 claim packet through a real recipient-only MCP server.
P1 and P2 use the same `snapshot_probe.py` checks, source-impact hypotheses,
architecture guidance and verification choice. P2 additionally records the
authored route, its claim status and defeater disposition. The source-impact
map is a host-specified review hypothesis derived from public requirements
and the A-stage ports; it is not a required implementation plan.

The checks verify the code-tree digest, run the **candidate-visible** unittest
suite, parse production imports and inspect six original port declarations,
injection and effect call sites. A missing old port file is a migration
finding; malformed Python, changed source during acquisition or an unavailable
collector fails collection. The import and effect checks are syntactic.
Neither arm sees the sealed `study/assess.py` or its findings before finishing
the episode. A retained port signature and passing visible tests do not prove
that an implementation meets the new feature. The EAL migration route gives
review guidance without declaring replacement conformance.

The source-tree digest excludes `AGENTS.md`, `FEATURE.md` and
`architecture-context.json`; these are agent-visible inputs with **separate
SHA-256 values** in the exposure manifest. `prepare` permits only the selected
brief and the arm's packet. `snapshot` verifies those bytes after coding and
carries only source files into the next episode. A trial is an exported
directory, not a filesystem security boundary when agents share a local
scratch filesystem. The live workflow places host-only study files outside
the coding job's downloaded artefact.

## Commands

Use the project environment (`python -m pip install -e '.[dev]'` if needed).
Each assessment needs a new host-only state directory. This example assesses
the frozen A source before family R, feature B:

```bash
python experiments/architecture_extension_v3/host.py assess \
  --baseline experiments/architecture_extension_v2/results/snapshots/a \
  --candidate experiments/architecture_extension_v2/results/snapshots/a \
  --family R --feature B --arm P2 --state-dir /tmp/rb-p2-host
python experiments/architecture_extension_v3/host.py prepare \
  --source experiments/architecture_extension_v2/results/snapshots/a \
  --brief experiments/architecture_extension_v3/study/features/R-B.md \
  --family R --feature B --arm P2 \
  --packet /tmp/rb-p2-host/packet-P2.json \
  --destination /tmp/rb-p2-trial --record /tmp/rb-p2-exposure.json
```

P1 uses `--arm P1` and `packet-P1.json`; P0 uses `prepare --arm P0`
without a packet or prior assessment. After the coding attempt:

```bash
python experiments/architecture_extension_v3/host.py snapshot \
  --trial /tmp/rb-p2-trial --record /tmp/rb-p2-exposure.json \
  --destination /tmp/rb-p2-clean --manifest /tmp/rb-p2-source.json
```

For P2, a reviewer with access to the host state can reopen the precise
recipient-scoped MCP explanation using `host.py explain --state-dir ...
--assessment-id ...`. The coding agent has no such endpoint in the pilot.
`mcp-wire.json` retains exact request and response UTF-8 lines, their hashes,
tool inventory and call results; `metrics.json` binds its digest. A supported,
uncontested and untruncated claim uses assess and finish on the routine path.
A contested or truncated claim fetches its scoped explanation immediately;
otherwise `explain` fetches it only when an operator requests it and stores a
separate `mcp-explain-wire.json`. P1 retains
its direct tool request/response hashes in `plain-collector-trace.json`.
The packet cap is 3,072 UTF-8 bytes. Detailed traces remain host-side.

## Performance and evidence limits

The [reproducible benchmark](benchmark_host.py) records one warm-up and five
interleaved repetitions per arm on the same frozen A tree, with all measured
observation digests equal. Its [result](results/host-benchmark.json) reports
packet bytes, host elapsed time, host and waited-child CPU, MCP phase time and
tool exchange bytes. `--eager-explain` is a same-revision P2 ablation: it
fetches the full scoped explanation on every clean assessment to quantify
deferral. This measures host apparatus, not model tokens, agent
latency or accepted feature cost. The static check cache is keyed by candidate
and baseline trees, feature, interpreter and pinned collector bytes; it is
confined to one host state. Candidate-visible tests are never cached. The
measured cache effect on this small fixture is negligible, so no cost-saving
claim follows. `--disable-cache` reproduces the uncached P2 comparator.

The separate [technical-debt model](technical_debt/README.md) can be assessed
on demand with its own pinned TOML and EAL source. Its incomplete empirical
ledger yields `not_estimable`; a synthetic calculation does not turn this
current-source review into evidence of future debt reduction. Running that
model on every code edit is not on this host's critical path.
