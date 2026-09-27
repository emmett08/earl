# Architecture extension EAL/2 experiment

The [paper](paper.md) reports one exploratory, fully retained coding sequence.
Engineer 1's scoped design argument is [pre-run EAL/2](architecture.eal), with
ASPIC+ `strict` and `contrary` directives. A fresh coding agent implemented
email feature A without EAL; two further fresh agents independently implemented
the same SMS feature B from the exact A snapshot, one with the EAL source in
its prompt. Both B results passed 9/9 declared checks. This case found no
measured benefit from EAL context on those checks and does not estimate later
technical debt.

## Reproduce retained checks

Install the root package and dependencies, then run from the repository root:

```bash
python3 -m pip install -e '.[dev]'
python3 -m pytest experiments/architecture_extension/test_report_collector.py
python3 experiments/architecture_extension/replay.py
python3 experiments/architecture_extension/run_eal.py
```

`replay.py` verifies the frozen inputs, source and prompt hashes, and retained
transition patches; it runs the independent behavioural and AST assessor on
all three snapshots and compares every Boolean outcome with
[observations.json](results/observations.json).
`run_eal.py` validates both EAL sources, collects the pinned report through
the trusted command binding, evaluates the two argument sources, compiles the
post-run tie goal to ASPIC+, checks the `aspic-view/1` schema and writes the
collection, assessment, formal and view JSON under `results/`. The retained
[run summary](results/eal-run.json) records the original outcome: the tie was
supported and formally accepted; the advantage route was unconstructed and
future debt remained contested at the ordinary EAL level. Re-running this
command overwrites those outputs with new collection and assessment IDs, and
therefore a new snapshot digest. Compare claim and route statuses and the
checked report/source identities when reproducing the result.

To inspect the formal graph, load [aspic-view.json](results/aspic-view.json)
in the separate [ASPIC visualisation app](https://github.com/emmett08/aspic_visualisation).
The CloudBrowser captures show the [accepted local tie](screenshots/paired-tie-1790513118711.jpg)
and the [future-debt undercut](screenshots/debt-undercut-1790513167512.jpg).
The [screenshot record](screenshots/README.md) pins the app revision, imported
view digest and image hashes. The UI renders the exported graph; it does not
perform the coding-session assessment.

The [protocol](PROTOCOL.md), [freeze manifests](materials), exact
[prompts](results/exact_prompts), three [source snapshots](results/snapshots),
[patches](results), [session final messages](results/sessions), report and
formal outputs provide the audit trail. The design argument, the observed
Boolean checks and a future-debt prediction have different evidential status.
`architecture-argument.md` records the whole–part interpretation and unresolved
review questions. The EAL source presented to the B treatment was frozen
before B; [observed-results.eal](observed-results.eal) was written for analysis
and was not in either coding prompt.
