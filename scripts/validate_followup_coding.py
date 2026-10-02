"""Validate masked coding records and grade frozen calibration examples.

This script checks evidence identity and label agreement; it does not generate
semantic judgements or establish human-validated assessor accuracy.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from experiments.model_transfer.annotations import LABELS, CONSISTENCY_LABELS


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(public: dict, coded: dict) -> dict:
    originals = {item['id']: item for item in public['items']}
    records = {item['id']: item for item in coded['items']}
    if len(originals) != len(public['items']) or len(records) != len(coded['items']):
        raise ValueError('Duplicate masked item identifier')
    if set(originals) != set(records):
        raise ValueError('Coding must cover every masked item exactly once')
    for identifier, item in records.items():
        original = originals[identifier]
        if item.get('text') != original['text']:
            raise ValueError('Masked answer text changed: ' + identifier)
        if item.get('decision') not in LABELS:
            raise ValueError('Invalid decision: ' + identifier)
        required = [('quote', 'note')]
        if 'explanation_consistency' in original:
            if item.get('explanation_consistency') not in CONSISTENCY_LABELS:
                raise ValueError('Invalid explanation consistency: ' + identifier)
            required.append(('consistency_quote', 'consistency_note'))
        for quote, note in required:
            if not isinstance(item.get(quote), str) or not item[quote].strip() or item[quote] not in original['text']:
                raise ValueError('Supporting quotation does not match answer: ' + identifier)
            if not isinstance(item.get(note), str) or not item[note].strip():
                raise ValueError('Missing semantic coding note: ' + identifier)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('public', type=Path)
    parser.add_argument('reviews', nargs='+', type=Path)
    parser.add_argument('--key', type=Path)
    parser.add_argument('--key-review', type=Path,
                        help='Frozen independent validity review required for calibration qualification')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    public = read(args.public)
    decoded = [validate(public, read(path)) for path in args.reviews]
    key = read(args.key) if args.key else None
    key_review = read(args.key_review) if args.key_review else None
    if key:
        if not key_review or not key_review.get('qualification_gate_valid') or key_review.get('unresolved_label_count') != 0:
            raise ValueError('Calibration qualification requires a valid independently reviewed key with no unresolved labels')
        sources = key_review.get('source_sha256', {})
        if sources.get(args.public.name) != sha(args.public) or sources.get(args.key.name) != sha(args.key):
            raise ValueError('Independent key review does not match the administered materials')
    elif key_review:
        raise ValueError('An independent key review requires a calibration key')
    expected = ({item['id']: item for item in key['items']} if key else {})
    if key and set(expected) != set(decoded[0]):
        raise ValueError('Calibration key identity differs from the public examples')
    reports = []
    fields = ['decision', 'explanation_consistency']
    for path, records in zip(args.reviews, decoded):
        errors = [{ 'id': identifier, 'field': field,
                    'expected': expected[identifier][field], 'observed': record[field]}
                  for identifier, record in records.items() for field in fields
                  if key and record[field] != expected[identifier][field]]
        reports.append({'path': str(path), 'sha256': sha(path),
            'items': len(records), 'quotes_and_notes_valid': True,
            'decision_counts': dict(Counter(item['decision'] for item in records.values())),
            'consistency_counts': dict(Counter(item.get('explanation_consistency') for item in records.values())),
            'calibration_errors': errors,
            'calibration_status': ('passed' if not errors else 'failed') if key else 'not_applicable',
            'correct_decision_codes': sum(record['decision'] == expected[identifier]['decision']
                                           for identifier, record in records.items()) if key else None,
            'correct_consistency_codes': sum(record['explanation_consistency'] == expected[identifier]['explanation_consistency']
                                               for identifier, record in records.items()) if key else None})
    disagreements = [{'id': identifier, 'fields': [field for field in fields
                      if len({review[identifier].get(field) for review in decoded}) > 1]}
                     for identifier in decoded[0]]
    disagreements = [record for record in disagreements if record['fields']]
    result = {'schema': 'EAL/masked-coding-validation/1',
              'source_items_sha256': sha(args.public),
              'calibration_key_sha256': sha(args.key) if args.key else None,
              'independent_key_review_sha256': sha(args.key_review) if args.key_review else None,
              'validator_sha256': sha(Path(__file__)),
              'status': 'failed' if key and any(r['calibration_errors'] for r in reports) else 'passed',
              'reviews': reports, 'disagreements': disagreements,
              'interpretation': 'Exact synthetic-example agreement or masked reviewer agreement only; '
                                'no population assessor-error rate or human validation.'}
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'status': result['status'], 'items': len(decoded[0]),
                      'reviews': len(reports), 'disagreements': len(disagreements),
                      'calibration_errors': sum(len(r['calibration_errors']) for r in reports)}))
    if result['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
