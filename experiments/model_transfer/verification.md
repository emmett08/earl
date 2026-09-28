# Investigation verification

Protocol **5.0.0**, package **2.17.0**, EAL/2. Primary plan/result schemas are
`/4`; diagnostic and information-design schemas are `/2`. The scientific
protocol schema is **1.2** and the investigation remains **specified**.
The baseline is GitHub commit `86f2f13b6c57a78433c68529136e99d8d28756d1`.
No live model requests were made for this change.

## Executed checks

| Check | Actual result |
|---|---|
| Baseline regression check | 35 existing information-design and diagnostic tests passed before implementation. |
| Scientific protocol validator | VALID at specified status, zero errors and zero warnings. |
| Integrated verification | `make check`: 884 passed, 1 skipped; ANTLR 4.13.2 generated sources and the maintained CLI/MCP example passed. |
| Final statistical regression | 31 tests passed after the final screening-policy change, covering information planning and all new investigation components. |
| Principal scripted rehearsal | 384 sequences, 4,224 sessions, 6,528 synthetic API attempts; 83 calibration checks passed. All 4,224 answers passed annotation import; original rows unchanged and resources reproduced by offline analysis. |
| Component diagnostic rehearsal | 10 donors and 46 recipients, 66 synthetic attempts; 27 calibration checks. All 38 pairwise manipulation checks passed. Annotation and reconstruction passed. |
| Cadence diagnostic rehearsal | Six donors and 30 recipients, 42 synthetic attempts; 23 calibration checks. Annotation and reconstruction passed. Two frequent-change reuse comparisons correctly remain invalid for actual-reuse attribution because both policies recollect. |
| Complete cadence calibration | 215 checks passed across all 18 cases and eleven snapshots. No model requests. |
| Statistical operating characteristics | Eight known generating processes, 1,200 independent paired trajectories per replication; 1,000 replications per scenario, except 10,000 at the saving boundary. All declared calibration checks passed. |
| Distribution | `make build` produced the 2.17.0 wheel and source archive. |
| Workflow and diff | Manual dispatch only; live execution defaults off. `git diff --check` clean. |

The JSON records in [validation/rehearsals.json](validation/rehearsals.json)
retain rehearsal summaries, raw/derived file fingerprints, invalid contrast
reasons and the full cadence calibration results. These are software observations,
not model performance evidence. Full generated request/session directories are
reproducible outputs rather than repository source files.

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

Use fresh output paths. The scientific validator belongs to the
`design-scientific-investigations` skill; run its `validate_investigation.py`
against `experiments/model_transfer/protocol.json` when that skill is installed.

The full 12,672-session cadence comparison was calibrated, not executed. Actual
allocation adequacy still requires complete live pilot observations and their
fresh-seed simulation assessment. Independently authored tasks and measured
adoption work must be supplied before making those broader claims. The USD 2 and
7,200-second per-run limits remain in force. Historical results under earlier
protocols are retained unchanged and are not evidence for protocol 5.0.0.
