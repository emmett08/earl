#!/usr/bin/env python3
"""Read-only analysis composite of exact original, A2 and A3 960-call ledgers.

No provider calls, retries, imputation, or changes to source directories. A3
must be terminal; the output is a new analysis-only directory and never a
resumable paid ledger. Both separate connection probes stay outside 960 slots.
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
import continue_mechanisms_960_a3 as a3  # noqa: E402
import consolidate_mechanisms_960 as earlier  # noqa: E402
import analyse_mechanisms_960 as analyser  # noqa: E402

SCHEMA='eal2-mechanisms-960-a3-analysis-composite/1'
A3_SEMANTIC_FREEZE='170ea3d6aec0fd0e2d071fe02968031ffab4ee078f15b1c5480ddbe2d3e1db4f'
A3_FREEZE_FILE='dcc17ddb96dae06db28a44a5c94c3be635bf9586245c83a86d724477679a34ea'
TERMINAL={'completed','completed_with_failures'}


def _read(path:Path):
    raw=path.read_bytes()
    return study.strict_json(raw.decode('utf-8')),raw,hashlib.sha256(raw).hexdigest()


def compose(original_dir:Path,a2_dir:Path,a3_dir:Path):
    original_dir,a2_dir,a3_dir=(p.resolve() for p in (original_dir,a2_dir,a3_dir))
    prior,joined,source_freeze_raw,a2_probe_raw,prior_paths=earlier.compose(original_dir,a2_dir)
    if prior['attempted']!=468 or prior['unattempted']!=492:
        raise ValueError('Only the frozen 468-attempt A2 stop may precede A3')
    a3_freeze,a3_freeze_raw,a3_freeze_sha=_read(a3_dir/'freeze.json')
    a3_ledger,a3_ledger_raw,a3_ledger_sha=_read(a3_dir/'ledger.json')
    a3_probe,a3_probe_raw,a3_probe_sha=_read(a3_dir/'probe.json')
    if (a3_freeze_sha!=A3_FREEZE_FILE or a3_freeze.get('freeze_sha256')!=A3_SEMANTIC_FREEZE
            or a3_freeze!=a3.prepare(original_dir,a2_dir)):
        raise ValueError('A3 freeze is not the exact reviewed continuation')
    frozen=a3.verify(a3_freeze,original_dir,a2_dir)
    if (a3_ledger.get('schema')!=a3.LEDGER or a3_ledger.get('freeze_sha256')!=A3_SEMANTIC_FREEZE
            or a3_ledger.get('status') not in TERMINAL and
            not str(a3_ledger.get('status')).startswith('stopped_')):
        raise ValueError('A3 ledger is live or belongs to another freeze')
    if (a3_probe.get('schema')!=a3.PROBE or a3_probe.get('state')!='completed'
            or a3_probe.get('continuation_freeze_sha256')!=A3_SEMANTIC_FREEZE
            or not isinstance(a3_probe.get('response'),dict)):
        raise ValueError('Separate A3 probe is incomplete or unmetered')
    measured=study.ModelResponse(**a3_probe['response'])
    if (measured.model not in frozen['plan']['accepted_response_models']
            or study.response_cost(measured,frozen['provider_identity'])!=a3_probe.get('cost_usd')):
        raise ValueError('A3 probe model, usage or configured charge differs')
    new=a3_ledger['attempts']
    if (len(new)>492 or [r.get('index') for r in new]!=list(range(468,468+len(new)))
            or a3_freeze['indexes']!=list(range(468,960))):
        raise ValueError('A3 must retain an exact disjoint original-order prefix')
    if a3_ledger['status'] in TERMINAL and len(new)!=492:
        raise ValueError('A3 declares completion with unattempted slots')
    allowed=set(frozen['plan']['accepted_response_models'])
    for row in new:
        earlier._check_row(row,frozen['schedule'][row['index']],frozen['provider_identity'],allowed)
    if a3_ledger['status'] in TERMINAL and a3.failure_stop(new,a3_freeze['failure_policy']):
        raise ValueError('A3 declares completion after crossing its failure threshold')
    if (a3_ledger['status']=='stopped_identity_usage_or_other_failure'
            and a3.failure_stop(new,a3_freeze['failure_policy'])!=a3_ledger['status']):
        raise ValueError('A3 fatal stop does not match retained failure')
    if (a3_ledger['status']=='stopped_repeated_provider_failures'
            and a3.failure_stop(new,a3_freeze['failure_policy'])!=a3_ledger['status']):
        raise ValueError('A3 provider-failure stop does not match retained sequence')
    paths=[*prior_paths,(a3_dir/'freeze.json',a3_freeze_sha),
           (a3_dir/'ledger.json',a3_ledger_sha),(a3_dir/'probe.json',a3_probe_sha)]
    for path,digest in paths:earlier._again(path,digest)
    all_rows=joined['attempts']+new
    if [r['index'] for r in all_rows]!=list(range(len(all_rows))):
        raise ValueError('Composite has a gap or duplicate assignment')
    unknown=[r['index'] for r in all_rows if r.get('cost_usd') is None]
    if any(r['state']!='failed' for r in all_rows if r['index'] in unknown):
        raise ValueError('Unknown charges may not be imputed as zero')
    known=sum(r['cost_usd'] for r in all_rows if r['cost_usd'] is not None)
    summary={'schema':SCHEMA,'source_freeze_sha256':frozen['freeze_sha256'],
             'a2_freeze_sha256':earlier.A2_SEMANTIC_FREEZE,
             'a3_freeze_sha256':A3_SEMANTIC_FREEZE,
             'input_file_sha256':{'original_freeze':prior['input_file_sha256']['original_freeze'],
                                  'original_ledger':prior['input_file_sha256']['original_ledger'],
                                  'a2_freeze':prior['input_file_sha256']['continuation_freeze'],
                                  'a2_ledger':prior['input_file_sha256']['continuation_ledger'],
                                  'a2_probe':prior['input_file_sha256']['separate_probe'],
                                  'a3_freeze':a3_freeze_sha,'a3_ledger':a3_ledger_sha,'a3_probe':a3_probe_sha},
             'assignments':960,'attempted':len(all_rows),'unattempted':960-len(all_rows),
             'index_ranges':{'original':[0,131],'a2':[132,467],
                             'a3':[468,467+len(new)]},
             'state_counts':dict(Counter(r['state'] for r in all_rows)),
             'unknown_charge_attempt_indexes':unknown,
             'known_study_model_cost_usd':known,
             'actual_unknown_charges_usd':None if unknown else 0,
             'separate_probes':{'a2_configured_rate_usd':prior['probe_outside_960']['configured_rate_cost_usd'],
                                'a3_configured_rate_usd':a3_probe['cost_usd'],
                                'excluded_from_960_decisions':True},
             'limitations':['Analysis-only composite; source ledgers and their failed slots are unchanged.',
                            'Unknown failed-call charges are not zero; known model cost excludes them.',
                            'A2 and A3 connection probes are outside the 960 assigned decisions.',
                            'Selected synthetic tasks and author-constructed references remain developmental.']}
    ledger={'schema':study.LEDGER,'freeze_sha256':frozen['freeze_sha256'],
            'status':'composite_completed_with_failures' if len(all_rows)==960 else 'composite_terminal_with_unattempted',
            'attempts':all_rows,'analysis_only':True,'composite_provenance_sha256':study.digest(summary)}
    return summary,ledger,source_freeze_raw,a2_probe_raw,a3_probe_raw,paths


def write_new(output:Path,summary:dict,ledger:dict,freeze_raw:bytes,a2_probe_raw:bytes,
              a3_probe_raw:bytes,paths):
    output=output.resolve()
    if output.exists() or any(output==p.parent or output.is_relative_to(p.parent) for p,_ in paths):
        raise ValueError('Composite must be written in a new directory outside every source')
    for path,digest in paths:earlier._again(path,digest)
    output.mkdir(parents=True,mode=0o700)
    (output/'freeze.json').write_bytes(freeze_raw)
    (output/'probe-a2.json').write_bytes(a2_probe_raw)
    (output/'probe-a3.json').write_bytes(a3_probe_raw)
    study.write(output/'ledger.json',ledger)
    study.write(output/'composition.json',summary)
    analysis=analyser.analyse(output)
    if (analysis['scheduled']!=960 or analysis['attempted']!=summary['attempted']
            or analysis['unknown_cost_attempts']!=len(summary['unknown_charge_attempt_indexes'])):
        raise AssertionError('Analyser disagrees with composite accounting')
    study.write(output/'analysis.json',analysis)
    return {'output':str(output),'attempted':analysis['attempted'],
            'unattempted':analysis['unattempted'],'failed':analysis['failed'],
            'malformed':analysis['malformed'],'unknown_charge_attempts':analysis['unknown_cost_attempts'],
            'known_study_model_cost_usd':analysis['known_configured_model_cost_usd'],
            'separate_probes_usd':summary['separate_probes']}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('original',type=Path)
    ap.add_argument('a2',type=Path)
    ap.add_argument('a3',type=Path)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    print(json.dumps(write_new(args.output,*compose(args.original,args.a2,args.a3)),sort_keys=True))


if __name__=='__main__':main()
