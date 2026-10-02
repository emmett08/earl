"""Bounded evidence-loss/restoration checks and task-level descriptive outcomes.

This module checks authored interventions against raw facts and an independent
reference. It does not interpret EAL, repair answers or establish model power.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy

from .corpus_reference import CorpusReference
from .task_manifest import cases_for_plan

CONDITIONS = ('complete', 'critical_gap', 'restored_positive', 'restored_negative', 'noncritical_gap')
METADATA = ('evidence_condition', 'availability_cause', 'manipulated_requirement_ids',
            'manipulated_fact_keys', 'restoration_requirement_id', 'pairing_id',
            'comparison_condition', 'noncritical_comparator_session')


def condition_metadata(case, position: int) -> dict:
    return {'task_family': case.family, 'recipient_session': position,
            **{key: deepcopy(case.timeline[position][key]) for key in METADATA
               if key in case.timeline[position]}}


def _facts(snapshot: dict, excluded: set[str] = frozenset()) -> list[dict]:
    """Refresh dates are matched clock changes; all other fact fields are retained."""
    return [{key: deepcopy(value) for key, value in fact.items() if key != 'observed_at_minute'}
            for fact in snapshot['facts'] if fact['key'] not in excluded]


def _eligible(snapshot: dict, requirement: dict) -> list[dict]:
    return [fact for fact in snapshot['facts']
            if fact['key'] == requirement['fact_key'] and fact['status'] == 'active'
            and all(fact['scope'].get(key) == snapshot['scope'].get(key)
                    and key in fact['scope'] and key in snapshot['scope']
                    for key in requirement['scope_keys'])
            and 0 <= snapshot['now_minute'] - fact['observed_at_minute'] <= requirement['max_age_minutes']]


def _gap_cause(snapshot: dict, requirement: dict, cause: str) -> bool:
    records = [fact for fact in snapshot['facts'] if fact['key'] == requirement['fact_key']]
    if cause == 'missing':
        return not records
    if not records:
        return False
    scope_matches = lambda fact: all(fact['scope'].get(key) == snapshot['scope'].get(key)
                                     for key in requirement['scope_keys'])
    fresh = lambda fact: 0 <= snapshot['now_minute'] - fact['observed_at_minute'] <= requirement['max_age_minutes']
    if cause == 'stale':
        return all(fact['status'] == 'active' and scope_matches(fact) and
                   snapshot['now_minute'] - fact['observed_at_minute'] > requirement['max_age_minutes'] for fact in records)
    if cause == 'invalidated':
        return all(fact['status'] == 'invalidated' and scope_matches(fact) and fresh(fact) for fact in records)
    if cause == 'version_mismatch':
        return all(fact['status'] == 'active' and fresh(fact) and not scope_matches(fact) and
                   fact['scope'].get('artifact_version') != snapshot['scope'].get('artifact_version') for fact in records)
    return False


def reference_check(case, positions: tuple[int, ...]) -> dict:
    snapshots = {case.timeline[position].get('evidence_condition'): case.timeline[position]
                 for position in positions}
    failures, references = [], {}
    if set(snapshots) != set(CONDITIONS) or len(positions) != len(CONDITIONS):
        return {'status': 'invalid', 'failures': ['evidence_conditions_missing_or_repeated'], 'references': {}}
    requirements = {item['id']: item for item in case.rule['requirements']}
    complete = snapshots['complete']
    critical = complete.get('restoration_requirement_id')
    if critical not in requirements:
        return {'status': 'invalid', 'failures': ['restoration_requirement_missing'], 'references': {}}
    critical_key = requirements[critical]['fact_key']
    for condition, snapshot in snapshots.items():
        position = snapshot['session']
        references[condition] = CorpusReference().reference(case, position)
        if references[condition]['decision'] != case.expected_decisions[position]:
            failures.append('authored_reference_disagrees')
        if snapshot.get('pairing_id') != case.identifier:
            failures.append('pairing_identity_differs')
        if snapshot.get('restoration_requirement_id') != critical:
            failures.append('restoration_target_differs')
        ids = snapshot.get('manipulated_requirement_ids')
        if not isinstance(ids, list) or not set(ids) <= set(requirements):
            failures.append('manipulated_requirement_metadata_invalid')
        if snapshot['scope'] != complete['scope']:
            failures.append('off_target_snapshot_scope_change')
    expected = {'complete': 'ready', 'critical_gap': 'undetermined',
                'restored_positive': 'ready', 'restored_negative': 'not_ready'}
    if any(references[condition]['decision'] != decision for condition, decision in expected.items()):
        failures.append('critical_loss_or_restoration_reference_not_delivered')
    gap = snapshots['critical_gap']
    if gap.get('manipulated_requirement_ids') != [critical] or _eligible(gap, requirements[critical]):
        failures.append('critical_fact_not_unavailable')
    if not _gap_cause(gap, requirements[critical], gap.get('availability_cause')):
        failures.append('declared_critical_unavailability_cause_not_delivered')
    if _facts(gap, {critical_key}) != _facts(complete, {critical_key}):
        failures.append('off_target_gap_fact_change')
    if _facts(snapshots['restored_positive']) != _facts(complete):
        failures.append('positive_restoration_does_not_recover_complete_facts')
    negative = snapshots['restored_negative']
    if (_facts(negative, {critical_key}) != _facts(complete, {critical_key}) or
            not _eligible(negative, requirements[critical])):
        failures.append('negative_restoration_off_target_or_unavailable')
    control = snapshots['noncritical_gap']
    comparator_position = control.get('noncritical_comparator_session')
    if comparator_position not in positions:
        failures.append('noncritical_comparator_missing')
    else:
        comparator = case.timeline[comparator_position]
        control_ids = control.get('manipulated_requirement_ids', [])
        control_keys = {requirements[item]['fact_key'] for item in control_ids if item in requirements}
        if (not control_ids or critical in control_ids or any(_eligible(control, requirements[item])
                for item in control_ids if item in requirements)):
            failures.append('noncritical_gap_not_delivered')
        if any(not _gap_cause(control, requirements[item], control.get('availability_cause'))
               for item in control_ids if item in requirements):
            failures.append('declared_noncritical_unavailability_cause_not_delivered')
        if _facts(control, control_keys) != _facts(comparator, control_keys):
            failures.append('off_target_noncritical_fact_change')
        if references['noncritical_gap']['decision'] != CorpusReference().reference(case, comparator_position)['decision']:
            failures.append('noncritical_gap_changes_reference_decision')
    return {'status': 'passed' if not failures else 'invalid', 'failures': sorted(set(failures)),
            'references': references, 'critical_requirement_id': critical,
            'fact_clock_normalisation': 'Only observed_at_minute omitted when checking off-target fact changes; eligibility checks retain actual dates.'}


def validate_restoration_plan(plan: dict) -> None:
    from .diagnostic_design import diagnostic_baseline, recipient_positions
    if not isinstance(plan['evidence_restoration'], dict):
        raise ValueError('Evidence-restoration settings must be explicit')
    if (len(plan['models']) != 1 or plan['recipients'] != [plan['donor']] or
            plan['native_tools'] != [False] or plan.get('donor_native_tools') is not False):
        raise ValueError('Restoration follow-up requires one fixed model and no native tools for donor or recipients')
    if set(plan['contrasts']) != {'reasoner'} or set(plan['contrasts']['reasoner']) != set(plan['cases']):
        raise ValueError('Restoration follow-up varies only the matched-fact reasoner')
    baseline = diagnostic_baseline(plan)
    if baseline['response_mode'] not in ('json_prompted', 'json_schema') or baseline['include_notes']:
        raise ValueError('Restoration follow-up declares a canonical JSON decision and excludes donor note exposure')
    positions = recipient_positions(plan)
    if any(position % 2 for position in positions):
        raise ValueError('Restoration follow-up schedules even snapshots, preserving odd continuity positions')
    cases = {case.identifier: case for case in cases_for_plan(plan)}
    for identifier in plan['cases']:
        case = cases[identifier]
        if getattr(case, 'task_kind', None) != 'task_rules':
            raise ValueError('Restoration follow-up requires separately authored rule tasks')
        for position in range(1, 11, 2):
            if any(case.timeline[position][key] != case.timeline[position - 1][key]
                   for key in ('scope', 'facts', 'evidence_revision')):
                raise ValueError('Odd continuity snapshots cannot change facts, scope or revision')
        checked = reference_check(case, positions)
        if checked['status'] != 'passed':
            raise ValueError(f'Invalid restoration task {identifier}: {checked["failures"]}')


def _counts(values: list) -> dict:
    known_true = sum(value is True for value in values)
    known_false = sum(value is False for value in values)
    unknown = len(values) - known_true - known_false
    return {'planned': len(values), 'known_correct': known_true, 'known_incorrect': known_false,
            'unresolved': unknown, 'correct_fraction_bounds':
            [known_true / len(values), (known_true + unknown) / len(values)] if values else [None, None]}


def _joint(values: list) -> bool | None:
    return False if any(value is False for value in values) else True if all(value is True for value in values) else None


def summarise_restoration(plan: dict, rows: list[dict], comparisons: list[dict]) -> dict:
    from .diagnostic_design import recipient_positions
    cases = {case.identifier: case for case in cases_for_plan(plan)}
    delivery = {(item['block_id'], item.get('recipient_session', 1)): item['manipulation']['status'] == 'passed'
                for item in comparisons}
    profiles, condition_groups, family_groups = [], defaultdict(list), defaultdict(list)
    qualified_condition_groups, qualified_family_groups = defaultdict(list), defaultdict(list)
    reference_checks = []
    for row in rows:
        case = cases[row['case']]
        reference = reference_check(case, recipient_positions(plan))
        reference_checks.append({'case': case.identifier, 'task_family': case.family, **reference})
        snapshots = row.get('donor_snapshots', {})
        states = [{key: value for key, value in snapshot.items() if key != 'collector_state_sha256'}
                  for snapshot in snapshots.values()]
        common_initial_state = len(states) == len(recipient_positions(plan)) and all(state == states[0] for state in states)
        for reasoner in ('facts', 'eal', 'conventional'):
            outcomes = []
            for condition in CONDITIONS:
                variant = next((variant for variant in row['variants']
                                if variant['level'] == reasoner and
                                variant.get('evidence_condition', {}).get('evidence_condition') == condition), {})
                result, metadata = variant.get('result') or {}, variant.get('evidence_condition', {})
                valid = reference['status'] == 'passed' and common_initial_state and delivery.get(
                    (row['block_id'], variant.get('recipient_session', 1)), False)
                score = result.get('score', {})
                supplied = (result.get('task_context') or {}).get('decision')
                outcome = {'condition': condition, 'recipient_session': variant.get('recipient_session'),
                    'session_id': variant.get('session_id'), 'reference': reference['references'].get(condition),
                    'manipulation_passed': valid, 'communicated_decision': (result.get('answer') or {}).get('decision'),
                    'canonical_decision': result.get('canonical_decision'),
                    'communicated_decision_match': score.get('decision_match'),
                    'canonical_decision_match': score.get('canonical_decision_match'),
                    'explanation_consistent': score.get('explanation_consistent'),
                    'substantive_match': score.get('substantive_match'),
                    'manipulation_qualified_match': score.get('substantive_match') if valid else None,
                    'session_status': result.get('status', 'not_observed'), 'error': result.get('error'),
                    'supplied_conclusion': supplied,
                    'supplied_conclusion_matches_reference': (supplied == reference['references'].get(condition, {}).get('decision')
                        if supplied is not None else None),
                    'host_assessment_attempts': sum(event.get('kind') == 'eal_assess' for event in result.get('events', [])),
                    'host_assessments_without_result': sum(event.get('kind') == 'eal_assess' and not event.get('assessment')
                        for event in result.get('events', [])),
                    'format_valid': result.get('format_valid'), 'annotation': result.get('annotation'),
                    'availability_cause': metadata.get('availability_cause')}
                outcomes.append(outcome)
                condition_groups[(case.family, reasoner, condition)].append(outcome['substantive_match'])
                qualified_condition_groups[(case.family, reasoner, condition)].append(outcome['manipulation_qualified_match'])
            profile = {'block_id': row['block_id'], 'case': case.identifier, 'task_family': case.family,
                'reasoner': reasoner, 'common_initial_state': common_initial_state, 'outcomes': outcomes,
                'all_conditions_substantive_match': _joint([outcome['substantive_match'] for outcome in outcomes]),
                'all_conditions_manipulation_qualified_match': _joint([outcome['manipulation_qualified_match'] for outcome in outcomes])}
            profiles.append(profile)
            family_groups[(case.family, reasoner)].append(profile['all_conditions_substantive_match'])
            qualified_family_groups[(case.family, reasoner)].append(profile['all_conditions_manipulation_qualified_match'])
    return {'schema': 'EAL/evidence-restoration-summary/1', 'reference_checks': reference_checks,
        'profiles': profiles,
        'condition_outcomes': [{'task_family': family, 'reasoner': reasoner, 'condition': condition, **_counts(values)}
                               for (family, reasoner, condition), values in sorted(condition_groups.items())],
        'joint_task_outcomes': [{'task_family': family, 'reasoner': reasoner, **_counts(values)}
                               for (family, reasoner), values in sorted(family_groups.items())],
        'manipulation_qualified_condition_outcomes': [{'task_family': family, 'reasoner': reasoner, 'condition': condition, **_counts(values)}
                               for (family, reasoner, condition), values in sorted(qualified_condition_groups.items())],
        'manipulation_qualified_joint_task_outcomes': [{'task_family': family, 'reasoner': reasoner, **_counts(values)}
                               for (family, reasoner), values in sorted(qualified_family_groups.items())],
        'primary_endpoint': 'Communicated whole-task verdict matches the independent reference and independently coded internal verdict/canonical-field consistency is established.',
        'factual_explanation_accuracy': 'Unassessed: masked consistency coding receives answer text, not task evidence.',
        'canonical_endpoint': 'Parsed decision field matches reference; this does not establish communicated substantive success.',
        'interpretation': 'Descriptive bounded follow-up on selected authored tasks with shared donor clones. '
            'Five condition observations and three reasoners are repeated views of each task, not independent cases. '
            'Failed manipulations, unsuccessful acquisitions and unresolved communication remain in planned denominators. '
            'Observed failures remain failures in descriptive outcomes; failed manipulations qualify attribution separately. '
            'No principal-study power, representative task population or model-class claim is established.'}
