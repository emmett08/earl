"""Evaluate supplied task facts without EAL or the independent scoring oracle."""
from __future__ import annotations

from datetime import datetime


def evaluate(case, measurement: dict, now: str) -> str:
    stamp = lambda value: datetime.fromisoformat(value.replace('Z', '+00:00'))
    current = stamp(now)
    limit = 60 if getattr(case, 'task_kind', 'threshold') == 'task_rules' else 300
    if not 0 <= (current - stamp(measurement['observed_at'])).total_seconds() <= limit:
        return 'undetermined'
    data = measurement['value']
    if getattr(case, 'task_kind', 'threshold') != 'task_rules':
        if case.assumption_until and not stamp(case.assumption_from) <= current < stamp(case.assumption_until):
            return 'undetermined'
        if (data.get('service') != 'orders' or data.get('metric') != case.metric or
                data.get('unit') != case.unit or type(data.get('reading')) not in (int, float)):
            return 'undetermined'
        if data['reading'] < 0:
            return 'undetermined'
        holds = data['reading'] <= case.threshold if case.direction == 'at_most' else data['reading'] >= case.threshold
        return 'ready' if holds else 'not_ready'
    equal = lambda x, y: (type(x) is type(y) or type(x) in (int, float) and type(y) in (int, float)) and x == y
    if any(not equal(data['scope'].get(key), value) for key, value in case.target_identity().items()):
        return 'undetermined'
    values = {}
    for requirement in case.rule['requirements']:
        best, tied = None, False
        for fact in data['facts']:
            if fact['key'] != requirement['fact_key'] or fact['status'] != 'active':
                continue
            if any(key not in fact['scope'] or key not in data['scope'] or
                   not equal(fact['scope'][key], data['scope'][key]) for key in requirement['scope_keys']):
                continue
            if not 0 <= data['now_minute'] - fact['observed_at_minute'] <= requirement['max_age_minutes']:
                continue
            if best is None or fact['observed_at_minute'] > best['observed_at_minute']:
                best, tied = fact, False
            elif fact['observed_at_minute'] == best['observed_at_minute']:
                tied = True
        if tied:
            raise ValueError('Conventional evaluator requires a unique newest fact')
        if best is None:
            values[requirement['id']] = None
            continue
        x, y = best['value'], requirement['expected_value']
        op = requirement['operator']
        if op == 'eq':
            numeric = type(x) in (int, float) and type(y) in (int, float)
            answer = (type(x) is type(y) or numeric) and x == y
        else:
            if type(x) not in (int, float) or type(y) not in (int, float):
                raise ValueError('Ordered comparison requires numbers')
            answer = x <= y if op == 'lte' else x >= y
        values[requirement['id']] = answer
    groups = [route['requirement_ids'] for route in case.rule.get('alternatives', [])] or [list(values)]
    unresolved = False
    for group in groups:
        selected = [values[key] for key in group]
        if all(value is True for value in selected):
            return 'ready'
        if not any(value is False for value in selected):
            unresolved = True
    return 'undetermined' if unresolved else 'not_ready'
