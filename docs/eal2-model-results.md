# EAL/2 model experiments — 23 September 2026

These live API trials ran package **2.1.0**, source language **EAL/2**, at commit `dc30aa5aa29c63b50e452118fd455311bf89c88e`. All **84 comparison trials and eight development-ablation trials** completed and are retained, including failures. Both reports record no implementation or reference drift. No implementation, prompt, scorer or task changes were made during either run.

On the six comparison tasks, GPT-4.1 mini with stateful text delegation and GPT-5 mini with stateful native delegation each scored **12/12**, against **8/12** for their own unaided baselines. Nano scored **6/12** unaided, **9/12** with text delegation and **10/12** with native delegation. Every delegated condition cost more per correct task than its own unaided baseline. The development comparison also exposes interface defects that limit interpretation of its stateful advantage.

These are **regression measurements on previously exposed synthetic cases**, not fresh held-out evidence. The matrix's stored `held_out` split selects records; it does not restore their independence from earlier development. The experiments compare complete model/host systems under different validation obligations. They do not establish general model reasoning ability, an improvement caused by the 2.1.0 changes, human comprehension, or a benefit attributable specifically to the notation.

## Comparison matrix

| Model and condition | Correct / trials | Repairs | Requests | Tokens | Cost | Cost / correct task | Mean trial time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GPT-4.1 nano — unaided | 6/12 | 0 | 12 | 85,348 | $0.0040552 | $0.0006759 | 9.2 s |
| GPT-4.1 nano — stateful text | 9/12 | 14 | 42 | 446,763 | $0.0174255 | $0.0019362 | 31.2 s |
| GPT-4.1 nano — stateful native | 10/12 | 6 | 32 | 323,696 | $0.0126770 | $0.0012677 | 24.4 s |
| GPT-4.1 mini — unaided | 8/12 | 0 | 12 | 85,352 | $0.0162272 | $0.0020284 | 8.9 s |
| GPT-4.1 mini — stateful text | 12/12 | 2 | 28 | 264,994 | $0.0473800 | $0.0039483 | 20.0 s |
| GPT-5 mini — unaided | 8/12 | 0 | 12 | 88,009 | $0.0135330 | $0.0016916 | 11.9 s |
| GPT-5 mini — stateful native | 12/12 | 12 | 38 | 395,199 | $0.0288333 | $0.0024028 | 29.0 s |

Every condition ran the same six tasks twice. Requests count all model responses, including repair attempts; costs include failures. A correct task requires every requested status to match the independent reference. Delegated tasks additionally require source correspondence, a verified observation/assessment trace and any required explanation workflow. Unaided tasks return status labels without providing a checked source or derivation. In repair tasks both arms receive the defective draft, but only delegation must execute the repair and preserve the corrected reference's meaning.

| Condition ID | Correct: all supported | Correct: qualified outcome | Unjustified | Unresolved |
| --- | --- | --- | --- | --- |
| `nano_unaided` | 6 | 0 | 4 | 3 |
| `nano_text_stateful` | 6 | 3 | 0 | 3 |
| `nano_native_stateful` | 6 | 4 | 0 | 2 |
| `mini_unaided` | 6 | 2 | 2 | 0 |
| `mini_text_stateful` | 8 | 4 | 0 | 0 |
| `reasoning_mini_unaided` | 6 | 2 | 0 | 3 |
| `reasoning_mini_native_stateful` | 8 | 4 | 0 | 0 |

“Correct: qualified outcome” is the scorer's `justified_unresolved`: a correct task containing an expected `contested`, `unsupported` or `out_of_scope` conclusion. It is a success. `unjustified` and `unresolved` are error flags that can overlap and do not partition all incorrect answers; a wrong `contested` label can have neither flag. Definitions and the expanded-source scorer are in [model evaluation](model-evaluation.md).

Each entry below records success (`1`) or failure (`0`) in **repetition 0, repetition 1 order**. Trial IDs reflect scheduled order, not completion order.

| Task | nano unaided | nano text | nano native | mini unaided | mini text | GPT-5 mini unaided | GPT-5 mini native |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `defence-with-independent-subargument` | 0, 0 | 1, 1 | 1, 1 | 0, 0 | 1, 1 | 1, 1 | 1, 1 |
| `defence-cannot-ground-itself` | 0, 0 | 1, 0 | 1, 1 | 1, 1 | 1, 1 | 1, 1 | 1, 1 |
| `registered-rms-velocity` | 1, 1 | 1, 1 | 1, 1 | 1, 1 | 1, 1 | 1, 1 | 1, 1 |
| `registered-rms-wrong-origin` | 0, 0 | 1, 1 | 1, 1 | 0, 0 | 1, 1 | 0, 0 | 1, 1 |
| `cold-room-calibration-reference-repair` | 1, 1 | 0, 0 | 0, 0 | 1, 1 | 1, 1 | 0, 0 | 1, 1 |
| `sampled-negative-finding` | 1, 1 | 1, 1 | 1, 1 | 1, 1 | 1, 1 | 1, 1 | 1, 1 |

The defence cases distinguish independently supported defence from a defence that cannot ground its own premise. The RMS cases exercise a registered method and a mismatch between the supplied formal query's reference origin and the claim's query. The calibration case requires fixing an undefined assumption reference. The negative-finding case binds a false formal result to an explicitly negative proposition. Observations, context and assessment times are synthetic and fixed; these trials did not operate physical equipment.

## Failures and recovered requests

All 19 matrix failures remain in the archive. Fourteen are completed unaided responses with incorrect labels: nano's six failures cover circular defence, the independent instrument-fault claim and the mismatched RMS origin; mini's four cover independent defence and the RMS origin; GPT-5 mini's four cover calibration repair and the RMS origin. For example, matrix `trial-00011` supplies `supported` where the circular-defence answer is `contested`; `trial-00044` supplies support for the wrong-origin RMS case. Incorrect status distinctions are preserved rather than collapsed into a generic “not supported” category.

The five delegated matrix failures were:

| Trial ID | Condition | Observed failure |
| --- | --- | --- |
| `trial-00007` | Nano text; circular defence; repetition 1 | Five correct interpreter assessments were followed by invalid status-map responses instead of `finish`. The run stopped after 10 model requests and 134,989 tokens, above the 120,000-token post-response threshold. There was no final answer. |
| `trial-00039`, `trial-00061` | Nano text; calibration repair; repetitions 1 and 0 | Invalid requests (including model-supplied diagnostics), invented assumption syntax and unsuccessful revisions exhausted the repair budget. Neither produced a validated final repair. |
| `trial-00040` | Nano native; calibration repair; repetition 1 | A replacement deleted the required argument; subsequent invalid collection/revision requests exhausted the repair budget. |
| `trial-00062` | Nano native; calibration repair; repetition 0 | The model finished after deleting the argument, explicitly reasoning with no collection, and omitting explanation. The result was `unsupported` instead of `supported`. Source, evidence and workflow checks all failed. |

Missing-source and missing-trace scores on incomplete runs describe the absence of a corresponding final answer; they do not mean that every intermediate assessment was wrong. All **43 successful delegated matrix trials** preserved reference source bytes exactly, in addition to passing semantic correspondence. Their observations, collection and assessment identities, context, time and required explanations were independently checked.

Success also carried repair cost. GPT-5 mini's native condition recorded 12 repairs. Six attempts were labelled by the provider adapter as “Native model response arguments are invalid JSON”. Inspection shows valid JSON with a redundant `operation` field inside function arguments: an **argument-schema violation**, not an endpoint failure or invalid JSON syntax. These failures were recovered and their usage remains included. Flat request examples in feedback may contribute to this error, but that explanation has not been isolated experimentally. There were no unknown-usage network failures in this run.

## Paired comparisons

| Comparison (first minus second) | Accuracy difference | 95% task-cluster interval | Mean cost difference (USD) | Mean time difference |
| --- | --- | --- | --- | --- |
| Nano text − nano unaided | +25.0 pp | [-33.3, +75.0] pp | +0.0011142 | +22.0 s |
| Nano native − nano unaided | +33.3 pp | [-33.3, +83.3] pp | +0.0007185 | +15.1 s |
| Nano native − nano text | +8.3 pp | [0.0, +25.0] pp | -0.0003957 | -6.8 s |
| Mini text − mini unaided | +33.3 pp | [0.0, +66.7] pp | +0.0025961 | +11.1 s |
| GPT-5 mini native − GPT-5 mini unaided | +33.3 pp | [0.0, +66.7] pp | +0.0012750 | +17.1 s |

There are **six task clusters**, not twelve independent engineering problems per condition. The runner resampled whole tasks, retaining both repetitions, for 2,000 bootstrap samples. Intervals describe variation across these deliberately selected cases; the cases are not a random population sample. The 12/12 conditions' raw accuracy intervals are [100%, 100%] because every observed outcome is identical. That zero observed variance cannot rule out unseen failures. Shared baselines make comparisons dependent; no multiple-comparison significance claim is made. The archive also retains paired cost and latency intervals and all other condition comparisons. Directions above have been converted from the runner's alphabetical `right_minus_left` ordering.

## Development stateful/stateless comparison

This separate eight-trial run used `engineering-v1.1-eal2`, two exposed development tasks and one repetition per condition. All four conditions use text interaction.

| Model and condition | Correct / trials | Repairs | Requests | Tokens | Cost | Cost / correct task | Mean trial time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GPT-4.1 nano — stateful text | 2/2 | 3 | 9 | 92,492 | $0.0044318 | $0.0022159 | 45.5 s |
| GPT-4.1 nano — stateless text | 0/2 | 9 | 11 | 106,605 | $0.0049764 | undefined (no correct tasks) | 68.8 s |
| GPT-4.1 mini — stateful text | 2/2 | 1 | 6 | 58,022 | $0.0154952 | $0.0077476 | 24.7 s |
| GPT-4.1 mini — stateless text | 1/2 | 5 | 11 | 118,771 | $0.0274492 | $0.0274492 | 48.7 s |

| Task | nano text | nano text stateless | mini text | mini text stateless |
| --- | --- | --- | --- | --- |
| `nested-model-observation` | 1 | 0 | 1 | 0 |
| `text-model-repair-and-explain` | 1 | 0 | 1 | 1 |

| Comparison (first minus second) | Accuracy difference | 95% task-cluster interval | Mean cost difference (USD) | Mean time difference |
| --- | --- | --- | --- | --- |
| Nano stateful − nano stateless | +100.0 pp | [+100.0, +100.0] pp | -0.0002723 | -23.2 s |
| Mini stateful − mini stateless | +50.0 pp | [0.0, +100.0] pp | -0.0059770 | -24.0 s |

The five successes all resolved every requested claim as supported. The three failures were unresolved; none supplied unjustified support. The nano interval of [+100, +100] percentage points simply reflects identical observed differences on two tasks. It supplies no general reliability guarantee.

These failures identify specific host-interface burdens:

- Ablation `trial-00004`, mini stateless on `nested-model-observation`, stopped after four source-mismatch errors. The submitted fixed source differed **only by its absent terminal newline** (1,825 instead of 1,826 characters). The fixed-input host requires exact bytes; the scorer did not reject a semantically equivalent source. This failure is an interface restriction, not evidence of incorrect engineering reasoning.
- Ablation `trial-00000`, nano stateless on the repair task, corrected the premise-claim reference from `missing_applicability` to `model_applies` but then omitted required collection context and used the literal placeholder `latest assessment ID` in later requests. It exhausted the repair budget without a collection or assessment.
- Ablation `trial-00005`, nano stateless on the nested task, sent an invalid validation field, omitted source/context in reasoning and reused placeholder identifiers before explicitly stopping.

The latter two also received the generic repair instruction to omit host-owned source and identifier fields, although stateless requests require explicit source/context and returned identifiers. That contradictory feedback is a concrete confound. The stateless prompt additionally presents `latest assessment ID` as an example placeholder; its contribution has not been separately tested. By contrast, the successful nano stateful repair in `trial-00001` also omitted a terminal newline from its revised draft, and the semantic scorer correctly accepted it with a valid trace. The different fixed-source and draft-revision contracts matter.

State retention, request schemas, feedback, source transport and orchestration change together. The results measure those complete host designs, with their observed defects; they do not isolate a memory effect or establish semantic weakness in the stateless models. Any feedback or source-handling repair should be evaluated in a new frozen run. No failing trial here was rerun or replaced.

## Models, budgets and cost

The response snapshots consistently matched `gpt-4.1-nano-2025-04-14`, `gpt-4.1-mini-2025-04-14` and `gpt-5-mini-2025-08-07`. GPT-4.1 used temperature zero. GPT-5 mini used low reasoning effort and no temperature parameter. Experimental class labels describe these selected groups; parameter counts and general class effectiveness were not measured. Five preliminary probes checked text responses for all three snapshots and native responses for nano and GPT-5 mini. All passed; they are excluded from experiment accuracy and cost-per-correct denominators.

| Phase | Trials | Model requests | Reported tokens | Complete estimated cost |
| --- | --- | --- | --- | --- |
| Matrix | 84 | 176 | 1,689,361 | $0.14013120 |
| Development ablation | 8 | 37 | 375,890 | $0.05235260 |
| Provider probes | 5 probes | 5 | 255 | $0.00011835 |
| Total | 92 trials + 5 probes | 218 | 2,065,506 | **$0.19260215** |

Every response has reported token usage and a configured price; there are no unknown-cost trials. Rates in USD per million input / cached input / output tokens were 0.10 / 0.025 / 0.40 for nano, 0.40 / 0.10 / 1.60 for mini and 0.25 / 0.025 / 2.00 for GPT-5 mini. Provider-reported cached input and reasoning usage are retained. The assumed marginal MCP fixture charge is zero. These are token-rate estimates, not invoices, and exclude host hardware, labour and taxes. Official rates were checked on 23 September 2026: [GPT-4.1 nano](https://developers.openai.com/api/docs/models/gpt-4.1-nano), [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [GPT-5 mini](https://developers.openai.com/api/docs/models/gpt-5-mini).

The frozen plan and each condition override determine budgets; the provider TOML's standalone `[budget]` table is not used by this runner. Common thresholds were 10 model iterations, four repairs, 32 tool calls, 120,000 total tokens and 4,096 output tokens per request. Standard conditions used 120 seconds and $0.035 model cost; the two GPT-5 mini matrix conditions used 180 seconds and $0.06. Limits are checked around host operations and after model responses, so token/cost thresholds can be overshot. They are not provider-enforced spending caps.

The seeded rotating schedule used order seed 20260923 and at most four concurrent trials. Scheduled sampling seeds were 241 and 397 for the matrix and 241 for the ablation, but **no provider sampling seed was applied**. Temperature zero does not guarantee replay. Cache warmth, provider load and concurrent wall-clock conditions were not controlled independently. Mean trial latency includes host interaction and repair; it is not overall study elapsed time.

## Frozen records and reproduction

The matrix suite was `engineering-v2.1-eal2`; the development suite was `engineering-v1.1-eal2`. Both used scorer **`expanded-alpha-equivalence+evidence-trace/2`** and report schema `EAL/experiment-report/1`. The scorer checks the expanded declaration/dependency graph while excluding source locations and pattern-origin metadata. The evaluated fixtures do not exercise argument-pattern authoring, so these results do not measure that capability. The runtime was Python 3.12.14 with ANTLR runtime 4.13.2, MCP 1.30.0, HTTPX 0.28.1 and jsonschema 4.26.0.

- Matrix freeze: `7e6d5ed9bbdbe753f3d7be6c2f579f425d1e2f807f0e421a683a111ef7bb53b1`.
- Ablation freeze: `541192dd8470ac8e7de35dc7d3877fbbb252045ababd6ae1f142b2f009a663d2`.

The [archive index](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-eal2/index.json) records archive hashes, complete aggregates and cost totals. [Execution metadata](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-eal2/execution-metadata.json) preserves the measured commit, provider configuration bytes/hashes and pricing sources. [Provider probes](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-eal2/provider-probes.json) retain their responses and usage. The [failure summary](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-eal2/failure-summary.json) indexes every failed trial by phase; trial IDs are unique within each phase.

Each lossless [matrix](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-eal2/matrix.json.gz) or [ablation](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/results/2026-09-23-eal2/ablation.json.gz) archive is gzip-compressed JSON, schema `EAL/experiment-archive/1`. Its `files` map contains the original UTF-8 strings for `freeze.json`, `report.json`, `trials.jsonl` and every `trials/*.json` file. Full conversations, model attempts, tool requests/results, observations, source identities, oracle inputs, schedules and failures remain available. Trial and journal SHA-256 values can be verified against each report; archive SHA-256 values can be verified against the index. Packaging was checked by reloading every original string. Credential patterns were checked before publication; no API credential is part of these artifacts.

For example, read one retained failure without extracting the archive:

```python
import gzip
import json
from pathlib import Path

path = Path("benchmarks/results/2026-09-23-eal2/matrix.json.gz")
bundle = json.loads(gzip.decompress(path.read_bytes()))
trial = json.loads(bundle["files"]["trials/trial-00062.json"])
print(trial["score"])
```

To launch a new measurement, configure `OPENAI_API_KEY` in the process environment and run the two [current plans](model-evaluation.md) into new output directories:

```sh
python -m eal.experiment --plan benchmarks/experiments/eal2-regression-matrix.json --output .eal/new-eal2-matrix
python -m eal.experiment --plan benchmarks/experiments/eal2-development-ablation.json --output .eal/new-eal2-ablation
```

Exact study inputs belong to the measured commit and archived freezes. Current plan notes were updated after completion to link this report; original pre-execution notes remain in the archives. A new run produces a new freeze and new observations, not a byte-for-byte reproduction of stochastic provider responses. Historical [earlier trials](live-model-results.md) and [EAL/0.3 trials](eal03-model-results.md) retain their original labels and scores. They are not pooled with this run: language, source, host and scorer changes prevent attributing cross-version differences to the 2.1.0 changes alone.
