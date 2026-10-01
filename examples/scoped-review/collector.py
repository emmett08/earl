"""Fixed synthetic values; this collector measures no deployed system."""
import json
import sys

def collect(request):
    if request['context'] != {'dataset': 'synthetic'} or request['tool'] != 'probe':
        raise ValueError('Synthetic request identity differs')
    sensor = request['input'].get('sensor')
    if sensor not in ('left', 'right', 'challenge'):
        raise ValueError('Unknown synthetic sensor')
    value = {'valid': True, 'samples': [1, 2, 3]}
    return {'value': value, 'observed_at': '2026-09-30T10:00:00Z',
            'context': request['context'],
            'request': {key: request[key] for key in ('tool', 'tool_version', 'input', 'context')}}

if __name__ == '__main__':
    print(json.dumps(collect(json.load(sys.stdin)), allow_nan=False))
