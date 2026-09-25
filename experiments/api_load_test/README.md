# One API load-test experiment

This experiment turns the [worked engineering example](../../examples/api-load-test/README.md) into real measurements. It starts a small orders API, sends concurrent HTTP requests, asks a model whether the measured run meets the criteria, and grades the answer against an independent calculation from the raw requests. It does not use the example's synthetic report.

The claim is deliberately finite: **this identified build and run, with ten concurrent clients, recorded at least 100 requests, nearest-rank sample p95 at most 200 ms and at most 1% errors, with matching identities and observations no older than 300 seconds at assessment**. Every attempted request counts; non-2xx responses and transport failures are errors. This does not establish production capacity or future reliability.

## Comparison

Every model receives all five arms and all four profiles. The fixed argument is supplied to the model; source authoring is outside this experiment.

| Arm | Prompt | Execution available to the model |
| --- | --- | --- |
| `eal_mcp` | Complete EAL/2 argument | `assess_load_test`: actual MCP validation, collection, reasoning and explanation |
| `json_prompt` | JSON semantic representation of that exact argument | `run_load_test`: direct measurement collector; no MCP or EAL evaluation |
| `plain_brief` | “Test the API under load and make sure it is within the latency and error bounds below.” | Same direct collector |
| `plain_explicit` | Developer asks to compare measured p95 and error rate with acceptance criteria | Same direct collector |
| `plain_review` | Developer asks for a performance check before merging | Same direct collector |

The plain prompts all include the same workload, identity, freshness and acceptance requirements. JSON is ordinary input text, not an API structured-output mode. JSON equivalence is tested against the parsed EAL semantic representation. A common `finish` function supplies a comparable answer format for every arm.

Only the EAL tool bridge starts `eal.server` and uses the MCP SDK over stdio. It calls `eal_validate`, `eal_collect`, `eal_reason` and `eal_explain`, checking collection, source and assessment identities. The configured command tool is implemented in `collector.py`; it executes the real HTTP workload in `api.py`. JSON and prose call that same collector directly and receive metrics and provenance without a host verdict. Repeated tool requests return the same observation; failed collections cannot be rerun within a trial.

The EAL reasoning method is **`structured/1`**: it checks the argument's declared evidence dependencies and inclusive predicates. Its rationale connects these finite measurements to this run's criteria. It does not independently prove an informal rationale or infer a population performance bound. The model must request measurements and accurately communicate the result; host support alone earns no model credit.

| Model snapshot | Tier | Model class | Provider setting |
| --- | --- | --- | --- |
| `gpt-4.1-mini-2025-04-14` | Small | Non-reasoning | Temperature 0.2 |
| `gpt-4.1-2025-04-14` | Large | Non-reasoning | Temperature 0.2 |
| `gpt-5.4-mini-2026-03-17` | Small | Reasoning | Medium reasoning effort |
| `gpt-5.4-2026-03-05` | Large | Reasoning | Medium reasoning effort |

Small/large denotes the mini/full product tier, not a disclosed parameter count. Model reasoning effort is distinct from EAL's `structured/1` reasoning method. Settings and standard token prices are frozen in [models.json](models.json), with official model-page sources checked on 25 September 2026. The Responses adapter uses `store: false` and replays the original encrypted reasoning and function-call items for reasoning models. Private reasoning replay payloads and credentials are not written to results. See the official [function-calling guide](https://developers.openai.com/api/docs/guides/function-calling).

The four controlled profiles are healthy, deliberately slow, 10% errors and an incomplete 80-request run. Each arm gets a fresh real HTTP run, so observed timing may differ. The reference grades that trial's actual measurements, never the intended profile label. Both execution routes must pass a healthy control and reject the three negative controls before the workflow starts paid calls.

This estimates the **combined EAL/MCP system difference**, including executable assessment. It cannot isolate a notation effect. Equal measurement access does not imply equal checking authority or prompt length; tokens, calls, cost and elapsed time are retained to expose those differences.

## Run the custom Docker image in GitHub Actions

The [workflow](../../.github/workflows/api-experiment.yml) needs a runner with Docker and outbound access to package registries, GitHub actions, ANTLR and OpenAI. Python, Java, Make, the EAL package, pinned Python dependencies, parser generator, tests, HTTP service and collectors are inside the [Dockerfile](Dockerfile). No host Python installation is needed.

1. Set repository secret **`OPENAI_API_TOKEN`**.
2. The runner defaults to GitHub-hosted **`ubuntu-24.04`**, which executes the custom Docker image. No separately registered machine is required. To use an existing custom runner, set repository variable **`EAL_RUNNER_LABEL`** to its available label.
3. A qualifying change to an owner-authored, same-repository PR runs the complete Docker checks and the 80-trial smoke comparison. Fork PRs do not run the paid experiment or receive the secret. A new PR revision cancels a superseded smoke run; manual studies retain their fixed sample.
4. Once the workflow is available on the default branch, **Actions → API load-test model experiment → Run workflow** offers `smoke` or `study`.

The token is passed through the container environment only for paid calls, never through a build argument, command-line value or image layer. Collector and MCP child environments omit it. The workflow records the source revision and image inspection, then uploads the assigned trials, raw measurements, provider outcomes, tool traces, failures and Markdown/JSON summaries. It does not silently substitute a different model if a snapshot is unavailable.

The default smoke run has **80 assigned trials**: 4 models × 4 profiles × 5 arms. The study has **800 assigned trials**, using ten repeats. Each trial permits four model calls and 4096 output tokens per call. Admission allowances are $5/model for smoke and $50/model for study; these are conservative local estimates, not provider billing guarantees. Missing usage, a provider error, an unexpected model identity or exhausted allowance stops that model and retains its remaining assignments as unattempted.

## Run the same image locally

```bash
docker build -f experiments/api_load_test/Dockerfile -t eal-api-experiment .
# Full repository tests, parser verification, synthetic example and eight real HTTP controls:
docker run --rm --network none eal-api-experiment

# OPENAI_API_TOKEN must already be exported in your environment.
mkdir -p experiment-results
docker run --rm --user "$(id -u):$(id -g)" \
  --env OPENAI_API_TOKEN \
  --env EAL_SOURCE_COMMIT="$(git rev-parse HEAD)" \
  --volume "$PWD/experiment-results:/results" \
  eal-api-experiment \
  python -m experiments.api_load_test run --mode smoke --output /results/run
```

Use a fresh output directory for each invocation; the runner refuses to overwrite one. Add `--model` with an exact ID from the table to diagnose a single snapshot. Replace `smoke` with `study` for the fixed larger sample. To recompute summaries without model calls:

```bash
python -m experiments.api_load_test analyse --output experiment-results/run
```

For an installed development checkout, `make experiment-check` exercises real HTTP and MCP without credentials. Unit tests use explicitly mocked paid-provider responses to verify the integration; those tests are never presented as model-comparison evidence.

## Protocol and interpretation

[protocol.json](protocol.json) is the specified investigation protocol; [plan.json](plan.json) contains executable limits. Structural protocol validation passed with zero errors and warnings. The protocol is versioned before paid trials; no independent preregistration is claimed. Materials, dependencies, source revision, model settings and the entire assignment schedule are recorded before the first paid request.

The primary outcome requires collection, the correct supported/unsupported status, an exact request count, and p95/error measurements within 0.01 units. The short explanation is retained for inspection but is not automatically scored. Missing, malformed, uncollected and failed trials score zero in the assigned denominator. False support and unsupported assertions without collection are also reported separately. Complete means the planned model conversations finished, not that every answer was correct.

Analysis pairs arms within model × repeat × profile blocks. HTTP requests and model calls are nested observations, not independent model trials. The two primary comparisons per model are EAL minus JSON and EAL minus `plain_brief`; the other prose variants are secondary. Results remain separate by model.

For a complete study, decision bounds use Hoeffding's inequality for independent paired differences in [-1, 1], with Bonferroni correction for eight primary comparisons. A bounded advantage requires the lower bound to exceed 0.05; a disadvantage requires the upper bound below -0.05. The profile-stratified paired bootstrap is exploratory only, so a degenerate bootstrap cannot establish certainty. Smoke, incomplete invocations and insufficient samples remain descriptive. Correlated blocks or failed measurement controls invalidate inferential interpretation.

Forty blocks per model provide coarse precision: the primary bound's half-width is about 0.537. This economical study can establish only large differences; it is not powered to establish a five-percentage-point gain. The task may be easy enough that every arm succeeds. Such a result does not establish equivalence or EAL superiority. General claims require independently selected tasks and replications.

No live model outcome is embedded in this directory. Actual observations belong to the workflow artefact identified by its source SHA, run ID and attempt. Docker's base image and OS packages may change between builds; retain the image inspection when replicating. Python dependencies, the ANTLR digest and model snapshots are pinned.
