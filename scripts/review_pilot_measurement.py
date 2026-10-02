"""Reconstruct a masked supplemental coding audit without changing pilot records."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

LABELS = {'ready', 'not_ready', 'undetermined', 'ambiguous', 'no_answer'}


def read(path: Path):
    return json.loads(path.read_text())


def review(directory: Path, rows_path: Path) -> dict:
    masked_path = directory / 'masked-items.json'
    texts = {item['id']: item['text'] for item in read(masked_path)['items']}
    mapping = read(directory / 'private-mapping.json')['items']
    assert len(texts) == len(mapping) == len({x['id'] for x in mapping})
    records = {}
    hashes = {}
    for name in ('reviewer-a', 'reviewer-b', 'adjudicator'):
        path = directory / (name + '.json')
        if not path.exists():
            continue
        payload = read(path)
        source = directory / ('adjudication-items.json' if name == 'adjudicator' else 'masked-items.json')
        declared = payload.get('sourceSHA') if name == 'adjudicator' else payload.get('input_sha256')
        assert declared == hashlib.sha256(source.read_bytes()).hexdigest(), 'Review source identity mismatch'
        items = {item['id']: item for item in payload['items']}
        assert len(items) == len(payload['items'])
        assert set(items) <= set(texts)
        if name != 'adjudicator':
            assert set(items) == set(texts)
        for ident, item in items.items():
            assert item['decision'] in LABELS
            assert item['quote'].strip() and item['quote'] in texts[ident]
            assert item['note'].strip()
        records[name] = items
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert {'reviewer-a', 'reviewer-b'} <= set(records)
    rows = read(rows_path)
    sessions = {s['session_id']: (row, s) for row in rows for s in row['sessions']}
    before = Counter()
    after = Counter()
    flagged = []
    for location in mapping:
        ident = location['id']
        row, session = sessions[location['session_id']]
        assert texts[ident] == session['raw_answer']
        assert hashlib.sha256(texts[ident].encode()).hexdigest() == location['sha256']
        assert session['annotation']['decision_code'] == location['original_code']
        assert session['score']['reference']['decision'] == location['reference']
        a, b = (records[name][ident]['decision'] for name in ('reviewer-a', 'reviewer-b'))
        initial = a if a == b else 'ambiguous'
        final = records.get('adjudicator', {}).get(ident, {}).get('decision', initial)
        before[location['selection'], location['original_code']] += 1
        after[location['selection'], final] += 1
        if final != location['original_code'] or initial != location['original_code']:
            flagged.append({**location, 'first_review_a': a, 'first_review_b': b,
                            'initial_consensus': initial, 'supplemental_code': final,
                            'adjudication': records.get('adjudicator', {}).get(ident)})
    alternatives = {item['session_id']: item['supplemental_code'] for item in flagged}
    quality = {}
    for arm in ('ordinary', 'eal'):
        chosen = [(row, s) for row in rows if row['arm'] == arm
                  for s in row['sessions'] if s['session'] > 0]
        counts = Counter()
        for row, s in chosen:
            code = alternatives.get(s['session_id'], s['annotation']['decision_code'])
            outcome = 'unknown' if code == 'ambiguous' else (
                'match' if code == s['score']['reference']['decision'] else 'mismatch')
            counts[outcome] += 1
        n = len(chosen)
        quality[arm] = {**dict(counts), 'n': n,
                        'bounds': [counts['match'] / n, (counts['match'] + counts['unknown']) / n]}
    summary = {
        'schema': 'EAL/supplemental-measurement-review/1',
        'input_rows_sha256': hashlib.sha256(rows_path.read_bytes()).hexdigest(),
        'masked_items_sha256': hashlib.sha256(masked_path.read_bytes()).hexdigest(),
        'review_hashes': hashes,
        'sample_n': len(mapping),
        'original_ambiguity_census_n': sum(x['selection'] == 'all_ambiguous' for x in mapping),
        'resolved_stratified_sample_n': sum(x['selection'] == 'stratified_resolved' for x in mapping),
        'sampling': read(directory / 'private-mapping.json')['sampling'],
        'first_review_disagreements': sum(records['reviewer-a'][i]['decision'] !=
                                          records['reviewer-b'][i]['decision'] for i in texts),
        'supplemental_counts_by_selection': {
            selection: dict(Counter({code: n for (group, code), n in after.items() if group == selection}))
            for selection in ('all_ambiguous', 'stratified_resolved')},
        'flagged_records': flagged,
        'supplemental_recipient_reference_agreement': quality,
        'status': 'supplemental_ai_review; completed pilot and its published primary codes unchanged',
        'limits': ['Separate masked AI contexts share model-family and rubric risks.',
                   'Reviewer agreement does not establish independent coding accuracy.',
                   'Purposive census plus one-per-stratum sample does not estimate a population error rate.',
                   'Alternative coding bounds address interpretations, not assessor error or sampling uncertainty.']}
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--rows', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--derived-rows', type=Path)
    parser.add_argument('--cases', type=Path)
    args = parser.parse_args()
    result = review(args.directory, args.rows)
    if args.derived_rows:
        if not args.cases:
            parser.error('--derived-rows requires the retained --cases file')
        if args.derived_rows.exists():
            raise ValueError('Use a new derived rows path; historical records remain unchanged')
        import copy
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
        from experiments.model_transfer.cases import case_from_record
        from experiments.model_transfer.scoring import ReferenceScorer
        original_rows = read(args.rows)
        original_sessions = {s['session_id']: s for row in original_rows for s in row['sessions']}
        rows = copy.deepcopy(original_rows)
        cases = {case['identifier']: case_from_record(case) for case in read(args.cases)}
        amended = {item['session_id']: item for item in result['flagged_records']
                   if item['supplemental_code'] != item['original_code']}
        assessor = {'kind': 'ai', 'model': 'OpenAI ChatGPT/Codex; exact serving identifier unavailable',
                    'method': 'blinded-whole-answer-semantic-adjudication/1',
                    'validation': 'Two masked reviews followed by a fresh semantic adjudication; six targeted amendments. No independent human validation.',
                    'protocol': 'supplemental-coding-protocol.md',
                    'source_items_sha256': result['masked_items_sha256'],
                    'adjudicator_sha256': result['review_hashes'].get('adjudicator.json')}
        for row in rows:
            for session in row['sessions']:
                item = amended.get(session['session_id'])
                if item:
                    adjudication = item['adjudication']
                    session.setdefault('annotation_history', []).append(copy.deepcopy(session['annotation']))
                    session['annotation'] = {**session['annotation'], 'status': 'ai', 'assessor': assessor,
                        'method': assessor['method'], 'decision_code': item['supplemental_code'],
                        'quote': adjudication['quote'], 'note': adjudication['note'],
                        'supplemental_review_id': item['id']}
                    session['answer']['decision'] = item['supplemental_code']
                    session['score'] = ReferenceScorer().score(cases[row['case']], session['session'], session)
                original = original_sessions[session['session_id']]
                assert session['raw_answer'] == original['raw_answer']
                assert session['api_attempt_ids'] == original['api_attempt_ids']
        args.derived_rows.write_text(json.dumps(rows, indent=2) + '\n')
        result['derived_rows'] = str(args.derived_rows)
        result['amended_codes'] = len(amended)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('sample_n', 'first_review_disagreements',
                     'supplemental_counts_by_selection', 'supplemental_recipient_reference_agreement')}))


if __name__ == '__main__':
    main()
