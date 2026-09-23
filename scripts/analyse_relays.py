#!/usr/bin/env python3
"""Inspect completed relay checkpoints and export exact, reproducible summaries.

No provider calls. Endpoint correctness and tool verification remain separate.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import statistics

from eal.benchmark import score_answer
from eal.experiment import _digest, aggregate_experiment, cluster_interval
from eal.relay import handoff_packet, known_model_cost


def read_record(path: Path, freeze_digest: str) -> dict:
    record = json.loads(path.read_text())
    if record['sha256'] != _digest(record['trial']) or record['freeze_digest'] != freeze_digest:
        raise ValueError('Checkpoint integrity mismatch: '+str(path))
    return record['trial']


def analyse(directory: Path) -> dict:
    freeze=json.loads((directory/'freeze.json').read_text())
    frozen={k:v for k,v in freeze.items() if k not in {'freeze_digest','frozen_at'}}
    if _digest(frozen)!=freeze['freeze_digest']:
        raise ValueError('Freeze integrity mismatch')
    report=json.loads((directory/'report.json').read_text())
    if report['reference_or_implementation_drift']:
        raise ValueError('Code or reference drift invalidates comparison')
    stages={p.stem:read_record(p,freeze['freeze_digest']) for p in sorted((directory/'stages').glob('*.json')) if not p.name.endswith('.inflight.json')}
    trials=[read_record(p,freeze['freeze_digest']) for p in sorted((directory/'trials').glob('*.json'))]
    schedule={x['trial_id']:x for x in freeze['schedule']}
    if len(trials)!=len(schedule) or len({t['trial_id'] for t in trials})!=len(schedule):
        raise ValueError('Incomplete or duplicate trial coverage')
    references=freeze['task_references']
    endpoint_rows=[]
    integrity_errors=[]
    reused=Counter()
    for trial in trials:
        sid=trial['trial_id'];expected=references[trial['task_id']]['expected']['claims']
        if any(trial[k]!=v for k,v in schedule[sid].items()): integrity_errors.append(sid+':schedule')
        keys=trial['stage_keys'];chain=[stages[k] for k in keys]
        if len(keys)!=len(trial['condition']['stages']):integrity_errors.append(sid+':incomplete sequence')
        reused.update(keys)
        common=score_answer(expected,chain[-1]['report'])
        if common!=trial['score']:integrity_errors.append(sid+':endpoint score')
        cost=sum(s['cost']['total_usd'] for s in chain) if all(s['cost']['total_usd'] is not None for s in chain) else None
        if cost!=trial['cost']['total_usd']:integrity_errors.append(sid+':cost')
        for i,stage in enumerate(chain):
            if stage['task_id']!=trial['task_id']:integrity_errors.append(sid+':task identity')
            packet=handoff_packet(chain[i-1],trial['condition']['stages'][i].get('handoff','none')) if i else None
            if stage.get('inputs',{}).get('prior_stage')!=packet:integrity_errors.append(sid+':handoff identity')
            if packet is not None:
                original=stage['inputs'].get('source',stage['inputs'].get('draft_source'))
                ref=references[trial['task_id']]
                if original!=(ref['draft_source'] or ref['inputs']['source']):integrity_errors.append(sid+':anchor changed')
        correctness=[score_answer(expected,s['report'])['correct'] for s in chain]
        final=chain[-1];tool_endpoint=final.get('arm')=='delegated'
        endpoint_rows.append({'trial_id':sid,'task_id':trial['task_id'],'repetition':trial['repetition'],'condition':trial['condition_id'],
            'correct':int(common['correct']),'unjustified':int(common['unjustified']),
            'completed_answer':int(final['report']['status']=='completed'),
            'tool_endpoint':int(tool_endpoint),'verified_correct_endpoint':int(tool_endpoint and final['score']['correct']),
            'corrected_transitions':sum(not a and b for a,b in zip(correctness,correctness[1:])),
            'damaged_transitions':sum(a and not b for a,b in zip(correctness,correctness[1:])),
            'first_correct':int(correctness[0]),'sequence_cost_usd':cost,
            'sequence_seconds':sum(s['report']['latency_seconds'] for s in chain),
            'sequence_tokens':trial['report']['usage'].get('total_tokens'),
            'sequence_requests':len(trial['report']['attempts']),
            'sequence_repairs':trial['report']['repairs'],
            'stage_keys':';'.join(keys),'stage_correctness':','.join(str(int(x)) for x in correctness),
            'stop_reason':final['report']['stop_reason']})
    if integrity_errors:raise ValueError('Integrity failures: '+str(integrity_errors))
    recomputed=aggregate_experiment(trials,freeze['schedule'],seed=freeze['plan']['order_seed'],samples=freeze['plan']['bootstrap_samples'])
    if recomputed!=report['aggregate']:raise ValueError('Stored aggregate differs from independent recomputation')
    for name,base in recomputed['conditions'].items():
        rows=[r for r in endpoint_rows if r['condition']==name]
        base.update(corrected_transitions=sum(r['corrected_transitions'] for r in rows),
                    damaged_transitions=sum(r['damaged_transitions'] for r in rows),
                    verified_correct_endpoints=sum(r['verified_correct_endpoint'] for r in rows),
                    completed_answers=sum(r['completed_answer'] for r in rows),
                    first_stage_correct=sum(r['first_correct'] for r in rows),
                    mean_seconds=statistics.mean(r['sequence_seconds'] for r in rows))
    usage=[];failures=[]
    for key,stage in stages.items():
        r=stage['report'];expected=references[stage['task_id']]['expected']['claims'];score=score_answer(expected,r)
        row={'stage_key':key,'task_id':stage['task_id'],'model':r['provider']['model'],'arm':stage.get('arm'),
             'correct':score['correct'],'operational_correct':stage['score']['correct'],
             'status':r['status'],'stop_reason':r['stop_reason'],'uses':reused[key],
             'requests':len(r.get('attempts',[])),'repairs':r.get('repairs',0),
             'model_cost_usd':stage['cost']['model_usd'],'total_tokens':r.get('usage',{}).get('total_tokens'),
             'known_model_cost_usd':known_model_cost(stage),
             'seconds':r.get('latency_seconds'),
             'tool_calls':len(r.get('tool_calls',[])),
             'provider_errors':sum(a.get('status')!='received' for a in r.get('attempts',[])),
             'response_models':sorted({a['response_model'] for a in r.get('attempts',[]) if a.get('response_model')})}
        usage.append(row)
        if not score['correct'] or not stage['score']['correct']:
            failures.append({**row,'score':score,'operational_score':stage['score'],
                             'errors':[{'phase':a.get('status'),'error':a.get('error')} for a in r.get('attempts',[]) if a.get('error')]})
    known=sum(s['known_model_cost_usd'] for s in usage)
    if abs(known-report['known_unique_model_cost_usd'])>1e-10:raise ValueError('Campaign charging mismatch')
    paired={(r['condition'],r['task_id'],r['repetition']):r for r in endpoint_rows}
    differences=[];primary_blocks=[]
    for row in endpoint_rows:
        if row['condition']!='l_tool_n_evidence':continue
        other=paired['l_tool_n_answer',row['task_id'],row['repetition']]
        if row['stage_keys'].split(';')[0]!=other['stage_keys'].split(';')[0]:raise ValueError('Primary producer not shared')
        difference=row['correct']-other['correct'];differences.append({'task_id':row['task_id'],'value':difference})
        primary_blocks.append({'task_id':row['task_id'],'repetition':row['repetition'],'answer_correct':other['correct'],'evidence_correct':row['correct'],'difference':difference})
    invariant=True
    for row in endpoint_rows:
        if row['condition']=='l_tool_n_none':
            solo=paired['n_solo',row['task_id'],row['repetition']]
            invariant &= row['stage_keys'].split(';')[-1]==solo['stage_keys'] and row['correct']==solo['correct']
    if not invariant:raise ValueError('No-handoff invariant failed')
    return {'schema':'EAL/relay-analysis/1','freeze_digest':freeze['freeze_digest'],'trial_count':len(trials),
            'unique_stages':len(stages),'stage_uses':sum(reused.values()),'unique_model_cost_usd':known if all(s['model_cost_usd'] is not None for s in usage) else None,
            'known_unique_model_cost_usd':known,'unique_requests':sum(x['requests'] for x in usage),
            'unique_total_tokens':sum(x['total_tokens'] for x in usage) if all(x['total_tokens'] is not None for x in usage) else None,
            'all_integrity_checks_passed':True,'no_handoff_invariant_passed':invariant,
            'primary_contrast':{'direction':'l_tool_n_evidence minus l_tool_n_answer','blocks':primary_blocks,
                                'difference':cluster_interval(differences,lambda r:r['value'],seed=freeze['plan']['order_seed'],samples=freeze['plan']['bootstrap_samples'])},
            'aggregate':recomputed,'endpoint_rows':endpoint_rows,'stage_rows':usage,'failures':failures}


def export(data:dict, output:Path):
    output.mkdir(parents=True,exist_ok=True)
    (output/'analysis.json').write_text(json.dumps(data,indent=2)+'\n')
    for key,filename in [('endpoint_rows','endpoints.csv'),('stage_rows','stages.csv')]:
        rows=data[key]
        with (output/filename).open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (output/'failure-summary.json').write_text(json.dumps(data['failures'],indent=2)+'\n')
    compact={key:data[key] for key in ('schema','freeze_digest','trial_count','unique_stages','stage_uses','unique_model_cost_usd','unique_requests','unique_total_tokens','all_integrity_checks_passed','primary_contrast')}
    compact['conditions']={key:{k:v[k] for k in ('correct','completed_trials','total_cost_usd','cost_per_correct_task_usd','mean_seconds','corrected_transitions','damaged_transitions','verified_correct_endpoints')} for key,v in data['aggregate']['conditions'].items()}
    (output/'summary.json').write_text(json.dumps(compact,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();data=analyse(args.run);export(data,args.output)
    print(json.dumps({k:data[k] for k in ('trial_count','unique_stages','unique_model_cost_usd','all_integrity_checks_passed')}))
