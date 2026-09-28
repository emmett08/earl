# Running the investigation

This guide describes protocol 6.0.0 and package 2.18.0. The implementation supports
collection, resumption, independent coding, offline analysis and prospective
allocation. A completed software run is not a completed scientific investigation.
Read `execution_status`, annotation counts, accounting flags and decision status
separately. No current protocol benefit is asserted by the supplied synthetic checks.

## One workflow for the ordered stages

Open **Actions → EAL experiment → Run workflow**. For the principal pilot, leave
**operation = start**, **plan = comparison**, **workers = 0**, and every other
field blank. Configure the repository secret `OPENAI_API_KEY` before collection.
This is the recommended entry point; **EAL tests** remains available for an
individual stage or verification alone.

The wrapper runs the shared verification/build job, calibrates the selected
plan, then rehearses its collection, annotation and analysis using scripted
responses. Once these checks pass, it collects live observations with four
workers by default. Up to four successive collection jobs each allow 6,000
seconds. They pass the cumulative artefact ID automatically and stop early when
collection completes. The frozen plan's USD 2 and 21,600-second ceilings apply
across all jobs; no segment receives a new budget. Setup, free checks and uploads
add to overall workflow duration and GitHub Actions usage.

Only an ordinary collection deadline starts the next segment automatically.
Provider errors, cancellation, exhausted limits and unexpected failures retain
their data for inspection. Collection jobs reject **Re-run jobs**, which could
replay paid work from an older artefact. Recover with a new **resume** dispatch
using the latest full artefact. The wrapper cannot make an exhausted plan
complete by resetting its allowances.

After collection stops, the wrapper reconstructs a resource/completeness report
and exports the answers for independent coding. Its summary links two distinct
artefacts: the full retained run and `experiment-annotations-…`, containing only
the masked `items.json`. Give the assessor the latter. The full artefact includes
the private assignment mapping and reference material.

Independent coding is the only required external hand-off. The workflow ends
with **awaiting_annotations**, retaining its data while the assessor works; no
runner waits for the labels. Commit the completed labels JSON to the repository.
Run **EAL experiment** again with **operation = finish**, the **full export
artefact ID**, and **annotation_labels = the repository path to that file**.
The wrapper requires a code for every exported answer, imports the labels,
analyses the retained observations, and runs prospective allocation planning
for a principal/cadence pilot. An ambiguous code remains unresolved. A successful
processing job can still report incomplete measurement or no supported allocation.
Repeating `finish` on its latest full artefact archives earlier derived outputs
under `processing/` before importing the supplied labels. An earlier evaluation
plan cannot remain active when the current processing finds no supported allocation.

| Operation | Required inputs | Ordered work and stopping point |
|---|---|---|
| `start` | Pilot `plan`; `plan_path` only for `custom` | Verify → calibrate → rehearse → collect/resume automatically → analyse retained resources → export masked answers. Stops for independent labels. |
| `resume` | Latest **full** `source_artifact_id` | Verify runtime/implementation/plan identity → continue the same bounded collection → analyse/export. Saved workers and cumulative allowances remain in force. |
| `finish` | Full export `source_artifact_id`, completed `annotation_labels`; optional matching `information_config` | Verify → import every answer code → analyse → plan a supported allocation when applicable. No model calls. |
| `evaluate` | Full finish/planning `source_artifact_id` containing `evaluation-plan.json` | Verify → calibrate/rehearse the allocated plan → collect a **fresh**, separately bounded evaluation → analyse/export. Finish its labels with `finish`. Pilot rows are not copied into evaluation outcomes. |
| `rehearse` | Pilot `plan`; `plan_path` for `custom` | Verify → calibrate → full scripted collection, annotation roundtrip and analysis. No live model evidence or API charges. |

`workers=0` uses the selected plan. A new pilot can select 1–8; resume preserves
its saved count, and evaluation rejects any change to its allocated count.
`information_config` is used only by `finish`. Diagnostics finish after their
mechanism analysis; they do not feed the principal allocation planner. An
evaluation also finishes after analysis. Starting another paid evaluation always
requires the explicit `evaluate` operation and a supported saved plan.

The wrapper records orchestration schema `EAL/experiment-pipeline/1`. Package
2.18.0, protocol 6.0.0, measured implementation, scoring and execution contracts
remain unchanged. Workflow scripts live outside the measured implementation
digest, so otherwise compatible retained protocol-6 runs can use the wrapper.
Changes to measured code, runtime dependencies or the plan still prevent resume.

The wrapper is a manually dispatched caller of [reusable GitHub workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows).
Every job uses the dispatch commit, and only collection jobs receive the model
API secret. Calibration and scripted records have their own retained artefact.
The stage summary supplies the artefact IDs needed at the two explicit hand-offs
(labels and a fresh evaluation); collection passes its own IDs between jobs.

## Choose a question, then a plan

| Actions plan input | Local plan | Question and intended use |
|---|---|---|
| `comparison` | `plan.json` | Does the complete EAL workflow preserve correctness and reduce cumulative tokens at ten recipients? Start with this pilot for the principal question: 384 sequences, 4,224 sessions. |
| `diagnostics` | `diagnostic-plan.json` | Which projection, notes, format, reuse or computed-conclusion component changes a recipient outcome? Ten donors and 46 recipients; a separate mechanism investigation. |
| `cadence` | `cadence-plan.json` | How does the whole workflow behave across stable, periodic and frequent evidence changes? Separate 18-case synthetic population, 1,152 sequences and 12,672 sessions. |
| `cadence-diagnostics` | `cadence-diagnostic-plan.json` | Test reasoning and actual reuse within those change regimes. Six donors and 30 recipients. |
| `custom` | Explicit `plan_path` | A validated independent-task pilot or the evaluation plan exported by information planning. An evaluation requires a fresh run. |

Paths in this table are relative to `experiments/model_transfer/`. Diagnostics
may help investigate a mechanism before or after the principal pilot; they are
not a prerequisite and never contribute independent units to the principal mean.
Run cadence experiments only for that separate question. None of these four
bundled plans is an independently allocated confirmatory evaluation.

## Order and purpose

| Order | Stage | Input | Output and gate |
|---|---|---|---|
| 1 | Validate and calibrate | Chosen plan, task sources, pinned runtime | `make check` and `calibration.json`; invalid task/source measurements stop before model calls. |
| 2 | Rehearse | Same plan, scripted transport | Retained rows, annotation roundtrip and `rehearsal.json`; no paid requests and no model evidence. |
| 3 | Collect pilot | Frozen plan and `OPENAI_API_KEY` | All planned rows, request journal, per-session checkpoints, `report.json`, `progress.json` and execution contract. |
| 3a | Resume if needed | Latest artefact, same revision/runtime/paths | Same run identity and cumulative limits; later sessions only. Keep the latest descendant artefact. |
| 4 | Export annotation | Final retained pilot, including failures | Masked `annotation-bundle/items.json` for an independent assessor; keep `mapping.json` private from the assessor. |
| 5 | Import annotation | Original run and bundle, completed assessor labels | New `annotated-rows.json`. Raw rows stay unchanged. Ambiguous or missing decisions stay unresolved. |
| 6 | Analyse pilot | Retained run and annotated rows | Resource, correctness and incompleteness reports. A pilot estimates nuisance quantities; it cannot establish the evaluation claim. |
| 7 | Plan information | Completely measured, annotated live pilot and matching information configuration | `information-report.json`; `evaluation-plan.json` exists only when a supported allocation passes prospective gates. |
| 8 | Collect fresh evaluation | Exported evaluation plan, new output directory | Independent execution, with frozen worker count and pilot identity recorded. Repeat steps 4–6 on its results. |
| Optional | Measure adoption expenditure | Real activity records in both arms | Versioned cost ledger and analysis with `--cost-ledger`; needed for claims about total adoption cost. |

If planning reports `no_supported_allocation`, inspect its blockers and failed
scenarios. Do not rerun paid collection or raise its budget automatically. Missing
annotations are resolved by coding, not extra API requests. Incomplete receipts
cannot be converted into exact costs. A larger or different investigation needs
a prospectively revised plan and separate run.

## GitHub Actions inputs

Open **Actions → EAL tests → Run workflow** and select the branch/revision with
this implementation. All runs are manual. Tests and scientific validation run
before the optional experiment job.

| Input | Value and purpose |
|---|---|
| `model_transfer` | `false` runs verification only. Set `true` for any experiment stage, including free offline stages. |
| `experiment_action` | `collect`, `calibrate`, `rehearse`, `export-annotations`, `import-annotations`, `analyse` or `plan`. Only `collect` contacts the model API. |
| `model_transfer_plan` | Choose from the question table. Ignored for resume and offline stages, which use the saved plan. |
| `plan_path` | For `custom`, a checked-in JSON path; when starting a new run from an artefact, a path within that artefact such as `evaluation-plan.json`. |
| `source_artifact_id` | Numeric artefact ID from this repository. Required for resume and offline stages. For new custom collection it supplies the prospective plan. |
| `resume_run` | `true` only with `collect` and the latest retained run artefact. No new plan, worker count, budget or time limit is substituted. |
| `segment_seconds` | `6000` by default; valid range 1–6000. The experiment job has a 120-minute outer ceiling. |
| `workers` | `0` uses the plan (bundled plans use four). Values 1–8 can change a new pilot; resume uses its saved value. An evaluation rejects a different value. |
| `annotation_labels` | Checked-in completed assessor JSON file for `import-annotations`, relative to repository root. It must correspond to the retained bundle. |
| `information_config` | Optional checked-in JSON path for `plan`. Defaults to the six-case configuration, or the supplied 18-case configuration for that population; other populations need a matching file. |

For a first principal pilot use `model_transfer=true`, plan `comparison`, action
`collect`, `resume_run=false`, `workers=0`, `segment_seconds=6000`, with the other
fields empty. Configure the repository secret `OPENAI_API_KEY` beforehand.

Each stage uploads `model-transfer-RUN_ID-RUN_ATTEMPT`, including partial data.
The GitHub artefact link ends in its numeric ID; it is **not** the workflow run ID.
You can also list IDs with:

```bash
gh api repos/emmett08/earl/actions/runs/RUN_ID/artifacts --jq '.artifacts[] | {id,name,expired}'
```

For a partial run, dispatch `collect` with `resume_run=true` and that artefact ID.
Use the same code revision; select its retained branch/tag in the dispatch menu.
Download/save significant artefacts before their 90-day expiry. The latest
artefact includes the cumulative rows and journal, not merely that segment.

For annotation, dispatch `export-annotations` on the latest collection artefact.
Give only the exported `items.json` to the assessor. Add their completed file to
the repository, then dispatch `import-annotations` on the **export-stage** artefact
with `annotation_labels` set to its repository path. Dispatch `analyse` and `plan`
on the **import-stage** artefact so they automatically use annotated rows.
Documentation/label commits are acceptable for offline stages; collection resume
requires the original implementation and plan. Finish collection before exporting
annotations: collecting more rows invalidates the bundle's immutable row digest.
If collection is resumed after coding, existing annotation bundles, derived rows
and analysis/allocation files are moved into the previous segment archive. Export
and code a new bundle when collection finishes; the workflow never silently uses
those stale derived rows.

For evaluation, dispatch `collect`, plan `custom`, `resume_run=false`, the
**planning-stage** artefact ID and `plan_path=evaluation-plan.json`. Keep
`workers=0`. The workflow reads the saved plan into a new run directory and
records its source artefact; pilot rows are not copied into evaluation outcomes.

## Local commands

Use Python 3.12.14 and the runtime constraints for reproducible segments. The
package itself also supports Python 3.11 or later. Run from the repository root:

The experiment runner uses POSIX file locks. Use Linux or WSL2 for these commands;
the GitHub workflow uses Ubuntu 24.04. Invoke the modules as shown below so their
isolated reasoning workers can start from a real Python module.

```bash
python -m pip install -c experiments/model_transfer/requirements.lock -e '.[dev]'
make check
python -m experiments.model_transfer.runner --plan experiments/model_transfer/plan.json --calibrate-only --output /tmp/eal-calibration
python -m experiments.model_transfer.rehearse --plan experiments/model_transfer/diagnostic-plan.json --output /tmp/eal-rehearsal
python -m experiments.model_transfer.runner --plan experiments/model_transfer/plan.json --output experiments/model_transfer/runs/pilot-001 --segment-seconds 6000
```

Use the selected plan for its own calibration/rehearsal. The short diagnostic
rehearsal above exercises the annotation and format interventions; a rehearsal
of the full principal plan exercises all 4,224 planned sessions without API cost.
All fresh output directories must be absent. To resume the retained run:

```bash
python -m experiments.model_transfer.runner --resume --output experiments/model_transfer/runs/pilot-001 --segment-seconds 6000
```

The same absolute directory, interpreter executable, Python/dependency versions,
implementation digest and plan must be available. These checks protect stored
collector bindings and inference provenance. To resume an Actions artefact,
prefer the workflow, which restores its original path. For offline analysis,
downloaded artefacts can be located elsewhere and need no API key.

```bash
python -m experiments.model_transfer.annotations export experiments/model_transfer/runs/pilot-001 --all --output /tmp/eal-annotation
```

The assessor fills the `annotator` field and each item's `decision`, `quote` and
`note`, saving `/tmp/eal-labels.json`. Use the supplied rubric; code the communicated
whole-answer decision, without consulting reference outcomes. JSON explanations
and conflicting conclusions need the same independent treatment as prose.

```bash
python -m experiments.model_transfer.annotations import experiments/model_transfer/runs/pilot-001 /tmp/eal-annotation /tmp/eal-labels.json --output /tmp/annotated-rows.json
python -m experiments.model_transfer.analyse experiments/model_transfer/runs/pilot-001 --rows /tmp/annotated-rows.json --output /tmp/pilot-analysis.json
python -m experiments.model_transfer.plan_information experiments/model_transfer/runs/pilot-001 --rows /tmp/annotated-rows.json --output /tmp/information-report.json --evaluation-plan /tmp/evaluation-plan.json
python -m experiments.model_transfer.runner --plan /tmp/evaluation-plan.json --output experiments/model_transfer/runs/evaluation-001 --segment-seconds 6000
```

Run the last command only if planning actually creates that file. For cadence,
pass `--config experiments/model_transfer/cadence-information-design.json` to
planning. Independently authored manifests use the [manifest workflow](README.md#independently-supplied-tasks)
and a configuration whose candidates retain the entire new population. The
[cost-ledger commands](README.md#authoring-maintenance-and-host-costs) are a
separate optional measurement path; the activity values must come from observations.

## Performance, interruption and retained data

Four workers overlap provider waiting across independent pairs. They do not
reduce planned calls, response limits or the correctness standard. Use fewer
workers in a **new** pilot if provider rate limits make four unsuitable. The
runner has no hidden retries: HTTP access/quota errors stop further starts and
retain the attempts. Already in-flight bounded calls finish before finalisation.

`progress.json` records retained and planned sessions, observed throughput,
estimated remaining duration, known cost and charged/reserved cost. Estimates
exclude annotation/analysis and do not promise future provider latency. The
USD 2 ceiling covers all segments, including reservations for unknown charges;
the 21,600-second plan allowance is also cumulative. These are maximum spending
and elapsed allowances, not a price or completion guarantee. Once exhausted,
analyse the partial data; resumption does not reset them.

SIGINT/SIGTERM stops new requests. A hard kill may interrupt a request or a final
write: the durable journal retains its start and reservation, the torn tail is
preserved separately, and recovery records incomplete timing/side effects. It
never replays that request or silently replaces the failed session. Subsequent
planned sessions may continue, but incompleteness can prevent allocation or a
scientific claim. `segments/` preserves previous reports and `segments.json`
records each time lease. A directory lock rejects simultaneous local writers.

Artefacts predating `EAL/execution-contract/1` can still be analysed offline.
They cannot be resumed under this protocol: their saved implementation identity
and interruption behaviour do not establish the new execution contract. Keep
their observations and study identity separate; do not invent a contract file.

To analyse a downloaded partial run at any location:

```bash
python -m experiments.model_transfer.analyse /path/to/extracted-run --output /tmp/partial-analysis.json
```

To reproduce the free throughput benchmark:

```bash
python -m experiments.model_transfer.benchmark --output /tmp/harness-benchmark.json
```

This compares one and four workers with fixed synthetic latency and identical
outcomes/call counts. Its speedup is software evidence, not a measured live-model
speedup. See [verification.md](verification.md) for actual results and limits.
