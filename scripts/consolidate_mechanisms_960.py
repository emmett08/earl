#!/usr/bin/env python3
"""Make a read-only, analysis-only composite of an original 960 stop and A2.

This script never calls a provider or changes either input directory. It only
writes a *new* output directory after both campaigns are terminal, preserving
all failed attempts and a separate probe. Its composite ledger must not be
resumed as a paid run.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import run_mechanisms_960 as study  # noqa: E402
import continue_mechanisms_960 as continuation  # noqa: E402
import analyse_mechanisms_960 as analyser  # noqa: E402

COMPOSITE='eal2-mechanisms-960-analysis-composite/1'
TERMINAL={'completed','completed_with_failures'}
ORIGINAL_SEMANTIC_FREEZE='35a98da55ab1f9f5963d3fa603a6a022c2830b497596e4d9f441c22d84a39a3c'
ORIGINAL_FREEZE_FILE='fb0528e5a280b938de4756cc27c56ac75d4275f30c0948d0960e171f394dd9be'
ORIGINAL_STOPPED_LEDGER_FILE='9cb880af12042dfc953775cf430d9cfcca8217c3d439790e725716c2418e5c66'
A2_SEMANTIC_FREEZE='2c1dab75cc37ad3bdb3402555d6aec5b3a435487c33bf8c3f3caf597572564d2'
A2_FREEZE_FILE='3fd359c05ce55073e65b425ce70ce50a23fbe97a639d569eb70ad183467dc468'


def _file(path:Path):
    raw=path.read_bytes()
    return study.strict_json(raw.decode('utf-8')),raw,hashlib.sha256(raw).hexdigest()


def _again(path:Path,expected:str):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        raise ValueError(f'Input changed during read-only consolidation: {path.name}')


def _check_row(row:dict,case:dict,identity:dict,allowed_models:set[str]):
    index=row.get('index')
    if (type(index) is not int or (row.get('case_id'),row.get('prompt_sha256'))
            !=(case['id'],case['prompt_sha256'])):
        raise ValueError('Attempt identity differs from its frozen assignment')
    if study.digest(case['messages'])!=case['prompt_sha256']:
        raise ValueError(f'Frozen prompt content differs at index {index}')
    if row.get('state') not in {'completed','malformed','failed'}:
        raise ValueError(f'Attempt {index} is pending or has an unknown state')
    response=row.get('response')
    usage=row.get('usage')
    if response is None:
        if (row['state']!='failed' or usage is not None or row.get('cost_usd') is not None
                or row.get('answered_status') is not None or row.get('admitted') is not False):
            raise ValueError(f'Response-less attempt {index} was imputed')
        return
    if not isinstance(response,dict):
        raise ValueError(f'Invalid response at index {index}')
    for key in ('input_tokens','output_tokens'):
        if type(response.get(key)) is not int or response[key]<0:
            if row.get('cost_usd') is not None:
                raise ValueError(f'Unknown token usage given a measured cost at index {index}')
    if response.get('model') not in allowed_models and row['state']!='failed':
        raise ValueError(f'Unpinned completed response model at index {index}')
    if usage is None:
        if row['state']!='failed':
            raise ValueError(f'Completed response lacks usage at index {index}')
    elif usage!={
        'input_tokens':response.get('input_tokens'),
        'output_tokens':response.get('output_tokens'),
        'cached_input_tokens':(response.get('metadata') or {}).get('cached_input_tokens',0),
    }:
        raise ValueError(f'Recorded usage differs from response at index {index}')
    measured=study.response_cost(study.ModelResponse(**response),identity)
    if measured!=row.get('cost_usd'):
        raise ValueError(f'Configured-rate response cost differs at index {index}')
    answer=study._answer(response['text'],case['claim']) if row['state']!='failed' else None
    if row['state']=='completed' and answer is None or row['state']=='malformed' and answer is not None:
        raise ValueError(f'Strict answer parsing differs at index {index}')
    status=answer['claims'][case['claim']] if answer else None
    expected={
        'answered_status':status,'admitted':status is not None,
        'available_information_correct':status==case['available_reference'] if status else False,
        'full_information_agreement':status==case['full_information_reference'] if status else False,
        'false_support':status=='supported' and case['available_reference']!='supported',
        'proposal_adopted':status==case['proposal'] if status and case['proposal'] else None,
    }
    if any(row.get(key)!=value for key,value in expected.items()):
        raise ValueError(f'Stored response score differs at index {index}')


def compose(original_dir:Path,a2_dir:Path):
    original_dir,a2_dir=original_dir.resolve(),a2_dir.resolve()
    original_freeze,original_freeze_raw,original_freeze_hash=_file(original_dir/'freeze.json')
    original_ledger,original_ledger_raw,original_ledger_hash=_file(original_dir/'ledger.json')
    a2_freeze,a2_freeze_raw,a2_freeze_hash=_file(a2_dir/'freeze.json')
    a2_ledger,a2_ledger_raw,a2_ledger_hash=_file(a2_dir/'ledger.json')
    probe,probe_raw,probe_hash=_file(a2_dir/'probe.json')
    if (original_freeze.get('freeze_sha256')!=ORIGINAL_SEMANTIC_FREEZE
            or original_freeze_hash!=ORIGINAL_FREEZE_FILE
            or original_ledger_hash!=ORIGINAL_STOPPED_LEDGER_FILE
            or a2_freeze.get('freeze_sha256')!=A2_SEMANTIC_FREEZE
            or a2_freeze_hash!=A2_FREEZE_FILE):
        raise ValueError('This composite only accepts the exact original stop and A2 freezes')
    study.verify_freeze(original_freeze)
    continuation.verify(a2_freeze,original_dir)
    if original_ledger['schema']!=study.LEDGER or original_ledger['freeze_sha256']!=original_freeze['freeze_sha256']:
        raise ValueError('Original ledger belongs to another freeze')
    if original_ledger['status']!='stopped_after_failed_batch':
        raise ValueError('Original stop changed or was resumed')
    if a2_ledger.get('schema')!=continuation.LEDGER or a2_ledger.get('freeze_sha256')!=a2_freeze['freeze_sha256']:
        raise ValueError('Continuation ledger belongs to another freeze')
    if a2_ledger['status'] not in TERMINAL and not str(a2_ledger['status']).startswith('stopped_'):
        raise ValueError('Continuation is live; no composite output is allowed')
    if (probe.get('schema')!=continuation.PROBE or probe.get('state')!='completed'
            or probe.get('continuation_freeze_sha256')!=a2_freeze['freeze_sha256']
            or probe.get('response') is None or probe.get('cost_usd') is None):
        raise ValueError('Missing or incomplete distinct connection probe')
    probe_response=study.ModelResponse(**probe['response'])
    if (probe_response.model not in original_freeze['plan']['accepted_response_models']
            or study.response_cost(probe_response,original_freeze['provider_identity'])!=probe['cost_usd']):
        raise ValueError('Probe model or usage/cost differs from original provider freeze')
    original_rows,a2_rows=original_ledger['attempts'],a2_ledger['attempts']
    if len(original_rows)!=132 or [r.get('index') for r in original_rows]!=list(range(132)):
        raise ValueError('Original attempts must retain exact 0..131 sequence')
    if (len(a2_rows)>828 or [r.get('index') for r in a2_rows]!=list(range(132,132+len(a2_rows)))
            or a2_freeze['indexes']!=list(range(132,960))):
        raise ValueError('Continuation attempts must be a disjoint original-order prefix of 132..959')
    if len(original_freeze['schedule'])!=960 or len({c['id'] for c in original_freeze['schedule']})!=960:
        raise ValueError('The exact original schedule has not retained 960 unique assignments')
    if original_rows[129].get('state')!='failed' or original_rows[129].get('cost_usd') is not None:
        raise ValueError('Failed index 129 is missing or has an imputed charge')
    allowed=set(original_freeze['plan']['accepted_response_models'])
    for row in original_rows+a2_rows:
        _check_row(row,original_freeze['schedule'][row['index']],original_freeze['provider_identity'],allowed)
    if a2_freeze['case_prompt_sha256']!=[c['prompt_sha256'] for c in original_freeze['schedule'][132:]]:
        raise ValueError('Continuation freeze differs from original prompts')
    paths=[(original_dir/'freeze.json',original_freeze_hash),
           (original_dir/'ledger.json',original_ledger_hash),(a2_dir/'freeze.json',a2_freeze_hash),
           (a2_dir/'ledger.json',a2_ledger_hash),(a2_dir/'probe.json',probe_hash)]
    for path,expected in paths:_again(path,expected)
    rows=original_rows+a2_rows
    unknown=[r['index'] for r in rows if r.get('cost_usd') is None]
    if not set(unknown)<={r['index'] for r in rows if r['state']=='failed'}:
        raise ValueError('Unknown charge cannot be relabelled as a measured zero')
    known_cost=sum(r['cost_usd'] for r in rows if r['cost_usd'] is not None)
    summary={
        'schema':COMPOSITE,'original_freeze_sha256':original_freeze['freeze_sha256'],
        'continuation_freeze_sha256':a2_freeze['freeze_sha256'],
        'input_file_sha256':{'original_freeze':original_freeze_hash,'original_ledger':original_ledger_hash,
                             'continuation_freeze':a2_freeze_hash,'continuation_ledger':a2_ledger_hash,
                             'separate_probe':probe_hash},
        'assignments':960,'attempted':len(rows),'unattempted':960-len(rows),
        'original_indexes':[0,131],'continuation_indexes':[132,131+len(a2_rows)],
        'state_counts':dict(Counter(r['state'] for r in rows)),
        'unknown_charge_attempt_indexes':unknown,
        'known_study_model_cost_usd':known_cost,'actual_unknown_charges_usd':None if unknown else 0,
        'probe_outside_960':{'state':'completed','configured_rate_cost_usd':probe['cost_usd'],
                             'response_model':probe_response.model},
        'limitations':['Analysis-only composite; original and A2 ledgers remain independent and immutable.',
                       'Unknown failed-call charges are not zero and are excluded from known measured cost.',
                       'Probe usage is excluded from the 960 assigned decisions and listed separately.',
                       'Six roots per family are synthetic tasks and the author-provided reference remains developmental.']}
    composite={'schema':study.LEDGER,'freeze_sha256':original_freeze['freeze_sha256'],
               'status':'composite_completed_with_failures' if len(rows)==960 else 'composite_terminal_with_unattempted',
               'attempts':rows,'analysis_only':True,'composite_provenance_sha256':study.digest(summary)}
    return summary,composite,original_freeze_raw,probe_raw,paths


def write_new(output:Path,summary:dict,ledger:dict,original_freeze_raw:bytes,probe_raw:bytes,paths):
    output=output.resolve()
    if output.exists() or output in [path.parent for path,_ in paths] or any(output.is_relative_to(path.parent) for path,_ in paths):
        raise ValueError('Composite must be written to a new independent directory')
    for path,expected in paths:_again(path,expected)
    output.mkdir(parents=True,mode=0o700)
    (output/'freeze.json').write_bytes(original_freeze_raw)
    (output/'probe.json').write_bytes(probe_raw)
    study.write(output/'ledger.json',ledger)
    study.write(output/'composition.json',summary)
    report=analyser.analyse(output)
    if (report['scheduled']!=960 or report['attempted']!=summary['attempted']
            or report['unknown_cost_attempts']!=len(summary['unknown_charge_attempt_indexes'])):
        raise AssertionError('Existing analysis disagrees with composite accounting')
    study.write(output/'analysis.json',report)
    return {'output':str(output),'status':report['status'],'attempted':report['attempted'],
            'unattempted':report['unattempted'],'failed':report['failed'],
            'unknown_charges':report['unknown_cost_attempts'],
            'known_study_model_cost_usd':report['known_configured_model_cost_usd'],
            'probe_outside_960_usd':summary['probe_outside_960']['configured_rate_cost_usd']}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('original',type=Path)
    ap.add_argument('continuation',type=Path)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    result=compose(args.original,args.continuation)
    print(json.dumps(write_new(args.output,*result),sort_keys=True))


if __name__=='__main__':main()
