# Investigation verification

Protocol **6.0.0**, package **2.18.0**, EAL/2. Primary plan/result schemas remain
`/4`; diagnostic and information-design schemas remain `/2`. The new resumable
execution contract is `EAL/execution-contract/1`; scientific protocol schema is
**1.2** and investigation status remains **specified**. EAL syntax, observation
schemas and reasoning-method contracts are unchanged.

The implementation baseline is commit `810330d94946f5309acf785ee0906afef7f6aef5`.
No paid model requests were made for these changes. Rehearsal answers, annotations,
usage and dollar totals are deliberately scripted software inputs.

## Executed checks

| Check | Actual result |
|---|---|
| Scientific validation | Pinned validator self-test passed; both maintained protocols valid with zero errors and warnings. Source digests verified by regression test. |
| Integrated repository check | `make check`: 958 tests passed, one optional ASPIC reference test skipped. ANTLR 4.13.2 parser verification and the maintained CLI/MCP example passed. |
| Final interruption accounting check | 50 execution/diagnostic tests passed after conservative timing and collector-coverage hardening. |
| Full principal rehearsal | All 384 sequences, 4,224 sessions and 6,528 synthetic API attempts retained with four workers. All 4,224 answer codes imported; raw rows unchanged and resources reproduced offline. 83 calibration checks passed. |
| Component diagnostic rehearsal | Ten donors, 46 recipients, 66 synthetic attempts; 27 calibration checks. All 56 answers passed the annotation roundtrip, including JSON explanations. |
| Cadence diagnostic rehearsal | Six donors, 30 recipients, 42 synthetic attempts; 23 calibration checks. All 36 answers passed annotation and reconstruction. Frequent-change reuse can remain an invalid actual-reuse contrast because both policies recollect. |
| Complete cadence calibration | 215 checks passed across all 18 cases and eleven snapshots; no model requests. |
| Workflow inputs | Single-stage dispatch retains ten inputs; the ordered wrapper has seven. All four YAML files passed workflow-schema and reusable-call interface checks. Entry workflows are manual; the two supporting workflows are callable only. |
| Ordered wrapper | 22 targeted tests passed after final offline-reprocessing changes. Tests exercise deadline-only automatic continuation, cumulative reservations and hard-kill time leases, paid rerun rejection, frozen worker counts, and actual scripted collection across two artefact transfers with earlier attempts unchanged. |
| Wrapper annotation and allocation | Principal and diagnostic scripted observations passed actual export/import/analysis. Missing labels stop import. Reprocessing archives earlier derived records and clears stale evaluation plans. Synthetic observations cannot produce a supported evaluation allocation. |
| Wrapper principal preflight | The actual `rehearse` entry point completed 83 calibration checks, all 384 sequences / 4,224 sessions / 6,528 scripted requests, and imported 4,224 answer codes. Raw rows and resource totals were preserved. No live model requests. |
| Distribution | `make build` produced the 2.18.0 wheel and source archive. The source includes runtime constraints, the pinned validator, wrapper script and reusable workflows. |

Current complete-pipeline summaries and fingerprints are retained in
[validation/runtime-rehearsals.json](validation/runtime-rehearsals.json). The
older `validation/rehearsals.json` remains a baseline software record. Neither
file supplies empirical answers, human annotations or a supported evaluation
allocation. Raw generated rehearsal directories are reproducible local outputs.

[validation/wrapper.json](validation/wrapper.json) records the wrapper checks.
Its orchestration contract is `EAL/experiment-pipeline/1`; the measured
implementation digest remains
`dcd14a0c70a424fb0d138789595080f341c032873f70364fb2ce695e2b9152bd`.
The wrapper was exercised locally with scripted transport and artefact transfer
fixtures. GitHub-hosted orchestration and live-provider throughput have not been
executed for this change. Workflow structure/interface checks are distinct from
a completed hosted run.

Recovery tests cover bounded overlap, serial order within each matched pair,
unique receipt IDs, atomic budget admission, cancellation/deadline stops, exact
resume identity, exclusive run locks, retained hard-kill reservations, torn
journal recovery, cumulative segment leases, unchanged donor state, unknown
preparation duration and retirement of stale derived annotations. A finished
request is never retried. A complete run can be reopened without new API calls.

## Throughput and recovered observations

[validation/throughput.json](validation/throughput.json) records three alternating
one-worker/four-worker comparisons, Python/platform identity, code digest and
individual elapsed times. Each run has 16 sequences, 48 sessions and 80 synthetic
calls, with fixed 150 ms provider latency. Outcome, request-count and synthetic
cost equivalence are checked. The control is the same implementation using one
worker. The medians were 17.31 seconds with one worker and
5.17 seconds with four: **3.35× faster** under this controlled
load. This isolates scheduling without claiming a measured live-service speedup.

The cancelled run `36469096727`, artefact `10990314626`, retained ten complete
sequences, 116 sessions and 161 attempts. Offline reconstruction reports partial
status, USD 0.01880995 known API expenditure, USD 0.02075715 charged/reserved, and
one unfinished request with unknown final cost. API waiting accounted for about
93% of retained session elapsed time. These are partial observations under its
saved earlier protocol; they are not pooled into protocol 6.0.0. The archive
SHA-256 is `c09942d759682a900d2995f3cde0040b83f43a1d7464444fd64de0c23226e773`.

The run had no resumable execution contract. Its data can be analysed and coded,
but its paid requests are not replayed under a fabricated new contract. New runs
retain their actual contract, cumulative limits and previous segment reports.

## Statistical evidence

[design-validation.json](validation/design-validation.json) retains the actual
simulation counts, generating truths, seeds, uncertainty and checks. In the
beneficial reference scenario, joint success was 98.8% with a 95% Monte Carlo
interval of 97.91–99.31%. At the token-saving boundary, false success was 5.07%
(507/10,000; interval 4.66–5.52%). The other partial-null scenarios had no joint
successes in 1,000 replications each. The lowest simultaneous-coverage lower
Monte Carlo bound across scenarios was 96.81%.

These results support the declared numerical checks for the examined generating
processes. They do not prove a uniform error guarantee for arbitrary resource
populations. Resource inference remains approximate: the protocol declares 5%
nominal false success and 95% nominal coverage, with a one-percentage-point
numerical calibration tolerance. The practical effect thresholds are unchanged.

The initial 1,000-replication screening result is retained in
[design-validation-screening.json](validation/design-validation-screening.json).
Its saving-boundary false-success interval extended above 6%; that check failed.
Increasing boundary replication to 10,000 resolved simulation uncertainty without
changing the test or thresholds. Both outcomes remain visible. Reproduce the
screen using `--boundary-simulations 1000`; the default reproduces the refined
run. These operating-characteristic checks are distinct from the allocation
planner's independent, fresh-seed validation of screened candidates.

At zero observed paired correctness variance, the simultaneous empirical
Bernstein half-width is approximately 0.02500 at 1,024 pairs and 0.01666 at 1,536
pairs. The Hoeffding comparison at those allocations is 0.09670 and 0.07895.
Zero observed errors still yield nonzero uncertainty. These are conditional
method comparisons, not required sample sizes for a real population.

Tests additionally cover exact binomial one-sided tail probabilities, all endpoint
completions of a missing-outcome example, strict intersection-union boundaries,
restoration of resampling variance, budget/request replay, rare-tail failure,
missing usage, small pilots, fixed strata and exclusion of scripted allocation
proposals. Screening only rules out demonstrably inadequate candidates. Final
selection requires favourable adverse Monte Carlo bounds on new draws, adjusted
across candidates, scenarios and four gates. The default final replication is
10,000 per scenario.

## Task, mechanism and cost checks

The conventional reasoner agrees with the independent reference for all fourteen
existing cases and eighteen new fixtures at all eleven positions. A test replaces
both scoring entry points with failures and verifies that facts-only, conventional
and EAL diagnostic contexts still work. Inputs are identical across variants;
identical EAL/conventional conclusions produce identical model-facing messages.

Actual host tests confirm that an evidence revision invalidates reuse. Stable and
periodic fixtures reuse at the first recipient while the frequent fixture collects
again. Ordinary age limits still apply when a revision is unchanged. Cadence
calibration verifies later snapshots, not merely the initial state. Reuse
manipulations permit differing acquisition times only when both observations are
fresh; other task fields must agree. Failed or absent manipulations remain in the
report and denominator, with no component-effect attribution.

Manifest checks reject false answer keys, silently changed evidence, duplicate or
shadowed task identities, invalid scope/rules and nonmonotone revision records.
The 18 included cases are labelled internal synthetic fixtures. Provenance fields
are attestations, not authentication or evidence of external task validation.

Cost tests preserve unknown effort/rates, explicitly measured zero work, fixed
initial cost counted once, complete coverage requirements and run/plan identity.
The CLI writes new ledger versions and preserves earlier records. No human cost,
labour rate or adoption saving is supplied as an empirical observation.

## Reproduction and scope

Run from the repository root:

```bash
make check
make build
python -m experiments.model_transfer.validate_design --output /tmp/design-validation.json
python -m experiments.model_transfer.rehearse --plan experiments/model_transfer/plan.json --output /tmp/principal-rehearsal
python -m experiments.model_transfer.rehearse --plan experiments/model_transfer/diagnostic-plan.json --output /tmp/diagnostic-rehearsal
python -m experiments.model_transfer.rehearse --plan experiments/model_transfer/cadence-diagnostic-plan.json --output /tmp/cadence-diagnostic-rehearsal
python -m experiments.model_transfer.runner --plan experiments/model_transfer/cadence-plan.json --calibrate-only --output /tmp/cadence-calibration
```

Use fresh output paths. `make scientific` uses the pinned repository-local
validator and is included in `make check`; no installed personal skill is needed.
The [workflow guide](WORKFLOW.md) gives the stage order, inputs and resumption rules.

The full 12,672-session cadence comparison was calibrated, not executed. Actual
allocation adequacy still requires complete live pilot observations and their
fresh-seed simulation assessment. Independently authored tasks and measured
adoption work must be supplied before making those broader claims. The USD 2 and
21,600-second cumulative per-run limits remain in force, with at most
6,000 collection seconds per Actions segment. Historical results under earlier
protocols are retained unchanged and are not evidence for protocol 6.0.0.
