"""Scientific failure modes in the controlled evidence-restoration follow-up."""
from copy import deepcopy
from pathlib import Path

import pytest

from experiments.model_transfer.annotations import AnnotationExchange
from experiments.model_transfer.diagnostic_design import DiagnosticSchedule, load_diagnostic_plan
from experiments.model_transfer.diagnostic_reporting import DiagnosticReportBuilder
from experiments.model_transfer.diagnostics import DiagnosticPilot
from experiments.model_transfer.rehearse import ScriptedTransport
from experiments.model_transfer.restoration import reference_check
from experiments.model_transfer.scoring import ReferenceScorer
from experiments.model_transfer.task_manifest import cases_for_plan
from experiments.transfer_study.workspace import read_json, write_json

BASE = Path('experiments/model_transfer')


def plan_at(path: Path, *, all_cases=False):
    plan = read_json(BASE / 'diagnostic-plan.json')
    manifest = read_json(BASE / 'followup/task-manifest.json')
    selected = [case['identifier'] for case in manifest['cases']]
    if not all_cases:
        selected = [selected[0], selected[-1]]
    plan.update(task_manifest=manifest, cases=selected, models={'plain': plan['models']['plain']},
        recipients=['plain'], donor='plain', donor_native_tools=False, native_tools=[False],
        recipient_positions=[2, 4, 6, 8, 10], diagnostic_baseline={'response_mode': 'json_prompted'},
        evidence_restoration={'purpose': 'bounded diagnostic'}, contrasts={'reasoner': selected},
        repetitions=1, workers=1, max_output_tokens=1024, max_calls_per_session=2)
    write_json(path, plan)
    return load_diagnostic_plan(path)


@pytest.fixture
def collected(tmp_path):
    plan = plan_at(tmp_path / 'source-plan.json')
    root = tmp_path / 'run'
    report = DiagnosticPilot(plan, root, ScriptedTransport()).run()
    from dataclasses import asdict
    write_json(root / 'cases.json', [asdict(case) for case in cases_for_plan(plan) if case.identifier in plan['cases']])
    return plan, root, report, read_json(root / 'rows.json'), read_json(root / 'calls.json')


def test_authored_controls_restore_opposite_decisions_and_preserve_odd_continuity(tmp_path):
    plan = plan_at(tmp_path / 'plan.json', all_cases=True)
    cases = [case for case in cases_for_plan(plan) if case.identifier in plan['cases']]
    assert len(cases) == 8
    for case in cases:
        checked = reference_check(case, (2, 4, 6, 8, 10))
        assert checked['status'] == 'passed'
        decisions = {condition: value['decision'] for condition, value in checked['references'].items()}
        assert decisions['critical_gap'] == 'undetermined'
        assert decisions['restored_positive'] == 'ready'
        assert decisions['restored_negative'] == 'not_ready'
        assert decisions['noncritical_gap'] == ('not_ready' if case.rule['type'] == 'all_of' else 'ready')
    schedule = DiagnosticSchedule(plan).allocations()
    assert len(schedule) == 8 and sum(1 + len(block['variants']) for block in schedule) == 128
    assert DiagnosticSchedule(plan).allocations() == schedule
    changed = deepcopy(plan)
    changed['seed'] += 1
    assert DiagnosticSchedule(changed).allocations() != schedule


def test_unobserved_coding_and_canonical_json_are_separate_endpoints(collected):
    plan, root, report, rows, calls = collected
    assert report['status'] == 'pending_annotation'
    assert report['planned_blocks'] == 2 and report['planned_sessions'] == 32
    assert report['api_attempts'] == 32 and report['resource_accounting_complete']
    assert report['resources']['native_tool_calls'] == 0
    assert report['resources']['host_raw_snapshot_reads'] == 30
    assert all('tools' not in call['request'] for call in calls)
    assert all(item['manipulation']['status'] == 'passed' for item in report['comparisons'])
    assert report['contrast_intervals'] == []
    for profile in report['evidence_restoration']['profiles']:
        assert profile['common_initial_state'] is True
        assert profile['all_conditions_substantive_match'] is None
        negative = next(item for item in profile['outcomes'] if item['condition'] == 'restored_negative')
        assert negative['format_valid'] is True and negative['canonical_decision_match'] is False
        assert negative['communicated_decision_match'] is None and negative['substantive_match'] is None
    assert all(group['planned'] == 1 and group['unresolved'] == 1
               for group in report['evidence_restoration']['joint_task_outcomes'])


def test_masked_consistency_coding_preserves_canonical_and_raw_rows(collected, tmp_path):
    plan, root, report, rows, calls = collected
    bundle = tmp_path / 'bundle'
    AnnotationExchange().export(root, bundle, include_all=True)
    labels = read_json(bundle / 'items.json')
    assert all('explanation_consistency' in item for item in labels['items'])
    labels['annotator'] = 'independent-scripted-fixture-coder'
    for item in labels['items']:
        item.update(decision='ready', quote=item['text'], note='The fixed answer says ready.',
            explanation_consistency='consistent', consistency_quote=item['text'],
            consistency_note='The fixed answer has no conflicting current verdict.')
    labels_path = tmp_path / 'labels.json'
    write_json(labels_path, labels)
    derived = tmp_path / 'annotated.json'
    AnnotationExchange().import_labels(root, bundle, labels_path, derived)
    rebuilt = DiagnosticReportBuilder(plan).build(read_json(derived), calls)
    assert read_json(root / 'rows.json') == rows
    assert rebuilt['status'] == 'complete'
    assert rebuilt['resources'] == report['resources']
    outcomes = rebuilt['evidence_restoration']['profiles'][0]['outcomes']
    assert [item['substantive_match'] for item in outcomes[:4]] == [True, False, True, False]
    assert all(profile['all_conditions_substantive_match'] is False
               for profile in rebuilt['evidence_restoration']['profiles'])


def test_correct_enum_with_contradictory_explanation_cannot_establish_substantive_success(tmp_path):
    plan = plan_at(tmp_path / 'plan.json')
    case = next(case for case in cases_for_plan(plan) if case.identifier == plan['cases'][0])
    result = {'whole_answer_consistency_required': True, 'canonical_decision': 'ready',
        'answer': {'decision': 'ready'}, 'format_valid': True,
        'annotation': {'status': 'human', 'explanation_consistency': 'contradictory'}}
    score = ReferenceScorer().score(case, 2, result)
    assert score['canonical_decision_match'] is True and score['decision_match'] is True
    assert score['explanation_consistent'] is False and score['substantive_match'] is False
    result['annotation'].update(status='ambiguous', explanation_consistency='ambiguous')
    score = ReferenceScorer().score(case, 2, result)
    assert score['canonical_decision_match'] is True
    assert score['decision_match'] is None and score['substantive_match'] is None


def test_equal_off_target_facts_and_changed_delivery_invalidate_comparison(collected):
    plan, root, report, rows, calls = collected
    altered = deepcopy(rows)
    position = 4
    for variant in altered[0]['variants']:
        if variant['recipient_session'] == position:
            variant['result']['task_context']['inputs']['measurement']['value']['facts'] = []
    rebuilt = DiagnosticReportBuilder(plan).build(altered, calls)
    affected = [item for item in rebuilt['comparisons'] if item['block_id'] == altered[0]['block_id']
                and item['recipient_session'] == position]
    assert all('authored_current_facts_not_delivered' in item['manipulation']['failures'] for item in affected)
    assert all(item['decision_difference_right_minus_left'] is None for item in affected)
    altered_calls = deepcopy(calls)
    recipient = next(call for call in altered_calls if '.donor.' not in call['session_id'])
    recipient['request']['input'][0]['content'] = 'An altered prompt'
    rebuilt = DiagnosticReportBuilder(plan).build(rows, altered_calls)
    assert any('recorded_prompt_not_delivered' in item['manipulation']['failures'] for item in rebuilt['comparisons'])


def test_provider_failure_retains_all_conditions_and_reservation(tmp_path):
    from experiments.model_transfer.execution import ExecutionStopped
    class Unavailable:
        def send(self, payload, timeout):
            raise ExecutionStopped('Synthetic provider unavailable')
    plan = plan_at(tmp_path / 'plan.json')
    report = DiagnosticPilot(plan, tmp_path / 'failed', Unavailable()).run()
    assert report['status'] == 'partial' and report['planned_sessions'] == 32
    assert report['api_attempts'] == 1 and report['unknown_cost_attempts'] == 1
    assert report['charged_or_reserved_usd'] > 0
    assert len(report['evidence_restoration']['profiles']) == 6
    assert all(group['unresolved'] == group['planned']
               for group in report['evidence_restoration']['condition_outcomes'])


def test_restoration_plan_rejects_cause_metadata_that_matches_wrong_operation(tmp_path):
    plan = plan_at(tmp_path / 'plan.json')
    changed = deepcopy(plan)
    changed['task_manifest']['cases'][0]['timeline'][4]['availability_cause'] = 'stale'
    path = tmp_path / 'invalid.json'
    write_json(path, changed)
    with pytest.raises(ValueError, match='cause_not_delivered'):
        load_diagnostic_plan(path)


@pytest.mark.parametrize('override, message', [({'include_notes': 1}, 'Boolean'),
    ({'response_mode': 'json_schema'}, 'structured-output support')])
def test_invalid_baseline_delivery_is_rejected_before_collection(tmp_path, override, message):
    plan = plan_at(tmp_path / 'plan.json')
    plan['diagnostic_baseline'].update(override)
    plan['models']['plain']['supports_structured_output'] = False
    path = tmp_path / 'invalid-baseline.json'
    write_json(path, plan)
    with pytest.raises(ValueError, match=message):
        load_diagnostic_plan(path)


def test_known_no_answer_is_failure_but_unresolved_communication_stays_unknown(tmp_path):
    plan = plan_at(tmp_path / 'plan.json')
    case = next(case for case in cases_for_plan(plan) if case.identifier == plan['cases'][0])
    result = {'whole_answer_consistency_required': True, 'canonical_decision': None,
              'answer': None, 'annotation': {'status': 'empty'}}
    score = ReferenceScorer().score(case, 2, result)
    assert score['no_answer'] is True and score['substantive_match'] is False
    result['annotation']['status'] = 'unobserved'
    score = ReferenceScorer().score(case, 2, result)
    assert score['decision_match'] is None and score['substantive_match'] is None


def test_failed_host_acquisition_is_retained_without_discarding_other_recipients(tmp_path, monkeypatch):
    from experiments.model_transfer.conditions import EALContext
    original = EALContext.prepare
    def unavailable(self, project, question, **kwargs):
        if project.session:
            project.events.append({'session': project.session, 'kind': 'eal_assess', 'assessment': None,
                                   'elapsed_seconds': 0.0})
            raise OSError('Synthetic acquisition unavailable')
        return original(self, project, question, **kwargs)
    monkeypatch.setattr(EALContext, 'prepare', unavailable)
    plan = plan_at(tmp_path / 'plan.json')
    root = tmp_path / 'failed-acquisition'
    report = DiagnosticPilot(plan, root, ScriptedTransport()).run()
    assert report['execution_status'] == 'complete' and report['status'] == 'invalid_manipulation'
    assert report['planned_sessions'] == 32 and report['api_attempts'] == 22
    rows = read_json(root / 'rows.json')
    assert sum(variant['result']['status'] == 'failed' for row in rows for variant in row['variants']) == 10
    profiles = [profile for profile in report['evidence_restoration']['profiles'] if profile['reasoner'] == 'eal']
    assert all(profile['all_conditions_substantive_match'] is False for profile in profiles)
    assert all(profile['all_conditions_manipulation_qualified_match'] is None for profile in profiles)
    assert all(item['error']['type'] == 'OSError' and item['host_assessments_without_result'] == 1
               for profile in profiles for item in profile['outcomes'])


def test_failed_host_raw_snapshot_read_retains_attempt_and_duration(tmp_path):
    from experiments.model_transfer.project import Project
    plan = plan_at(tmp_path / 'plan.json')
    case = next(case for case in cases_for_plan(plan) if case.identifier == plan['cases'][0])
    project = Project(tmp_path / 'project', case, 'eal')
    project.state.unlink()
    with pytest.raises(FileNotFoundError):
        project.probe(host_snapshot=True)
    event = project.events[-1]
    assert event['kind'] == 'host_raw_snapshot_read' and event['status'] == 'failed'
    assert event['elapsed_seconds'] >= 0 and event['error']['type'] == 'FileNotFoundError'
