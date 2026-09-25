# One API load-test development experiment

This experiment extends the [single engineering example](../../examples/api-load-test/README.md) with real HTTP measurements and live model calls. A developer asks whether an identified orders API run meets its latency and error limits. The model must select the right report, inspect its evidence and give a decision limited to that measured run.

Version 2 is a **development pilot** with 40 reviewed cases and six model snapshots. It tests evidence selection, scope and failure handling after the first, simpler experiment reached 80/80 correct answers. It is not a powered superiority or equivalence study.

## What is compared?

Each model receives all five arms on the **same immutable evidence for each case**. The fixed argument is supplied; authoring EAL source is outside the experiment.

| Arm | Prompt | Tool available to the model |
| --- | --- | --- |
| `eal_mcp` | Complete EAL/2 argument | `assess_load_test(report_id)`: real MCP validation, collection, reasoning and explanation |
| `json_prompt` | JSON semantic representation of that exact argument | `inspect_report(report_id)`: direct evidence inspection; no MCP or EAL assessment |
| `plain_brief` | “Test the API under load and make sure it is within the latency and error bounds below.” | Same direct inspection tool |
| `plain_explicit` | Developer asks to compare measured p95 and errors with acceptance criteria | Same direct inspection tool |
| `plain_review` | Developer asks for a performance check before merging | Same direct inspection tool |

The prose prompts include the same workload, identity, freshness and acceptance requirements. JSON is ordinary prompt text, not an API structured-output setting. Its equivalence is checked against the parsed EAL semantic representation. Both representations contain the same `SELECT_REPORT` acquisition selector: the host substitutes only the chosen report ID, leaving the target claim and criteria fixed. JSON and prose never receive an EAL assessment.

There are **four comparator contrasts for each model**: EAL minus JSON, EAL minus brief prose, EAL minus explicit prose, and EAL minus review prose. Each contrast has **40 paired cases** in the pilot. For example, a pair compares the EAL and JSON answers from the same model, transport and report bundle. With six models, that is 24 separately reported contrasts. The EAL outcome is reused across its four contrasts; these are not 160 independent cases per model.

The earlier report's “four paired blocks” meant four case pairs for one model/comparator: healthy, slow, errors and short run. It did not mean four model comparisons. Its “Insufficient blocks” label meant that the old interval gate had not been met, not that API calls or tokens were missing. Version 2 reports explicit assigned/completed pair counts and descriptive paired tables instead of that opaque label.

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

The finite acceptance criteria are: matching service/build/run/workload and response identities; valid, complete, consistent evidence; age at most 300 seconds at assessment; at least 100 requests; nearest-rank sample p95 at most 200 ms; and at most 1% errors. Every attempted request counts; non-2xx and transport failures are errors.

| Decision | Meaning |
| --- | --- |
| `supported` | Adequate evidence meets every finite criterion. |
| `unsupported` | Adequate evidence demonstrates a failed sample-size, latency or error criterion. |
| `unavailable` | Invalid, mismatched, incomplete, stale or conflicting evidence prevents that assessment. |

The final answer contains the selected `report_id`, `status`, requested `scope` (service, build, run and concurrent clients), all `failed_checks`, measured count/p95/error rate, and a short explanation. The reference grades those fields independently from raw rows and case provenance. Full correctness requires collection, correct selection and scope, the correct status and complete failed-check set, an exact count, and numeric measurements within 0.01 units; fields that cannot be computed must be null. Narrative explanation and private model reasoning are not scored.

EAL's raw support status and the experiment's decision status are retained separately. When EAL cannot support the claim because evidence is inadequate, the host explicitly maps that evidence condition to `unavailable`; an adequate measured failure maps to `unsupported`. The independent reference must agree with this mapping. Host support alone earns no model credit.

Missing, malformed, uncollected, failed and unattempted assignments score zero in the planned denominator. Component counts expose status, metric, selection, scope and failed-check errors. False support, false rejection, correct unavailability and unsupported assertions without collection are reported separately. “Complete” means the assigned conversations finished, not that every answer was correct.

For each model and comparator, the paired table reports both correct, EAL only correct, comparator only correct and both incorrect. The assigned-suite difference is:

```text
(EAL-only correct − comparator-only correct) / all assigned paired cases
```

Completed-pair counts and a separate completed-pair 2×2 table are reported alongside that denominator, so a provider outage is not mistaken for a task-decision discordance. The completed subset may be selected by model or transport failure; it supports diagnosis, not an efficacy estimate with failures discarded. These are exact descriptions of the recorded assignments. **No population confidence interval, superiority, equivalence or model-class ranking is claimed.** Forty purposively selected development cases are not a power calculation. The next inference gate is a separately frozen held-out case distribution, with simulation-checked interval coverage and power across plausible discordance, family dependence, model variability and missingness. That future protocol must declare its practical effect margin, comparison family and stopping rule before observing held-out results.

## Run in GitHub Actions

The [workflow](../../.github/workflows/api-experiment.yml) builds the custom [Docker image](Dockerfile). Python, Java, Make, the package, locked Python dependencies, parser generator, tests, HTTP service and collectors are bundled. The runner needs Docker and outbound package/OpenAI access; it does not need host Python.

1. Set repository secret **`OPENAI_API_TOKEN`**.
2. The runner defaults to GitHub-hosted **`ubuntu-24.04`**. To use a registered custom runner, set repository variable **`EAL_RUNNER_LABEL`** to its available label. A queued job awaiting a runner has not started its container or made model calls.
3. A qualifying owner-authored, same-repository PR change runs Docker checks and the development pilot. Fork PRs receive no token. A newer PR revision cancels a superseded PR run; retained artefacts show any incomplete assignments.
4. Once the workflow is on the default branch, manual dispatch offers `pilot` or `smoke`; it uses the common text transport.

The default pilot assigns **1,200 trials**: 40 cases × 6 models × 5 arms. Smoke assigns **120 trials** using healthy, errors, stale and distractor cases. Up to six model workers run concurrently, each following its seeded case/arm order. Each trial permits six model calls, 4,096 output tokens per call and a 120-second request timeout. Per-model admission allowances are $20 for pilot and $5 for smoke: $120 or $30 across all six models. These conservative local limits are not provider billing guarantees or predicted costs.

The secret enters only the paid container's runtime environment, never an image layer, build argument or command-line value. Collector and MCP child environments omit it. Missing usage, provider failure, unexpected model identity or exhausted allowance stops further calls for the affected model; remaining assignments are retained as unattempted. There is no implicit favourable retry or model substitution.

The paid step prints a start event for each request, followed by completion with response ID and token usage, or failure. A start records an attempt; returned usage establishes measured token consumption. Evidence acquisition and Docker checks occur before paid calls and consume no OpenAI tokens. Raw evidence, manifests, responses, traces, component scores and summaries are uploaded as workflow artefacts.

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
  python -m experiments.api_load_test run --mode pilot --transport text --output /results/run
```

Use a fresh output directory; the runner refuses to overwrite one. Use `--mode smoke` for a feasibility subset, `--model` with an exact table ID for one snapshot, or `--transport native` for a separately labelled native-function diagnostic. Recompute summaries without model calls with:

```bash
python -m experiments.api_load_test analyse --output experiment-results/run
```

`make experiment-check` exercises real HTTP and MCP without credentials in an installed checkout. Unit tests may use explicitly mocked paid-provider replies; those replies are never empirical model-comparison evidence.

[protocol.json](protocol.json) is the versioned, specified development protocol; [plan.json](plan.json) contains executable limits. The manifest freezes materials, case hashes, model settings, source revision, dependencies and assignments before the first paid request. There is no independent preregistration claim. Protocol, experiment-manifest and raw-report schema versions identify separate contracts; the raw report is now `eal-live-api-report/2`. EAL source syntax remains EAL/2 and its reasoning method remains `structured/1`.

## Retained version 1 feasibility result

[Run 36158948994](https://github.com/emmett08/earl/actions/runs/36158948994), from source `6fd9623a09d08da99333c3a5a74dedb47dec72eb`, completed 80/80 correct assigned trials and 160 successful OpenAI calls. Its frozen standard-token estimate was **$0.34201775**, not an invoice. The four-profile task was at ceiling, so this established live feasibility and no observed accuracy advantage; it established neither equivalence nor general superiority.

That result belongs to version 1, not the revised cases or newly added nano models. Its [retained artefact](https://github.com/emmett08/earl/actions/runs/36158948994/artifacts/10875053357) has ZIP SHA-256 `2de6bbf2ccddb335d6622ffb8428594e5267f3da3756ec5f3f5d62c16bf7537e`. New outcomes must identify their own source revision, manifest, run and attempt. Docker base/OS packages may change between builds, so image inspection is retained alongside pinned Python dependencies, ANTLR digest and model snapshots.
