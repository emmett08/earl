# EAL/3 composition verification

Package **3.1.0**, source **EAL/3**, model-transfer protocol **7.0.0**, handover protocol **2.0.0**. [Machine-readable checks](validation/eal31-composition.json) retain each rehearsal's execution hash and the reporting implementation hash. Historical [3.0.0 verification](verification-eal3.md), original failed storage check, earlier empirical rows, labels and protocol identities remain unchanged.

| Check | Observed result |
|---|---|
| Complete repository check | `make check`: 1,080 tests passed, ANTLR 4.13.2 generated sources verified, scientific validator self-test and both protocols passed, CLI/MCP API load-test example passed. |
| Composition example | Scoped review collected three independent synthetic observations, expanded decreasing evidence-list recursion and nested block arguments, compiled preferred sceptical acceptance with partial priorities, and exported its complete reviewed directive list. |
| Principal scripted rehearsal | 384 sequences, 4,224 sessions, 6,528 synthetic attempts, 4,224 annotated answers and 83 calibration checks. Raw rows unchanged and resources reconstructed. |
| Observation persistence | All 192 SQLite stores passed integrity checks; all 4,224 referenced collection/assessment records were present. |
| Component diagnostic | 56 sessions, 66 attempts, 27 calibration checks; annotation and reconstruction passed. |
| Cadence diagnostic | 36 sessions, 42 attempts, 23 calibration checks; annotation and reconstruction passed. |
| Cadence calibration | 215 checks passed. |
| Public host budgets | Dedicated CLI/MCP raw-graph tests, compiled replay budgets, worker propagation and incomplete-result handling passed. |
| Companion visualisation | 52 unit tests, six process bridge tests, ten automated browser tests and production build passed; actual recursive export passed consumer validation. |
| Distribution | Package 3.1.0 wheel and source archive built. |

The principal rehearsal captures its own exact implementation identity. A subsequent CLI/MCP adjustment forwards host budgets into the separate raw grounded-graph operation; it is covered by dedicated tests and the final complete suite. The principal experiment does not call that operation. Each diagnostic run also retains its own identity; earlier records are not relabelled as a later code snapshot.

Cloud Browser observed the existing earlier visualisation tab, then refused its reload with a URL-policy error. No workaround was attempted and no screenshot of the new build is claimed. Existing cloud captures are retained under their original contract/version labels. Automated browser checks independently exercised actual file import, reviewed priorities, extension selection/restoration, typed evidence grouping, exact undercuts, text inertness and mobile layout.

Reproduce from the repository root with fresh output paths:

```sh
make check
make build
python examples/scoped-review/run.py --export-view /tmp/scoped-review.json
python -m experiments.model_transfer.rehearse --plan experiments/model_transfer/plan.json --output /tmp/eal31-principal
python -m experiments.model_transfer.rehearse --plan experiments/model_transfer/diagnostic-plan.json --output /tmp/eal31-diagnostic
python -m experiments.model_transfer.rehearse --plan experiments/model_transfer/cadence-diagnostic-plan.json --output /tmp/eal31-cadence-diagnostic
python -m experiments.model_transfer.runner --plan experiments/model_transfer/cadence-plan.json --calibrate-only --output /tmp/eal31-cadence-calibration
```

Keep mutable experiment SQLite stores in an isolated directory. Scripted responses and provider usage/cost are synthetic; these checks establish no model-performance, allocation, cost-saving or human-authoring advantage.
