# Model-session transfer investigation

Protocol **2.0.0**, schema **1.1**, status **specified**. This exploratory
investigation measures reference-task completion and resources when models
start fresh sessions with ordinary project artefacts or existing EAL knowledge.
The [human developer study](../transfer_study/README.md) addresses developer
handover and authoring effort separately.

## Conditions and scope

The primary comparator is a new ordinary prompt session with the project
specification and notes naturally produced in earlier sessions. The experiment
supplies neither a runbook nor selected previous tool results. Conversation
history resets. Both arms can write the same bounded project notes.

EAL additionally supplies pre-authored source, a sibling TOML collector binding
and persisted observations. Its host opens the knowledge base anew each session,
reuses eligible measurements and collects missing or expired evidence. The model
receives the current checked context, without needing to read the EAL source.
The interpreter computes the declared threshold comparison; the model supplies
the task answer. Both components are measured separately.

| Model snapshot | Dedicated reasoning setting | Recipient native tools |
| --- | --- | --- |
| `gpt-4.1-nano-2025-04-14` | No reasoning parameter | Off and on |
| `gpt-5-nano-2025-08-07` | Low | Off and on |

Every case crosses both donor models with both recipient models and both native
tool settings. Initial sessions have native tools. Each sequence contains an
initial session and **two fresh recipient sessions**, with two independently
executed repetitions per configuration. Persisted files and EAL observations
continue within a sequence; conversations and model responses do not.

The standard plan has **256 sequences, 768 sessions and at most 2,304 API
requests**, with a **USD 2 request-reservation limit**. Matched arm sequences are
adjacent within shuffled blocks; their order is randomised. Both arms execute
independent initial sessions, so naturally produced notes may differ. Paired
recipient observations share task, donor, receiver, tool setting and repetition.

Six **diagnostic** latency cases cover fresh positive/negative measurements,
refresh to positive/negative findings, missing measurements and assumption expiry.
Two **additional** free-storage cases exercise an inclusive lower threshold and a
changed negative finding. They are prospectively specified additions authored
with the implementation, not an independent confirmatory sample. The two cohorts
are reported separately. Sessions within a case are dependent observations.

This tests the full EAL workflow, including its information and computation
advantage. It does not isolate notation or reasoning capability. Both selected
models can call functions: the off condition restricts access. Dedicated
reasoning varies with model family. The synthetic threshold tasks do not establish
performance on all EAL methods, complex engineering work or human development.

## Evidence and answers

Evidence admission requires a usable nonnegative measurement and the specified
threshold/direction. `experiment/threshold/1` returns the reading, threshold,
`meets` and `fails`. Both positive and negative comparisons are usable computed
results. The claim `criterion_evaluated` concerns successful evaluation within
scope; its support status is not a readiness decision. Assumptions use
`[valid_from, valid_until)`; observations remain usable through `max_age`
inclusively. Re-ingesting an unchanged report preserves its observation time.

A preflight calibration runs each selected case and session through the real EAL
host and model-context projection, comparing visible distinctions with the
independent reference. Calibration failure stops before any API request. This is
an instrument check, not evidence of model effectiveness.

Both arms use the same structured answer contract and provider output schema.
The primary descriptive outcome, `grounded_match`, requires the reference decision
and basis, plus the measured value and observation timestamp for a definite
answer. Any voluntarily cited value or time must also agree with the current
reference. It measures agreement with the reference, not proof that the model
consulted a particular observation. Free-text explanation quality is ungraded.
The reference uses fixture facts and independent specification arithmetic; it
never reads EAL conclusions and never enters a model prompt.

Decision agreement, decision/basis agreement, internal consistency, false definite
answers, abstentions when the reference is decisive, no answer, format validity
and optional file-write validity are separate outcomes. A valid decision survives
an invalid file request. File validation precedes writes. Unparseable answers
remain failures; no oracle-driven repair or permissive extraction occurs.
An abstention without accessible evidence can be appropriate even when it does
not complete the full-information reference task.

## Resources and analysis

The report separates initial and recipient costs, each recipient session index,
setup time, API calls, tokens, reasoning tokens, native probes and host
collections/reuses. Total collector calls include both paths. Completeness flags
distinguish known subtotals from missing timing, token or host-collection records.
End-to-end session
time includes context preparation and file handling. API cost per grounded answer
includes failed API attempts with known usage; unknown costs make the ratio
unavailable. Prices are recorded estimates at uncached rates, not invoices.
Human authoring time and host infrastructure costs are unmeasured. Synthetic local
collector latency cannot estimate real Kubernetes or authentication costs.

`paired_comparisons` retains case, cohort, repetition, same/different-model
transition, session index, quality differences and resource differences.
`case_summaries` shows means and observed ranges. These are descriptive results;
repetition does not create new sampled tasks. There are no population confidence
intervals or significance tests. Every planned unit remains in the denominator.
Unobserved outcomes have explicit best/worst bounds, not fabricated zero cost or
assumed failure. Partial runs cannot establish a completed comparative result.

An optional [ablation plan](ablation-plan.json) adds `eal_fresh`, which forces
collection while retaining the same source and context machinery. It has
48 sequences and 144 sessions. The EAL-versus-forced-collection contrast diagnoses
reuse costs under the fixture's unchanged underlying measurements. Ordinary
prompting remains the primary comparator. This contrast does not isolate every
EAL component, and independently generated notes can differ between arms.

## Run

From the repository root, install the package and first verify the instrument:

```bash
python -m pip install -e '.[dev]'
python -m experiments.model_transfer.runner --calibrate-only --output /tmp/eal-calibration
```

With `OPENAI_API_KEY` configured, choose a new output directory:

```bash
python -m experiments.model_transfer.runner --output experiments/model_transfer/runs/comparison-001
python -m experiments.model_transfer.runner --plan experiments/model_transfer/ablation-plan.json --output experiments/model_transfer/runs/ablation-001
```

Run only the intended plan; these are separate API-funded investigations. The
manual **EAL tests** workflow has a live-run toggle and comparison/ablation choice.
It uses the existing `OPENAI_API_KEY` repository secret. No workflow runs
on push, pull request or a schedule. The live job has a 120-minute ceiling;
the request budget can stop it earlier, retaining partial results.

Artifacts include plan/protocol/case snapshots, assignment, code identity,
calibration, raw session inputs/responses, project notes, EAL state, scored rows
and the report. `calls.jsonl` appends request starts before transmission and
completion records afterwards. `calls.json` is written once at orderly completion;
an interrupted job may have only the journal. Recompute retained scores without
changing them using `python -m experiments.model_transfer.analyse RUN_DIRECTORY`;
this writes a new `analysis.json` and keeps interrupted attempts unknown. Never
overwrite a run directory.
GitHub retains uploaded artifacts for 90 days, subject to repository limits.

See [verification](verification.md) for software checks and
[the original run analysis](results/run-36432530106.md) for the historical result.

## Method and implementation

The investigation follows the distinction between instrument validation,
exploration and confirmation in the design-scientific-investigations skill.
[Tukey (1980)](https://doi.org/10.1080/00031305.1980.10482706) motivates reporting
these observations as exploratory and reserving confirmation for independently
selected cases. [Cronbach and Meehl (1955)](https://psychclassics.yorku.ca/Cronbach/construct.htm)
motivates separating answer correctness from formatting and file side effects.
These methodological choices do not establish an EAL performance benefit.

`AssignmentSchedule` owns allocation; `Project` owns files and fixture state;
context strategies implement ordinary, compatible-reuse and forced-collection
conditions. `SessionRunner` handles the provider interaction, `AnswerParser`
handles the answer contract, `ReferenceScorer` handles task arithmetic,
`ResourceSummary` handles accounting and `ReportBuilder` composes comparisons.
The injected provider `Transport` permits independent scripted verification.
These boundaries separate changing scientific procedures from transport details.

The Responses implementation follows official
[structured-output](https://developers.openai.com/api/docs/guides/structured-outputs)
and [reasoning](https://developers.openai.com/api/docs/guides/reasoning)
contracts. Structured decoding constrains format; it does not ensure correct facts.
Reasoning response items are retained within a session and excluded from subsequent
sessions. No provider response is fabricated or silently substituted.
