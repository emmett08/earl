#!/usr/bin/env python3
"""Compare fully attempted blocks while preserving interrupted cohorts separately.

Block eligibility depends only on coverage, never correctness. All raw records
remain immutable. The target estimand is withheld while any task block is missing.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import statistics

from audit_relay_checkpoints import audit
from analyse_relays import read_record, token_details
from eal.experiment import cluster_interval
from eal.relay import execution_state, known_model_cost


def select_blocks(schedule: list[dict], cohorts: dict[str, list[dict]]) -> tuple[dict, list]:
    expected = defaultdict(set)
    for row in schedule:
        expected[row['block_id']].add(row['condition_id'])
    selected, missing = {}, []
    for block, conditions in expected.items():
        eligible = []
        for name, trials in cohorts.items():
            rows = [t for t in trials if t['block_id'] == block]
            if (len(rows) == len(conditions) and {t['condition_id'] for t in rows} == conditions
                    and all(execution_state(t) == 'attempted' for t in rows)):
                eligible.append((name, rows))
        if len(eligible) > 1:
            raise ValueError('Multiple fully attempted cohorts for block: ' + block)
        if eligible:
            selected[block] = eligible[0]
        else:
            missing.append(block)
    return selected, missing


def analyse(runs: list[Path], canonical: Path) -> dict:
    reference = json.loads(canonical.read_text())
    datasets, audits, all_stages, freezes = {}, {}, {}, {}
    for directory in runs:
        name = directory.name
        if name in datasets:
            raise ValueError('Cohort names must be unique')
        frozen = json.loads((directory / 'freeze.json').read_text())
        report_path = directory / 'report.json'
        if report_path.exists() and json.loads(report_path.read_text()).get('reference_or_implementation_drift'):
            raise ValueError('Recorded reference or implementation drift: ' + name)
        for field in ('suite_digest', 'provider_configurations', 'scorer'):
            if frozen[field] != reference[field]:
                raise ValueError('Incompatible cohort ' + field)
        if frozen['runtime']['source_digest'] != reference['runtime']['source_digest']:
            raise ValueError('Implementation changed across cohorts')
        for field in ('conditions', 'budget', 'per_mcp_call_usd', 'max_handoff_bytes'):
            if frozen['plan'][field] != reference['plan'][field]:
                raise ValueError('Treatment changed across cohorts: ' + field)
        audits[name] = audit(directory)
        datasets[name] = [read_record(p, frozen['freeze_digest']) for p in sorted((directory / 'trials').glob('*.json'))]
        all_stages[name] = {p.stem: read_record(p, frozen['freeze_digest']) for p in sorted((directory / 'stages').glob('*.json'))
                            if not p.name.endswith('.inflight.json')}
        freezes[name] = frozen['freeze_digest']
    selected, missing = select_blocks(reference['schedule'], datasets)
    if not selected:
        raise ValueError('No fully attempted block is available')
    canonical_rows = {(r['block_id'], r['condition_id']): r for r in reference['schedule']}
    rows, selected_stage_keys = [], set()
    selected_record_ids = set()
    for block, (cohort, trials) in selected.items():
        for trial in trials:
            selected_record_ids.add((cohort, trial['trial_id']))
            chain = [all_stages[cohort][key] for key in trial['stage_keys']]
            selected_stage_keys.update((cohort, key) for key in trial['stage_keys'])
            correct = trial['stage_endpoint_correct']
            details = [token_details(s['report']) for s in chain]
            final = chain[-1]
            row = {**canonical_rows[block, trial['condition_id']], 'cohort': cohort,
                   'source_trial_id': trial['trial_id'], 'correct': int(trial['score']['correct']),
                   'completed_answer': int(trial['report']['status'] == 'completed'),
                   'unjustified': int(trial['score']['unjustified']),
                   'corrected_transitions': sum(not a and b for a, b in zip(correct, correct[1:])),
                   'damaged_transitions': sum(a and not b for a, b in zip(correct, correct[1:])),
                   'stage_correctness': ','.join(str(int(x)) for x in correct),
                   'stage_keys': ';'.join(trial['stage_keys']),
                   'verified_tool_endpoint': int(final.get('arm') == 'delegated' and final['score']['correct']),
                   'model_cost_usd': trial['cost']['model_usd'],
                   'latency_seconds': trial['report']['latency_seconds'],
                   'stop_reason': trial['report']['stop_reason']}
            for key in details[0]:
                row[key] = sum(d[key] for d in details) if all(d[key] is not None for d in details) else None
            rows.append(row)
    rows.sort(key=lambda r: r['schedule_index'])
    stage_rows = []
    for cohort, key in sorted(selected_stage_keys):
        stage = all_stages[cohort][key]
        report = stage['report']
        stage_rows.append({'cohort': cohort, 'stage_key': key, 'task_id': stage['task_id'],
                           'model': report['provider']['model'], 'arm': stage.get('arm'),
                           'status': report['status'], 'stop_reason': report['stop_reason'],
                           'model_cost_usd': stage['cost']['model_usd'],
                           'known_model_cost_usd': known_model_cost(stage),
                           'requests': len(report.get('attempts', [])),
                           'tool_events': len(report.get('tool_calls', [])),
                           'repairs': report.get('repairs', 0), **token_details(report),
                           'response_models': sorted({a['response_model'] for a in report.get('attempts', []) if a.get('response_model')})})
    conditions = {}
    for condition in reference['plan']['conditions']:
        subset = [r for r in rows if r['condition_id'] == condition['id']]
        total = sum(r['model_cost_usd'] for r in subset) if all(r['model_cost_usd'] is not None for r in subset) else None
        n_correct = sum(r['correct'] for r in subset)
        by_task = defaultdict(list)
        for r in subset:
            by_task[r['task_id']].append({'repetition': r['repetition'], 'correct': r['correct'], 'stop_reason': r['stop_reason']})
        conditions[condition['id']] = {'attempted': len(subset), 'finished': sum(r['completed_answer'] for r in subset),
                                      'correct': n_correct, 'unjustified': sum(r['unjustified'] for r in subset),
                                      'model_cost_usd': total, 'cost_per_correct_usd': total / n_correct if total is not None and n_correct else None,
                                      'mean_seconds': statistics.mean(r['latency_seconds'] for r in subset),
                                      'corrected_transitions': sum(r['corrected_transitions'] for r in subset),
                                      'damaged_transitions': sum(r['damaged_transitions'] for r in subset),
                                      'verified_tool_endpoints': sum(r['verified_tool_endpoint'] for r in subset),
                                      'task_outcomes': dict(by_task)}
    indexed = {(r['block_id'], r['condition_id']): r for r in rows}
    primary = []
    for block in selected:
        evidence = indexed[block, 'l_tool_n_evidence']
        answer = indexed[block, 'l_tool_n_answer']
        if (evidence['cohort'], evidence['stage_keys'].split(';')[0]) != (answer['cohort'], answer['stage_keys'].split(';')[0]):
            raise ValueError('Primary producer mismatch')
        solo, none = indexed[block, 'n_solo'], indexed[block, 'l_tool_n_none']
        if (solo['cohort'], solo['stage_keys']) != (none['cohort'], none['stage_keys'].split(';')[-1]) or solo['correct'] != none['correct']:
            raise ValueError('No-handoff invariant mismatch')
        primary.append({'task_id': evidence['task_id'], 'repetition': evidence['repetition'],
                        'answer_correct': answer['correct'], 'evidence_correct': evidence['correct'],
                        'difference': evidence['correct'] - answer['correct'],
                        'extra_cost_usd': evidence['model_cost_usd'] - answer['model_cost_usd']
                        if evidence['model_cost_usd'] is not None and answer['model_cost_usd'] is not None else None})
    task_differences = defaultdict(list)
    for row in primary:
        task_differences[row['task_id']].append(row['difference'])
    unselected_attempts = [{**t, 'cohort': name} for name, trials in datasets.items() for t in trials
                           if (name, t['trial_id']) not in selected_record_ids and execution_state(t) == 'attempted']
    known = sum(r['known_model_cost_usd'] for r in stage_rows)
    return {'schema': 'EAL/relay-block-analysis/1', 'coverage_complete': not missing,
            'expected_blocks': len({r['block_id'] for r in reference['schedule']}),
            'selected_blocks': {block: cohort for block, (cohort, _) in selected.items()}, 'missing_blocks': missing,
            'selected_endpoints': len(rows), 'selected_finished_endpoints': sum(r['completed_answer'] for r in rows),
            'selected_stages': len(stage_rows), 'selected_known_model_cost_usd': known,
            'selected_model_cost_usd': known if all(r['model_cost_usd'] is not None for r in stage_rows) else None,
            'all_cohort_known_model_cost_usd': sum(a['known_model_cost_usd'] for a in audits.values()),
            'all_cohort_model_cost_usd': sum(a['total_model_cost_usd'] for a in audits.values())
            if all(a['total_model_cost_usd'] is not None for a in audits.values()) else None,
            'cohort_freezes': freezes, 'unselected_attempted_endpoints': len(unselected_attempts),
            'unselected_attempts': [{'cohort': t['cohort'], 'trial_id': t['trial_id'], 'task_id': t['task_id'],
                                    'repetition': t['repetition'], 'condition_id': t['condition_id'],
                                    'correct': t['score']['correct'], 'stop_reason': t['report']['stop_reason']}
                                   for t in unselected_attempts],
            'primary': {'blocks': primary, 'covered_tasks': len(task_differences),
                        'observed_subset_task_weighted_difference': statistics.mean(statistics.mean(v) for v in task_differences.values()),
                        'planned_estimand': cluster_interval(primary, lambda r: r['difference'], seed=reference['plan']['order_seed'], samples=reference['plan']['bootstrap_samples'])
                        if not missing else {'estimate': None, 'reason': 'incomplete_planned_task_coverage'}},
            'conditions': conditions, 'endpoint_rows': rows, 'stage_rows': stage_rows,
            'all_integrity_checks_passed': True, 'no_handoff_invariant_passed': True,
            'interpretation': 'Complete blocks are selected by attempted coverage only; failed outcomes remain. Any incomplete planned coverage prevents estimation of the declared six-task contrast. Subset counts describe only observed blocks, with repeats clustered by task. Costs use realised cache discounts; uncached repricing is a projection, not another measurement. All incomplete cohorts and unknown charges remain separate.'}


def export(data: dict, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    (output / 'block-analysis.json').write_text(json.dumps(data, indent=2) + '\n')
    for key, filename in [('endpoint_rows', 'complete-block-endpoints.csv'), ('stage_rows', 'complete-block-stages.csv')]:
        with (output / filename).open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[key][0]))
            writer.writeheader()
            writer.writerows(data[key])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, action='append', required=True)
    parser.add_argument('--canonical-freeze', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyse(args.run, args.canonical_freeze)
    export(result, args.output)
    print(json.dumps({k: result[k] for k in ('coverage_complete', 'selected_endpoints', 'selected_finished_endpoints', 'selected_stages', 'selected_model_cost_usd', 'all_cohort_known_model_cost_usd', 'unselected_attempted_endpoints')}))
