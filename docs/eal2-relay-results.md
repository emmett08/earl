# EAL/2 model-sequence results — 23 September 2026

The **92 earlier trials are recovered and pushed**, with their original prompts, failures, usage and frozen inputs. Their [report](eal2-model-results.md) retains the stateless-host interface confounds and original findings.

The explicitly authorised new campaign produced **194 attempted endpoints: 192 finished answers, one endpoint stopped at its repair limit and one transport-failed endpoint**. The transport failure returned no usage and halted further calls. The remaining 130 scheduling records comprise 123 unexecuted conditions and seven partial sequences. They are not model-outcome observations.

Seven complete task/repetition blocks provide **189 comparable endpoints**, including the repair-limit failure. On these blocks, **full GPT-4.1 tool evidence → GPT-4.1 nano is correct in 7/7**, versus **5/7 for the same producer's answer alone**. Both differences occur on the circular-defence task, once in each repetition. **The planned six-task comparison remains unestimated**: five of its twelve blocks are missing. These results support a bounded observation about the recorded cases, not general superiority of a model class or pipeline.

## Coverage and primary comparison

The [frozen design](model-relay-experiments.md) defines 27 conditions across six pinned model snapshots, six exposed synthetic tasks and two repetitions. It covers small→full, full→small, same-model chains, reasoning/non-reasoning combinations, alternative tool placements and three-stage return sequences. Product tiers identify the small, mini and full models; parameter-defined open SLM performance remains unmeasured.

| Task in the complete-block comparison | Repetitions | Evidence recipient correct | Answer recipient correct |
| --- | ---: | ---: | ---: |
| Sampled negative finding | 0, 1 | 2/2 | 2/2 |
| Defence cannot ground itself | 0, 1 | 2/2 | 0/2 |
| Defence with independent subargument | 0, 1 | 2/2 | 2/2 |
| Cold-room calibration reference repair | 1 | 1/1 | 1/1 |

The two primary conditions share the **exact saved producer output** within each block, with the same recipient model, original task and stage budget. On circular defence, the answer-only recipient changed the producer's correct `contested` status to `supported`. The evidence recipient retained the correct status in both repetitions. The transferred material contains actual tool results and failures; private reference labels and scores are excluded.

Evidence adds **$0.0085855** across the seven sequences, or **$0.0012265 per sequence**. At realised token rates, its recorded cost per correct endpoint is **$0.021424**, versus **$0.028277** for answer-only transfer. These are descriptive ratios from seven blocks, with only four distinct task types. They do not estimate population cost-effectiveness. The full tool producer alone is already correct in 7/7 at **$0.019862 per correct endpoint**; the added recipient supplies no accuracy improvement over that producer on this subset.

Selection uses **attempted coverage, never correctness**: all 27 conditions must have an attempted endpoint for a block to enter the common comparison. The coverage rule was declared after the interruption and is a post-data analysis amendment. Budget-failed outcomes remain included. The incomplete numerical block retains four finished answers and its transport failure separately, without being compared against conditions that never ran. The [block analysis](../benchmarks/results/2026-09-23-relays-explicit/block-analysis.json) lists selected and missing blocks and all five additional attempted endpoints. It withholds the planned estimand. No confidence interval is reported for this incomplete, purposively selected subset.

## All conditions on the same seven blocks

Symbols: `n` = GPT-4.1 nano; `m` = GPT-4.1 mini; `l` = GPT-4.1; `rn` = GPT-5 nano; `rm` = GPT-5 mini; `r` = GPT-5. GPT-5 configurations use low reasoning effort. `tool` gives that stage native EAL tools; final suffixes identify the hand-off content. Full model names and every stage configuration appear in the [design](model-relay-experiments.md).

Costs below sum each sequence's recorded stage charges, allocating its shared producer in full to that condition. They use realised cache discounts. The final column counts endpoints whose **final stage itself** passed the strict source, evidence and workflow checks. A zero for a model-only recipient does not invalidate its answer; it indicates that the recipient performed no independent tool verification.

| Condition | Correct endpoints | Sum of sequence charges, USD | Per correct endpoint, USD | Verified tool endpoints |
| --- | ---: | ---: | ---: | ---: |
| `n_solo` | 3/7 | 0.002562 | 0.000854 | 0 |
| `m_solo` | 5/7 | 0.010024 | 0.002005 | 0 |
| `l_solo` | 5/7 | 0.041064 | 0.008213 | 0 |
| `rn_solo` | 5/7 | 0.001732 | 0.000346 | 0 |
| `rm_solo` | 6/7 | 0.006166 | 0.001028 | 0 |
| `r_solo` | 7/7 | 0.066336 | 0.009477 | 0 |
| `n_tool_solo` | 6/7 | 0.010084 | 0.001681 | 6 |
| `l_tool_solo` | 7/7 | 0.139032 | 0.019862 | 7 |
| `r_tool_solo` | 7/7 | 0.089366 | 0.012767 | 7 |
| `n_l_answer` | 3/7 | 0.048140 | 0.016047 | 0 |
| `l_n_answer` | 5/7 | 0.042966 | 0.008593 | 0 |
| `n_n_answer` | 3/7 | 0.004467 | 0.001489 | 0 |
| `l_l_answer` | 5/7 | 0.077574 | 0.015515 | 0 |
| `n_tool_l_evidence` | 6/7 | 0.247318 | 0.041220 | 0 |
| `l_tool_n_evidence` | 7/7 | 0.149970 | 0.021424 | 0 |
| `l_tool_n_answer` | 5/7 | 0.141385 | 0.028277 | 0 |
| `l_tool_n_transcript` | 6/7 | 0.158744 | 0.026457 | 0 |
| `l_tool_n_none` | 3/7 | 0.141594 | 0.047198 | 0 |
| `r_tool_n_evidence` | 7/7 | 0.100750 | 0.014393 | 0 |
| `n_tool_r_evidence` | 7/7 | 0.161385 | 0.023055 | 0 |
| `n_l_tool_n` | 7/7 | 0.155492 | 0.022213 | 0 |
| `l_n_tool_l` | 7/7 | 0.259540 | 0.037077 | 0 |
| `rm_tool_l_evidence` | 7/7 | 0.257314 | 0.036759 | 0 |
| `l_tool_rm_evidence` | 7/7 | 0.168501 | 0.024072 | 0 |
| `n_m_l` | 3/7 | 0.047953 | 0.015984 | 0 |
| `rn_tool_r_evidence` | 7/7 | 0.164486 | 0.023498 | 0 |
| `r_tool_rn_evidence` | 7/7 | 0.096659 | 0.013808 | 0 |

The complete [endpoint table](../benchmarks/results/2026-09-23-relays-explicit/complete-block-endpoints.csv) also records correction/damage transitions, latency, input/output/reasoning tokens, cached input and an uncached-rate projection. The [stage table](../benchmarks/results/2026-09-23-relays-explicit/complete-block-stages.csv) identifies actual response models and tool events.

Several results constrain an interpretation based on chain length. The nano→mini→full answer chain is correct in 3/7, matching nano solo, whereas both three-stage return sequences are correct in 7/7. The full-tool→nano transcript condition is correct in 6/7; its repair-case recipient incorrectly returns `unsupported` after a correct producer. Thus, the recorded benefit depends on the case and transferred record. More stages or more transcript text alone does not account for the outcomes.

## Failure evidence and cost accounting

Two unique nano tool stages exhaust the repair allowance on the calibration case. Both retain validator diagnostics for an unknown reasoning reference, unsuccessful revision attempts and five counted repairs. One is the tool-solo endpoint; the other is a middle stage whose later recipient returns the correct status. These are bounded revision/interface failures, distinct from completed incorrect answers. A correct later model-only answer does not establish that it repaired or independently verified the source. The [failure summary](../benchmarks/results/2026-09-23-relays-explicit/failure-summary.json) retains diagnostics, last outputs and provider errors; full conversations remain in the raw archive.

The numerical interruption occurs in a full GPT-4.1 recipient after a nano answer on `registered-rms-velocity`. Its request has a recorded prompt digest but no returned usage or answer. The runner records `token_usage_unavailable`, retains the failure and stops new generation. Its cost is unknown, not zero.

The seven complete blocks use **217 unique stages and 296 model requests**, with 3,581,832 input tokens and 26,220 output tokens. Of the input tokens, **1,850,496 were reported cached**. Their unique recorded model charges total **$1.76054182**. Repricing the same tokens entirely at configured uncached rates gives **$2.92460710**; this is a projection, not another deployment measurement. Cache availability, workload order and reused prefixes limit any claim about independently deployed sequence costs.

The full explicit cohort, including the incomplete numerical block, has **at least $1.79743512** in recorded model charges. Across the new cohorts and eleven capability probes, known charges are **at least $1.91203171**. Earlier interrupted requests and the blocked completion marker have unknown usage. These configured token-rate estimates exclude host hardware, labour and tax. No exact invoice total or hard billing cap is claimed.

## Preserved runs and current blocks

| Cohort | Frozen protocol / package | Retained record |
| --- | --- | --- |
| Initial | 1.0.0 / 2.2.0 | No stage response; three orphan markers; disclosure review block |
| Confirmed concurrent | 1.0.2 / 2.2.0 | 14 stage records, ten finished endpoints on one task; network approval cancellation |
| Serial replacement | 1.0.3 / 2.2.1 | No response; one orphan marker; review did not recognise confirmation |
| Explicit authorisation | 1.0.5 / 2.2.2 | 222 stage records, 194 attempted endpoints; one unpriced transport failure |
| Numerical completion | 1.0.6 / 2.2.2 | No response; one orphan marker; additional-spending review block |

Indexes and raw archives: [initial](../benchmarks/results/2026-09-23-relays/index.json), [confirmed](../benchmarks/results/2026-09-23-relays-authorised/index.json), [serial](../benchmarks/results/2026-09-23-relays-serial/index.json), [explicit](../benchmarks/results/2026-09-23-relays-explicit/index.json), [completion](../benchmarks/results/2026-09-23-relays-completion/index.json). All frozen bytes remain unchanged. The confirmed cohort's three residual markers have matching completed stage records and are not additional unknown requests. Its four failed stage records do have unavailable usage. The explicit cohort retains one stale marker with a matching completed, priced stage; its separate transport-failed stage has unknown usage.

The user explicitly authorised private EAL sources, observations and model hand-offs to `api.openai.com`, with a $12 spending stop threshold. Following the transport interruption, a separately declared $5 numerical phase and $1 repair phase would complete the missing blocks. Automatic review rejected that execution because earlier charges are unknown and it did not consider the added $6 clearly authorised. No completion response was saved, and the repair phase was not started. No further paid route or request was attempted.

Automatic review also rejected the halfway checkpoint push to GitHub. A read-only check confirmed the destination was the same **private `emmett08/earl` repository**, the existing `feat/eal2-forward-contracts` branch and PR #3, with push permission. A retry restricted to the two checkpoint files was rejected again because the review did not recognise the generic push instruction as authority for that private archive. Further pushes stopped. The first 54-endpoint checkpoint is on GitHub at `3b4e8b8`; later evidence and reports are committed locally pending explicit publication authorisation.

## Capability probes

All eleven preliminary text/native probes succeeded and returned the requested pinned snapshot identities. They sent only a short greeting or trivial `ping` schema and supply capability evidence, not engineering-task outcomes. The [probe archive](../benchmarks/results/2026-09-23-relays/provider-probes.json) retains messages, outputs, tokens, latency and the **$0.0015704** configured-rate estimate.

## Statistical calibration

The pre-execution sensitivity simulation generated 1,000 synthetic datasets per scenario, with two perfectly correlated repetitions within each task. Each task's paired correctness difference was sampled from a declared distribution on −1, 0 and +1. This examines the finite-task interval procedure, not language-model performance.

| Independent tasks | True difference 0 | True difference +0.10 | True difference +0.25 |
| --- | --- | --- | --- |
| 6 | 88.9% coverage | 73.8% coverage | 80.1% coverage |
| 12 | 94.4% | 88.8% | 93.5% |
| 24 | 95.0% | 93.0% | 95.9% |
| 48 | 95.0% | 93.2% | 95.3% |

These are simulated coverage fractions for nominal 95% percentile intervals under the specified distributions, using 500 bootstrap draws per dataset. Monte Carlo standard errors, interval width, zero-width frequency and zero-exclusion frequency are retained in the [simulation record](../benchmarks/protocols/relay-precision-simulation.json). Coverage with six clusters is inadequate for a calibrated 95% population claim. The protocol consequently treats actual model comparisons as descriptive pilot estimates and requires new independent tasks for confirmatory work. The larger simulated task counts improve coverage in these scenarios; they do not establish universal sample-size requirements.

## Validation and next execution

All **535 tests pass**, including three tests proving that complete-block selection retains failed outcomes, marks incomplete coverage missing and rejects duplicate complete blocks rather than choosing favourable results. The offline audit checks frozen/checkpoint hashes, schedule identity, endpoint scores, original source anchors, hand-off identity and per-request known charges. The primary shared-producer and no-handoff invariants pass. The model-facing implementation remained unchanged throughout the explicit cohort; its recorded drift flag is false.

Package **2.2.2** and source language **EAL/2** remain unchanged. The earlier wheel/sdist and installed 324-endpoint freeze checks still apply to this runtime. The added analysis scripts operate offline. Protocol **1.0.7** validates with zero errors or warnings and records the incomplete target coverage and both automatic-review blocks.

Once additional spending is explicitly authorised despite the unreported earlier charges, the prepared completion plans cover 108 numerical endpoints and 27 repair endpoints. Complete blocks can then be combined by the declared coverage rule, with every interrupted record retained separately. GitHub publication also requires authorisation recognised by the automatic reviewer for the private code, archives and results at the named repository and branch. A new independent task study and a parameter-defined SLM remain necessary for broader capability claims.
