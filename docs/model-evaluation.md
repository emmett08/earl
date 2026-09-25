# Measuring text-model delegation

The paired harness runs the same configured text-generation model on each selected task twice: once using the supplied source and observations alone, and once through the bounded MCP host. It records actual responses, attempts, repairs, token usage, operation calls, latency and the configured cost model. It does not require native model tool calls.

The [23 September 2026 EAL/2 regression report](eal2-model-results.md) measures selected model/host systems using package 2.1.0 on previously exposed tasks. Human comprehension, generalisation to unseen tasks and the effect of EAL notation remain unmeasured. The [historical live experiments](live-model-results.md) and [EAL/0.3 repeated experiments](eal03-model-results.md) preserve their original inputs, version labels and outcomes; those earlier trials do not measure EAL/2.

The automated tests use an explicitly identified scripted regression provider to check host and harness wiring through an actual MCP subprocess. Those tests are not evidence that a language model reasons correctly or costs less. Live provider comparisons must be reported separately with their actual model identity, task selection, usage and outcomes.

First check the independent task references:

```sh
python -m eal.benchmark --check-tasks --summary
```

Configure a supported provider as described in the model host documentation. Its configuration names the provider, model, sampling settings and optional current token rates. Use an actual model/version identity rather than a class description such as “small model”. To exercise the stored split selector (these public cases are development knowledge for EAL/2):

```sh
python -m eal.benchmark \
  --provider provider.toml \
  --split held_out \
  --max-iterations 16 \
  --max-total-tokens 64000 \
  --max-elapsed-seconds 120 \
  --output .eal/model-comparison.json
```

`--task` can select named tasks within the chosen split. The Python `evaluate_models` API also accepts an `AgentBudget`, including repair, operation, output and elapsed-time limits. Both arms receive the same task, observations, context, time, requested claim identifiers and static executable-language reference from `describe_language()`. The host arm additionally receives live operation/schema discovery and diagnostic feedback; the unaided arm receives only output-schema repair feedback, never the answer key. Arm order alternates across tasks. Neither arm receives `expected` statuses or the independent `oracle` explanation.

## What the score means

| Recorded measure | Meaning |
|---|---|
| `correct` | Every requested status matches the independent answer, no unexpected claim is supplied, and the run completes. Delegated results must also preserve the full reference source meaning. |
| `correctly_resolved` | A correct task whose requested claims are all supported. This intentionally stricter count excludes correct insufficiency/conflict answers. |
| `justified_unresolved` | A correct task containing an expected unsupported, contested or out-of-scope conclusion. These are useful answers, counted separately from fully supported tasks. |
| `unjustified` | A model supplies support where the known answer does not, supports an unexpected claim, or obtains support after changing the reference argument. |
| `unresolved` | A needed result is missing, a run is incomplete, or a model declines/denies support that the reference can supply. This can overlap with other errors on a multi-claim task. |
| `source_correspondence` | The assessed declaration/reference graph, after argument pattern expansion, is alpha-equivalent to the independent reference. Consistent internal identifier renaming is allowed; tool registry names and requested claim IDs remain fixed. JSON scalar types and all proposition/dependency fields are preserved. |
| `evidence_trace` | The final assessment references a collection actually produced earlier in this run from the validated final source and fixed context. Every task-supplied observation is present with the same value, original time and collector outcome as the independent reference. |
| `workflow` | Where required, successful validation, collection, assessment and explanation of the final assessment are present in the actual operation trace. |

Protocol completion alone is not correctness. In draft-repair tasks the model can propose a different source, so scorer profile `expanded-alpha-equivalence+evidence-trace/2` compares its expanded declaration/reference graph with the independent corrected reference. Pattern applications are compared through their ordinary arguments; expansion origins and source locations do not affect the comparison. It permits consistently renaming an internal assumption, premise or argument. It preserves every reference and literal in the expanded graph, including statements, rationale, method selectors, units, query atoms, scopes, intervals, predicates and JSON scalar types. Operator registry tool names and the requested claim identifiers are external anchors. Graph matching has a 100,000-step search limit; exceeding it yields `comparison_limit`, not inferred equivalence.

A model cannot obtain credit merely by retaining a claim identifier while weakening its dependencies or changing its question. Alpha-equivalence does not attempt arbitrary logical equivalence, algebraic simplification, prose paraphrase or reordering of conjunctive reference lists. Such an alternative representation needs its own acceptance specification. The current paired-report schema is `EAL/model-benchmark/3`; the repeated-experiment report schema is `EAL/experiment-report/1`. Both identify the scorer separately as `expanded-alpha-equivalence+evidence-trace/2`. Earlier paired-report `/1` results retain their exact-identifier scores; phase-one `/2` results retain their alpha-equivalence scores. Historical results keep their recorded scorer versions and are not silently rescored.

Every delegated task also requires an independently checked validation–collection–assessment trace. The final reasoning request must use the exact final source, fixed context/time and a collection identifier returned earlier in that run. Every observation supplied by the task must occur in that collection, using the identifier mapping established by alpha-equivalence. Values, tool identity, original observation time and success/error outcomes must match the independent fixture collection. This prevents credit for guessing an expected `unsupported` result by reasoning over no observations. Intentionally omitted evidence and expected out-of-scope import errors remain legitimate; the scorer compares their actual reference outcomes rather than requiring all records to be successful. Explicit explanation retrieval remains an additional requirement for workflow tasks.

The `claims` section of each score preserves expected and actual statuses. Keep these per-task results alongside aggregate figures: a single average hides the difference between numerical mistakes, ungrounded positive answers, scope failures and correctly identified missing evidence.

## Costs and reproducibility

All received model responses and failures remain in the report, including discarded formatting attempts and repair turns. Usage or price information that is unavailable remains `null`. Cost totals are reported only when every required component is known. A provider failure with unknown billed usage therefore prevents a complete cost claim.

The harness accepts an explicitly declared all-in cost per MCP call through `--per-mcp-call-usd`. Every attempted MCP operation, including failed calls, contributes. Without that value, delegated tool cost and total cost remain unknown. For a local fixture run, a value of zero describes zero marginal tool charges only if that is the chosen accounting scope; it does not measure hardware, engineering labour or infrastructure expense. When operations have different charges, retain the raw calls and calculate those charges separately rather than substituting an unjustified flat rate.

Total cost per correct task divides **all** task costs, including failures, by the number of correct tasks. Total cost per correctly resolved task uses the stricter fully supported count. Zero denominators and incomplete cost records produce `null`, not zero or an invented saving. Token-rate calculations are estimates using configured rates, not reconciled billing statements. Model response identities, sampling settings, budgets, transcripts, actual task inputs and suite content digests are retained for review.

The report's `measurement_kind` preserves the provider's declaration. `interface_only` identifies command adapters that exercise the interface without a live model. `unclassified` means the provider supplied no measurement classification. Neither supports a claim of empirical model performance. Selecting a named live model is necessary but not sufficient: inspect provider identity, actual responses and recorded failures before interpreting its results.

Use the development split to construct prompts or interfaces, then freeze those choices before running held-out tasks. Repeated runs with recorded seeds/settings are needed to investigate variation. Public task labels alone do not establish generalisation, and a single successful run does not justify a production cost estimate. Report capability and any savings only for the models, task versions, budgets and accounting scope actually evaluated.

## Repeated model and host comparisons

`eal.experiment` runs an explicit matrix of model and host conditions. The original EAL/0.3 matrix and development-ablation plans are preserved in the [historical plan archive](history/eal03/README.md). Their bytes retain the old host names and relative paths as experimental records. Running an updated source suite produces a new experiment with new digests. Current runnable plans are [eal2-regression-matrix.json](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/experiments/eal2-regression-matrix.json) and [eal2-development-ablation.json](https://github.com/emmett08/earl/blob/a9cdabee643118ff3ae28b3ec5c346427cca8cad/benchmarks/experiments/eal2-development-ablation.json), including the explicit stateless host condition. Their previously exposed tasks are development/regression cases. The [23 September 2026 report](eal2-model-results.md) records live runs using EAL/2 package 2.1.0; these measurements are separate from fresh held-out evaluation. Each run's freeze preserves the original plan, including its notes. Freeze the chosen plan before making another model call.

The historical matrix used six then-new engineering-v2 instances, two repetitions per instance, seven conditions and 84 total calls to the host/baseline runners. Each runner may itself make several model requests. The v1 and v2 instances and their earlier held-out results now count as EAL/2 development knowledge. A separate development plan compares stateless full-source requests with the stateful host on two v1 tasks; its results must not be reported as held-out measurements.

For an explicitly chosen plan, inspect its definition without issuing model-generation requests:

```sh
python -m eal.experiment \
  --plan benchmarks/experiments/eal2-regression-matrix.json \
  --output .eal/eal2-definition \
  --freeze-only
```

Run into a new directory:

```sh
python -m eal.experiment \
  --plan benchmarks/experiments/eal2-regression-matrix.json \
  --output .eal/eal2-regression-run
```

An existing output directory is never overwritten. `freeze.json` records the exact plan, schedule, provider identities, dependency versions, installed EAL Python file hashes, expected answers and every selected task's source, observations, method-registry fingerprint and language reference. Each completed run is saved separately under `trials/` before its result is appended to `trials.jsonl`. `report.json` contains artifact hashes, coverage, aggregate measurements and paired comparisons. Raw responses, failed attempts and tool traces remain in the referenced trial artifacts. The final report flags changes to task references or EAL implementation files during execution.

The shipped custom method is inside the hashed EAL package. A separately installed method factory needs its own retained source/package revision; the current runner does not hash every external dependency's implementation. Keep provider configuration files unchanged during a run: the recorded identity covers model, sampling, prices and advertised capabilities, but it is not a complete snapshot of every adapter setting such as an HTTP timeout. These limits do not change the recorded requests, responses or outcomes, but they narrow what can be reconstructed from the freeze alone.

The plan declares `conditions`, `repetitions`, `order_seed`, optional per-repetition `sampling_seeds`, `concurrency`, budgets and cost assumptions. A condition names its provider configuration, model-class label, `unaided` or `delegated` arm, `stateful` or `stateless` host, and `text` or `native` interaction. A baseline can be shared across host conditions for the same model, avoiding duplicate baseline charges. Each trial constructs a fresh provider object and isolated runtime store. Concurrency is bounded at four, and requested launch order is recorded separately from completion order.

The schedule permutes task/repetition blocks with a recorded seed, rotates condition positions and reverses alternate complete sweeps. Comparisons pair conditions on the same task and repetition. This controls requested ordering without promising equal wall-clock conditions under concurrent requests or provider caching. Provider sampling seeds are injected only when a condition explicitly declares support. The supplied plans leave that setting false; their seeds control scheduling, not the provider's random generation. Each artifact records the scheduled seed and the actually applied provider seed separately. Neither a fixed seed nor temperature zero guarantees exact replay by an external provider.

## Uncertainty and coverage

Condition summaries show all repeated outcomes by task, supported versus correctly unresolved answers, claim-status breakdowns, provider-returned model identities, actual host conditions, missing measurements and scheduled/completed coverage. Failed or incomplete runs count in cost and accuracy denominators. A completed trial artifact can still contain an unsuccessful model interaction; it is not an automatic success.

Intervals use a seeded percentile bootstrap over **task clusters**, retaining repetitions of a task together. Paired differences preserve task/repetition matching and report `right_minus_left` for accuracy, cost and latency. Repeating six tasks twice therefore does not turn the experiment into twelve independent engineering problems. With fewer than two task clusters, intervals are omitted. Missing costs remain unknown; no cost interval is manufactured from partial billing data.

These intervals describe observed variation within a small, selected suite. A zero-variance interval does not rule out unseen failures, and tasks were not sampled randomly from all engineering work. Two repetitions can expose run-to-run instability but provide little precision. Distinguish failure to complete a protocol, unjustified support, a correct unsupported/contested conclusion, and successful support for a negative computational finding. The results cannot establish reliability for all models, all model classes or unrestricted engineering reasoning.

## Heterogeneous model sequences

The [model-sequence runner](model-relay-experiments.md) adds shared-prefix experiments with answer, evidence and transcript transfer. It scores all final endpoints with the same claim-status criterion and retains the stricter tool execution score separately. Existing frozen single-stage measurements retain their original scoring and version labels.
