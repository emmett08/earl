# Measuring text-model delegation

The paired harness runs the same configured text-generation model on each selected task twice: once using the supplied source and observations alone, and once through the bounded MCP host. It records actual responses, attempts, repairs, token usage, operation calls, latency and the configured cost model. It does not require native model tool calls.

The [23 September 2026 live experiments](live-model-results.md) record actual nano and mini development comparisons and the frozen mini held-out run, including unsuccessful protocol attempts.

The automated tests use an explicitly identified scripted regression provider to check host and harness wiring through an actual MCP subprocess. Those tests are not evidence that a language model reasons correctly or costs less. Live provider comparisons must be reported separately with their actual model identity, task selection, usage and outcomes.

First check the independent task references:

```sh
python -m eal.benchmark --check-tasks --summary
```

Configure a supported provider as described in the model host documentation. Its configuration names the provider, model, sampling settings and optional current token rates. Use an actual model/version identity rather than a class description such as “small model”. To compare the reserved split:

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
| `source_correspondence` | The assessed source has the same parsed representation as the independent reference, ignoring source bytes but retaining JSON scalar types and all proposition/dependency fields. |
| `workflow` | Where required, successful validation, collection, assessment and explanation of the final assessment are present in the actual operation trace. |

Protocol completion alone is not correctness. In draft-repair tasks the model can propose a different source, so the scorer compares its entire parsed representation with the independent corrected reference. A model cannot obtain credit merely by retaining a claim identifier while changing its statement, method, units, query, interval or premises. This conservative comparison can reject a semantically equivalent alternative argument; such a repair needs separate review and a revised acceptance specification.

The `claims` section of each score preserves expected and actual statuses. Keep these per-task results alongside aggregate figures: a single average hides the difference between numerical mistakes, ungrounded positive answers, scope failures and correctly identified missing evidence.

## Costs and reproducibility

All received model responses and failures remain in the report, including discarded formatting attempts and repair turns. Usage or price information that is unavailable remains `null`. Cost totals are reported only when every required component is known. A provider failure with unknown billed usage therefore prevents a complete cost claim.

The harness accepts an explicitly declared all-in cost per MCP call through `--per-mcp-call-usd`. Every attempted MCP operation, including failed calls, contributes. Without that value, delegated tool cost and total cost remain unknown. For a local fixture run, a value of zero describes zero marginal tool charges only if that is the chosen accounting scope; it does not measure hardware, engineering labour or infrastructure expense. When operations have different charges, retain the raw calls and calculate those charges separately rather than substituting an unjustified flat rate.

Total cost per correct task divides **all** task costs, including failures, by the number of correct tasks. Total cost per correctly resolved task uses the stricter fully supported count. Zero denominators and incomplete cost records produce `null`, not zero or an invented saving. Token-rate calculations are estimates using configured rates, not reconciled billing statements. Model response identities, sampling settings, budgets, transcripts, actual task inputs and suite content digests are retained for review.

The report's `measurement_kind` preserves the provider's declaration. `interface_only` identifies command adapters that exercise the interface without a live model. `unclassified` means the provider supplied no measurement classification. Neither supports a claim of empirical model performance. Selecting a named live model is necessary but not sufficient: inspect provider identity, actual responses and recorded failures before interpreting its results.

Use the development split to construct prompts or interfaces, then freeze those choices before running held-out tasks. Repeated runs with recorded seeds/settings are needed to investigate variation. Public task labels alone do not establish generalisation, and a single successful run does not justify a production cost estimate. Report capability and any savings only for the models, task versions, budgets and accounting scope actually evaluated.
