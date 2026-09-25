# Mitigating failures by removing model restatement

Use `--finalisation checked` when the required output is the selected report's
checked decision. The model selects evidence; the host runs the checker,
validates its result and returns the decision fields directly. Keep
`--finalisation model` for research on whether models can communicate those
results correctly.

This follows the `optimise-software-performance-and-cost` skill: remove work
that the accepted result does not require before making that work cheaper.
The objective is zero model calls after a successful checked assessment,
subject to preserving report selection, evidence collection, scope, status,
metrics, failed and unknown checks, independent verification and accounting.
Explanation quality is outside the experiment's scored outcome.

## Measured opportunity

The baseline is nano-only run 36176588712, plan 3.1.0. The candidate mechanism
already exists in merged commit `70a1bb1b0153a9038398c1ae21232aa29d2d2c57`.
The comparison below divides **recorded calls** at the first successful checked
packet. It does not generate alternative model responses or alter old scores.

| Recorded quantity | EAL/MCP | Ordinary validator | Combined |
| --- | ---: | ---: | ---: |
| Assigned trials | 40 | 40 | 80 |
| Attempted trials with a target-correct checked packet | 30 | 31 | 61 |
| Unattempted trials | 10 | 9 | 19 |
| All model calls | 131 | 134 | 265 |
| Calls through that first packet | 30 | 34 | 64 |
| Later calls | 101 | 100 | 201 |
| Known cost of all calls, USD | 0.0233845 | 0.0210980 | 0.0444825 |
| Known cost through that first packet, USD | 0.0054272 | 0.0047514 | 0.0101786 |
| Known cost of later calls, USD | 0.0179573 | 0.0163466 | 0.0343039 |

The continuations account for **201/265 = 75.85% of recorded calls** and
**77.12% of their known cost**. The costs are archived estimates at frozen token
rates, not current prices or invoices. The one unknown-cost call also lies in
the continuation and is excluded from the monetary sums.

All 61 first checked packets yield correct answer fields when passed through
the current answer assembly and the independent historical grader. The original
conversations subsequently produced 14 correct answers, 20 incorrect completed
answers and 27 failed conversations. These are conditional reconstructions
given the recorded report selections, not 61 newly successful model trials.
The 19 unattempted assignments remain unobserved. No latency improvement or
future billing reduction is inferred from the trace partition.

## Why this addresses the failures

Checked finalisation makes the returned decision a copy of the verified tool
result. A later model response cannot change `unsupported` or `unavailable` to
`supported`, discard metrics, or confuse operation errors with evidence errors.
It also removes the need for a model `finish` request and its field-repair loop.
Only the inspection operation is advertised in this mode.

The historical HTTP 503 occurred in an ordinary-validator continuation after a
correct packet had already been obtained. Terminating at that packet would omit
that particular recorded request. This observation cannot establish that a new
run will avoid provider outages. Protocol 4 separately bounds transient retries,
retains unknown-charge reservations and allows later assignments until the
three-trial transient circuit or another declared stopping condition applies.

Initial selection, initial operation formatting, acquisition and checker faults
remain possible. A wrong selection retains its identity and is graded as wrong;
the host never substitutes the reference answer. A checker/reference mismatch
still invalidates the result.

## Alternatives and decision

| Option | Supported benefit | Constraint or uncertainty |
| --- | --- | --- |
| Checked finalisation | Removes post-assessment rewriting and finish requests by construction | Measures the checked system; keep separate from model-authored accuracy |
| Explicit templates and repair feedback | Already implemented for model finalisation | Model behaviour under the revised prompt still needs live evaluation |
| Native tool calls or stronger output constraints | Can constrain operation representation | Correct structure does not establish a correct decision; native mode currently uses `strict: false` |
| Larger models or larger call limits | Could improve some model-authored answers | Adds expenditure; these traces do not establish the improvement |
| Deterministic report selection | Can eliminate model calls when the caller already supplies an unambiguous report identity | Changes this experiment's selection task; requires a separately labelled control |

The smallest supported solution is to use the existing checked path and retain
the existing recovery limits. This change adds evidence and transport coverage;
it adds no runtime branch, dependency, model, retry or paid invocation.

## Reproduction and next invocation

From an installed development checkout:

```bash
python paper/analysis/analyse_finalisation.py
python -m pytest -q tests/test_api_recovery.py
```

The analysis verifies the preserved dataset and source hashes, replays the
historical scores, checks the selected packets, and writes
`paper/results/finalisation-opportunity.json`. Its arithmetic is deterministic;
repetition measures reproducibility, not independent observations. The tests
exercise the actual Responses adapter with scripted HTTP replies and real local
collectors/MCP, including unsupported and unavailable outcomes in both text and
native transports. Provider-model behaviour is not measured by these tests.

For a subsequent manual calibration, select `mode=calibration`, the same pinned
nano snapshot, `transport=text`, and `finalisation=checked`. This assigns three
cases to each of the two checked arms: **six assignments**, with the existing
USD 0.50 admission allowance. Inspect initial-operation failures, checked-answer
correctness, provider retries and unknown costs before increasing the workload.
Use a fresh output directory and retain its manifest. The subsequent checked
smoke mode adds errors and distractor selection, with eight assignments for one
snapshot; select it manually only after reviewing calibration. No calibration
or smoke invocation has been dispatched by this analysis.

Validation on Python 3.12.14: **127 focused experiment tests passed**, including
eight checked-finalisation combinations across two routes, two transports and
two evidence conditions. Runtime files and paid-workflow defaults are unchanged.
