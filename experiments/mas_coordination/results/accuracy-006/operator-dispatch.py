"""Operator-only native-agent dispatch; never provided to measured workers."""
import argparse
import json
import time
from pathlib import Path
from eal.coordination import Coordinator
from experiments.mas_coordination.accuracy_study import read_study, start_unit, write_json

root = Path('/workspace/earl/experiments/mas_coordination/results/accuracy-006')
p = argparse.ArgumentParser()
p.add_argument('operation', choices=['reserve', 'record', 'export'])
p.add_argument('index', type=int)
p.add_argument('--role', choices=['assessor', 'reviewer'])
p.add_argument('--identity')
a = p.parse_args()
output, manifest, plan = read_study(root)
unit = manifest['units'][a.index-1]
directory = Path(unit['run']).parent
if a.operation == 'reserve' and a.role == 'assessor':
    start_unit(root, unit['unit_id'])
with Coordinator(unit['run']) as c:
    if a.operation == 'reserve':
        r = c.reserve_worker(a.role, execution_mode='actual_host_agent')
        if not r['new']:
            raise ValueError('Do not relaunch an existing reserved worker')
        context = directory / (a.role+'-context.json')
        response = directory / (a.role+'-response.json')
        write_json(context,r['context'])
        prompt = plan['worker_prompt_template'].format(context_path=str(context), response_path=str(response))
        write_json(directory/(a.role+'-dispatch.json'), {'role':a.role,'prompt':prompt,
                   'call_id':r['call_id'],'response_path':str(response),'reserved_monotonic':time.monotonic(),
                   'reserved_unix':time.time(),'maximum_soft_seconds':180})
        print(json.dumps({'index':a.index,'role':a.role,'prompt':prompt,'call_id':r['call_id'],
                          'context_path':str(context),'response_path':str(response)}))
    elif a.operation == 'record':
        dispatch=json.loads((directory/(a.role+'-dispatch.json')).read_bytes())
        raw=Path(dispatch['response_path']).read_bytes()
        result=c.record(dispatch['call_id'],raw,a.identity,execution_mode='actual_host_agent')
        write_json(directory/(a.role+'-record.json'),result)
        write_json(directory/(a.role+'-host-execution.json'),{'execution_id':a.identity,
                   'execution_mode':'actual_host_agent','fresh_context':True,'model':None,
                   'tokens':None,'cost_usd':None,'elapsed_from_reservation_seconds':time.time()-dispatch['reserved_unix']})
        c.export(unit['export'])
        print(json.dumps({'index':a.index,'role':a.role,'accepted':result['accepted'],
                          'outcome':result['outcome'],'status':c.status()['status']}))
    else:
        c.export(unit['export'])
        print(json.dumps({'index':a.index,'status':c.status()['status']}))
