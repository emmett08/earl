# GitHub workflow for the prospective v3 study

`.github/workflows/architecture-extension-v3.yml` has two paths. Pull requests
and `workflow_dispatch` with `live=false` install the pinned Python environment,
verify the pre-run freeze, run the EAL, host, study and debt-tool tests, and
exercise a deterministic P1 plain collector and P2 EAL MCP round trip against
the same frozen A source. The validation artifact retains packets, host state,
the staged trial and baseline assessment. It creates no v3 coding outcome.

[Workflow amendment 1](study/WORKFLOW-AMENDMENT-1.md) records the operational
repair after run 36331015150. The original freeze and failed outcomes are
retained. The active freeze records observed outcomes and the amended apparatus;
new results belong to a separate development exercise.

`workflow_dispatch` with `live=true` requires `OPENAI_API_KEY` for Codex stages
and `ANTHROPIC_API_KEY` for Claude Code stages. Start a new dispatch with a distinct
block ID after a failed acquisition. `live=false` also checks the pinned Codex
sandbox without provider calls. A failed-jobs-only retry cannot assemble inputs
from a previous workflow attempt.

## Assignment and source flow

Run `python experiments/architecture_extension_v3/study/freeze.py verify`
before dispatch. The host job reads its frozen random clone assignment:
`R-K1..3` and `W-K1..3` each map to P0, P1 or P2. One block contains exactly
six independently cloned B–C–D sequences and 18 coding episodes. All arms
within a family and stage use the same requested model, agent class, effort,
CLI version, tool permission set and 30-minute model invocation cap. The
class/model may differ between B, C and D, provided the choice is made before
the block. More than one block needs a separately versioned allocation and
analysis; this workflow accepts one block for the frozen pilot.

For B, the host starts every clone from the exact v2 A source. For C, it uses
that clone's verified B source; for D, its verified C source. P1 obtains a
current plain deterministic packet; P2 obtains the corresponding EAL/2 packet
from a real recipient-only MCP assessment. P0 obtains no packet. The B→C
collection compares A with B, and the C→D collection compares B with C.
`host.py prepare` stages only the source, existing tests and architecture
document, `AGENTS.md`, the **current** `FEATURE.md`, and P1/P2's
`architecture-context.json`. It writes `exposure.json` with exact hashes.
The user prompt passed to either CLI is the current feature brief alone;
`AGENTS.md` directs the agent to the separately staged packet if assigned.
The packet-only intervention uses the host's scoped `explain` command for
operator audit after the run, not for agent retrieval during coding.

Coding jobs have **no repository checkout**. They download one trial artifact,
check its top-level entries, and cannot see the host's independent assessor,
later briefs or other clones on the local runner filesystem. The source and
briefs are committed in a public PR, so a network-enabled agent could still
retrieve them externally; this is workspace withholding rather than a claim
of complete secrecy. Codex runs with `workspace-write` using distribution Bubblewrap and its loaded AppArmor
profile; Claude Code runs in
restricted mode with file tools but without Bash. Those tool differences
belong to the agent-class block, so model-class comparisons across blocks
cannot isolate model identity. Within each three-arm family-stage block the
tool affordance is held constant. The host reruns the independent assessor
only after the coding job ends. A source-only `host.py snapshot` verifies
the original brief and packet hashes, removes episode sidecars and caches,
and carries code to the next stage.

The direct Codex CLI receives `CODEX_API_KEY` for the invocation. Its own
command tools may read process environment, even though the code job has no
checkout and the sandbox restricts network. Exact occurrences of both
provider keys are redacted from retained artefacts; that post-run step does
not prevent runtime access. A dedicated short-lived key and review of the
run artefacts are necessary for this manual feasibility route. A secure proxy
action could reduce credential exposure, but would need a verified way to
retain the complete token ledger before replacing this route.

## Dispatch input

`model_blocks` is a JSON array with **one** object. This example keeps the
same class/model for B, C and D:

```json
[{"id":"pilot","b_class":"codex_cli","c_class":"codex_cli","d_class":"codex_cli","b_model":"gpt-6-sol","c_model":"gpt-6-sol","d_model":"gpt-6-sol","b_effort":"medium","c_effort":"medium","d_effort":"medium"}]
```

A prespecified cross-class sequence can use Codex for B and D and Claude
Code for C; each stage remains matched across P0, P1 and P2:

```json
[{"id":"mixed","b_class":"codex_cli","c_class":"claude_cli","d_class":"codex_cli","b_model":"gpt-6-sol","c_model":"claude-sonnet-5","d_model":"gpt-6-sol","b_effort":"medium","c_effort":"high","d_effort":"medium"}]
```

The defaults pin `@openai/codex@0.154.0` and
`@anthropic-ai/claude-code@2.1.283`; the job records the actual CLI version
and binary digest. The requested model label does not prove the provider's
backend revision. A mismatch, missing usage trace, unavailable key or package,
model timeout, absent stage artifact or changed sidecar is a retained
deviation. It is never replaced with a successful retry under the same
assignment.

## Artifacts and interpretation

`attempt-{attempt}-input-{stage}-{block}-{clone}` contains only `trial/` and `exposure.json`.
`attempt-{attempt}-episode-{stage}-{block}-{clone}` additionally retains the CLI JSONL trace,
stderr, start/end/exit records, version and invocation metadata, including
failure attempts. `attempt-{attempt}-host-pre-B-{block}-{clone}` and
`attempt-{attempt}-host-{stage}-{block}-{clone}` retain host state and metrics, exact packet,
source snapshot/manifest, independent assessment, exposure verification and
parsed usage where available. Each artifact is retained for 30 days; copy
the run's artifacts to durable study storage before expiry.

The compare job downloads assigned episodes and host artifacts only from the
current workflow attempt. It prints assembly diagnostics in the job log.
`study/assemble.py` recomputes the brief and packet hashes, joins each host
source to its independent assessment, checks exposure and the 30-minute
timeout record, and emits `ledger.json`. Missing or inconsistent attempts
produce `partial_acquisition` with named errors, and the job fails after
uploading that record. A complete acquisition invokes `study/analyse.py` for
the exact 18 episodes, replays the assessor, and produces `analysis.json`.
`masked_review` is initially `unresolved`; the architecture judgement and
any 25% local time criterion remain **not adjudicated** until independent
masked reviews are recorded in a versioned ledger and the analyser rerun.

`workflow_ledger.py` records model token classes and the Claude CLI's
client-side cost estimate when supplied by the trace. It reports monetary
cost as missing until dated provider rates, billing classes and runner rates
are supplied; it does not mistake static complexity or the debt-model
scenario for observed maintenance cost. Token usage may be missing after a
failed invocation. The 30-minute cap applies to each model invocation,
whereas preparation, queueing, collector and assessment times are separately
recorded. The pilot's primary local time comparison is conditional on all
independent invariants and the masked architecture review, as specified in
`study/PROTOCOL.md`.

The manual live path is an acquisition harness for one selected codebase and
two task families. Even a favourable local result would motivate independent
systems and a registered replication before a general technical-debt claim.
