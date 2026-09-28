# Model-session workflow investigation

Protocol **4.0.0**, schema **1.1**, status **specified**. The primary investigation
estimates recipient correctness and cumulative expenditure across an initial
session and ten fresh recipients. Pilot observations inform a prospective
precision-based evaluation allocation; adequate live information remains unestablished.
A separate diagnostic investigation varies individual components on cloned donor
states. The [human developer study](../transfer_study/README.md) addresses
human handover and authoring effort separately.

## EAL/2 experiment methodology

The [methodology](../../docs/eal2-experiment-methodology.md) defines the
scientific question, estimands, task provenance and inference limits. The practical
criterion is **at least 20% less cumulative input-plus-output tokens**, counting
the initial session and ten recipients, with mean recipient correctness no more
than **five percentage points lower** and **at least 90% EAL recipient
correctness**. Initial correctness is reported separately. All three uncertainty
bounds must satisfy their thresholds; cheap failures
cannot count as success. Estimated USD and elapsed seconds remain separate
secondary outcomes. These are prospective configurable operating thresholds.

The allocation target is 95% nominal joint confidence, correctness half-width at
most 2.5 percentage points and token-reduction half-width at most 10 percentage
points. The lower 95% Monte Carlo assurance bound must reach 80% over 200
seeded replications in each declared design scenario. The lower 95% Wilson bound
for joint interval coverage must also reach the nominal 95% level. Monte Carlo
intervals are pointwise per candidate/scenario, not simultaneous across the grid.
This is conditional precision planning, not a claim of achieved statistical power.
Pilot and fresh evaluation runs remain separate.

## Primary comparison

The comparator is a new ordinary prompt session with the task specification and
naturally produced project notes. It receives no supplied runbook, curated tool
cache or previous conversation. Every session has empty conversation history.
Both workflows retain the latest complete model answer verbatim as an ordinary
project note. This requires no file-writing instruction or answer schema.
An answer exceeding the 8,192-byte note limit remains in the raw session record;
the host records why it was not added to the project notes.

EAL additionally uses pre-authored EAL source, a sibling TOML collector binding
and persisted observations. Its host opens the knowledge base anew each session,
reuses eligible measurements and collects missing or expired evidence. A task
contract validates the authored source against the task metadata. A task-specific
adapter derives the scoped decision from the actual assessment and sends a
standalone compact task context containing the current result, meaning, scope
and evidence. The prompt omits the repeated full specification and older notes.

The two workflows solve the same external task with appropriate prompts.
Differences in prompt length, host computation and information organisation are
part of the workflow treatment. The experiment measures whether these differences
improve decisions or reduce work; it does not require like-for-like prompts.
The full raw requests preserve exactly what each recipient received.

| Model snapshot | Dedicated reasoning setting | Recipient native tools |
| --- | --- | --- |
| `gpt-4.1-nano-2025-04-14` | No reasoning parameter | Off and on |
| `gpt-5-nano-2025-08-07` | Low | Off and on |

Every case crosses both donor models with both recipient models and both native
tool settings. Initial sessions have native tools. Each sequence contains an
initial session and **ten fresh recipient sessions**, with two pilot executions
per configuration. Persisted artefacts and EAL observations continue within a
sequence. Provider conversation history does not.

The candidate pilot plan has **448 sequences, 4,928 sessions and at most 14,784
API requests**, with a **USD 2 request-reservation limit**. These counts specify
coverage; the budget may truncate the plan, and no adequate precision or complete
execution is asserted. Evaluation allocation is selected from eligible pilot
information before new evaluation outcomes. Matched arm sequences are
adjacent within shuffled blocks; their order is randomised. Their initial
sessions execute independently, so natural notes may differ. The paired primary
contrast describes this complete workflow difference.

Eight retained calibration cases cover fresh positive/negative measurements,
refresh to positive/negative findings, missing measurements, assumption expiry
and inclusive storage thresholds. Six separately AI-authored synthetic cases
add conjunctions of obligations (`conjunctive_release`), alternative support
routes (`alternative_routes`) and version/scope applicability
(`version_applicability`). `task_corpus.json` records the six task definitions and
separate `separate_ai_authored` provenance. The installed
`experiment/task-rules/1` method uses three-valued rules and applicable dated
facts. Each tool acquisition is a bundled fact snapshot. Updates at positions
0, 2, 4, 6, 8 and 10 alternate with unchanged snapshots at odd recipient positions,
under a 60-second inclusive lifetime. Selective acquisition of individual facts
and general temporal logic are outside this experiment. The case definitions retain family, authorship and cohort metadata.
Separate AI construction is not external investigator or human authorship.
Reports separate cases and cohorts; retained case definitions identify each family. The finite task pool is
purposively selected; sessions and requests are not independent task replications.

Both selected models can call functions; the off condition restricts access.
Dedicated reasoning varies with model family. EAL host collection and evaluation
remain available when recipient native tools are disabled. Results therefore
concern these configurations, not an isolated reasoning or intrinsic-tooling
capability effect.

## Task meaning and independent calibration

The eight threshold calibration cases admit usable nonnegative measurements
under their specified threshold/direction. `experiment/threshold/2` returns the
reading, threshold, `meets` and `fails`. Positive and negative comparisons are
both usable results. The claim `criterion_evaluated` concerns a completed
comparison; its support status alone is not a readiness decision. Additional
families have task-specific evidence and decision contracts. The task adapter interprets the checked
method result with the applicable scope and evidence status. It has no access to
the scorer's reference answer.

The task contract checks the authored source's claim meaning, threshold,
direction, measurement and scope before accepting that mapping. Generic EAL
context retains claim statements and `prose_verified`; formal support does not
silently become proof of arbitrary natural-language text. Assumptions use
`[valid_from, valid_until)` and observations remain usable through `max_age`
inclusively. An unchanged report preserves its observation time.

Preflight calibration runs selected cases through the actual EAL host and task
adapter and compares the results with independently authored expected outcomes.
Additional checks exercise changed claim meaning, reversed criteria, changed
thresholds, missing observations, scope errors and time boundaries. Invalid
correspondence stops before any API request. A defective authored argument or
information projection is thereby identified separately from a model error.
These checks establish the exercised software behaviour, not model effectiveness.

## Answers and annotation

The primary plan uses **ordinary prose**. The requested task answer carries no
experimental JSON reporting contract. `task_match`/`decision_match` is the primary
descriptive outcome: does the expressed decision agree with the independent
full-information task reference? The reference is calculated from fixture facts
and task arithmetic; it never reads EAL conclusions or enters a model prompt.

Answer annotation and correctness scoring are separate. Automatic prose coding
accepts only a complete standalone canonical decision, such as “Ready.” or
“The service is not ready.” It never selects a sentence from an explanation.
All other non-empty prose, including volunteered JSON, and malformed diagnostic
JSON remain pending until blind review; they do not become incorrect
task decisions merely because the parser cannot classify them. Partial text from
an incomplete provider response also remains pending; provider completion is a
separate measurement. Text accompanying tool calls is retained before tool
processing and remains available for annotation if the session ends without a
final answer. Unfinished responses produce no file effects or handoff notes.
An empty or absent attempted answer is an observed no-answer. Unobserved sessions remain unknown.
Reports retain best/worst bounds for pending and unobserved decisions.

Basis agreement, voluntary measurement/time citations, coded internal consistency,
false definite assertions, abstention, format compliance and optional file-writing
outcomes are separate dimensions. Absent optional basis or citation content is
unmeasured, not a primary task failure. Complete free-text argument quality is
outside the automatic rubric. An appropriate abstention without accessible
evidence may disagree with the full-information task reference; this distinction
is reported rather than hidden inside a single grounding score.

For pending decisions or an audit of all automatic labels:

```bash
python -m experiments.model_transfer.annotations export RUN_DIRECTORY --output ANNOTATION_BUNDLE
python -m experiments.model_transfer.annotations export RUN_DIRECTORY --output AUDIT_BUNDLE --all
```

The assessor receives only the bundle's `items.json`, with shuffled identifiers
and raw answers. Keep `mapping.json` with the analyst. The assessor copies the
items into a labels file, supplies an `annotator`, and records each `decision`,
an exact supporting `quote` and a coding `note`. Permitted decisions are
`ready`, `not_ready`, `undetermined`, `no_answer` and `ambiguous`.
The last remains pending. Case, model, arm and oracle metadata are hidden;
answer wording can still reveal treatment.

```bash
python -m experiments.model_transfer.annotations import RUN_DIRECTORY ANNOTATION_BUNDLE LABELS_JSON --output annotated-rows.json
python -m experiments.model_transfer.analyse RUN_DIRECTORY --rows annotated-rows.json --output annotated-analysis.json
```

Imported annotations create derived rows and preserve the original raw answers
and scores. Independent assessors can produce separate imports; discrepant
interpretations and adjudications should remain inspectable. Manual coding
identifies the answer expressed, not which answer the task should have produced.

## Component diagnostics

The separate [diagnostic plan](diagnostic-plan.json) prepares one real prose EAL
donor session per block, fixes the recipient-time external fixture and copies
that complete donor state into independent recipient directories. No recipient
can change another recipient's notes or observations.

| Component | Recipient variants | Required equality |
| --- | --- | --- |
| Projection | Compact; full | Current task facts, donor state and fixture |
| Prior notes | Omitted; included | Current task context, donor state and fixture |
| Reporting | Prose; prompted JSON; schema-enforced JSON | Current task context, donor state and fixture |
| Collection | Compatible reuse; forced collection | Authored source, donor state and unchanged underlying measurement |

The projection and reporting contrasts use `fresh_positive` and
`refresh_negative`. The notes contrast uses `refresh_negative` with a declared,
dated synthetic stale positive note added before cloning. This deliberate
perturbation is labelled and remains confined to diagnostics. The collection
contrast uses `fresh_positive`, where the retained observation is eligible.

Four donor blocks cross these two cases with both recipient models, using the
plain donor model and disabled recipient native tools. The plan has **four donor
sessions and 28 recipient sessions**, at most **96 API requests**, and its own
**USD 2 reservation limit**. The shared donor is counted once per block; each recipient appears once in the
resource subtotals. Reports separate donor, shared preparation, recipient and
clone-preparation resources. Pairwise contrast entries are comparisons and must
not be summed as a resource total. Preparation records retain completed, failed
and unobserved operations. Preparation timing excludes fingerprinting and
diagnostic serialisation/logging. Session timing retains the session-runner
interval, including request journalling and input-file persistence. Report
construction and annotation are outside these intervals.

Fingerprints and intervention manifests check shared state, unchanged fixture,
required task-fact equality and actual variant delivery. Failed checks preserve
the raw responses and costs while invalidating component attribution. Comparisons
remain separate by component and donor block; they are not pooled with the primary
workflow comparison.

The protocol specifies rival explanations: compact context may preserve task
meaning or remove needed explanation; stale notes may interfere or be correctly
qualified; reporting requirements may alter task decisions or only representation.
Observed differences generate candidate explanations. Expand a diagnostic only
when a concrete uncertainty justifies its cases, repetitions and information
target; the main observation allocation remains with the whole-workflow question. Few stochastic observations
cannot establish equivalence, absence of interference or a unique mechanism.
Forced collection also checks whether reuse actually removes collection work;
local fixture timings do not establish savings for remote infrastructure.

`prose` requests an ordinary task response. `json_prompted` requests the reporting
contract without constrained decoding. `json_schema` adds provider schema
enforcement. Reasoning and native tool access are separate settings. The primary
workflow requires no provider JSON-schema facility; schema diagnostics require a
serving interface that supports it. Structured decoding constrains representation,
not factual correctness.

## Resources and interpretation

Reports separate initial, each recipient and cumulative API input/output/cached/
reasoning tokens, requests, estimated cost, wall time, host collections/reuses,
native probes and setup time. Every attempted request counts. Completeness flags
distinguish known subtotals from unknown resources. Each session records its exact
API attempt identifiers, which reports reconcile with the journal. An explicit
empty receipt records confirmed zero requests; absent or inconsistent receipts
and missing journal entries leave accounting incomplete. Cost/token contrasts
and cost per correct decision require reconciled coverage. End-to-end session time
includes context preparation and note handling. Cost per correct decision is
available only with complete outcome and resource coverage.

Initial overhead may be recovered by later savings. The relevant comparison is
cumulative cost/tokens at each observed session position together with task
success, as well as each later session's marginal usage. This finite investigation
does not extrapolate a break-even point beyond the observed sessions.
Prices are recorded estimates rather than invoices. Source authoring, human effort
and host infrastructure prices are unmeasured. These limits qualify any claimed
saving. The experiment does not charge pre-authored EAL as measured authoring work.

Every planned unit remains visible. Reports retain paired differences,
annotation coverage, failures and unknown bounds. The information procedure
conditions precision on the finite case/configuration mixture and independent
matched sequences. It uses a conservative Hoeffding bound for recipient
correctness and an approximate paired, stratified delta interval for cumulative
token reduction, with Bonferroni allocation across the three criteria. Resource and joint
coverage remain approximate. No developer-population inference is claimed.
Budget exhaustion or timeout leaves a partial run; ties in a small diagnostic
sample do not establish equivalence.

## Pilot-informed allocation

At least two pilot repetitions per included case/model/tool cell provide estimates
of paired token variability and correctness disagreements. The planner retains
complete matched session trajectories, including their within-sequence dependence,
when simulating candidate repetition allocations. Every primary candidate retains
all fourteen tasks and every declared model/tool cell, preserving the estimand. It evaluates declared beneficial, null, adverse, higher-cost and slower-execution
design scenarios. Separate missing-data and rare-tail stresses expose limitations. A single error-free
pair cannot establish zero stochastic error or adequate correctness precision.

The [information settings](information-design.json) record practical thresholds,
precision targets, candidate allocations, design/stress roles and simulation seed.
The default grid keeps fourteen tasks and tests 2, 4, 8, 16, 32 and 137 repetitions.
The conservative quality bound requires at least 15,320 matched sequences for a
2.5-percentage-point half-width: the balanced 137-repetition candidate supplies
15,344 pairs and 337,568 sessions. All smaller default candidates are inadequate
for that target even with an error-free pilot. The large candidate remains subject
to observed variability, the USD 2 reservation cap and execution time.

Planning uses the 7,200-second deadline, a prospective 300-second workflow-overhead
allowance, retained setup/session timing and a twice-slower design scenario.
Allocation must meet both precision assurance and joint-coverage calibration in
each declared design scenario. Coverage is calculated against known simulated
truths; its lower 95% Wilson bound must reach nominal confidence.
Missing-annotation, missing-usage and rare-tail scenarios are separate stress
reports; failures of precision, coverage or effect attainability remain
limitations without independently blocking a proposal. The planner reports
candidate precision, marginal/joint coverage, expenditure, pointwise Monte Carlo
uncertainty and limiting conditions. Candidate flags distinguish
`precision_target_satisfied`, `coverage_calibration_satisfied` and
`eligible_for_evaluation`.
It exports an evaluation plan only when empirical support, precision, joint
coverage and both the USD 2 budget and execution deadline permit one. Sparse data or an infeasible target produces an
explicit unresolved result, with no adequate sample-size claim.

Pilot and evaluation use distinct `study_id` and `study_role` values. Evaluation
records its `pilot_run_ids`, uses fresh executions and never pools the pilot's
outcomes into its own answer. Scripted records can verify calculation and delivery,
but do not supply live model variability. Keep real annotation decisions separate
from scripted rehearsal labels.

## Run and retained artefacts

From the repository root:

```bash
python -m pip install -e '.[dev]'
python -m experiments.model_transfer.runner --calibrate-only --output /tmp/eal-calibration
```

With `OPENAI_API_KEY` configured, select one plan and a new directory:

```bash
python -m experiments.model_transfer.runner --output experiments/model_transfer/runs/comparison-001
python -m experiments.model_transfer.runner --plan experiments/model_transfer/diagnostic-plan.json --output experiments/model_transfer/runs/diagnostic-001
```

The default comparison is a pilot. Evaluation uses the prospectively selected
plan from the information procedure and a new directory. Primary and diagnostic
runs are separate API-funded investigations. The manual **EAL tests** workflow
has a live-run toggle and `comparison`/`diagnostics` plan choice. It uses the existing `OPENAI_API_KEY`
repository secret. Workflows run only by manual dispatch. The live job has a
120-minute ceiling; the budget can stop it sooner while preserving partial data.

Each run retains protocol/plan/case snapshots, study role/identity, allocation, code identity,
calibration, raw inputs/answers, natural notes, EAL state, outcomes and reports.
Diagnostics also retain donor snapshots, clone fingerprints and manipulation
checks. `calls.jsonl` records request starts before transmission and completions
afterwards; `calls.json` is written at orderly completion. Interrupted attempts
remain distinguishable from zero work. Per-sequence checkpoints reconstruct
interrupted runs against the saved assignment. `provenance.json` distinguishes
live transport from scripted rehearsal and records the run identity; an evaluation
cannot reuse a pilot run identity.

```bash
python -m experiments.model_transfer.analyse RUN_DIRECTORY
```

Offline analysis writes a new report from retained records without overwriting the
run. GitHub retains uploaded artefacts for 90 days, subject to repository limits.
See [verification](verification.md) for implementation checks and
[the historical run analysis](results/run-36432530106.md) for unchanged earlier
observations.

A full scripted rehearsal uses the actual EAL runtime, annotation roundtrip and
offline report reconstruction without paid API calls:

```bash
python -m experiments.model_transfer.rehearse \
  --plan experiments/model_transfer/plan.json --output /tmp/eal-primary-rehearsal
python -m experiments.model_transfer.rehearse \
  --plan experiments/model_transfer/diagnostic-plan.json --output /tmp/eal-diagnostic-rehearsal
```

After collecting and annotating an eligible pilot, estimate information with:

```bash
python -m experiments.model_transfer.plan_information PILOT_RUN_DIRECTORY \
  --config experiments/model_transfer/information-design.json \
  --rows annotated-rows.json --output information-report.json \
  --evaluation-plan evaluation-plan.json
```

The report records whether a runnable allocation exists. `evaluation-plan.json`
is written only when an eligible empirical allocation qualifies; no file is
created when the report is `no_supported_allocation`. Use a new output path for
every report. The presence of a scripted or incomplete pilot, inadequate precision
or infeasible resources can each prevent an export. A qualifying plan can then
be passed to the experiment runner in a new run directory. A scripted rehearsal requires the explicit `--allow-scripted` option; its report remains
labelled as scripted and cannot establish live precision or efficacy.

## Method and responsibilities

[Tukey (1980)](https://doi.org/10.1080/00031305.1980.10482706) informs the separation
of exploratory findings from confirmation. [Cronbach and Meehl (1955)](https://psychclassics.yorku.ca/Cronbach/construct.htm)
informs independent validation of the task-decision measure.
[Platt (1964)](https://doi.org/10.1126/science.146.3642.347) informs the rival
explanations and discriminating component comparisons. These choices support
bounded interpretation. [McKenzie (2025)](https://doi.org/10.1111/1475-5890.70003)
informs outcome-specific information requirements, measurement and dependent
follow-ups. The [Dovetail experimental-design guide](https://dovetail.com/research/what-is-experimental-design/)
informs explicit treatment, comparator, assignment and measurement. These sources
do not evaluate EAL or establish its performance.

Allocation, project persistence, context preparation, task contracts, provider
interaction, annotation, independent scoring and resource aggregation have
separate modules/classes. Context strategies encapsulate the workflow variants;
the injected provider transport permits scripted integration verification.
The Responses adapter preserves reasoning items within a session and excludes
provider history from later sessions. No provider answer is fabricated or replaced.
