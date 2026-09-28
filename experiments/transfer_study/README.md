# Developer and model handover experiment

## Research question

Does EAL/2 increase the probability that a developer reaches the correct scoped
engineering decision in a **new prompt session**, especially when both the
developer and language model change?

Each case has two independent developer teams working from identical project
files. Seeded random allocation assigns one slot to ordinary practice and the
other to EAL/2. The later question is released only after the first session is
submitted. A copy of the resulting project travels to the next session; the
earlier model conversation does not.

| Arm | First session | New session |
| --- | --- | --- |
| `ordinary` | Prompt the assigned model; use project files, ordinary tools and artefacts naturally produced while working. | Inspect the resulting project and prompt the assigned model. The experiment supplies no special runbook, curated cache or earlier transcript. |
| `eal` | Do the same work while authoring and registering an EAL/2 source and TOML bindings. Its assessment can be used during this session. | Inspect the resulting project, select a claim and use the registered assessment. Source and observations persist in the copied workspace. |

Both arms begin with the same project and underlying tool access. The EAL source,
registration work and observations are effects of that arm. Developers choose
their own prompts and available tools. A command gateway records model calls
and starts a fresh conversation for each session, while preserving turns inside
the current session. Apply equal time and token limits across arms; include
failed attempts in the result.

## Assignment and case material

The four transfer strata are `same_developer_same_model`,
`same_developer_different_model`, `different_developer_same_model` and
`different_developer_different_model`. Each matched case uses the same model
transition in both arms, and developer teams do not overlap across arms. The
last stratum is primary. Balance small-to-large and large-to-small changes,
along with small-to-small and large-to-large cases. Pin exact provider model
versions. Findings about selected versions cannot automatically generalise to
all models of a given size.

The pilot should include at least two independent cases per stratum. After
pilot calibration, freeze a confirmation plan, sample size and practical
threshold. A starting target is 24 independent cases, with three cases centred
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

For each stratum, estimate the mean paired difference
`correct_eal - correct_ordinary` and a case-resampled 95% interval when at
least four pairs are available. The primary estimand is the difference in the
different-developer/different-model stratum. Confirmation plans declare
`meaningful_difference` (for example 0.10) and `primary_min_pairs` before
outcomes. An interval entirely above that threshold supports a meaningful
benefit under the tested conditions; an interval below zero favours ordinary
practice. Other outcomes remain inconclusive. Pilot reports are exploratory.
Submit and score an explicit failed decision if a session cannot finish.

Report initial preparation effort, later developer effort, model calls,
tokens, elapsed model time, provider cost when available, tool calls, EAL
collection and reuse, and failures separately. Include initial authoring cost
when comparing total effort after repeated questions. Reconcile provider
billing if its adapter has no per-call price. Select the confirmation sample
size from pilot paired discordance and prespecified simulations of precision
or power; do not extend confirmation after inspecting its outcomes.

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

After both slots finish, export assessor material. A rating has fields
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
