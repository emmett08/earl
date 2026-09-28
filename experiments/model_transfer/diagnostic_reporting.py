"""Retain diagnostic denominators and component contrasts without pooling."""
from __future__ import annotations

import itertools

from .diagnostic_design import DiagnosticSchedule, diagnostic_levels
from .diagnostic_measurement import ManipulationCheck
from .resources import ResourceSummary


class DiagnosticReportBuilder:
    def __init__(self, plan: dict):
        self.plan = plan

    def build(self, rows: list[dict], calls: list[dict], stop: str | None = None) -> dict:
        expected = DiagnosticSchedule(self.plan).allocations()
        if [r['block_id'] for r in rows] != [r['block_id'] for r in expected]:
            raise ValueError('Diagnostic rows do not preserve the planned denominator')
        for actual, planned in zip(rows, expected):
            if ([v['session_id'] for v in actual['variants']] != [v['session_id'] for v in planned['variants']] or
                    any(actual[key] != planned[key] for key in
                        ('case', 'donor', 'receiver', 'native_tools', 'repeat', 'donor_session_id'))):
                raise ValueError('Diagnostic rows alter a planned allocation or denominator')
            for received, assigned in zip(actual['variants'], planned['variants']):
                if any(received[key] != assigned[key] for key in ('factor', 'level', 'level_index', 'options')):
                    raise ValueError('Diagnostic rows alter a planned intervention')
                result = received.get('result')
                if result and (result.get('session_id') != assigned['session_id'] or result.get('session') != 1):
                    raise ValueError('Recipient result does not match its assigned session')
            donor = actual.get('donor_result')
            if donor and (donor.get('session_id') != planned['donor_session_id'] or donor.get('session') != 0):
                raise ValueError('Donor result does not match its assigned session')
        comparisons, sessions, ids = [], [], set()
        for row in rows:
            ids.add(row['donor_session_id'])
            if row.get('donor_result'):
                sessions.append(row['donor_result'])
            for variant in row['variants']:
                ids.add(variant['session_id'])
                if variant.get('result'):
                    sessions.append(variant['result'])
            for factor in sorted({v['factor'] for v in row['variants']}):
                variants = sorted((v for v in row['variants'] if v['factor'] == factor),
                                  key=lambda item: item['level_index'])
                check = ManipulationCheck().check(factor, variants, row.get('donor_snapshot', {}),
                                                 levels=diagnostic_levels(self.plan, factor), calls=calls)
                for left, right in itertools.combinations(variants, 2):
                    resources = []
                    outcomes = []
                    for variant in (left, right):
                        result = variant.get('result')
                        resources.append(ResourceSummary().summarise(
                            [result] if result else [], calls, session_ids={variant['session_id']}))
                        score = (result or {}).get('score', {})
                        outcomes.append(score.get('decision_match'))
                    difference = (int(outcomes[1]) - int(outcomes[0])
                                  if check['status'] == 'passed' and all(type(v) is bool for v in outcomes) else None)
                    comparisons.append({'block_id': row['block_id'], 'case': row['case'],
                        'receiver': row['receiver'], 'native_tools': row['native_tools'], 'factor': factor,
                        'levels': [left['level'], right['level']], 'manipulation': check,
                        'decision_matches': outcomes, 'decision_difference_right_minus_left': difference,
                        'format_validity': [(variant.get('result') or {}).get('format_valid')
                                            for variant in (left, right)],
                        'resources': resources,
                        'resource_differences_right_minus_left': self._resource_differences(resources)})
        resources = ResourceSummary().summarise(sessions, calls, session_ids=ids)
        execution = 'complete' if all(row['status'] == 'complete' for row in rows) else 'partial'
        invalid = sum(comparison['manipulation']['status'] != 'passed' for comparison in comparisons)
        pending = sum(session.get('score', {}).get('assessment_status') == 'pending_annotation' for session in sessions)
        status = ('partial' if execution == 'partial' else 'invalid_manipulation' if invalid else
                  'pending_annotation' if pending else 'complete')
        return {'schema': 'EAL/model-transfer-diagnostic-report/1',
                'status': status, 'execution_status': execution,
                'stop_reason': stop, 'planned_blocks': len(rows), 'planned_sessions': len(ids),
                'invalid_comparisons': invalid, 'pending_annotation_sessions': pending,
                'api_attempts': resources['api_attempts'], 'estimated_cost_usd': resources['known_cost_usd'],
                'unknown_cost_attempts': resources['unknown_cost_attempts'],
                'charged_or_reserved_usd': sum(call['charged_or_reserved_usd'] for call in calls),
                'resources': resources, 'comparisons': comparisons,
                'interpretation': 'Component contrasts conditional on the retained donor state and selected cases. '
                    'Invalid manipulations do not identify a component effect. Missing coding is unknown, not failure. '
                    'Comparisons share donors and are not independent samples; no population or model-class inference.'}

    @staticmethod
    def _resource_differences(resources: list[dict]) -> dict:
        left, right = resources
        attempted = all(item['attempted_sessions'] for item in resources)
        known_tokens = attempted and all(item['token_usage_complete'] for item in resources)
        timed = all(item['timed_sessions'] for item in resources)
        return {**{key: right[key] - left[key] if known_tokens and all(item[flag] for item in resources) else None
                   for key, flag in (('input_tokens', 'token_usage_complete'), ('output_tokens', 'token_usage_complete'),
                                     ('reasoning_tokens', 'reasoning_usage_complete'), ('cached_input_tokens', 'cached_usage_complete'))},
                'estimated_cost_usd': (right['known_cost_usd'] - left['known_cost_usd']
                    if attempted and not any(item['unknown_cost_attempts'] for item in resources) else None),
                'elapsed_seconds': right['elapsed_seconds'] - left['elapsed_seconds'] if timed else None,
                'total_collector_calls': (right['total_collector_calls'] - left['total_collector_calls']
                    if all(item['collection_counts_complete'] for item in resources) else None)}
