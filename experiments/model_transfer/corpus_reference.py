"""Independent task oracle: no EAL status, installed method or authored answer lookup."""
from __future__ import annotations


class CorpusReference:
    def reference(self, case, session: int) -> dict:
        snapshot = case.timeline[session]
        identity = case.task_specification
        if any(snapshot['scope'].get(key) != identity['scope'][key] for key in identity['identity_scope_keys']):
            return {'decision': 'undetermined', 'basis': 'evidence_unavailable', 'reading': None,
                    'observed_at': case.time(session)}
        true, false = set(), set()
        for requirement in case.rule['requirements']:
            records = []
            for fact in snapshot['facts']:
                if fact['key'] != requirement['fact_key'] or fact['status'] != 'active':
                    continue
                if any(key not in fact['scope'] or key not in snapshot['scope'] or
                       fact['scope'][key] != snapshot['scope'][key] for key in requirement['scope_keys']):
                    continue
                elapsed = snapshot['now_minute'] - fact['observed_at_minute']
                if elapsed < 0 or elapsed > requirement['max_age_minutes']:
                    continue
                records.append(fact)
            if not records:
                continue
            records.sort(key=lambda item: item['observed_at_minute'], reverse=True)
            if len(records) > 1 and records[0]['observed_at_minute'] == records[1]['observed_at_minute']:
                raise ValueError('Reference task contains ambiguous simultaneous facts')
            value, target = records[0]['value'], requirement['expected_value']
            relation = requirement['operator']
            same_scalar_kind = (type(value) is type(target) or
                                type(value) in (int, float) and type(target) in (int, float))
            holds = ((same_scalar_kind and value == target) if relation == 'eq' else
                     value <= target if relation == 'lte' else value >= target)
            (true if holds else false).add(requirement['id'])
        routes = [set(item['requirement_ids']) for item in case.rule.get('alternatives', [])]
        if not routes:
            routes = [{item['id'] for item in case.rule['requirements']}]
        if any(route <= true for route in routes):
            decision, basis = 'ready', 'criterion_met'
        elif all(route & false for route in routes):
            decision, basis = 'not_ready', 'criterion_failed'
        else:
            decision, basis = 'undetermined', 'evidence_unavailable'
        return {'decision': decision, 'basis': basis, 'reading': None, 'observed_at': case.time(session)}
