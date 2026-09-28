"""Retain diagnostic denominators and component contrasts without pooling."""
from __future__ import annotations

import itertools

from .diagnostic_design import DiagnosticSchedule, diagnostic_levels
from .diagnostic_measurement import ManipulationCheck
from .diagnostic_resources import DiagnosticResources


class DiagnosticReportBuilder:
    def __init__(self, plan: dict):
        self.plan = plan
        self.resources = DiagnosticResources()

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
        comparisons, sessions, ids, blocks = [], [], set(), []
        donor_sessions, donor_ids, donor_preparation = [], set(), []
        recipient_sessions, recipient_ids, recipient_preparation = [], set(), []
        for row in rows:
            ids.add(row['donor_session_id'])
            donor_ids.add(row['donor_session_id'])
            shared_preparation = [row.get('preparation', {}).get(stage, {})
                                  for stage in ('donor_setup', 'shared_state')]
            donor_preparation.extend(shared_preparation)
            donor_results = [row['donor_result']] if row.get('donor_result') else []
            sessions.extend(donor_results)
            donor_sessions.extend(donor_results)
            block = {'block_id': row['block_id'],
                     'shared_donor': {'session_id': row['donor_session_id'],
                                      'preparation': row.get('preparation', {}),
                                      'resources': self.resources.summarise(donor_results, calls,
                                          {row['donor_session_id']}, shared_preparation)},
                     'recipients': []}
            blocks.append(block)
            for variant in row['variants']:
                ids.add(variant['session_id'])
                recipient_ids.add(variant['session_id'])
                preparation = variant.get('preparation', {})
                recipient_preparation.append(preparation)
                results = [variant['result']] if variant.get('result') else []
                sessions.extend(results)
                recipient_sessions.extend(results)
                block['recipients'].append({'session_id': variant['session_id'],
                    'factor': variant['factor'], 'level': variant['level'], 'preparation': preparation,
                    'resources': self.resources.summarise(results, calls, {variant['session_id']}, [preparation])})
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
                        resources.append(self.resources.summarise(
                            [result] if result else [], calls, {variant['session_id']},
                            [variant.get('preparation', {})]))
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
                        'resource_differences_right_minus_left': self.resources.differences(resources)})
        resources = self.resources.summarise(sessions, calls, ids, donor_preparation + recipient_preparation,
                                    include_unassigned=True)
        groups = {'shared_donors': self.resources.summarise(donor_sessions, calls, donor_ids, donor_preparation),
                  'recipients': self.resources.summarise(recipient_sessions, calls, recipient_ids, recipient_preparation)}
        accounting_complete = all(resources[field] for field in
            ('api_accounting_complete', 'cost_accounting_complete', 'token_usage_complete',
             'preparation_timing_complete'))
        execution = 'complete' if all(row['status'] == 'complete' for row in rows) else 'partial'
        invalid = sum(comparison['manipulation']['status'] != 'passed' for comparison in comparisons)
        pending = sum(session.get('score', {}).get('assessment_status') == 'pending_annotation' for session in sessions)
        status = ('partial' if execution == 'partial' else 'invalid_manipulation' if invalid else
                  'incomplete_accounting' if not accounting_complete else
                  'pending_annotation' if pending else 'complete')
        return {'schema': 'EAL/model-transfer-diagnostic-report/1',
                'status': status, 'execution_status': execution,
                'stop_reason': stop, 'planned_blocks': len(rows), 'planned_sessions': len(ids),
                'invalid_comparisons': invalid, 'pending_annotation_sessions': pending,
                'api_attempts': resources['api_attempts'],
                'estimated_cost_usd': resources['known_cost_usd'] if resources['cost_accounting_complete'] else None,
                'known_cost_usd': resources['known_cost_usd'],
                'unknown_cost_attempts': resources['unknown_cost_attempts'],
                'charged_or_reserved_usd': sum(call['charged_or_reserved_usd'] for call in calls),
                'resource_accounting_complete': accounting_complete,
                'resources': resources, 'resource_groups': groups, 'blocks': blocks,
                'comparisons': comparisons,
                'timing_scope': 'Session execution plus donor construction, shared-state preparation and clone construction. '
                    'Preparation timing excludes snapshot validation and diagnostic serialisation/logging; session timing covers the session-runner interval. '
                    'Report construction and annotation are outside these intervals. '
                    'Incomplete timing fields are known subtotals, not measured total workflow durations.',
                'interpretation': 'Component contrasts conditional on the retained donor state and selected cases. '
                    'Invalid manipulations do not identify a component effect. Missing coding is unknown, not failure. '
                    'Each donor and recipient is counted once in resource_groups and the overall resources. '
                    'Pairwise entries reuse recipients and must not be summed. Missing accounting cannot establish savings. '
                    'Comparisons share donors and are not independent samples; no population or model-class inference.'}
