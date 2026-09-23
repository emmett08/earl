#!/usr/bin/env python3
"""Audit complete or interrupted relay records without provider calls.

Unexecuted conditions are not scored as model outcomes. Frozen raw files are
read only; derived audit tables go to a separate output directory.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from eal.benchmark import score_answer
from eal.experiment import _digest
from eal.relay import execution_state, handoff_packet, known_model_cost


def audit(directory: Path) -> dict:
    freeze = json.loads((directory / 'freeze.json').read_text())
    if _digest({k: v for k, v in freeze.items() if k not in {'freeze_digest', 'frozen_at'}}) != freeze['freeze_digest']:
        raise ValueError('Freeze integrity mismatch')

    def read(path):
        record = json.loads(path.read_text())
        if record['freeze_digest'] != freeze['freeze_digest'] or record['sha256'] != _digest(record['trial']):
            raise ValueError('Checkpoint integrity mismatch: ' + str(path))
        return record['trial']

    stages = {p.stem: read(p) for p in sorted((directory / 'stages').glob('*.json'))
              if not p.name.endswith('.inflight.json')}
    trials = [read(p) for p in sorted((directory / 'trials').glob('*.json'))]
    schedule = {x['trial_id']: x for x in freeze['schedule']}
    if len({t['trial_id'] for t in trials}) != len(trials):
        raise ValueError('Duplicate endpoint record')
    references = freeze['task_references']
    stage_rows, endpoint_rows = [], []
    for key, stage in stages.items():
        report = stage['report']
        expected = references[stage['task_id']]['expected']['claims']
        cost = sum(a.get('model_cost_usd') or 0 for a in report.get('attempts', []))
        if abs(cost - known_model_cost(stage)) > 1e-10:
            raise ValueError('Per-request charging mismatch: ' + key)
        stage_rows.append({'stage_key': key, 'task_id': stage['task_id'], 'model': report['provider']['model'],
                           'arm': stage.get('arm'), 'status': report['status'], 'stop_reason': report['stop_reason'],
                           'correct': score_answer(expected, report)['correct'],
                           'operational_correct': stage['score']['correct'],
                           'known_model_cost_usd': cost, 'model_cost_usd': stage['cost']['model_usd'],
                           'requests': len(report.get('attempts', [])),
                           'received_requests': sum(a.get('status') == 'received' for a in report.get('attempts', [])),
                           'tool_events': len(report.get('tool_calls', []))})
    for trial in trials:
        row = schedule[trial['trial_id']]
        if any(trial[k] != v for k, v in row.items()):
            raise ValueError('Schedule mismatch: ' + trial['trial_id'])
        state = execution_state(trial)
        chain = [stages.get(k) for k in trial['stage_keys']]
        if state == 'attempted':
            if not chain or any(s is None for s in chain):
                raise ValueError('Attempted endpoint lacks stage record')
            expected = references[trial['task_id']]['expected']['claims']
            if score_answer(expected, chain[-1]['report']) != trial['score']:
                raise ValueError('Endpoint scoring mismatch')
            if trial['report']['status'] == 'completed' and len(chain) != len(trial['condition']['stages']):
                raise ValueError('Completed endpoint has a truncated sequence')
        for i, stage in enumerate(chain):
            if stage is None:
                continue
            if stage['task_id'] != trial['task_id']:
                raise ValueError('Cross-task stage')
            packet = handoff_packet(chain[i - 1], trial['condition']['stages'][i].get('handoff', 'none')) if i else None
            if stage.get('inputs', {}).get('prior_stage') != packet:
                raise ValueError('Hand-off mismatch')
            if packet is not None:
                reference = references[trial['task_id']]
                original = stage['inputs'].get('source', stage['inputs'].get('draft_source'))
                if original != (reference['draft_source'] or reference['inputs']['source']):
                    raise ValueError('Original source anchor changed')
        endpoint_rows.append({**row, 'execution_state': state, 'status': trial['report']['status'],
                              'stop_reason': trial['report']['stop_reason'],
                              'correct': trial['score']['correct'] if state == 'attempted' else None,
                              'model_cost_usd': trial['cost']['model_usd'],
                              'stage_keys': ';'.join(trial['stage_keys'])})
    markers = []
    for p in sorted((directory / 'stages').glob('*.inflight.json')):
        key = p.name.removesuffix('.inflight.json')
        markers.append({'stage_key': key, 'completion_record_present': key in stages})
    attempted = [r for r in endpoint_rows if r['execution_state'] == 'attempted']
    completed = [r for r in attempted if r['status'] == 'completed']
    known = sum(r['known_model_cost_usd'] for r in stage_rows)
    complete_cost = all(r['model_cost_usd'] is not None for r in stage_rows) and all(m['completion_record_present'] for m in markers)
    primary_blocks = []
    indexed = {(r['condition_id'], r['task_id'], r['repetition']): r for r in attempted}
    for r in attempted:
        if r['condition_id'] != 'l_tool_n_evidence':
            continue
        other = indexed.get(('l_tool_n_answer', r['task_id'], r['repetition']))
        if other:
            if r['stage_keys'].split(';')[0] != other['stage_keys'].split(';')[0]:
                raise ValueError('Primary producer mismatch')
            primary_blocks.append({'task_id': r['task_id'], 'repetition': r['repetition'],
                                   'evidence_correct': r['correct'], 'answer_correct': other['correct'],
                                   'difference': int(r['correct']) - int(other['correct']),
                                   'extra_sequence_cost_usd': r['model_cost_usd'] - other['model_cost_usd']
                                   if r['model_cost_usd'] is not None and other['model_cost_usd'] is not None else None})
    return {'schema': 'EAL/relay-checkpoint-audit/1', 'freeze_digest': freeze['freeze_digest'],
            'scheduled_endpoints': len(schedule), 'recorded_endpoints': len(trials),
            'attempted_endpoints': len(attempted), 'finished_endpoints': len(completed),
            'correct_finished_endpoints': sum(r['correct'] for r in completed),
            'execution_states': dict(Counter(r['execution_state'] for r in endpoint_rows)),
            'unrecorded_endpoints': len(schedule) - len(trials),
            'completed_task_ids': sorted({r['task_id'] for r in completed}),
            'recorded_stages': len(stages), 'known_model_cost_usd': known,
            'total_model_cost_usd': known if complete_cost else None,
            'unpriced_stage_records': sum(r['model_cost_usd'] is None for r in stage_rows),
            'inflight_markers': markers, 'all_integrity_checks_passed': True,
            'primary_matched_blocks': primary_blocks,
            'interpretation': 'Observed cohort coverage only. Scheduling stops are excluded from outcome denominators. An incomplete set of tasks or repetitions does not estimate whole-suite performance. Markers with matching completed stage records are not additional unknown requests. Raw archives remain unchanged.',
            'stage_rows': stage_rows, 'endpoint_rows': endpoint_rows}


def export(data: dict, directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'checkpoint-audit.json').write_text(json.dumps(data, indent=2) + '\n')
    for key, filename in [('stage_rows', 'stages.csv'), ('endpoint_rows', 'endpoints.csv')]:
        rows = data[key]
        if rows:
            with (directory / filename).open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.run)
    export(result, args.output)
    print(json.dumps({k: v for k, v in result.items() if k not in {'stage_rows', 'endpoint_rows', 'inflight_markers'}}))
