# One argument in multiple environments

This synthetic example applies the same `bounded_sample` argument pattern to staging and production. Both instances use `sample_criterion`, the shared reasoning definition. Each instance creates its own evidence declaration, claim and argument, qualified as `staging_check.*` or `production_check.*`. Its criterion is at least three retained temperature readings with every reading at most 80 degrees Celsius.

From the repository root after installation:

```sh
python examples/multi-environment/run.py
```

The runner registers `source.eal`, acquires the pinned fixtures through the real command collector and assesses both claims. It then opens a second session using the same observation store, changes the production scenario to overheating and assesses production with its environment context omitted.

| Case | Staging | Production | Acquisition behaviour |
| --- | --- | --- | --- |
| First session, safe samples | `supported` | `supported` | One distinct acquisition per environment |
| Second session, same contexts | `supported` | `supported` | Each claim reuses its own observation; no repeated calls |
| Production overheating sample | Existing staging result remains scoped to staging | `unsupported` | Changed production context requires a new acquisition |
| Production context omitted | Staging context remains available | `out_of_scope` | Production collector rejects the missing context; no staging observation is reused |

The runtime context uses `{"$environments": {"staging": {...}, "production": {...}}`; each collector receives only its selected context. Separate evidence identities and context fingerprints preserve scope. The source pattern expresses reuse of an argument structure, while compatible observations can be reused across sessions within their original environment. This example performs no transfer of an observation from staging to production.

`fixtures.json` contains invented samples observed at the fixed demonstration time; the runner supplies an explicit historical assessment time 30 seconds later. `tools.toml` pins both fixture and collector bytes. `structured/1` checks the authored dependencies and evidence predicates; the prose connecting the criterion to the claim remains author supplied. The results concern these retained samples. They establish neither physical sensor accuracy nor a temperature bound between readings. `unsupported` in the overheating case records the failed positive criterion; a separate negative claim would be needed to represent an accepted contrary conclusion. `collected_count` counts acquisition attempts, including the collector error for an omitted environment.
