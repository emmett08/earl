# Paired composition and revision comparison

Run the local synthetic fixture without provider credentials:

```bash
python -m experiments.composition_comparison.experiment run --output fresh-comparison-directory
```

The runner imports `experiments.composition_revision.study`, assigns each fixed case
to both EAL/2 and the independently authored typed rule evaluator, and writes the
fixture, assignment manifest, every arm's result, and a summary. An evaluator
exception remains a failed assignment and counts as incorrect. No run overwrites
an existing directory. The first executed arm alternates between cases. The
comparison elapsed time surrounds the same `run_arm` boundary for both arms;
the implementation's internal evaluation time is retained separately. The
call time includes EAL parsing on each case while the typed configuration is
constructed when its module loads. This is a descriptive local measurement,
not a controlled estimate of steady-state speed. A production comparison
would choose and apply the same caching and process-lifetime assumptions.

For cases selected separately from development, supply a fixture in the same
schema. Freeze it **before** executing the comparison, then run it:

```bash
python -m experiments.composition_comparison.experiment freeze \
  --fixture independent-cases.json --output independent-freeze.json
python -m experiments.composition_comparison.experiment run \
  --fixture independent-cases.json --freeze independent-freeze.json \
  --output independent-results
```

The freeze binds the exact fixture bytes, case IDs and case hashes. The runner
rejects a changed or unfrozen external fixture, records the freeze in its
assignment manifest, retains the original fixture bytes, and passes each
fixture's time and context to both arms.
The tool cannot establish that an operator selected cases independently; that
fact belongs in the study record. The current EAL source and typed rules are
both fixed implementations of one engineering example, so fresh cases in this
schema test that example rather than broad language efficacy.

`expected` in the fixture gives the status of each named claim. `revision_of`
identifies the comparison state, and `affected` declares exactly which claim
statuses should change. The runner checks that those declarations are internally
consistent before executing an arm. It then scores complete claim decisions,
false support, actual affected conclusions, stale conclusions and unnecessary
changes. It reports separate elapsed times for completed assessments and retains
the outcome of every paired case.

All observations in the fixture are synthetic and all revisions share a common
scenario. The result tests implementations of a bounded example. It does not
estimate performance on an independently sampled task population, model
comprehension, authoring/review effort, or financial operating cost. Model tokens
and model charges are zero for this offline control; human and host costs are
unmeasured. The held-out engineering and timed authoring comparisons require
separately selected tasks and engineers, a frozen comparison plan, and recorded
human effort.
