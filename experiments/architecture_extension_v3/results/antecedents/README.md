# Earlier observations retained for the v3 report

The active architecture experiment is v3. These are **historical** v1 and v2
observations, copied byte for byte from [PR head `e6e43e1`](https://github.com/emmett08/earl/commit/e6e43e163fe5501039b88d265536960b6d5e9dd6)
before removing the two earlier experiment trees from the working branch. They
are not v3 episodes or additional evidence for a v3 treatment effect. The
[manifest](manifest.json) gives each original path, retained path, byte count,
SHA-256 and Git blob ID. The [original v1 paper](https://github.com/emmett08/earl/blob/e6e43e163fe5501039b88d265536960b6d5e9dd6/experiments/architecture_extension/paper.md)
and [v2 paper](https://github.com/emmett08/earl/blob/e6e43e163fe5501039b88d265536960b6d5e9dd6/experiments/architecture_extension_v2/paper.md)
describe their full protocols. Their links to source, patches, exact prompts
and remaining packets refer to that same commit, not the pruned working tree.

## Recorded outcomes and limits

| Earlier case | Retained direct evidence | Interpretation |
| --- | --- | --- |
| V1 notification service | [Observations](v1/results/observations.json), [post-run EAL](v1/observed-results.eal), [EAL run](v1/results/eal-run.json), [ASPIC export](v1/results/aspic-view.json) | Both B outputs passed 9/9 fixed checks. The no-follow-up objection undercut the future-debt forecast. The failed-dispatch predicates were unmet because their successfully collected checks passed. No later debt outcome was measured. |
| V2 fulfilment service | [A](v2/results/assessments/a.json), [B control](v2/results/assessments/b_control.json) and [B treatment](v2/results/assessments/b_treatment.json) independent assessments | A passed 10/10 and both B sources passed 15/15. This is a primary tie on those checks. The [pre-A MCP wire](v2/results/wire/pre-a-mcp-success.json.gz) and [summary](v2/results/pre-a-mcp-success-summary.json) record a real host acquisition; the [B treatment packet](v2/results/pre-b-treatment-packet.json) and [summary](v2/results/pre-b-treatment-mcp-summary.json) retain the stale pre-A exposure. They cannot establish what an agent understood. |
| V2 structural and diagnostic review | [Condition-masked review](v2/results/review_blinded.json), [mapping](v2/results/review_mapping.json), [exploratory reproduction](v2/results/review_reproduction.json), [C1/C2 sources](v2/results/review_candidates/) | C1 was treatment and C2 control. No independent fulfilment path or confirmed dead production function was found. A known pre-effect refund-failure difference favoured C1 in a **post-run** diagnostic, outside the primary checks. |
| V2 control-flow diagnostic | [B control](v2/results/metrics/b_control.json) and [B treatment](v2/results/metrics/b_treatment.json) scores, [scope](v2/metrics/README.md) | Scores were 145 and 140. The metric describes branching under a declared Python scope; five score points are not five units of technical debt. The archived scope document's old commands require the original commit's full tree. |

The C1 and C2 production, test and architecture files are byte-identical to
the nine tracked source files of the respective original v2 B treatment and
control snapshots. They are kept once, under their masked names, with the
[mapping](v2/results/review_mapping.json). The v3 assessor can recheck their
R-B capability; the retained [refund diagnostic script](v2/results/review_reproduction.py)
can re-exercise the exploratory case. These checks do not rerun the old agents
or authenticate their private reasoning. Full v1/v2 replay requires the
historical commit above. The ten v2 files used by the v3 freeze remain at
their original paths, including the A source, assessor probe and complexity
instrument.

From the repository root, verify the archive and selected observations:

```bash
python3 - <<'PY'
import hashlib, json
from pathlib import Path
root = Path('experiments/architecture_extension_v3/results/antecedents')
manifest = json.loads((root / 'manifest.json').read_text())
for item in manifest['files']:
    data = (root / item['retained']).read_bytes()
    assert len(data) == item['bytes']
    assert hashlib.sha256(data).hexdigest() == item['sha256']
print(f"verified {len(manifest['files'])} historical files")
PY
python3 experiments/architecture_extension_v3/study/assess.py --candidate experiments/architecture_extension_v3/results/antecedents/v2/results/review_candidates/C1 --family R --stage B
python3 experiments/architecture_extension_v3/study/assess.py --candidate experiments/architecture_extension_v3/results/antecedents/v2/results/review_candidates/C2 --family R --stage B
python3 experiments/architecture_extension_v3/results/antecedents/v2/results/review_reproduction.py --output /tmp/earl-v2-refund-recheck.json
python3 experiments/architecture_extension_v2/metrics/cognitive_complexity.py experiments/architecture_extension_v3/results/antecedents/v2/results/review_candidates/C1/fulfilment
python3 experiments/architecture_extension_v2/metrics/cognitive_complexity.py experiments/architecture_extension_v3/results/antecedents/v2/results/review_candidates/C2/fulfilment
```

The assessor's source digest uses its own documented recipe and differs from
the v2 historical digest recipe. Compare the Boolean findings and metric
totals, not unlike digests. The archive sits under `v3/results`, outside the
117 pre-run inputs in `v3/study/freeze.json`.
