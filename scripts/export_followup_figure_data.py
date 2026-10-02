"""Export the follow-up's 120 scored recipient cells without answer text.

The input is a derived annotated snapshot, never the original rows. Each cell
retains separate canonical, communicated-verdict and conjunctive endpoints.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rows', type=Path)
    parser.add_argument('--labels', required=True, type=Path)
    parser.add_argument('--calibration', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    calibration = json.loads(args.calibration.read_text())
    if calibration['status'] != 'passed':
        raise ValueError('Participant result export requires passed actual-coder calibration')
    blocks = json.loads(args.rows.read_text())
    records = []
    identities = set()
    for block in blocks:
        for variant in block['variants']:
            condition = variant['evidence_condition']
            result = variant['result']
            score = result['score']
            annotation = result['annotation']
            family = condition['task_family'].removeprefix('followup-')
            primary = score['substantive_match']
            record = {
                'task_id': block['case'], 'family': family,
                'cause': condition['availability_cause'],
                'position': variant['recipient_session'],
                'condition': condition['evidence_condition'],
                'context': variant['level'],
                'reference_decision': score['reference']['decision'],
                'canonical_match': score['canonical_decision_match'],
                'whole_verdict_match': score['decision_match'],
                'explanation_consistency': annotation['explanation_consistency'],
                'primary_state': 'success' if primary is True else 'failure' if primary is False else 'unresolved',
            }
            identity = (record['task_id'], record['context'], record['position'])
            if identity in identities:
                raise ValueError('Duplicate matched recipient cell')
            identities.add(identity)
            records.append(record)
    if len(blocks) != 8 or len(records) != 120:
        raise ValueError('Unexpected follow-up allocation')
    records.sort(key=lambda row: (row['family'], row['cause'], row['task_id'], row['context'], row['position']))
    export = {
        'schema': 'EARL/followup-final-figure-data/1',
        'source': {'collection_run_id': '37023431850',
                   'live_experiment_id': 'adc97f7b-113d-4404-811d-16c5857e9d20',
                   'annotated_rows_sha256': digest(args.rows),
                   'final_labels_sha256': digest(args.labels),
                   'calibration_receipt_sha256': digest(args.calibration),
                   'stage': 'offline-derived-after-calibrated-masked-coding',
                   'donors_excluded': 8, 'recipient_cells': 120,
                   'independent_task_units': 8, 'repeats': 1},
        'rows': records,
    }
    with args.output.open('x') as stream:
        json.dump(export, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'recipient_cells': len(records), 'donors_excluded': 8}))


if __name__ == '__main__':
    main()
