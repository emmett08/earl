# EAL/2 model-sequence results — 23 September 2026

The **92 earlier trials are recovered and pushed**, with their original prompts, failures, usage and frozen inputs. Their [report](eal2-model-results.md) retains the stateless-host interface confounds and original findings.

The first explicitly authorised cohort retained **194 attempted endpoint records, including 192 finished answers**. The continuation added **49 attempted endpoint records, including 48 finished answers**, before a GPT-4.1 mini request returned HTTP 429. A separate diagnostic then returned `insufficient_quota` / `credit_balance_exhausted`. The provider account needs prepaid credits before generation can continue. The repair phase was not started. Both cohorts retain their original records; their combined **243 attempts and 240 finished answers** include repeated cases in incomplete blocks and must not be treated as 243 independent cases.

Eight complete task/repetition blocks provide **216 comparable endpoints**, including one repair-limit failure. **Full GPT-4.1 tool evidence → GPT-4.1 nano is correct in 8/8**, versus **5/8 for the same producer's answer alone**. Two differences occur on circular defence and one on an observation with the wrong origin. **Four of the planned twelve blocks remain incomplete**, so the six-task estimand is still withheld. All recovered code, freezes, observations, model outputs and reports are committed to the existing branch for [PR #3](https://github.com/emmett08/earl/pull/3).

## Coverage and primary comparison

The [frozen design](model-relay-experiments.md) defines 27 conditions across six pinned model snapshots, six exposed synthetic tasks and two repetitions. It covers small→full, full→small, same-model chains, reasoning/non-reasoning combinations, alternative tool placements and three-stage return sequences. Product tiers identify the small, mini and full models; parameter-defined open SLM performance remains unmeasured.

| Task in the complete-block comparison | Repetitions | Evidence recipient correct | Answer recipient correct |
| --- | ---: | ---: | ---: |
| Sampled negative finding | 0, 1 | 2/2 | 2/2 |
| Defence cannot ground itself | 0, 1 | 2/2 | 0/2 |
| Defence with independent subargument | 0, 1 | 2/2 | 2/2 |
| Cold-room calibration reference repair | 1 | 1/1 | 1/1 |
| Registered RMS with wrong observation origin | 0 | 1/1 | 0/1 |

The two primary conditions share the **exact saved producer output** within each block, with the same recipient model, original task and stage budget. On circular defence, the answer-only recipient changes the producer's correct `contested` status to `supported`. On the wrong-origin case, it changes the correct `unsupported` status to `supported`. The evidence recipient preserves the correct status in all three comparisons. Transferred records contain actual tool results and failures; private reference labels and scores are excluded.

Evidence adds **$0.0093476** across the eight sequences, or **$0.00116845 per sequence**. Its recorded cost per correct endpoint is **$0.022252**, versus **$0.033733** for answer-only transfer. These descriptive ratios concern eight blocks drawn from five distinct task types. They do not estimate population cost-effectiveness. The full tool producer alone is already correct in 8/8 at **$0.020695 per correct endpoint**; the added recipient supplies no accuracy improvement over that producer on this subset.

Block selection depends on **attempted coverage, never correctness**: every one of the 27 conditions must have an attempted endpoint. The rule was declared after the original interruption, before this continuation, and is a post-data analysis amendment. Budget-failed outcomes remain included. The two incomplete numerical blocks retain **27 further attempted records** separately: five from the original cohort and 22 from the continuation. Both concern `registered-rms-velocity/repeat-1`. The [combined analysis](../benchmarks/results/2026-09-23-relays-continuation/block-analysis.json) lists every selected and missing block. It withholds the planned estimand and reports no confidence interval for this incomplete subset. The earlier [seven-block analysis](../benchmarks/results/2026-09-23-relays-explicit/block-analysis.json) remains unchanged.

## All conditions on the same eight blocks

Symbols: `n` = GPT-4.1 nano; `m` = GPT-4.1 mini; `l` = GPT-4.1; `rn` = GPT-5 nano; `rm` = GPT-5 mini; `r` = GPT-5. GPT-5 configurations use low reasoning effort. `tool` gives that stage native EAL tools; final suffixes identify the transferred content. Full snapshot names and stage configurations appear in the [design](model-relay-experiments.md).

Costs sum each sequence's recorded stage charges, allocating its shared producer in full to that condition at realised cache rates. The final column counts endpoints whose **final stage itself** passed the strict source, evidence and workflow checks. A model-only recipient can return a correct answer without independently verifying the source or evidence.

| Condition | Correct endpoints | Sum of sequence charges, USD | Per correct endpoint, USD | Verified tool endpoints |
| --- | ---: | ---: | ---: | ---: |
| `n_solo` | 3/8 | 0.002848 | 0.000949 | 0 |
| `m_solo` | 5/8 | 0.012974 | 0.002595 | 0 |
| `l_solo` | 5/8 | 0.055812 | 0.011162 | 0 |
| `rn_solo` | 5/8 | 0.001872 | 0.000374 | 0 |
| `rm_solo` | 7/8 | 0.007123 | 0.001018 | 0 |
| `r_solo` | 7/8 | 0.076242 | 0.010892 | 0 |
| `n_tool_solo` | 7/8 | 0.011411 | 0.001630 | 7 |
| `l_tool_solo` | 8/8 | 0.165558 | 0.020695 | 8 |
| `r_tool_solo` | 8/8 | 0.105295 | 0.013162 | 8 |
| `n_l_answer` | 3/8 | 0.054510 | 0.018170 | 0 |
| `l_n_answer` | 5/8 | 0.058019 | 0.011604 | 0 |
| `n_n_answer` | 3/8 | 0.005057 | 0.001686 | 0 |
| `l_l_answer` | 5/8 | 0.098406 | 0.019681 | 0 |
| `n_tool_l_evidence` | 7/8 | 0.279014 | 0.039859 | 0 |
| `l_tool_n_evidence` | 8/8 | 0.178014 | 0.022252 | 0 |
| `l_tool_n_answer` | 5/8 | 0.168666 | 0.033733 | 0 |
| `l_tool_n_transcript` | 7/8 | 0.187914 | 0.026845 | 0 |
| `l_tool_n_none` | 3/8 | 0.168406 | 0.056135 | 0 |
| `r_tool_n_evidence` | 8/8 | 0.118645 | 0.014831 | 0 |
| `n_tool_r_evidence` | 8/8 | 0.182900 | 0.022863 | 0 |
| `n_l_tool_n` | 8/8 | 0.172277 | 0.021535 | 0 |
| `l_n_tool_l` | 8/8 | 0.306270 | 0.038284 | 0 |
| `rm_tool_l_evidence` | 8/8 | 0.301468 | 0.037683 | 0 |
| `l_tool_rm_evidence` | 8/8 | 0.200106 | 0.025013 | 0 |
| `n_m_l` | 3/8 | 0.055816 | 0.018605 | 0 |
| `rn_tool_r_evidence` | 8/8 | 0.192487 | 0.024061 | 0 |
| `r_tool_rn_evidence` | 8/8 | 0.113628 | 0.014204 | 0 |

The complete [endpoint table](../benchmarks/results/2026-09-23-relays-continuation/complete-block-endpoints.csv) records correction/damage transitions, latency, tokens, cached input and an uncached-rate projection. The [stage table](../benchmarks/results/2026-09-23-relays-continuation/complete-block-stages.csv) identifies actual response models and tool events.

The nano→mini→full answer chain is correct in 3/8, matching nano solo, whereas both three-stage return sequences are correct in 8/8. Full-tool→nano transcript transfer is correct in 7/8; its repair-case recipient returns `unsupported` after a correct producer. The observed benefit therefore depends on the case and transferred material. Chain length alone does not explain these outcomes.

## Failure evidence and cost accounting

Two original nano tool stages exhaust the repair allowance on the calibration case. Their records retain validator diagnostics for an unknown reasoning reference, unsuccessful revision attempts and five counted repairs. One is a tool-solo endpoint; the other is a middle stage whose later recipient returns a correct answer. A correct later model-only answer does not establish source repair or independent verification. The original [failure summary](../benchmarks/results/2026-09-23-relays-explicit/failure-summary.json) and raw archives retain the diagnostics and conversations.

The original numerical interruption occurred in a full GPT-4.1 recipient after a nano answer on `registered-rms-velocity`. The continuation stopped in a GPT-4.1 mini middle stage of `n_m_l` on the same task/repetition. Its retained attempt records HTTP 429 and unavailable token usage. A separate 16-token diagnostic request returned `insufficient_quota` / `credit_balance_exhausted`; it returned no completion or usage. The [diagnostic record](../benchmarks/results/2026-09-23-relays-continuation/provider-diagnostic.json) contains the safe error fields. OpenAI's [error reference](https://developers.openai.com/api/docs/guides/error-codes) identifies this code as an exhausted prepaid balance. No further generation was attempted after that diagnosis.

The continuation saved **52 stages and 49 attempted endpoints** from 66 task requests. It completed 48 answers, of which 36 were correct. Its remaining scheduling records contain **57 unexecuted conditions and two partial sequences**. They remain in the archive and are excluded from endpoint-accuracy denominators. The [checkpoint audit](../benchmarks/results/2026-09-23-relays-continuation/numerical-interrupted-audit/checkpoint-audit.json) distinguishes every category.

The eight selected blocks use **248 unique stages and 337 model requests**, with **4,082,245 input tokens**, **29,349 output tokens** and **2,055,808 cached input tokens**. Their unique recorded model charges total **$2.03785940**. Repricing those tokens entirely at configured uncached rates gives **$3.33088340**; this is a projection, not another deployment measurement. Cache availability, workload order and reused prefixes limit claims about independently deployed sequence costs.

The continuation added **at least $0.41123124** in recorded model charges. Across all new cohorts and the eleven original capability probes, known charges are now **at least $2.32326295**. Earlier interrupted requests, the blocked completion marker, the new failed stage and the diagnostic request have unavailable usage. Their actual total remains unknown. Configured token-rate estimates exclude host hardware, labour and tax.

The [continuation budget](../benchmarks/results/2026-09-23-relays-continuation/budget-reconciliation.json) reserved $4.50 for earlier unreported usage, lowered the numerical phase threshold to $3, and retained $1 for repair. A cumulative check included one-response headroom before either phase. The first phase stopped at the first new unknown charge. This planning allowance is not recovered billing or a provider-enforced invoice cap. The account credit limit ended execution before the user-defined $12 threshold was approached by recorded charges.

## Preserved runs and publication

| Cohort | Frozen protocol / package | Retained record |
| --- | --- | --- |
| Initial | 1.0.0 / 2.2.0 | No stage response; three orphan markers; disclosure review block |
| Confirmed concurrent | 1.0.2 / 2.2.0 | 14 stage records, ten finished endpoints on one task; network approval cancellation |
| Serial replacement | 1.0.3 / 2.2.1 | No response; one orphan marker; review did not recognise confirmation |
| Explicit authorisation | 1.0.5 / 2.2.2 | 222 stages, 194 attempts, 192 finished answers; one unpriced transport failure |
| Blocked numerical completion | 1.0.6 / 2.2.2 | No response; one orphan marker; additional-spending review block |
| Renewed authorisation | 1.0.8 / 2.2.2 | 52 stages, 49 attempts, 48 finished answers; HTTP 429 followed by confirmed exhausted credit balance |

Archive indexes: [initial](../benchmarks/results/2026-09-23-relays/index.json), [confirmed](../benchmarks/results/2026-09-23-relays-authorised/index.json), [serial](../benchmarks/results/2026-09-23-relays-serial/index.json), [explicit](../benchmarks/results/2026-09-23-relays-explicit/index.json), [blocked completion](../benchmarks/results/2026-09-23-relays-completion/index.json), and [continuation](../benchmarks/results/2026-09-23-relays-continuation/numerical-interrupted-index.json). The continuation also retains a [first-block checkpoint](../benchmarks/results/2026-09-23-relays-continuation/numerical-first-block-index.json), containing 28 endpoints. Checkpoints are overlapping snapshots and must not be added together as separate observations. All frozen bytes remain unchanged. Residual markers with matching priced stage records are not additional unknown requests.

The previous session's automatic-review blocks on private-data disclosure and GitHub upload are preserved in its metadata. The user renewed explicit authorisation for private EAL sources, observations and model hand-offs to `api.openai.com`, retained the $12 stop threshold, and requested remote push. The recovered commits and the first continuation checkpoint were successfully pushed to the same private `emmett08/earl` repository, branch `feat/eal2-forward-contracts`, PR #3. Publication is no longer blocked. The current execution blocker is the provider account's exhausted credit balance.

## Capability probes

All eleven original text/native probes succeeded and returned the requested pinned snapshots. Their [archive](../benchmarks/results/2026-09-23-relays/provider-probes.json) retains outputs and the **$0.0015704** configured-rate estimate. They supply capability evidence, not engineering-task outcomes. During continuation, the old available credential returned HTTP 401 on a read-only model check; the user-provided replacement returned HTTP 200. These checks performed no generation. The later failed diagnostic is separate from the eleven successful probes and from endpoint scoring.

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

Previous implementation validation passed **535 tests**, including complete-block selection tests. The continuation passed **25 targeted checks**, including seven new tests for cumulative spending controls. GitHub CI passed the repository checks and package build for the continuation commit. Protocol 1.0.9 validates the recorded interruption and remaining scope. Package **2.2.2** and source language **EAL/2** remain unchanged.

Archive hashes, frozen/checkpoint hashes, schedule identities, endpoint scores, original source anchors, transferred-record identities and per-request charges pass the offline audits. The earlier seven-block analysis reproduced exactly. The new eight-block analysis retains the shared-producer and no-handoff invariants. No model-facing runtime, task input, provider configuration, stage budget or scoring change occurred during either cohort; both drift flags are false.

The four missing complete blocks are `registered-rms-velocity/repeat-0`, `registered-rms-velocity/repeat-1`, `registered-rms-wrong-origin/repeat-1`, and `cold-room-calibration-reference-repair/repeat-0`. They represent **108 planned comparison slots**, some of which have partial-cohort observations. Restoring prepaid API credit is required before further requests. A subsequent frozen continuation must retain the failed attempts, refresh cumulative spending from all saved cohorts, and select only missing complete blocks without replaying old records silently. The present completion plans describe the interrupted five-block attempt, so they must be amended before another run. Fresh independent tasks and a parameter-defined SLM remain necessary for broader capability claims.
