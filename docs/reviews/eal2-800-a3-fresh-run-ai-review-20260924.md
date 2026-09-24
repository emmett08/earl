# Independent AI review: deployment-800 A3 fresh run

Date: 2026-09-24. Reviewer: repository/publication agent, separate from the
campaign author. Decision: **accept this exact zero-call A3 freeze for paid
execution**. A1, A2 and C1 remain separate diagnostics and are not pooled into
the A3 result.

| Object | SHA-256 |
| --- | --- |
| `benchmarks/experiments/deployment-800/run_a3.py` | `ec9afdb597022230e839290f9cf0e566acf3724057d6e98098861f9667e9f182` |
| `benchmarks/experiments/deployment-800/plan-a3.json` | `b751ff58bd72e500531729e7449f587c95da087263a1a32ca71801495f72b301` |
| `benchmarks/experiments/deployment-800/postcall-review-protocol-a3.json` | `fbf031ae9e4699a50240497e43b51c811ed91970a5057087513cd9d429933a11` |
| A3 freeze file, `paid-deployment-800-a3-pre-review-v2/freeze.json` | `c917a410aad0bdeefda4c2320b374a23cde0d0759057062bb986265a41f920cc` |
| A3 internal digest | `6adcab0e1d342990e81dca3e414799285e4bbf161097d01570dc7f184b6dbfbf` |

The ledger was frozen with zero provider requests. Recomputed `verify()` and a
freeze-only run pass. The 800 distinct assigned case IDs are 384 fixed, 96
author (32 groups with three linked turns), and 320 recipient. The fixed
stage is balanced over 96 assignments per format/instruction cell and 48 per
model/delivery cell (eight cells, including 96 total actual native function
requests). The final author response for each group is the only candidate
used by its ten isolated recipient sessions. Author turn messages include
only their own prior responses. All 24 root/state EAL and independent graph
statuses, source/record/scope hashes, provider identities, accepted synthetic
AI review, capability probe and post-call selection protocol are pinned.

A3 prospectively allows one identical-payload retry per assigned slot only
after a response-less HTTP 500–504, with a fixed one-second delay. Both
requests retain separate IDs, prompt and native-operation digests, response,
usage, latency and unknown-charge reserves. Provider adapters have no hidden
retry. A final author failure stops before dependent turns; three consecutive
or eight total double-failed assigned slots stop later batches. Other provider,
usage, identity, parsing-integrity and budget faults stop after already
dispatched peers finish. Pending requests and terminal ledgers cannot resume.
The version reviewed here fixed an earlier concurrent terminal-status race:
the retry acquires the same lock as the peer stop and checks terminal status
before creating another pending request.

I ran the four focused schedule/native-tool tests (4 passed). An independent
scratch-only fake-provider run confirmed a first HTTP 500 followed by the
same slot's success records two requests and one retry; another fake run
confirmed a simultaneous HTTP 500/HTTP 400 stops with two logged requests
and no post-stop retry. No actual provider request was made in these checks.
Every new request atomically reserves its full conservative charge before
dispatch, then reconciles measured configured-rate cost. The base allocation
reserves `$41.601638` against a `$45` cap; any additional retry consumes the
remaining allowance or a released measured reserve. Unknown invoices are
represented by reserved bounds, not reported as measured zero.

This is a new execution of the same developmental schedule, after the A1/A2/C1
diagnostics were observed. It is not an independent fresh draw of tasks, nor
the original fully crossed 800-call protocol. A3 has **800 assigned slots**;
actual API requests may exceed 800 by the number of logged retries. The
precommitted post-call review samples 32 final author products and 48
explanations without outcome-based replacements, but is independent-from-author
AI review, not masked human adjudication. The corpus is synthetic, and total
all-in cost per qualified decision remains unavailable until review effort,
host/evidence cost, and actual billing are reconciled. This sign-off is invalid
if any listed runner, plan, selection protocol, freeze, source material,
provider identity or evidence-basis digest changes before paid calls.

I also checked the derived predeclared selection file
`benchmarks/experiments/deployment-800/predeclared-review-slots-a3.json`
(SHA-256 `7e03bee4e828b109b175966c9d442f4e7954f3fcb5a4d7c40574cc7476fd7127`).
It binds the exact A3 freeze and protocol, lists all 32 final author turns in
index order, and selects the same 48 explanation cases as an independent
implementation of the protocol's root/state rotation and case-ID hash rule:
16 fixed-direct, 16 fixed-host-owned and 16 authored-recipient slots.
