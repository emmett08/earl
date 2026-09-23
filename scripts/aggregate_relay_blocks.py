#!/usr/bin/env python3
"""Export every descriptive pairwise contrast from fully covered relay blocks.

The existing block audit determines eligibility without inspecting correctness.
All immutable cohort records are retained; only a derived aggregate is written.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from analyse_relay_blocks import analyse
from analyse_relays import read_record
from eal.experiment import aggregate_experiment


def aggregate(runs: list[Path], canonical: Path) -> dict:
    blocks = analyse(runs, canonical)
    if not blocks['coverage_complete']:
        raise ValueError('All planned blocks must be attempted before full aggregation')
    directories = {directory.name: directory for directory in runs}
    trials = []
    for row in blocks['endpoint_rows']:
        directory = directories[row['cohort']]
        trial = read_record(directory / 'trials' / (row['source_trial_id'] + '.json'),
                            blocks['cohort_freezes'][row['cohort']])
        trials.append(trial)
    reference = json.loads(canonical.read_text())
    result = aggregate_experiment(trials, reference['schedule'],
                                  seed=reference['plan']['order_seed'],
                                  samples=reference['plan']['bootstrap_samples'])
    for name, expected in blocks['conditions'].items():
        actual = result['conditions'][name]
        actual_cost, expected_cost = actual['total_cost_usd'], expected['model_cost_usd']
        cost_matches = (actual_cost is expected_cost if None in (actual_cost, expected_cost)
                        else math.isclose(actual_cost, expected_cost, rel_tol=0, abs_tol=1e-10))
        if (not actual['coverage_complete']
                or actual['completed_trials'] != expected['attempted']
                or actual['correct'] != expected['correct']
                or not cost_matches):
            raise ValueError('Aggregate disagrees with audited block counts: ' + name)
    primary = next(row for row in result['paired_comparisons']
                   if row['left'] == 'l_tool_n_answer' and row['right'] == 'l_tool_n_evidence')
    # The pairwise helper sorts blocks; the primary analysis keeps canonical
    # schedule order. Bootstrap Monte Carlo draws can differ with task ordering.
    # The finite-task estimate and task-cluster count must nevertheless agree.
    primary_estimate = primary['correct_rate_difference']
    audited_estimate = blocks['primary']['planned_estimand']
    if (primary_estimate['estimate'] != audited_estimate['estimate']
            or primary_estimate['task_clusters'] != audited_estimate['task_clusters']):
        raise ValueError('Aggregate disagrees with the audited primary contrast')
    return {'schema': 'EAL/complete-relay-aggregate/1',
            'canonical_freeze_digest': reference['freeze_digest'],
            'cohort_freezes': blocks['cohort_freezes'],
            'selected_blocks': blocks['selected_blocks'],
            'selected_endpoints': blocks['selected_endpoints'],
            'unselected_attempted_endpoints': blocks['unselected_attempted_endpoints'],
            'primary_comparison': 'l_tool_n_evidence minus l_tool_n_answer',
            'primary_analysis': audited_estimate,
            'comparison_policy': 'One declared primary comparison; all other pairwise contrasts are exploratory. '
                'Intervals are descriptive task-cluster bootstrap summaries with six exposed tasks, '
                'not calibrated population confidence intervals. Failed attempted outcomes remain included.',
            'all_consistency_checks_passed': True, 'aggregate': result}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, action='append', required=True)
    parser.add_argument('--canonical-freeze', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = aggregate(args.run, args.canonical_freeze)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'endpoints': result['selected_endpoints'],
                      'conditions': len(result['aggregate']['conditions']),
                      'paired_comparisons': len(result['aggregate']['paired_comparisons']),
                      'consistency_checks_passed': result['all_consistency_checks_passed']}))
