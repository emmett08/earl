# Evidence loss and restoration follow-up

This is a **specified feasibility pilot**, with a fresh fictional corpus and a
prospective protocol. It fixes the prior diagnostic's reference saturation by
making only the decision-critical gap unknown. Apparatus checks and scripted
rehearsal are separate from actual model performance. Principal-study power has
not been established.

The fresh inputs were authored by `/root/restoration_design`, an AI agent in the
same orchestration session. A separate AI reviewer independently recalculated
the raw facts, without importing either reference implementation. That provides
a distinct computation and review role, not independent human task authorship,
external investigator validation, or representative task sampling. The record
is [review/independent-reference-review.json](review/independent-reference-review.json).

There are eight source tasks: `all_of` and `any_of`, each paired with missing,
stale, invalidated, or version-mismatched evidence. Task domains differ across
causes, so cause comparisons are descriptive. Each source task has five scheduled
positions, with one actual common donor and fifteen recipients cloned from that
donor. No recipient carries a preceding recipient's output.

| Position | Condition | `all_of` reference | `any_of` reference | Purpose |
|---|---|---|---|---|
| 0 | Donor complete | ready | ready | Shared actual donor history |
| 2 | Complete | ready | ready | Positive baseline |
| 4 | Critical gap | undetermined | undetermined | Genuine decision-critical loss |
| 6 | Restored positive | ready | ready | Eligible passing evidence restored |
| 8 | Restored negative | not_ready | not_ready | Eligible failing evidence restored |
| 10 | Noncritical gap | not_ready | ready | False conjunct or true route remains decisive |

Odd positions preserve the previous facts, scope and evidence revision and are
unscheduled continuity entries required by the existing corpus contract. These
snapshot positions are artificial fixture times. A negative restoration supplies
a new adverse value; it is a polarity check, not a physical reversal of the
original passing evidence.

For `all_of`, the noncritical control retains the negative restoration's false
critical conjunct and removes a different requirement. It compares with position
8. For `any_of`, the noncritical control retains the positive restoration's true
primary route and removes evidence on the alternative route. It compares with
position 6. This directly checks that unavailable evidence does not always make
the overall decision unknown.

The scheduled reference distribution is **20 ready, 12 not_ready, and 8
undetermined**. Thus 32/40 authored positions are decisive. An always-undetermined
response matches only 8/40 references; always-ready matches 20/40 and always-
not_ready matches 12/40. These are exact fixture calculations, not measured model
accuracy. Both implementations agree with all 88 authored keys and all 40
explicit scheduled requirement-state patterns; the separate reviewer also checks
mixed eligibility blockers and freshness boundaries.

The plan crosses facts, EAL, and conventional host-reasoner contexts at every
position. The model and response prompt are fixed. There are **8 donor blocks,
120 recipients, and 128 sessions**, using `gpt-4.1-nano-2025-04-14`, one repeat,
no native tools for donors or recipients, prompted JSON for recipients, a 1,024-token output
cap, at most two calls per session, and a cumulative USD 2 budget. The current
official model page lists this snapshot as deprecated; account availability is
unknown until a real request succeeds. The snapshot is never silently replaced.
The common donor retains the diagnostic runner's prose baseline; its answer is
excluded from recipient correctness denominators.

At the official rates checked on 2026-10-02 (USD 0.10 input / 0.40 output per
million tokens), the maximum provider reservation is

\[
128\times2\times
\frac{(32768+4096)\times0.10+1024\times0.40}{10^6}
=\text{USD }1.048576.
\]

The extra 4,096 input tokens are the existing provider's framing reservation.
One call per session would halve this envelope. Actual costs use retained
provider usage and include failed attempts. Repeating the full allocation twice
would bound USD 2.097152, above the cap. A two-task allocation is cheaper but
does not cover all four causes. These calculations justify the feasibility
allocation; they are not power or sensitivity results.

Resource logs distinguish `host_raw_snapshot_reads` used to construct a reasoner
context from `native_tool_calls` triggered by the model. Total collector calls
include host reads, native probes and EAL acquisitions. With native tools disabled,
host fixture reads can still occur; they are not model-native tool use. Scripted
rehearsal labels record a scripted assessor identity and are never labelled as
human ratings.

The primary quality endpoint is the **correct communicated whole-task verdict
with internal explanatory consistency**. A masked coder reads the whole answer,
codes its communicated decision, and checks whether the explanation and any
canonical field are internally consistent. The canonical decision enum is a
separate machine-readable endpoint. A correct enum with contradictory prose
cannot establish primary success. Missing, ambiguous and unresolved coding also
cannot establish success. Factual grounding and explanation accuracy against
the task evidence remain unassessed by this endpoint.

Report every cell and all failures. For a named context, passing all forty
primary outcomes and all declared control patterns demonstrates performance on
this fixed task set and configuration. Partial results remain descriptive.
There are eight task instances, two logic families and four cause manipulations;
the 120 recipients are not 120 independent cases. One repeat leaves stochastic
repeatability unknown. No superiority, population reliability, pure reasoning
capability, human-workflow benefit, or cost-saving claim follows from this pilot.

Reproduce and check the authored material from the repository root:

```bash
python3 experiments/model_transfer/followup/author_inputs.py
python3 -m experiments.model_transfer.followup.check_materials
python3 experiments/model_transfer/followup/author_protocol.py
python3 experiments/model_transfer/followup/author_plan.py
python3 tools/investigation-validator/scripts/validate_investigation.py experiments/model_transfer/followup/protocol.json
python3 -m experiments.model_transfer.rehearse --plan experiments/model_transfer/followup/plan.json --output /tmp/eal-restoration-rehearsal
```

The authoring scripts reproduce construction-stage materials. Once an execution
receipt amends the protocol, preserve that version and its plan digest; do not
overwrite the receipt by regenerating construction-stage files. Rehearsal uses
scripted answers and no API calls. Actual collection must use the frozen plan,
retain its raw journal, and preserve the original cumulative budget on resume.

The source language stays EAL/3 and the reasoning method stays
`experiment/task-rules/1`. Existing pilot plans, corpus and measured outcomes are
preserved. The diagnostic runner adds explicit recipient positions, common-donor
clones and a retained response-mode baseline to deliver this separate pilot.
