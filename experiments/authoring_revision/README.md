# EAL/2 authoring and revision comparison

This instrument records engineers' work on matched tasks in EAL/2 and a typed Python rule implementation. It freezes task briefs, machine-readable case inputs, target claims, an independently stated oracle and an operator runner digest for each arm. It retains submitted source, optional participant results, measured authoring time, independently replayed results, reviewer time and adjudicated semantic defects. **Only operator replay contributes correctness.** A participant's own result file is never graded.

The [example plan](example-plan.json) and [oracle](example-oracle.json) are **synthetic illustrations**, drawn from the executable [coolant-loop case](../composition_revision/README.md). Task A changes flow from either pump route to both routes. Task B raises the scoped bench load and exchanger criterion from 8 to 10 kW and renames the final claim. Both start from the existing [`cooling.eal`](../composition_revision/cooling.eal) and [`baseline.py`](../composition_revision/baseline.py). The sample intentionally provides no revised implementation and contains no human outcomes. The example plan's all-zero `source_commit` is a placeholder: analysis marks `source_provenance_limited: true`. Before a real study, commit the code and study files, set `source_commit` to that retrievable `git rev-parse HEAD`, select independent tasks, check the reference with domain experts and set useful margins.

## Freeze and perform actual work

Run from the repository root:

```bash
python -m experiments.authoring_revision freeze \
  --plan experiments/authoring_revision/example-plan.json \
  --oracle experiments/authoring_revision/example-oracle.json \
  --participants experiments/authoring_revision/example-participants.json \
  --output /tmp/eal-authoring-run
```

`assignments.json` gives each pseudonymous participant two tasks in a specified order, one per arm. A complete block of four participants balances each task's arm and the first arm; a partial block remains visible. Keep the run directory outside the Git checkout, as shown above, so retained submissions do not make a real study's checkout dirty. Give each participant the assigned brief, the same case inputs and the appropriate starting artefact. Record actual active work time under one consistent timing practice, excluding breaks. Initial work can use the supplied starting source. For a revision, edit that source to implement the assigned `revision_brief`; do not substitute the unchanged starting source as a successful revision.

```bash
python -m experiments.authoring_revision submit \
  --run /tmp/eal-authoring-run --assignment ASSIGNMENT_ID --stage initial \
  --active-seconds MEASURED_SECONDS \
  --artefact path/to/cooling.eal
python -m experiments.authoring_revision submit \
  --run /tmp/eal-authoring-run --assignment ASSIGNMENT_ID --stage revision \
  --active-seconds MEASURED_SECONDS \
  --artefact path/to/revised/cooling.eal
```

Use `baseline.py` for a typed-rules assignment. Submissions copy and hash source; a directory is also accepted. Optional `--results path/to/participant-results.json` retains what the participant produced for diagnosis. Its form is `{"schema":"eal-authoring-results/1","cases":{"a_nominal":{"cooling_at_8kw":"supported", ...}}}`. Results may contain `supported`, `unsupported`, `unavailable`, `contested` or `out_of_scope`. A failed attempt can be recorded with `--failure 'reason'` and its measured time even when source or results are absent. Record an initial attempt before its revision. Missing and failed work stays in the assigned denominator.

## Independently replay submitted source

The trusted operator invokes the included [cooling runner](cooling_runner.py) once per submission, in an **isolated environment** suited to executing submitted Python. It loads the copied EAL source or typed module, reads the frozen case payloads, constructs equivalent observation envelopes and evaluates each target claim. The runner file SHA-256 must equal the digest fixed in the plan for that arm. For a nonzero `source_commit`, the runner must live in the assessed repository, imported project modules resolve from that checkout, and replay checks its exact Git HEAD and clean worktree before and after execution. The record includes its observed revision and clean state, runner digest, Python and runner versions, source and case digests, captured output, exit status and elapsed time. The all-zero illustrative plan can run without a matching commit; its replay provenance remains explicitly limited.

```bash
python -m experiments.authoring_revision replay \
  --run /tmp/eal-authoring-run --submission ASSIGNMENT_ID-initial \
  --operator independent_operator --runner-version cooling_runner/1 \
  --runner experiments/authoring_revision/cooling_runner.py
python -m experiments.authoring_revision analyse \
  --run /tmp/eal-authoring-run \
  --oracle experiments/authoring_revision/example-oracle.json \
  --output /tmp/eal-authoring-analysis.json
```

The adapter does not certify that the authored rules represent the real thermal system; the oracle and review address that separate question. Its imported dependencies are tied to the recorded repository revision and installed environment. Updating the runner changes its digest and requires a newly frozen plan. The example's unchanged starting artefacts replay correctly for initial cases. Leave revisions unattempted until engineers actually implement them; the report marks them unscored and incomplete rather than inventing success.

The analysis includes all assignments and grades only successful, intact operator replays against the frozen oracle. It counts incorrect status, false support and exact target-claim errors; any extra invented support also counts. Absent or failed replays are unscored and cannot count as correct. Active and reviewer seconds are reported only where observed; missing time never becomes zero-time work. Participant/task-family pairs remain identifiable as the crossover units. The report is descriptive and makes no superiority claim from the example.

## Optional independent semantic review

Reviewers inspect the copied source and replay trace, then submit their own finding and review time:

```json
{"schema":"eal-authoring-review/1","reviewer_id":"reviewer_01",
 "submission_id":"ASSIGNMENT_ID-revision","review_seconds":145,
 "findings":[{"id":"revoked_pump","location":"flow_sufficient",
              "description":"The argument uses a revoked pump observation."}]}
```

Record it with `python -m experiments.authoring_revision review --run /tmp/eal-authoring-run --input review.json`. More than one reviewer can identify the same defect. An adjudicator groups duplicate findings under one confirmed defect:

```json
{"schema":"eal-authoring-adjudication/1","adjudicator_id":"reviewer_02",
 "submission_id":"ASSIGNMENT_ID-revision","adjudication_seconds":60,
 "confirmed_defects":[{"id":"revoked_pump",
   "finding_refs":["reviewer_01:revoked_pump"],
   "description":"Uses a revoked observation"}],
 "rationale":"The pump observation was revoked before reassessment."}
```

Record it using the `adjudicate` command with the same `--run` and `--input` options. The author cannot review or adjudicate their own submission. Source syntax can reveal the assigned arm, so reviewer identity independence does not imply blinding. Analysis distinguishes reported findings from confirmed defects and remains available before either review step.
