# Fresh-session EAL workflow experiment

EAL/3 source, package **3.0.0**, protocol **7.0.0**, scientific schema **1.2**, status **specified**. The
[methodology](../../docs/eal3-experiment-methodology.md) defines the practical
decision, statistical assumptions, task populations and inference limits.
Implementation checks and synthetic validation do not establish a live benefit.
Start with the [ordered workflow and input guide](WORKFLOW.md) for local commands,
GitHub Actions settings, resumption, annotation and evaluation.
In **Actions → EAL experiment**, the defaults `start` and `comparison` run the
free checks, automatically chained collection segments, resource analysis and
masked annotation export. After independent coding, `finish` imports the labels,
analyses the results and runs allocation planning when applicable. The workflow
retains its data between these two dispatches without keeping a runner waiting.

## What the plans measure

| Plan | Purpose | Allocation |
|---|---|---|
| `plan.json` | Principal nuisance pilot on six authored cases; threshold calibration excluded | 384 sequences, 4,224 sessions |
| `diagnostic-plan.json` | Projection, notes, formatting, reuse and matched-fact reasoning | 10 donors, 46 recipients |
| `cadence-plan.json` | Separate finite synthetic population: six patterns × three cadences | 1,152 sequences, 12,672 sessions |
| `cadence-diagnostic-plan.json` | Reasoner and reuse within stable, periodic and frequent regimes | Six donors, 30 recipients |

These are scheduled counts. USD 2 and 21,600 seconds are cumulative per-run ceilings;
completion and statistical adequacy are not guaranteed. The principal comparison
retains ordinary prompting with natural notes. It does not give the ordinary arm
a curated runbook or tool cache. EAL receives its host-computed compact context.

Success at ten recipients requires lower one-sided bounds above all three
boundaries: correctness difference -0.05, absolute EAL correctness 0.90, and token
reduction 0.20. Initial token expenditure is included. Two-sided simultaneous
estimation intervals remain separate from this intersection-union decision.
Whole paired trajectories, not individual answers, are independent observations.
The plans use four concurrent paired blocks; sessions and both arms within each
pair stay serial. Collection segments stop after at most 6,000 seconds in Actions,
leaving 20 minutes of its two-hour job for setup, finalisation and upload. Resuming
the same run continues its original budget and time allowance.

## Install, calibrate and rehearse

From the repository root:

```bash
python -m pip install -c experiments/model_transfer/requirements.lock -e '.[dev]'
make scientific
python -m experiments.model_transfer.runner --calibrate-only --output /tmp/eal-calibration
python -m experiments.model_transfer.rehearse --plan experiments/model_transfer/diagnostic-plan.json --output /tmp/eal-diagnostic-rehearsal
python -m experiments.model_transfer.runner --plan experiments/model_transfer/cadence-plan.json --calibrate-only --output /tmp/eal-cadence-calibration
```

Use a new output directory each time. Rehearsal uses actual EAL collection and
assessment with explicitly scripted responses and usage. It checks annotation and
reconstruction without calling a model. The generated labels are software checks,
not human ratings or empirical answers.

## Live pilot and independent annotation

With `OPENAI_API_KEY` configured:

```bash
python -m experiments.model_transfer.runner --plan experiments/model_transfer/plan.json --output experiments/model_transfer/runs/pilot-001
python -m experiments.model_transfer.annotations export experiments/model_transfer/runs/pilot-001 --output /tmp/eal-annotation
```

The assessor receives the exported `items.json`, without reference answers or
arm labels. Complete its decision, quote and note fields and annotator identity.
Human coding is the default for existing schema-1 files. AI coding must add an
`assessor` object with `kind: "ai"`, `model`, `method`, `validation`, `protocol`
and `source_items_sha256` (the SHA-256 of the original masked `items.json`).
The importer preserves this provenance, records AI decisions as `ai`, and never
identifies them as human assessments. Analysis and allocation reports carry
`EAL/annotation-provenance/1` and qualify inference conditional on AI labels.
See [the retained pilot coding amendment](../../annotations/AI-CODING.md).
Save the completed assessor file as `/tmp/eal-labels.json`, then import it:

```bash
python -m experiments.model_transfer.annotations import experiments/model_transfer/runs/pilot-001 /tmp/eal-annotation /tmp/eal-labels.json --output /tmp/annotated-rows.json
```

Standalone canonical decisions can be coded automatically. Other nonempty prose
and every JSON answer, including its explanation, remain pending independent annotation; malformed or contradictory text is not
silently repaired. Use `--all` when exporting to audit automatic labels as well.
The independent reference evaluates task correctness separately from answer coding.

```bash
python -m experiments.model_transfer.analyse experiments/model_transfer/runs/pilot-001 --rows /tmp/annotated-rows.json --output /tmp/pilot-analysis.json
python -m experiments.model_transfer.plan_information experiments/model_transfer/runs/pilot-001 --rows /tmp/annotated-rows.json --output /tmp/information-report.json --evaluation-plan /tmp/evaluation-plan.json
```

The information procedure retains all scheduled units. Complete annotation,
reconciled resource/timing records and at least four complete repetitions per
stratum are required for empirical allocation. It includes variance correction,
unobserved-variation scenarios, each decision boundary, joint power, precision,
false success and fresh-seed Monte Carlo validation. Required tail and
missing-annotation failures block selection. Missing usage must produce an
inconclusive resource decision.

`evaluation-plan.json` is created only when a live pilot supports an allocation.
If it is absent, read the report's blockers, scenario failures and candidate
results. A paid run must not be enlarged merely because no allocation qualified.
An exported plan uses a new study identity and fresh observations; pilot outcomes
are never pooled into evaluation. Pass it to `runner --plan` with a new directory.
`--allow-scripted` only rehearses planning and can never export evaluation.
For the 18-case cadence population use `--config experiments/model_transfer/cadence-information-design.json`.
Runtime feasibility uses the plan's worker count and conservatively admits whole
concurrent batches. An evaluation must retain that scheduling choice.

## Independently supplied tasks

Use `evaluation-tasks.example.json` as the data-format example. Its 18 cases are
**internal synthetic fixtures**, not externally authored evaluation evidence.
Supply independently authored specifications and keys with author/reviewer
attestations, population and sampling rationale. Each task has eleven snapshots,
explicit revision events, scope, rules and expected decisions. Invalid or
contradictory records are rejected.

```bash
python -m experiments.model_transfer.task_manifest independently-authored-tasks.json --plan experiments/model_transfer/plan.json --output /tmp/independent-task-pilot.json
python -m experiments.model_transfer.runner --plan /tmp/independent-task-pilot.json --calibrate-only --output /tmp/independent-task-calibration
```

The output embeds the manifest and starts a separate pilot population. Match the
candidate `cases` count in a copied information configuration to that population;
the planner rejects automatic task selection or extrapolation to absent strata.
Cadence variants of one task remain related cases, not new task families.

## Reasoning and reuse diagnostics

The reasoner contrast supplies identical raw facts and rules, with either no
computed conclusion, an EAL conclusion, or a conventional-evaluator conclusion.
The conventional evaluator calls neither EAL nor the reference scorer. Matched
state, input equality and actual backend delivery are checked. Identical computed
conclusions produce identical model-facing packets; no intrinsic notation effect
is presumed. The report includes all pairwise contrasts and simultaneous bounds
at the independent donor-block level. Small pilots will commonly remain unresolved.

The cadence diagnostic varies reuse versus forced collection within each evidence
regime. Revision events invalidate earlier observations through the existing
context-aware acquisition identity. Revision detection is supplied by the fixture.
Acquisition counters measure local collection work; remote collector latency or
prices require actual measurements from that system.

## Authoring, maintenance and host costs

The primary token comparison is conditional on pre-authored source. Optional cost
measurement uses a run-bound ledger. Initialise one after obtaining the run ID:

```bash
python -m experiments.model_transfer.adoption_costs init RUN_DIRECTORY --ledger /tmp/costs-0.json
python -m experiments.model_transfer.adoption_costs record RUN_DIRECTORY --ledger /tmp/costs-0.json --output /tmp/costs-1.json --arm eal --category authoring --session 0 --seconds 1800 --hourly-usd 60 --evidence time-log-entry-001
python -m experiments.model_transfer.adoption_costs cover RUN_DIRECTORY --ledger /tmp/costs-1.json --output /tmp/costs-2.json --arm eal --category authoring --session 10 --evidence authoring-log-complete
python -m experiments.model_transfer.analyse RUN_DIRECTORY --rows ANNOTATED_ROWS --cost-ledger /tmp/costs-2.json --output /tmp/analysis-with-costs.json
```

The numbers above illustrate arguments; enter measured durations and justified
rates. Record both arms and all four categories: authoring, correction, maintenance
and host. Coverage is a measurement assertion across the whole study up to that
session; declare it only when the log is complete, including verified zero work.
Omitting `--hourly-usd` retains measured effort with unknown monetary value.
Incomplete coverage or rates leave total adoption cost unknown. Every edit writes
a new ledger version. Duplicate IDs, wrong run/plan identity and invalid units fail.

Reports separate API expenditure, each activity category, cumulative differences,
the first observed cost crossing and the correctness decision. A cheaper workflow
with inadequate correctness cannot establish the adoption claim.

## Reproduce statistical checks

```bash
python -m experiments.model_transfer.validate_design --simulations 1000 --pairs 1200 --output /tmp/design-validation.json
python -m pytest tests/test_investigation_improvements.py -q
make check
make build
```

The default command uses 1,000 replications per scenario and 10,000 at the
token-saving boundary. To reproduce the initial screening report, add
`--boundary-simulations 1000`; its calibration check deliberately fails because
the Monte Carlo interval was too wide. The refined run changes replication only.

The simulation command reports known generating truths, joint decisions, partial-null
false success, coverage, seeds and Monte Carlo uncertainty. Its numerical calibration
tolerance is one percentage point: nominal 95% coverage and 5% false success are
checked against 94% and 6% diagnostic limits. This qualifies approximate resource
inference and does not relax the practical quality or saving thresholds.

All workflows remain manually dispatched; live execution defaults to off. Raw
requests, answers, receipts, task snapshots, annotations, state and incomplete
units remain retained. Unknown usage is never zero expenditure. See
[verification.md](verification.md) for actual implementation evidence and
`results/` for unchanged historical observations.

The reuse manipulation permits acquisition timestamps to differ while both
observations remain fresh and all other task information agrees. Counts of
actual reuse and recollection are retained. In a frequent-change block,
compatible reuse may correctly recollect; that block cannot identify an effect
of actual reuse and remains invalid for that component attribution.

Protocol 7.0.0 identifies the EAL/3 instrument. Current plans pin
`source_language` and `protocol_version`; new collection rejects earlier language
plans. Execution contracts freeze source version, implementation, dependencies
and plan identity, so an EAL/2 run cannot resume under EAL/3. Retained EAL/2
protocols, results and verification remain historical records available for
offline analysis. The grammar change has no measured model or authoring benefit
in those records. See [EAL/3 verification](verification-eal3.md).
