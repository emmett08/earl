"""Validate and freeze separately supplied evaluation tasks and their provenance."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

from jsonschema import validate

from .corpus_cases import CorpusCase
from .corpus_logic import RULE, FACT
from .corpus_reference import CorpusReference


def manifest_cases(payload: dict) -> tuple[CorpusCase, ...]:
    if not isinstance(payload, dict) or payload.get('schema') != 'EAL/evaluation-task-manifest/1':
        raise ValueError('Invalid evaluation task manifest')
    provenance = payload.get('provenance', {})
    for key in ('author', 'reviewer', 'construction', 'population', 'sampling', 'created_at'):
        if not isinstance(provenance.get(key), str) or not provenance[key].strip():
            raise ValueError('Task provenance requires ' + key)
    if provenance['author'] == provenance['reviewer']:
        raise ValueError('Task author and answer-key reviewer must be distinct declared identities')
    if provenance['construction'] not in ('external_human', 'external_ai', 'internal_synthetic'):
        raise ValueError('Declare task construction honestly')
    records = payload.get('cases')
    if not isinstance(records, list) or not records or len(records) > 1000:
        raise ValueError('Supply between one and 1000 task records')
    cases = []
    for record in records:
        validate(record['rule'], RULE)
        spec = record['specification']
        if not isinstance(record.get('identifier'), str) or not record['identifier'].strip():
            raise ValueError('Task identity is required')
        if not isinstance(record.get('family'), str) or not record['family']:
            raise ValueError('Task family is required')
        for field in ('scope_description', 'natural_language_rule'):
            if not isinstance(spec.get(field), str) or not spec[field]:
                raise ValueError('Task specification requires ' + field)
        if not spec.get('identity_scope_keys') or not all(key in spec['scope'] for key in spec['identity_scope_keys']):
            raise ValueError('Task identity scope must be explicit')
        ids = {r['id'] for r in record['rule']['requirements']}
        if len(ids) != len(record['rule']['requirements']) or any(
                not set(route['requirement_ids']) <= ids for route in record['rule'].get('alternatives', [])):
            raise ValueError('Task rule has ambiguous or unknown requirement identities')
        timeline = record['timeline']
        if [item['session'] for item in timeline] != list(range(11)):
            raise ValueError('Supply initial and ten recipient snapshots')
        previous = None
        for snapshot in timeline:
            if type(snapshot.get('now_minute')) not in (int, float) or not math.isfinite(snapshot['now_minute']) or snapshot['now_minute'] < 0:
                raise ValueError('Invalid snapshot time')
            if type(snapshot.get('evidence_revision')) is not int or snapshot['evidence_revision'] < 0:
                raise ValueError('Explicit evidence revision events are required')
            for fact in snapshot['facts']:
                validate(fact, FACT)
            if previous:
                if snapshot['now_minute'] <= previous['now_minute'] or snapshot['evidence_revision'] < previous['evidence_revision']:
                    raise ValueError('Times must increase and evidence revisions cannot decrease')
                changed = any(snapshot[key] != previous[key] for key in ('scope', 'facts'))
                if changed and snapshot['evidence_revision'] == previous['evidence_revision']:
                    raise ValueError('Changed evidence requires a declared invalidation event')
            previous = snapshot
        expected = tuple(item['expected'] for item in timeline)
        if not all(value in ('ready', 'not_ready', 'undetermined') for value in expected):
            raise ValueError('Invalid authored answer key')
        case = CorpusCase(record['identifier'], record['family'], deepcopy(spec), deepcopy(record['rule']),
            tuple({key: deepcopy(value) for key, value in item.items() if key != 'expected'} for item in timeline),
            expected, cohort=provenance['construction'])
        if any(CorpusReference().reference(case, i)['decision'] != expected[i] for i in range(11)):
            raise ValueError('Authored answer key disagrees with the independent task reference')
        cases.append(case)
    if len({case.identifier for case in cases}) != len(cases):
        raise ValueError('Duplicate evaluation case identity')
    return tuple(cases)


def cases_for_plan(plan: dict) -> tuple:
    from .cases import CASES
    payload = plan.get('task_manifest')
    if payload:
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        if plan.get('task_manifest_sha256', digest) != digest:
            raise ValueError('Task manifest digest differs from the frozen plan')
    additional = manifest_cases(payload) if payload else ()
    if {c.identifier for c in additional} & {c.identifier for c in CASES}:
        raise ValueError('Evaluation identities cannot shadow calibration cases')
    return (*CASES, *additional)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new output plan')
    payload = json.loads(args.manifest.read_text())
    cases = manifest_cases(payload)
    plan = json.loads(args.plan.read_text())
    plan.update(task_manifest=payload, cases=[c.identifier for c in cases], study_role='pilot',
                study_id=plan['study_id'] + '-independent-tasks', pilot_run_ids=[],
                task_manifest_sha256=hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest())
    args.output.write_text(json.dumps(plan, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'families': len({c.family for c in cases}),
        'construction': payload['provenance']['construction'], 'scope': payload['provenance']['population']}))


if __name__ == '__main__':
    main()
