# Claim-to-evidence audit for run 36275725154

This is a development-result paper about the complete Actions run, not a
confirmatory comparison. The [workflow run](https://github.com/emmett08/earl/actions/runs/36275725154)
and [retained artifact](https://github.com/emmett08/earl/actions/runs/36275725154/artifacts/10916929645)
identify the record. The analysis pins the archive SHA-256 to
`0d1286e661eabb78470a2283d160979d4aae7221f98a086189ee7495124de018`
and the tested commit to `f8c629f49b5bef6c760de2029f6bc7db0e762a6f`.

| Manuscript claim | Direct evidence | Scope and countercheck |
| --- | --- | --- |
| 1,440 of 1,440 assignments completed | `run/manifest.json`, `run/completion.json`, all `run/trials/*/trial.json`; regenerated `results/assignments.csv` | 40 case IDs × six exact snapshots × six arms, one realised conversation per cell; `analysis/analyse_run.py` verifies identities and totals. |
| Reference labels: nine supported, twelve unsupported, nineteen unavailable | Per-trial `reference.status` and the independent raw-row adjudicator `experiments/api_load_test/oracle.py` at the tested commit | These are 40 distinct, deliberately reviewed cases. Their repeated assignment does not change the case counts. |
| EAL 223/240, ordinary validator 219/240, JSON 166/240 | Per-trial `outcome.correct`, independently summed into `results/aggregate.json`, crosschecked against `run/summary.json` | Strict full-answer rubric; denominator is repeated model–case records, not a random sample of 240 cases. |
| EAL–validator differences are 6/2 discordances for GPT-4.1 nano and 3/3 for GPT-5.4 nano | Matched case IDs and `outcome.correct` from individual trials; `results/aggregate.json` pairs | The other four models have 40/40 on both arms. Equal scores on selected cases do not show population equivalence. |
| EAL's 17 errors are all unavailable → unsupported; validator's 21 include seven unavailable → supported | Trial `reference`, `answer`, `outcome`, selected scope and metric fields; checker/reference agreement in source run | Model finalisation remains fallible after deterministic checking. Zero EAL false supports does not mean zero unwarranted definitive statuses. |
| EAL's cost and time exceed the validator's for all six snapshots | Recorded call usage, frozen price schedule, per-cell `estimated_usd_known` and `median_seconds_attempted` in `run/summary.json` | Costs are token estimates, not invoices; median time is an observed runner/session statistic, not a general throughput estimate. |

Rival causes include prompt differences, native MCP versus direct-tool transport,
tool-return presentation, instruction wording, model tier and interaction length.
The EAL condition changes notation, MCP and checking together. The validator
supplies an ordinary checker, but the design does not isolate EAL syntax.
The provided answer is model-authored in every arm; checked-host finalisation
would be a new intervention. We make no population significance or superiority
claim and avoid treating HTTP requests or model calls as independent tasks.

The contextual references to program-aided and solver-assisted language-model
work are cited to their primary conference publications in `references.bib`.
The McNemar citation motivates showing paired discordances; it is not used as
a licence to test a purposively selected development suite.
