"""Retain diagnostic denominators and component contrasts without pooling."""
from __future__ import annotations

import itertools

from .diagnostic_design import DiagnosticSchedule, diagnostic_levels, diagnostic_baseline
from .diagnostic_measurement import ManipulationCheck
from .diagnostic_resources import DiagnosticResources
from .diagnostic_inference import summarise


class DiagnosticReportBuilder:
    def __init__(self, plan: dict):
        self.plan = plan
        self.resources = DiagnosticResources()

    def build(self, rows: list[dict], calls: list[dict], stop: str | None = None) -> dict:
        expected = DiagnosticSchedule(self.plan).allocations()
        restoration_cases = {}
        if self.plan.get('evidence_restoration'):
            from .task_manifest import cases_for_plan
            restoration_cases = {case.identifier: case for case in cases_for_plan(self.plan)}
        if [r['block_id'] for r in rows] != [r['block_id'] for r in expected]:
            raise ValueError('Diagnostic rows do not preserve the planned denominator')
        for actual, planned in zip(rows, expected):
            if ([v['session_id'] for v in actual['variants']] != [v['session_id'] for v in planned['variants']] or
                    any(actual[key] != planned[key] for key in
                        ('case', 'donor', 'receiver', 'native_tools', 'repeat', 'donor_session_id')) or
                    actual.get('task_family') != planned.get('task_family')):
                raise ValueError('Diagnostic rows alter a planned allocation or denominator')
            for received, assigned in zip(actual['variants'], planned['variants']):
                if any(received[key] != assigned[key] for key in ('factor', 'level', 'level_index', 'options')):
                    raise ValueError('Diagnostic rows alter a planned intervention')
                if any(received.get(key) != assigned.get(key) for key in ('recipient_session', 'evidence_condition')):
                    raise ValueError('Diagnostic rows alter a planned evidence condition')
                result = received.get('result')
                if result and (result.get('session_id') != assigned['session_id'] or
                               result.get('session') != assigned.get('recipient_session', 1)):
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
                    **({'evidence_condition': variant['evidence_condition']} if 'evidence_condition' in variant else {}),
                    'resources': self.resources.summarise(results, calls, {variant['session_id']}, [preparation])})
            for factor, position in sorted({(v['factor'], v.get('recipient_session', 1)) for v in row['variants']}):
                variants = sorted((v for v in row['variants'] if v['factor'] == factor
                                   and v.get('recipient_session', 1) == position),
                                  key=lambda item: item['level_index'])
                snapshot = row.get('donor_snapshots', {}).get(str(position), row.get('donor_snapshot', {}))
                check = ManipulationCheck().check(factor, variants, snapshot,
                    levels=diagnostic_levels(self.plan, factor), calls=calls, baseline=diagnostic_baseline(self.plan))
                if self.plan.get('evidence_restoration'):
                    case = restoration_cases[row['case']]
                    states = [{key: value for key, value in state.items() if key != 'collector_state_sha256'}
                              for state in row.get('donor_snapshots', {}).values()]
                    if len(states) != len(self.plan['recipient_positions']) or any(state != states[0] for state in states):
                        check['failures'] = sorted(set([*check['failures'], 'common_donor_state_not_preserved']))
                        check['status'] = 'invalid'
                    expected_inputs = {'specification': case.specification(), 'measurement': case.measurement(position),
                                       'now': case.time(position)}
                    if any(((variant.get('result') or {}).get('task_context') or {}).get('inputs') != expected_inputs
                           for variant in variants):
                        check['failures'] = sorted(set([*check['failures'], 'authored_current_facts_not_delivered']))
                        check['status'] = 'invalid'
                for left, right in itertools.combinations(variants, 2):
                    resources = []
                    outcomes = []
                    for variant in (left, right):
                        result = variant.get('result')
                        resources.append(self.resources.summarise(
                            [result] if result else [], calls, {variant['session_id']},
                            [variant.get('preparation', {})]))
                        score = (result or {}).get('score', {})
                        endpoint = 'substantive_match' if self.plan.get('evidence_restoration') else 'decision_match'
                        outcomes.append(score.get(endpoint))
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
                    if 'recipient_positions' in self.plan:
                        comparisons[-1]['recipient_session'] = position
                    if self.plan.get('evidence_restoration'):
                        comparisons[-1].update(evidence_condition=left['evidence_condition'],
                            endpoint='whole_task_verdict_and_explanation_consistency',
                            communicated_decision_matches=[(variant.get('result') or {}).get('score', {}).get('decision_match')
                                                          for variant in (left, right)],
                            canonical_decision_matches=[(variant.get('result') or {}).get('score', {}).get('canonical_decision_match')
                                                       for variant in (left, right)])
        resources = self.resources.summarise(sessions, calls, ids, donor_preparation + recipient_preparation,
                                    include_unassigned=True)
        groups = {'shared_donors': self.resources.summarise(donor_sessions, calls, donor_ids, donor_preparation),
                  'recipients': self.resources.summarise(recipient_sessions, calls, recipient_ids, recipient_preparation)}
        accounting_complete = all(resources[field] for field in
            ('session_coverage_complete', 'api_accounting_complete', 'cost_accounting_complete', 'token_usage_complete',
             'preparation_timing_complete'))
        execution = 'complete' if all(row['status'] == 'complete' for row in rows) else 'partial'
        invalid = sum(comparison['manipulation']['status'] != 'passed' for comparison in comparisons)
        pending = sum(session.get('score', {}).get('assessment_status') == 'pending_annotation' or
                      bool(self.plan.get('evidence_restoration')) and session.get('score', {}).get('explanation_consistent') is None
                      for session in sessions)
        status = ('partial' if execution == 'partial' else 'invalid_manipulation' if invalid else
                  'incomplete_accounting' if not accounting_complete else
                  'pending_annotation' if pending else 'complete')
        report = {'schema': 'EAL/model-transfer-diagnostic-report/2',
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
                'comparisons': comparisons, 'contrast_intervals': [] if self.plan.get('evidence_restoration') else summarise(comparisons),
                'timing_scope': 'Session execution plus donor construction, shared-state preparation and clone construction. '
                    'Preparation timing excludes snapshot validation and diagnostic serialisation/logging; session timing covers the session-runner interval. '
                    'Report construction and annotation are outside these intervals. '
                    'Incomplete timing fields are known subtotals, not measured total workflow durations.',
                'interpretation': 'Component contrasts conditional on the retained donor state and selected cases. '
                    'Invalid manipulations do not identify a component effect. Missing coding is unknown, not failure. '
                    'Each donor and recipient is counted once in resource_groups and the overall resources. '
                    'Pairwise entries reuse recipients and must not be summed. Missing accounting cannot establish savings. '
                    'Comparisons share donors and are not independent samples; no population or model-class inference.'}
        if self.plan.get('evidence_restoration'):
            from .restoration import summarise_restoration
            report['evidence_restoration'] = summarise_restoration(self.plan, rows, comparisons)
            # This bounded follow-up reports selected-task profiles and unresolved
            # bounds rather than applying donor intervals repeatedly across conditions.
            report['interpretation'] = report['evidence_restoration']['interpretation']
        return report
