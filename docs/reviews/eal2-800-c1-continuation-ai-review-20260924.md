# Independent AI review: deployment-800 A2-C1 continuation

Date: 2026-09-24. Reviewer: repository/publication agent, separate from the
campaign author. Decision: **accept this exact frozen continuation for paid
execution**, subject to its recorded failure and budget stops. This is a code
and input-integrity review, not an independent review of the model answers.

## Exact object reviewed

| Object | SHA-256 |
| --- | --- |
| `benchmarks/experiments/deployment-800/continue_unattempted.py` | `33b1cff8737c3c5826ffc806c52ca2e7983990479071be4fadd5bf779d279c12` |
| C1 freeze file, `paid-deployment-800-c1-reviewed/continuation-freeze.json` | `cf43a586703a30c32f5c52d3a728f5678d3023a11937cae077571c9b21ac5a19` |
| C1 internal continuation digest | `b6e2dbf3784cff0b456321a3fbdd964d73f5f02a9aa6b69fb9812e938f93d117` |
| Source A2 freeze file | `4c55e3a030600a76ee9d359307c3fb8cfd0bc716f299b225f323f1b2a3ee2b5f` |
| Source A2 ledger file | `de0333ace03f223e4f4cca9dee34770929f0c47bab4b007f775d1ffa092ec732` |
| Recomputed evidence-basis digest | `360b22a2b1de9f90c94e06ef0617fbd462793e86200b04eb9dc6e402c307d8a0` |

The C1 ledger was `frozen`, with zero attempts at review. The source A2 ledger
has exactly indices 0–127: 127 completed and one failed no-usage HTTP 500 at
index 125. C1 assigns precisely the unattempted IDs `deployment-0128` through
`deployment-0799` (672 cases). It neither reassigns nor retries index 125.

## Checks and repairs

- Recomputed `sources()` from pinned A2 freeze, ledger, materials, provider
  identities, and current EAL/graph evidence states; `execute(...,
  freeze_only=True, resume=True)` returned 672 assigned and zero attempted.
- Checked that the fixed-stage prompt is read literally from the A2 freeze.
  Dynamic author and recipient prompts are constructed after their upstream
  responses and then stored verbatim with digest in the C1 ledger. The sole
  permitted schedule reconstruction difference is the host acquisition trace's
  volatile timestamps and collection IDs; source, graph, records, scope,
  claim, and status are recomputed and pinned as the evidence-basis digest.
- Inspected the fail-closed attempt audit: source 128 cases are excluded;
  persisted C1 attempts must be a prefix of actual dispatch order, have a
  matching prompt digest and resolved status, and match the failure list.
  Pending attempts block resumption, and terminal ledgers cannot re-enter.
- Earlier drafts had an in-flight budget reservation gap and a resumed-ledger
  failure-threshold gap. This reviewed version reserves every dispatched call
  atomically under a lock. It checks both total failures and maximum
  consecutive failures already persisted before dispatch; each concurrent
  batch also checks a threshold crossed within the batch. A scratch-only
  synthetic ledger with three eligible failures followed by a success
  terminalized without sending a provider request.
- C1 retains the A2 unknown-billing allowance of `$0.12672`, and reserves the
  full configured upper bound for each new response-less eligible HTTP 500–504.
  The source known configured charge is `$0.1793467`; the campaign cap is `$45`.
  It stops after a batch on the third consecutive eligible failure, the eighth
  total including A2, or any noneligible error, identity, usage, integrity, or
  budget failure. Already dispatched concurrent calls remain in the ledger.

## Limits

The unknown charges are reservations, not an invoice or evidence of actual
billing. The per-case upper bound assumes the configured prompt/output limits
and provider rates. The study's synthetic evidence and its earlier fixture
reviews support a developmental comparison only. A terminal stop may leave
fewer than 800 cases attempted; unattempted cases must remain explicit in the
analysis. This approval is invalid if the runner, freeze, A2 inputs, or
evidence-basis digest change before the first C1 call.
