# Prospective architecture-evolution study materials

This directory freezes a **development and feasibility** follow-up to the v2
experiment. It contains two task families. `R` grows split fulfilment through
returns, cancellation, and payment acknowledgement loss; the latter was
informed by an exploratory v2 review. `W` tests a distinct warehouse-availability,
carrier-fallback, and bounded-outbox sequence. `W` is reserved before any v3
coding output is inspected. Neither family by itself represents all software.

The source anchor for every clone is the v2 A snapshot at
`../architecture_extension_v2/results/snapshots/a` relative to `experiments`.
The host copies only `fulfilment/`, its existing tests, `ARCHITECTURE.md`, and
the **current** feature brief to an agent worktree. It must not copy this study
directory, any future brief, the independent assessor, or another candidate's
results. The assessor runs outside each agent worktree.

Read [PROTOCOL.md](PROTOCOL.md) and [task-bank.json](task-bank.json) before
execution. `freeze.py create` writes a digest manifest and clone allocation before any v3 coding
session; `freeze.py verify` checks it. The assessor interface is:

```text
python experiments/architecture_extension_v3/study/assess.py \
  --candidate PATH --family R|W --stage B|C|D
```

It emits one JSON record containing `findings` with `pass`, `fail`, or `invalid`
for each independent probe. Later stages retain the earlier stage probes. An
import failure marks every due probe invalid. The assessor invokes the frozen
v2 A probes separately and never sends hidden cases to coding agents. Scores
must be read as a vector; an overall pass count cannot erase a critical
failure. Source review and actual later maintenance cost are separate measures.

The prospective study has no outcome until independently cloned, randomised
sequences run. In particular the v2 primary 15/15 tie and its post-run refund
case cannot be relabelled as v3 evidence.

Assessor apparatus checks against retained **older** snapshots: the v2 A
source passes the ten baseline/split checks and fails all five newly due R-B
return checks; each v2 completed B source passes R-B 15/15. The A source
passes the ten baseline/split checks and fails the eight W-B/C/D feature
checks. These expected capability differences verify assessor stage selection,
not an outcome or a comparison of v3 arms.

For registered workflow analysis, `analyse.py ledger.json` requires an object with
`schema_version: architecture-extension-v3/ledger/1`,
`status: complete_acquisition`, an empty `missing_or_invalid` list, 18 `runs` (every
`family` R/W × `arm` P0/P1/P2 × `stage` B/C/D), and `masked_review` mapping each
family to `no_worse`, `worse` or `unresolved`. Each run records its
`source_sha256`, `input_tree_sha256`, `output_tree_sha256`, masked `clone_id`,
`model_id`, `model_revision` (or `null` if unobservable), `agent_class`,
`packet_sha256` (`null` only for P0), the exact JSON from `assess.py` under
`assessor`, an accessible `candidate_snapshot_path`,
`coding_elapsed_seconds`, `host_assessment_seconds` (zero for P0),
optional `host_assessment_cpu_seconds` and `mcp_elapsed_seconds` and
nonnegative `packet_bytes`/`tool_exchange_bytes`,
`wall_cap_enforced: true`, and optional complete
`token_usage`/`cost_gbp` values. Keep raw action timestamps, usage invoices,
packets and source snapshots alongside the ledger. The analysis refuses a
missing or unbounded episode, recomputes the host whole-tree and assessor
Python/doc subset digests independently, verifies the exact due hidden case
set, reruns the independent assessor on each sealed snapshot, and returns only
local descriptive contrasts. These are two distinct
hash recipes; the subset digest must never be compared directly with the host
whole-tree digest.

The separately registered [local feasibility exercise](LOCAL-FEASIBILITY.md)
may use collaboration agents when CLI credentials or exposure isolation are
unavailable. Its observations are development results and never fill a
workflow ledger slot.
