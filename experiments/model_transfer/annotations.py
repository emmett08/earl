"""Blindly code retained task answers without changing raw experiment records.

Export gives assessors answer text and a decision-coding rubric. It excludes the
arm, model, case and reference outcome; answer wording can still reveal an arm.
Import validates the coding against its original text, then writes derived rows.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import uuid

from .cases import case_from_record
from .scoring import ReferenceScorer
from .records import SequenceRecords

SCHEMA = 'EAL/model-transfer-annotations/1'
LABELS = {'ready', 'not_ready', 'undetermined', 'no_answer', 'ambiguous'}
RUBRIC = (
    'Code the decision explicitly communicated by this answer. Do not assess its '
    'factual correctness or infer a decision from measurements. Use ready for an '
    'affirmative readiness conclusion, not_ready for a negative readiness conclusion, '
    'undetermined for an explicit inability to establish readiness, no_answer for '
    'text that provides no task decision, and ambiguous for unresolved conflicting '
    'decisions. Distinguish historical or hypothetical statements from the current '
    'conclusion. Supply an exact supporting quote from the answer and a brief note. '
    'Leave ambiguous answers unresolved; do not choose the most favourable reading.'
)


def _read(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _write_new(path: Path, value) -> None:
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def _sessions(row: dict):
    """Yield responses from either workflow sequences or cloned diagnostic blocks."""
    if 'sessions' in row:
        yield from row['sessions']
    else:
        if row.get('donor_result') is not None:
            yield row['donor_result']
        for variant in row['variants']:
            if variant.get('result') is not None:
                yield variant['result']


class AnnotationExchange:
    """Separate masked semantic coding from reference-based outcome scoring."""

    def export(self, run: Path, output: Path, *, include_all: bool = False) -> dict:
        rows_text = SequenceRecords(run).text()
        rows = json.loads(rows_text)
        items, mapping, seen = [], [], set()
        for row in rows:
            for session in _sessions(row):
                session_id = session['session_id']
                if session_id in seen:
                    raise ValueError('Duplicate session identifier')
                seen.add(session_id)
                status = (session.get('annotation') or {}).get('status')
                if not include_all and status not in ('pending', 'ambiguous'):
                    continue
                text = session.get('raw_answer')
                if not isinstance(text, str) or not text.strip():
                    continue
                identifier = uuid.uuid4().hex
                items.append({'id': identifier, 'text': text, 'decision': None,
                              'quote': '', 'note': ''})
                mapping.append({'id': identifier, 'session_id': session_id,
                                'answer_sha256': _digest(text)})
        random.SystemRandom().shuffle(items)
        public = {'schema': SCHEMA, 'rubric': RUBRIC, 'annotator': '', 'items': items}
        private = {'schema': SCHEMA, 'rows_sha256': _digest(rows_text), 'items': mapping}
        output.mkdir(parents=True, exist_ok=False)
        _write_new(output / 'items.json', public)
        _write_new(output / 'mapping.json', private)
        return {'exported': len(items), 'items': str(output / 'items.json'),
                'instruction': 'Give the assessor items.json only; retain mapping.json separately.'}

    def import_labels(self, run: Path, bundle: Path, labels: Path, output: Path) -> dict:
        if output.exists():
            raise ValueError('Use a new annotated output; original records are retained')
        rows_text = SequenceRecords(run).text()
        mapping, supplied = _read(bundle / 'mapping.json'), _read(labels)
        if mapping.get('schema') != SCHEMA or supplied.get('schema') != SCHEMA:
            raise ValueError('Unsupported annotation schema')
        if mapping.get('rows_sha256') != _digest(rows_text):
            raise ValueError('Run rows changed after annotation export')
        annotator = supplied.get('annotator')
        if not isinstance(annotator, str) or not annotator.strip():
            raise ValueError('Record an independent annotator identifier')
        rows = copy.deepcopy(json.loads(rows_text))
        session_list = [s for row in rows for s in _sessions(row)]
        sessions = {s['session_id']: s for s in session_list}
        if len(sessions) != len(session_list):
            raise ValueError('Duplicate session identifier')
        locations = {item['id']: item for item in mapping['items']}
        if len(locations) != len(mapping['items']):
            raise ValueError('Duplicate annotation mapping identifier')
        seen = set()
        for item in supplied['items']:
            identifier = item['id']
            if identifier in seen or identifier not in locations:
                raise ValueError('Unknown or duplicate annotation identifier')
            seen.add(identifier)
            location = locations[identifier]
            session = sessions[location['session_id']]
            text = session['raw_answer']
            if _digest(text) != location['answer_sha256']:
                raise ValueError('Answer changed after annotation export')
            decision, quote, note = item.get('decision'), item.get('quote'), item.get('note')
            if not isinstance(decision, str) or decision not in LABELS:
                raise ValueError('Supply a valid explicit decision code')
            if not isinstance(quote, str) or not quote.strip() or quote not in text:
                raise ValueError('Annotation needs an exact supporting quote from the answer')
            if not isinstance(note, str) or not note.strip():
                raise ValueError('Annotation needs a coding note')
            session.setdefault('annotation_history', []).append(copy.deepcopy(session.get('annotation')))
            status = {'ambiguous': 'ambiguous', 'no_answer': 'empty'}.get(decision, 'human')
            session['annotation'] = {'status': status, 'method': 'blind-human-decision/1',
                                     'id': identifier, 'annotator': annotator.strip(),
                                     'decision_code': decision, 'quote': quote, 'note': note}
            # Human coding supplies only the decision. Other fields are copied
            # from the parsed answer when present; no basis or citation is inferred.
            answer = copy.deepcopy(session.get('answer'))
            answer = answer if isinstance(answer, dict) else {}
            answer['decision'] = decision if decision in ('ready', 'not_ready', 'undetermined') else None
            session['answer'] = answer
        cases = {case['identifier']: case_from_record(case) for case in _read(run / 'cases.json')}
        scorer = ReferenceScorer()
        for row in rows:
            for session in _sessions(row):
                session['score'] = scorer.score(cases[row['case']], session['session'], session)
        _write_new(output, rows)
        return {'annotated': len(seen), 'output': str(output),
                'raw_records': 'unchanged', 'basis_and_citations': 'not inferred by annotation'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest='command', required=True)
    export = subcommands.add_parser('export')
    export.add_argument('run', type=Path)
    export.add_argument('--output', type=Path, required=True)
    export.add_argument('--all', action='store_true', help='Include automatic answers for a masked coding audit')
    ingest = subcommands.add_parser('import')
    ingest.add_argument('run', type=Path)
    ingest.add_argument('bundle', type=Path)
    ingest.add_argument('labels', type=Path)
    ingest.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    exchange = AnnotationExchange()
    if args.command == 'export':
        result = exchange.export(args.run, args.output, include_all=args.all)
    else:
        result = exchange.import_labels(args.run, args.bundle, args.labels, args.output)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
