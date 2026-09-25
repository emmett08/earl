# One API load-test development experiment

This experiment extends the [single engineering example](../../examples/api-load-test/README.md) with real HTTP measurements and live model calls. A developer asks whether an identified orders API run meets its latency and error limits. The model must select the right report, inspect its evidence and give a decision limited to that measured run.

Version 4 addresses failures observed in the version 3.1 nano run: successful checker output was followed by malformed or incorrect model answers, and a transient provider error stopped later assignments. It supplies explicit answer templates, concise operation-repair feedback, host-bound report context and optional explanation. A separately selected checked finalisation mode retains the checker decision directly. Transient provider recovery is bounded by call and spending limits. These changes are prospective; no live version 4 results are reported. A small, manually dispatched **calibration** precedes any larger development invocation. The full catalogue still contains 40 reviewed cases and six model snapshots. This is a measurement and development investigation; it is not a powered superiority or equivalence study.

## What is compared?

Each selected model receives the assigned arms on the **same immutable evidence for each case**. The default model-finalisation design has six arms. Checked finalisation assigns only EAL/MCP and `plain_validator`. The fixed argument is supplied; authoring EAL source is outside the experiment.

| Arm | Prompt | Tool available to the model |
| --- | --- | --- |
| `eal_mcp` | Complete EAL/2 argument | `assess_load_test(report_id)`: real MCP validation, collection, reasoning and explanation |
| `json_prompt` | JSON semantic representation of that exact argument | `inspect_report(report_id)`: direct evidence inspection; no MCP or EAL assessment |
| `plain_brief` | “Test the API under load and make sure it is within the latency and error bounds below.” | Same direct inspection tool |
| `plain_explicit` | Developer asks to compare measured p95 and errors with acceptance criteria | Same direct inspection tool |
| `plain_review` | Developer asks for a performance check before merging | Same direct inspection tool |
| `plain_validator` | Same explicit developer prompt as `plain_explicit` | Direct evidence inspection plus an ordinary deterministic checker; no MCP or EAL runtime |

The prose prompts include the same workload, identity, freshness and acceptance requirements. JSON is ordinary prompt text, not an API structured-output setting. Its equivalence is checked against the parsed EAL semantic representation. Both representations contain the same `SELECT_REPORT` acquisition selector: the host substitutes only the chosen report ID, leaving the target claim and criteria fixed. JSON and prose never receive an EAL assessment. The `plain_validator` arm receives an ordinary checker result, with the same decision, check and metric fields as the EAL packet. Its comparison with `plain_explicit` diagnoses the contribution of supplying executable checks in this setting; it does not establish that any remaining EAL difference comes solely from notation.

There are **five EAL comparator contrasts for each model**: EAL minus JSON, brief prose, explicit prose, review prose and prose with the conventional validator. Each contrast has **40 paired cases** in the full pilot. For example, a pair compares the EAL and JSON answers from the same model, transport and report bundle. With six models, that is 30 separately reported EAL contrasts. A further six tables compare `plain_validator` with `plain_explicit`. The same outcomes occur in several contrasts; the denominator remains 40 case pairs per comparator, not a sum across contrasts. Calibration reports only the cases and arms it actually assigns. Checked finalisation supplies only the EAL/ordinary-validator comparison, labelled as retained checker correctness rather than model-answer accuracy. Keep finalisation modes and operation transports separate.

The earlier report's “four paired blocks” meant four case pairs for one model/comparator: healthy, slow, errors and short run. It did not mean four model comparisons. Its “Insufficient blocks” label meant that the old interval gate had not been met, not that API calls or tokens were missing. Current reports give explicit assigned/completed pair counts and descriptive paired tables.

This compares the **combined EAL/MCP system**, including executable assessment. It does not isolate a notation effect. Prompt length and checking authority differ; calls, tokens, costs and elapsed time are retained.

## Six pinned models and two operation transports

| Model snapshot | Product tier | Model class | Provider setting |
| --- | --- | --- | --- |
| `gpt-4.1-nano-2025-04-14` | Nano | Non-reasoning | Temperature 0.2 |
| `gpt-4.1-mini-2025-04-14` | Mini | Non-reasoning | Temperature 0.2 |
| `gpt-4.1-2025-04-14` | Full | Non-reasoning | Temperature 0.2 |
| `gpt-5.4-nano-2026-03-17` | Nano | Reasoning | Medium reasoning effort |
| `gpt-5.4-mini-2026-03-17` | Mini | Reasoning | Medium reasoning effort |
| `gpt-5.4-2026-03-05` | Full | Reasoning | Medium reasoning effort |

Nano, mini and full are provider product tiers, not disclosed parameter counts. Settings, standard token prices and official sources are frozen in [models.json](models.json), checked on 25 September 2026. GPT-4.1 nano is scheduled to shut down on **23 October 2026** according to the [provider deprecation schedule](https://developers.openai.com/api/docs/deprecations). An unavailable snapshot is recorded as a failure; it is never silently replaced.

**A model does not need native function calling to use MCP through a host.** In the default `text` transport, the model writes a JSON operation request as normal response text. The host validates its operation name and arguments against an allowlisted schema, executes the configured tool, and returns its result as text. For the EAL arm that host starts `eal.server` and uses the real MCP SDK over stdio, calling `eal_validate`, `eal_collect`, `eal_reason` and `eal_explain`. For JSON and prose the host calls the direct collector without MCP or EAL assessment. No model-generated shell command is executed.

All six models use this same text transport by default. Native function calling and API structured-output constraints are disabled for those calls. The common operation envelope is a transport format; it does not turn the prose arms into the JSON-argument arm. `--transport native` is an optional diagnostic using provider-native functions. Its results remain separate. Disabling native tools demonstrates a host-mediated route; it does not establish that these snapshots inherently lack tool capability.

Model reasoning effort is separate from EAL's **`structured/1`** method. That method checks declared dependencies and inclusive predicates against collected evidence. The authored rationale justifies a finite measured-run claim; it is not independently proved, and no population performance guarantee follows. The Responses adapter uses `store: false` and preserves required encrypted reasoning replay during a conversation. Private reasoning replay payloads and credentials are not written to results.

## Forty cases, with one acquisition per case

[cases.py](cases.py) defines ten families with four variants each:

| Family | Engineering question |
| --- | --- |
| `healthy` | Can adequate matching evidence support the run's criteria? |
| `near_limit` | Are inclusive latency/error limits applied to actual measurements near the boundary? |
| `slow` | Is a measured latency failure recognised despite a favourable summary? |
| `errors` | Are failed requests counted despite a favourable summary? |
| `incomplete` | Does missing request evidence prevent a decision? |
| `wrong_identity` | Does evidence match the requested service, build, run and workload? |
| `stale` | Is evidence fresh at the declared assessment time? |
| `corrupt` | Are malformed measurement fields rejected? |
| `conflicting` | Do contradictory records for the same request prevent assessment? |
| `distractor` | Is the target run selected instead of an attractive report for another run? |

Each case acquires a fresh real loopback HTTP workload once. Original raw reports and server events are retained. Controlled changes to timestamps, identities and recorded rows, and the construction of distractor evidence, are recorded explicitly as fault injections. A misleading summary is an untrusted annotation, not a replacement for measured data. No fabricated request timing is presented as an observation.

The evidence bundle, target scope and assessment time are then frozen before any paid calls. Every arm and model sees the same bundle. Freshness means no more than 300 seconds old **at that frozen assessment time**; later model calls replay the assessment. This prevents slow model responses from changing the evidence's status. The result is a decision about that identified historical run, not a fresh production health check. Case family names and oracle answers are withheld from model prompts; report IDs are opaque.

Variants change concurrency and fault details. The reference uses actual measured timing, never an intended “healthy” or “slow” label. Repeating a variant is not a substitute for independent task coverage.

## Decision and grading

The finite acceptance criteria are: matching service/build/run/workload and response identities; valid, complete, consistent evidence; age at most 300 seconds at assessment; at least 100 requests; nearest-rank sample p95 at most 200 ms; and at most 1% errors. Every attempted request counts; non-2xx and transport failures are errors. A scored report must retain a valid acquisition envelope: its schema, dataset label, input/context objects and timezone-qualified observation time. Malformed request measurements within that envelope produce `unavailable` with unknown performance checks. Missing or malformed envelope metadata is an instrument failure; the host rejects it without inventing a measurement timestamp.

| Decision | Meaning |
| --- | --- |
| `supported` | Adequate evidence meets every finite criterion. |
| `unsupported` | Adequate evidence demonstrates a failed sample-size, latency or error criterion. |
| `unavailable` | Invalid, mismatched, incomplete, stale or conflicting evidence prevents that assessment. |

With `--finalisation model` (the default), the model must submit an explicit `finish` operation containing `status`, `failed_checks`, `unknown_checks` and measured count/p95/error rate. The host binds the most recently inspected `report_id` and requested `scope` (service, build, run and concurrent clients). These context fields are optional in the operation; conflicting supplied values are rejected rather than overwritten. Explanation is optional and defaults to an empty string. Its presence is recorded separately from substantive correctness. A check is **failed** only when its evaluated value is `false`. A check is **unknown** when its evaluated value is `null` because the evidence cannot establish it. A passed check belongs to neither list. Missing evidence can establish that evidence validity failed while leaving performance checks unknown; unknown performance is not a demonstrated performance failure.

The reference grades these fields independently from raw rows and case provenance. Full correctness requires collection, correct selection and scope, the correct status and both complete check sets, an exact count, and numeric measurements within 0.01 units; measurements that cannot be computed must be null. Narrative explanation and private model reasoning are not scored. The version 4 response contract separates required decision fields from host-owned context and optional narrative. Historical scores remain frozen under their original contracts.

The model receives **one canonical `status` field** in each checked result. When EAL cannot support the claim because evidence is inadequate, the host maps that evidence condition to `unavailable`; an adequate measured failure maps to `unsupported`. EAL's raw support status remains in the retained audit trace and is omitted from the model-facing packet. The ordinary validator uses the same canonical decision contract. Every route’s metrics and measurement facts are checked privately against the independent raw-row reference; checked routes also have their status and checklists verified. These audit results never supply a verdict to the measurement-only arms. Host support alone earns no model credit.

After inspection, checked arms receive a complete `finish` template containing their returned status, check sets and metrics. Measurement-only arms receive a partial template with status and check sets explicitly listed as fields the model must supply; the host does not insert oracle decisions. Repair feedback names the missing or invalid operation fields and states that the report evidence remains unchanged. The adapter never silently infers a missing `operation` or converts a syntax error into failed or unknown measurement checks.

With `--finalisation checked`, only `eal_mcp` and `plain_validator` are eligible. The model selects and inspects evidence; the host then retains the returned deterministic decision without asking the model to restate it. This tests the selected checker workflow. It does not measure model-authored answer accuracy. Finalisation enters assignment identities and appears in the manifest, trial records and summary. Reports distinguish `answer_origin`, retained-answer completion, valid model-finish completion and explanation presence. A checked answer is recorded separately from a successful model `finish`. Omitting the optional narrative does not prevent a valid model `finish`.

Missing, malformed, uncollected, failed and unattempted assignments score zero in the planned denominator. Component counts expose status, metric, selection, scope, failed-check and unknown-check errors. False support, false rejection, false unavailability, correct unavailability and unsupported assertions without collection are reported separately. “Complete” means a result was retained through the selected finalisation mode; correctness and valid model-finish counts are reported separately.

For each model and contrast, the paired table names its reference and comparator arms and reports both correct, reference only correct, comparator only correct and both incorrect. EAL is the reference in its five comparisons; `plain_validator` is the reference when compared with `plain_explicit`. The assigned-suite difference is:

```text
(reference-only correct − comparator-only correct) / all assigned paired cases
```

Completed-pair counts and a separate completed-pair 2×2 table are reported alongside that denominator, so a provider outage is not mistaken for a task-decision discordance. Collector/reference disagreement, host failures and frozen-evidence integrity defects suspend interpretation of affected comparisons. Diagnostic counts and recorded usage remain available. The completed subset may be selected by model or transport failure; it supports diagnosis, not an efficacy estimate with failures discarded. These are exact descriptions of the recorded assignments. **No population confidence interval, superiority, equivalence or model-class ranking is claimed.** Forty purposively selected development cases are not a power calculation. The next inference gate is a separately frozen held-out case distribution, with simulation-checked interval coverage and power across plausible discordance, family dependence, model variability and missingness. That future protocol must declare its practical effect margin, comparison family and stopping rule before observing held-out results.

## Run in GitHub Actions

The [workflow](../../.github/workflows/api-experiment.yml) builds the custom [Docker image](Dockerfile). Python, Java, Make, the package, locked Python dependencies, parser generator, tests, HTTP service and collectors are bundled. The runner needs Bash, Docker and outbound package/OpenAI access; it does not need host Python.

1. Set repository secret **`OPENAI_API_TOKEN`**.
2. The runner defaults to GitHub-hosted **`ubuntu-24.04`**. To use a registered custom runner, set repository variable **`EAL_RUNNER_LABEL`** to its available label. A queued job awaiting a runner has not started its container or made model calls.
3. The experiment runs **only by manual dispatch**. PR updates and pushes do not start the experiment or its Docker job. Changing the trigger does not cancel a run that has already started.
4. Once the workflow is on the default branch, open **Actions → API load-test model experiment → Run workflow**, select the branch and choose `calibration` (default), `smoke` or `pilot`. Select all six models or one exact snapshot. The transport defaults to `text`; `native` starts a separately labelled diagnostic. Select `finalisation: model` for model-authored answers or `checked` for direct retention of EAL/ordinary-validator results. A new dispatch does not cancel an existing run for that branch.

The workflow is available for manual dispatch. Updating this code does not start a paid experiment; version 4 calibration requires a fresh invocation.

| Mode | Cases | Model finalisation: arms / assignments | Checked finalisation: arms / assignments | Calls per trial | Admission allowance |
| --- | --- | --- | --- | ---: | --- |
| `calibration` | Healthy, corrupt and stale variant 0 | EAL, JSON, validator / **54** | EAL, validator / **36** | 3 | $0.50/model; $3 total |
| `smoke` | Healthy, errors, stale and distractor | Six arms / **144** | EAL, validator / **48** | 6 | $5/model; $30 total |
| `pilot` | All 40 cases | Six arms / **1,440** | EAL, validator / **480** | 6 | $20/model; $120 total |

Assignment totals above use all six snapshots. With one snapshot, calibration has nine model-finalisation assignments or six checked-finalisation assignments, with a $0.50 admission allowance. Calibration diagnoses the operation contract, finalisation and provider recovery. Inspect its retained outcomes before explicitly choosing a larger invocation. No successful calibration starts another run automatically.

Up to six model workers run concurrently, each following its seeded case/arm order. Every mode retains the 4,096 output-token cap and 120-second request timeout. The cap includes reasoning and visible output on reasoning models; calibration establishes whether it is adequate for the frozen settings. These conservative local spending limits are neither provider billing guarantees nor predicted costs.

The secret enters only the paid container's runtime environment, never an image layer, build argument or command-line value. Collector and MCP child environments omit it. A known-cost incomplete response or ambiguous multiple-message operation response fails its trial; subsequent assignments remain eligible. Provider termination status and `incomplete_details`, public response-message boundaries, response IDs and usage are retained for diagnosis. The host does not concatenate distinct visible messages into one operation or silently salvage a partial answer.

Provider-marked retryable `http_server`, `timeout` and `transport` failures may retry at most **twice per trial**, after delays of **1 and 2 seconds**. These attempts consume the existing model-call cap; they do not add calls beyond three in calibration or six in smoke/pilot. Unknown charges retain their original reservations and durable call records. A returned response whose model identity or usage cannot be verified remains fatal. These provider retries do not apply to an incorrect answer, schema mistake, output truncation or account/configuration failure. Operation errors instead receive the declared repair feedback within the same call cap.

If transient recovery is exhausted, that trial fails and the next frozen assignment remains eligible. **Three consecutive transient-failed trials** open the provider circuit and stop that model. Fatal account/configuration failures, unclassified failures, unexpected returned identity or usage, host exceptions, checker/reference disagreement and exhausted spending admission stop the model immediately. Remaining assignments are retained as unattempted. A single retryable 503 therefore no longer discards every later assignment. These are frozen recovery rules, not favourable reruns or model substitution.

The paid step prints a start event for each request, followed by completion with response ID and token usage, or failure. A start records an attempt; returned usage establishes measured token consumption. Evidence acquisition and Docker checks occur before paid calls and consume no OpenAI tokens. Raw evidence, manifests, responses, traces, component scores and summaries are uploaded as workflow artefacts. Each dispatched call has one durable record that is updated on completion or failure. Cancellation retains unresolved attempts as unknown-cost calls; requests still waiting for admission make no API call. Returned snapshot identity must match before the configured rate is used. The workflow stops its named paid container before credential-free, network-disabled summary recovery. If the runner itself is lost, recover from the retained files when available; no local checkpoint can guarantee evidence survives destruction of its storage.

## Run the same image locally

```bash
docker build -f experiments/api_load_test/Dockerfile -t eal-api-experiment .
# Full repository checks, the synthetic example, and real HTTP/MCP controls:
docker run --rm --network none eal-api-experiment

# OPENAI_API_TOKEN must already be exported in your environment.
mkdir -p experiment-results
docker run --rm --user "$(id -u):$(id -g)" \
  --env OPENAI_API_TOKEN \
  --env EAL_SOURCE_COMMIT="$(git rev-parse HEAD)" \
  --volume "$PWD/experiment-results:/results" \
  eal-api-experiment \
  python -m experiments.api_load_test run --mode calibration --transport text --finalisation model --output /results/run
```

Use a fresh output directory; the runner refuses to overwrite one. Calibration is the CLI default. Use `--model` with an exact table ID for one snapshot, or `--transport native` for a separately labelled native-function diagnostic. Use `--finalisation checked` in a fresh output directory for EAL/ordinary-validator finalisation without model restatement. Keep that result separate from `model` finalisation. Choose `--mode smoke` or `--mode pilot` explicitly only when their larger scope is intended. Recompute summaries, including interrupted-run summaries, without model calls with:

```bash
python -m experiments.api_load_test analyse --output experiment-results/run
```

Analysis reports retained running trials as interrupted without rewriting the original trial records or resuming paid work. It verifies case digests and suspends affected comparisons when measurement integrity fails.

`make experiment-check` exercises real HTTP and MCP without credentials in an installed checkout. Unit tests may use explicitly mocked paid-provider replies; those replies are never empirical model-comparison evidence.

[protocol.json](protocol.json) is the versioned, specified calibration and development protocol; [plan.json](plan.json) contains executable limits. The manifest freezes materials, case hashes, model settings, source revision, dependencies and assignments before the first paid request. There is no independent preregistration claim. The protocol version is **4.0.0**. Current plan, run and summary schemas are `eal-api-experiment/4`, `eal-api-experiment-run/4` and `eal-api-experiment-summary/4`. The protocol document schema remains 1.0 and raw reports remain `eal-live-api-report/2`. EAL source syntax remains EAL/2 and its reasoning method remains `structured/1`. Live version 4 validation is pending; prior observations below retain their original schemas and scores.

## Retained version 1 feasibility result

[Run 36158948994](https://github.com/emmett08/earl/actions/runs/36158948994), from source `6fd9623a09d08da99333c3a5a74dedb47dec72eb`, completed 80/80 correct assigned trials and 160 successful OpenAI calls. Its frozen standard-token estimate was **$0.34201775**, not an invoice. The four-profile task was at ceiling, so this established live feasibility and no observed accuracy advantage; it established neither equivalence nor general superiority.

That result belongs to version 1, not the revised cases or newly added nano models. Its [retained artefact](https://github.com/emmett08/earl/actions/runs/36158948994/artifacts/10875053357) has ZIP SHA-256 `2de6bbf2ccddb335d6622ffb8428594e5267f3da3756ec5f3f5d62c16bf7537e`. New outcomes must identify their own source revision, manifest, run and attempt. Docker base/OS packages may change between builds, so image inspection is retained alongside pinned Python dependencies, ANTLR digest and model snapshots.

## Retained version 2 development result

[Run 36163505801](https://github.com/emmett08/earl/actions/runs/36163505801), from source `3490076dd78404caa1326d9aae704f964910c4c8`, passed Docker validation, 742 tests and HTTP/MCP controls. Of 1,200 assignments, **628 completed, 131 failed and 441 were unattempted**. The failures comprised 128 trials at the six-call limit and three incomplete provider responses. Each incomplete response consumed exactly the 4,096 output-token allowance, strongly indicating exhaustion; the old adapter omitted `incomplete_details`, so the exact provider reason was not retained. Its broad stop rule then left all remaining assignments for those models unattempted.

The 2,342 API calls used 4,453,730 input tokens and 608,449 output tokens, including 254,011 reasoning tokens. The frozen standard-token estimate was **$3.97892431**, excluding GitHub charges and not representing an invoice. All 141 executed MCP assessments agreed with independently recomputed evidence and conclusions.

| Snapshot tier in GPT-4.1 | Completed / assigned | EAL | JSON | Brief | Explicit | Review |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 200 / 200 | 40 | 36 | 33 | 31 | 32 |
| Mini | 200 / 200 | 32 | 21 | 21 | 20 | 21 |
| Nano | 123 / 200 | 16 | 6 | 7 | 5 | 3 |

Scores are fully correct answers out of 40 assigned cases per arm under the **version 2 rubric**. Full GPT-4.1 gave 40/40 correct verdicts with both EAL and JSON; JSON's four full-answer misses labelled unassessable checks as failed. The prompt had not clearly distinguished those states. Seven of mini's eight EAL misses selected raw EAL `unsupported` instead of experiment `unavailable` while the packet exposed both status fields. Nano made zero false-support assertions with EAL and 24 with JSON, an observed development-suite signal with substantial remaining completion and classification failures.

GPT-5.4 full, mini and nano completed respectively 0, 80 and 25 conversations. These incomplete results and the adapter's lost message boundaries cannot support a reasoning-versus-non-reasoning ranking. The fixed-suite full-answer differences confound checking assistance, notation, prompt design and instrument defects. Version 3 introduced diagnostic repairs and the conventional checker control. Its later nano-only invocation is reported separately below; those changes never replace version 2 scores.

The [retained version 2 artefact](https://github.com/emmett08/earl/actions/runs/36163505801/artifacts/10879620453) has ZIP SHA-256 `bf5b59c340b1c11c85a3e39679bc9cc1bc4521af741f45d9dc5cc1c65cbd8547`. Preserve it as diagnostic evidence with its original manifest and source revision.


## Retained version 3.1 nano development result

[Run 36176588712](https://github.com/emmett08/earl/actions/runs/36176588712) used only `gpt-4.1-nano-2025-04-14`, source `8220e838a8d42922edc0496ff50927c672a1f87d` and six arms under the version 3.1 contract. Of 240 assignments, **141 completed, 43 failed and 56 were unattempted**. The original assigned-case scores were:

| Arm | Fully correct / assigned | Completed | Failed | Unattempted |
| --- | ---: | ---: | ---: | ---: |
| EAL/MCP | 3 / 40 | 16 | 14 | 10 |
| JSON | 6 / 40 | 28 | 3 | 9 |
| Brief prose | 6 / 40 | 27 | 4 | 9 |
| Explicit prose | 5 / 40 | 26 | 4 | 10 |
| Review prose | 6 / 40 | 26 | 5 | 9 |
| Ordinary validator | 11 / 40 | 18 | 13 | 9 |

Every attempted EAL trial selected the correct report and completed all four MCP operations successfully. All 30 EAL tool/reference comparisons agreed. Fourteen trials then exhausted the six-call cap while trying to submit a final operation; all had already received correct checker output. The first post-tool response in each of these fourteen retained correct metrics and failed/unknown check sets. Two trials subsequently supplied every scored field correctly but omitted the required explanation. These observations diagnose the historical contract; they do not replace its failure scores.

A retryable provider HTTP **503**, with unknown call cost, stopped the model under the version 3.1 rule. The remaining 56 assignments were consequently unattempted. They were not rejected by EAL and contain no evidence of model capability. The completed EAL answers also contain substantive errors: 12 of 16 statuses were incorrect, despite the tool supplying one canonical status. Thus schema completion alone would not explain or repair the whole performance deficit.

The ordinary validator's higher assigned-case yield is adverse evidence against an EAL/MCP advantage in this invocation. Prompt content, finalisation burden and incomplete execution prevent a notation-only conclusion. The cases were newly acquired and the rubric differed from version 2; do not pool these runs or describe the nano score change as an isolated model regression.

The [retained version 3.1 artefact](https://github.com/emmett08/earl/actions/runs/36176588712/artifacts/10883614782) has ZIP SHA-256 `186adeb144ccaf4c77f5e36165999f3ad203a98bcfc24a7119c68d5c5eb206c5`. Preserve its original manifest, transcripts and scores. Version 4 responds to these observed failures with a changed contract and prospective recovery settings; its performance requires fresh measured results.
