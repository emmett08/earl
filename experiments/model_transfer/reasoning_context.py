"""Present matched facts with a withheld, EAL-derived or conventional conclusion."""
from __future__ import annotations

import json
import time

from .conventional_reasoner import evaluate


def prepare_reasoning_context(project, question: str, *, reasoner: str, reuse: str) -> list[dict]:
    if reasoner not in ('facts', 'eal', 'conventional'):
        raise ValueError('Unknown diagnostic reasoner')
    start = time.monotonic()
    # All variants receive exactly the same current raw snapshot and rules.
    # Neither expected_decisions nor the scoring reference enters this path.
    measurement = project.probe(host_snapshot=True)
    inputs = {'specification': project.case.specification(), 'measurement': measurement,
              'now': project.case.time(project.session)}
    packet = {'schema': 'EAL/reasoning-diagnostic-context/1', 'inputs': inputs}
    if reasoner == 'eal':
        from .conditions import EALContext
        EALContext().prepare(project, question, style='compact', reuse=reuse)
        checked = next(event['task_context'] for event in reversed(project.events) if 'task_context' in event)
        packet['decision'] = checked['decision']
    elif reasoner == 'conventional':
        packet['decision'] = evaluate(project.case, measurement, inputs['now'])
    project.events.append({'session': project.session, 'kind': 'reasoning_diagnostic',
        'reasoner': reasoner, 'task_context': packet, 'elapsed_seconds': time.monotonic() - start})
    return [{'role': 'system', 'content': 'Current task facts and any supplied computed conclusion:\n' +
             json.dumps(packet, sort_keys=True, ensure_ascii=False, separators=(',', ':'))}]
