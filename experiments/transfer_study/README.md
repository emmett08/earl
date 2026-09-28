# Developer and model handover experiment

## Research question

Does EAL/2 help a developer reach the correct scoped engineering decision
within a fixed time budget in a **new prompt session**, and reduce the time
and repeated work required, especially when both developer and model change?

[protocol.json](protocol.json) specifies the investigation using schema 1.1.
Its status is **specified**, with the software implemented and synthetic checks
completed. Real case oracles, scorer calibration, participants and the final
confirmation plan remain to be supplied. No human or live-model trial has run.

Each case has two independent developer teams working from identical project
files. Seeded random allocation assigns one slot to ordinary practice and the
other to EAL/2. The later question is released only after the first session is
submitted. A copy of the resulting project travels to the next session; the
earlier model conversation does not.
The first project is snapshotted at submission; subsequent edits to that
workspace cannot change the later developer's handover.

| Arm | First session | New session |
| --- | --- | --- |
| `ordinary` | Prompt the assigned model; use project files, ordinary tools and artefacts naturally produced while working. | Inspect the resulting project and prompt the assigned model. The experiment supplies no special runbook, curated cache or earlier transcript. |
| `eal` | Do the same work while authoring and registering an EAL/2 source and TOML bindings. Its assessment can be used during this session. | Inspect the resulting project, select a claim and use the registered assessment. Source and observations persist in the copied workspace. |

Both arms begin with the same project and underlying tool access. The EAL source,
registration work and observations are effects of that arm. Developers choose
their own prompts and available tools. A command gateway records model calls
and starts a fresh conversation for each session, while preserving turns inside
the current session. The plan sets equal elapsed-time budgets per stage and a
model-call ceiling for both arms; failed model calls consume the ceiling. Token
use is an outcome, not an equalised resource. The operator opens a session when
the developer is ready; that starts its uninterrupted clock. Calls cannot start
after the deadline, and model/tool subprocess timeouts are capped by the time
remaining. In-process EAL work is timed but cannot be forcibly interrupted; an
answer submitted after the deadline cannot pass the primary endpoint.

Use real developers for developer comparisons. Native reasoning/tool support is
a property of the selected adapter and model configuration, not the assigned
arm. Match the adapter configuration and underlying tool access across arms.
The supplied Responses adapter is text-only; developer tool commands and EAL
assessments run outside it. A study of native agent tooling requires an adapter
that records those attempts and an independently rehearsed configuration.

## Assignment and case material

The four transfer strata are `same_developer_same_model`,
`same_developer_different_model`, `different_developer_same_model` and
`different_developer_different_model`. Each matched case uses the same model
transition in both arms, and developer teams do not overlap across arms.
Confirmation also requires distinct developers across cases to avoid learning
and interference between assignments. A pilot can reuse developers, but its
analysis then suppresses independent-case intervals. The
last stratum is primary. Select the task and model mixture before allocation.
Balance small-to-large and large-to-small changes,
along with small-to-small and large-to-large cases. Pin exact provider model
versions. Findings about selected versions cannot automatically generalise to
all models of a given size.

The pilot should include at least two independent cases per stratum. After
pilot calibration, freeze a confirmation plan, sample size and practical
threshold. A 24-case coverage pilot can include three cases centred
on each installed reasoning mode: structured, deductive, inductive, abductive,
causal, counterfactual, analogical and temporal. Distribute modes across
transfer strata. A task sequence has an initial question, unreleased later
question and shared seed project. Include compatible observation reuse,
`evidence.max_age` expiry, ended assumption validity, changed context,
objections, negative findings and missing evidence in distinct cases.

Independent case authors establish the facts, answer, accepted qualifications
and materially wrong conclusions from the specification and data before EAL
authors inspect held-out later observations. EAL status never supplies the
answer key. Freeze case files, oracle, provider versions, assessment times,
allocation seed, prompts and scoring rubric before confirmation outcomes.
The paired case is the independent analysis unit, not each prompt turn.

## Outcomes and decision rule

The primary outcome is the correctness of the **developer's submitted later
decision**: it reaches the independent reference result, includes material
scope and qualifications, and makes no material unsupported assertion. A
justified unresolved answer succeeds only when the available evidence cannot
decide the question. Retain raw model answers separately.

Two assessors independently score each submitted answer under an opaque ID,
without arm, model or developer metadata. They record correctness, material
error and reasons. Disagreements require adjudication. If an answer names the
intervention and reveals its arm, record that as a scoring deviation. The
harness cannot replace a human reference judgement with EAL's result.

The primary endpoint is a correct submitted later decision **within the
plan's elapsed-time budget**. The secondary time endpoint is time to a correct
submitted decision, restricted to that budget: an incorrect, late or absent
answer receives the full budget. This measures time to the final decision,
not the first correct thought or draft. Report raw correctness and late-answer
counts too. Self-reported active effort is distinct from elapsed time.

Every allocated session needs a terminal record. `submit` records an answer;
`close` records `no_answer`, `withdrawn` or `invalid_measurement` with a reason.
No answer is a known failure for the time-bounded endpoint. Withdrawal leaves
its correctness in [0, 1] and restricted time in [0, budget]. Unknown outcomes
remain in the allocated denominator; analysis propagates their bounds. Invalid
measurement prevents a confirmatory conclusion. Do not encode missingness as
an invented answer or silently exclude cases. Missing effort, billing or token
usage is reported as unknown alongside the known subtotal.

For each matched case, take EAL minus ordinary correctness. Random assignment
makes the mean difference unbiased for the average treatment effect across the
two eligible developer teams in each selected case, assuming no interference
and a valid common scorer. The estimand covers the assigned **whole workflow**:
authoring, persistence, retrieval, tooling and reasoning. It cannot isolate
which component caused an effect. Same-person memory is part of the stated
continuity condition. The equally weighted case mixture is the target; it is
not an estimate for every developer or every small/large model.

The primary stratum is different developer/different model. The estimator uses
a conservative two-sided 95% Hoeffding interval for independent paired
observations in [-1, 1]. With n pairs, the radius is
`sqrt(2 * log(40) / n)`, clipped to [-1, 1]. For unknown outcomes, expand the
worst-case mean bounds by that radius. This finite-sample procedure does not
need normally distributed or identically distributed cases. Its cost is wide
intervals: 24 pairs give a radius of about 0.55. Planned radii of 0.30, 0.20
and 0.10 require 82, 185 and 738 independent primary pairs respectively.
These are precision calculations, not empirical power estimates.

Confirmation plans declare `meaningful_difference` and `primary_min_pairs`
before assignment. A primary interval entirely above the practical threshold
supports meaningful correctness improvement under the tested conditions; an
interval below zero favours ordinary practice. Other outcomes are inconclusive.
Pilot results remain exploratory. Secondary time, transfer-stratum and model
transition estimates have descriptive, marginal intervals: no simultaneous
coverage or separate confirmatory discovery is claimed. A correctness benefit
alone does not establish faster work, lower cost or improved reasoning ability.

Report initial authoring/preparation effort and later effort, model calls and
failures, measured tokens, elapsed model and EAL time, known provider cost,
developer tool calls, and EAL collection/reuse. Total effort includes both
sessions. Retain failures and all within-budget retries; never select the best
attempt retrospectively. Reconcile unavailable cost/usage against billing before
making cost claims. The two-session study does not establish an amortisation
curve over many later sessions. That needs a separately planned extension.

The finite-sample bound follows Hoeffding (1963), Theorem 2,
[original paper](https://www.cs.rpi.edu/academics/courses/spring06/random/hoefding.pdf),
[DOI](https://doi.org/10.1080/01621459.1963.10500830).
[verification/calibration.json](verification/calibration.json) records synthetic
null, benefit, harm, within-pair dependence, informative missingness and declared
cross-case dependence checks. Monte Carlo uncertainty is reported separately.
Run the calibration with:

```sh
python -m experiments.transfer_study.calibration \
  --output experiments/transfer_study/verification/calibration.json
```

## Implementation and verification

`StudyDesign` validates the plan and creates paired allocation. `StudyRun` owns
session state and project handovers. `ModelGateway` is the provider adapter
boundary; `SessionOperations` records tools and the EAL adapter. `OutcomeReader`
joins terminal records to independent ratings. `BoundedPairedEstimator` handles
numeric uncertainty independently of collection and scoring. These separate
responsibilities keep provider, storage and statistical changes local; the
adapter and repository patterns reuse the existing EAL implementation.

`EAL/transfer-study-plan/2` requires `session_minutes.initial`,
`session_minutes.later` and `max_model_calls`. Session terminal records and
analysis output use version 2; provider request/response and ratings remain
version 1. EAL/2 grammar, semantics and production observation formats are
unchanged. Allocation is replay-checked when a run is loaded, and the project
snapshot digest is checked before opening its handover.

Protocol traceability names tests for assignment, collection, scoring, analysis
and the complete synthetic pipeline. Software checks establish the behaviour
exercised by those tests. Independent task/scorer calibration still needs known
correct, wrong, qualified-unresolved and borderline answers before a real trial.
If blinding breaks or a reference is invalid, record the deviation and withhold
a confirmatory interpretation. The harness cannot enforce human independence,
reference validity or exclusive use of the instrumented tools.

## CLI and provider boundary

From the repository root, run `pip install -e '.[dev]'`. The included synthetic
case verifies transport and persistence; its mock answers are **not** model or
developer performance data.

```sh
python -m experiments.transfer_study check-plan experiments/transfer_study/demo/plan.json
python -m experiments.transfer_study init experiments/transfer_study/demo/plan.json \
  experiments/transfer_study/runs/demo --seed 42
python -m experiments.transfer_study open experiments/transfer_study/runs/demo \
  orders_fixture A initial
```

The operator distributes only the resulting participant packet and project
workspace. Keep the run directory, allocations, other arm and later questions
outside participant access. Use separate accounts or containers where that
separation must be enforced. The operator invokes the following commands for
a participant; their prompt and final answer live in files:

```sh
python -m experiments.transfer_study invoke experiments/transfer_study/runs/demo \
  orders_fixture.A.initial --prompt-file prompt.txt
python -m experiments.transfer_study tool experiments/transfer_study/runs/demo \
  orders_fixture.A.initial -- python3 probe.py
python -m experiments.transfer_study submit experiments/transfer_study/runs/demo \
  orders_fixture.A.initial --answer-file answer.txt --effort-minutes 12
python -m experiments.transfer_study open experiments/transfer_study/runs/demo \
  orders_fixture A later
```

An EAL-assigned developer writes a `.eal` file and TOML binding inside their
initial workspace, then registers the chosen claim. The illustrative EAL
files under `demo/` are **outside** the participant seed and must not be
supplied as a reference answer in a real case.

```sh
python -m experiments.transfer_study register experiments/transfer_study/runs/demo \
  orders_fixture.A.initial --source source.eal --registry tools.toml \
  --entry orders --claim ready --context '{"service":"orders"}'
python -m experiments.transfer_study assess experiments/transfer_study/runs/demo \
  orders_fixture.A.later --registry tools.toml --entry orders --claim ready \
  --prompt-file prompt.txt
python -m experiments.transfer_study invoke experiments/transfer_study/runs/demo \
  orders_fixture.A.later --prompt-file prompt.txt --context-file PATH_FROM_ASSESS
```

The developer selects entry and claim; the harness does not infer a correct
selection from the oracle. Assessments use the case's declared later time.
`max_age` controls observation freshness; assumption dates govern assumption
applicability. The original observation time remains unchanged across sessions.

An allocated session that does not produce an answer is closed explicitly,
even if it never opened. Use `withdrawn` for an unknown outcome and
`invalid_measurement` for an unusable task/reference or measurement:

```sh
python -m experiments.transfer_study close experiments/transfer_study/runs/demo \
  orders_fixture.A.later --status no_answer --reason "No answer within the budget" \
  --effort-minutes 15
```

After all allocated sessions have terminal records, export assessor material. A rating has fields
`blind_id`, `rater`, `correct`, `material_error` and `reason`. The ratings
envelope has `schema: "EAL/transfer-ratings/1"`, a `ratings` list containing
two independent entries per answer, and an `adjudications` list for
disagreements.

```sh
python -m experiments.transfer_study blind-export experiments/transfer_study/runs/demo \
  --file blind-answers.json
python -m experiments.transfer_study score experiments/transfer_study/runs/demo \
  --ratings ratings.json
python -m experiments.transfer_study analyse experiments/transfer_study/runs/demo \
  --file analysis.json
```

The model command receives one `EAL/transfer-model-request/1` JSON object on
stdin with `model_version`, workspace and current-session messages. It emits
`EAL/transfer-model-response/1` with `model_version`, `content`, and
`usage.input_tokens`/`usage.output_tokens`; it can include `cost` and
`tool_calls`. `openai_responses` is one reference text adapter: set
`OPENAI_API_KEY` and a pinned model ID in the plan. Other providers can
implement the same command contract. `mock_model` verifies the harness
without making provider calls. Real task prompts and answers are kept in the
operator's private run directory.

The bundled fixture has the status **transport demonstration**. It provides
no independently authored case oracles, developer participants or live model
comparison. A confirmation claim requires those materials and observed runs.
