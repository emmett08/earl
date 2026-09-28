"""Component isolation and failure accounting, using no live model calls."""
import copy
import json
from pathlib import Path

import pytest

from experiments.model_transfer.diagnostics import (
    BASELINE, DiagnosticPilot, DiagnosticReportBuilder, DiagnosticSchedule,
    load_diagnostic_plan,
)
from experiments.model_transfer.diagnostic_measurement import ProjectSnapshot
from experiments.model_transfer.diagnostic_preparation import PreparationTimer
from experiments.model_transfer.cases import CASES
from experiments.model_transfer.project import Project
from experiments.model_transfer.provider import ExecutionStopped
from experiments.transfer_study.workspace import read_json, write_json

PLAN = Path(__file__).resolve().parents[1] / 'experiments/model_transfer/diagnostic-plan.json'


class ScriptedTransport:
    """Retained requests test the harness; replies are not model evidence."""

    def __init__(self):
        self.requests = []

    def send(self, payload, timeout):
        self.requests.append(copy.deepcopy(payload))
        text = 'The service is ready.'
        if payload.get('text', {}).get('format', {}).get('type') == 'json_schema':
            text = json.dumps({'decision': 'ready', 'basis': 'criterion_met', 'reading': 180,
                               'observed_at': '2026-09-28T10:00:00Z',
                               'explanation': 'Synthetic test response.', 'files': []})
        return {'model': payload['model'], 'status': 'completed',
                'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}],
                'usage': {'input_tokens': 80, 'output_tokens': 30}}


def test_plan_and_schedule_preserve_single_factor_and_replay():
    plan = load_diagnostic_plan(PLAN)
    schedule = DiagnosticSchedule(plan).allocations()
    assert schedule == DiagnosticSchedule(plan).allocations()
    # The retained plan is written with sorted mapping keys. Mapping order must
    # not alter randomisation when that exact plan is reloaded for analysis.
    saved_plan = json.loads(json.dumps(plan, sort_keys=True))
    assert schedule == DiagnosticSchedule(saved_plan).allocations()
    assert len(schedule) == 10
    assert sum(1 + len(block['variants']) for block in schedule) == 56
    ids = [variant['session_id'] for block in schedule for variant in block['variants']]
    assert len(ids) == len(set(ids)) == 46
    for block in schedule:
        for variant in block['variants']:
            changed = {key for key, value in variant['options'].items() if BASELINE[key] != value}
            assert len(changed) <= 1


@pytest.mark.parametrize('field,value', [('budget_usd', 2.01), ('native_tools', ['false']),
                                       ('recipients', ['unconfigured']), ('donor', 'unconfigured'),
                                       ('contrasts', {'reuse': ['unknown']})])
def test_invalid_diagnostic_plan_is_rejected_before_requests(tmp_path, field, value):
    plan = read_json(PLAN)
    plan[field] = value
    path = tmp_path / 'plan.json'
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError):
        load_diagnostic_plan(path)


def test_fork_preserves_observation_identity_binding_and_independent_notes(tmp_path):
    donor = Project(tmp_path / 'donor', CASES[0], 'eal')
    donor.context('Assess')
    donor.persist([{'name': 'donor.md', 'content': 'Actual donor note.'}])
    donor.set_session(1)
    before = ProjectSnapshot.capture(donor)
    first, second = [donor.fork(tmp_path / name, session=1) for name in ('first', 'second')]
    assert ProjectSnapshot.capture(first) == ProjectSnapshot.capture(second) == before
    first.context('Assess again')
    assessment = first.events[-1]['assessment']
    assert assessment['reused_count'] == 1 and assessment['collected_count'] == 0
    first.persist([{'name': 'donor.md', 'content': 'Changed recipient note.'}])
    assert second.files()['donor.md'] == donor.files()['donor.md'] == 'Actual donor note.'
    assert ProjectSnapshot.capture(donor) == before


def test_controlled_diagnostics_record_real_manipulations_and_cloned_state(tmp_path):
    plan = load_diagnostic_plan(PLAN)
    transport = ScriptedTransport()
    report = DiagnosticPilot(plan, tmp_path, transport).run()
    rows = read_json(tmp_path / 'rows.json')
    assert report['execution_status'] == 'complete' and report['status'] == 'pending_annotation'
    assert report['planned_blocks'] == 10 and report['planned_sessions'] == 56
    assert report['api_attempts'] == 56 and report['charged_or_reserved_usd'] <= 2
    assert len(report['comparisons']) == 38
    assert report['resource_accounting_complete'] is True
    groups = report['resource_groups']
    assert groups['shared_donors']['api_attempts'] == 10
    assert groups['recipients']['api_attempts'] == 46
    assert len(report['blocks']) == 10
    assert sum(len(block['recipients']) for block in report['blocks']) == 46
    for block in report['blocks']:
        donor = block['shared_donor']
        assert set(donor['preparation']) == {'donor_setup', 'shared_state'}
        assert donor['resources']['api_attempts'] == 1
        assert donor['resources']['preparation_status_counts'] == {'complete': 2}
        assert all(recipient['resources']['api_attempts'] == 1 for recipient in block['recipients'])
    for key in ('api_attempts', 'input_tokens', 'output_tokens', 'known_cost_usd',
                'preparation_seconds', 'elapsed_seconds', 'elapsed_with_preparation_seconds'):
        assert report['resources'][key] == pytest.approx(sum(group[key] for group in groups.values()))
    for group in (*groups.values(), report['resources']):
        assert group['preparation_timing_complete'] is True
        assert group['preparation_operations_complete'] is True
        assert group['elapsed_with_preparation_complete'] is True
        assert group['preparation_seconds'] > 0
        assert group['elapsed_with_preparation_seconds'] > group['elapsed_seconds']
    # Format variants occur in several pairwise contrasts. Those repeated entries
    # are useful comparisons but are deliberately absent from unique aggregation.
    assert sum(r['api_attempts'] for c in report['comparisons'] for r in c['resources']) == 76
    assert report['resources']['api_attempts'] == 56
    assert 'must not be summed' in report['interpretation']
    assert all(c['manipulation']['status'] == 'passed' for c in report['comparisons'])
    assert all(variant['input_snapshot'] == row['donor_snapshot']
               for row in rows for variant in row['variants'])
    for row in rows:
        assert row['donor_result']['native_tools'] is True
        assert all(v['result']['native_tools'] is False for v in row['variants'])
        schema_variants = [v for v in row['variants'] if v['options']['response_mode'] == 'json_schema']
        for variant in schema_variants:
            call = next(c for c in read_json(tmp_path / 'calls.json') if c['session_id'] == variant['session_id'])
            assert call['request']['text']['format']['type'] == 'json_schema'
    rebuilt = DiagnosticReportBuilder(plan).build(rows, read_json(tmp_path / 'calls.json'))
    assert rebuilt == report
    # Exercise the real exported-run interfaces, not only the in-memory builder.
    from dataclasses import asdict
    import subprocess
    import sys
    from experiments.model_transfer.annotations import AnnotationExchange
    write_json(tmp_path / 'plan.json', plan)
    (tmp_path / 'cases.json').write_text(json.dumps([asdict(c) for c in CASES if c.identifier in plan['cases']]))
    bundle = tmp_path / 'coding'
    AnnotationExchange().export(tmp_path, bundle)
    labels = read_json(bundle / 'items.json')
    labels['annotator'] = 'independent-fixture-coder'
    for item in labels['items']:
        item.update(decision='ready', quote='The service is ready.', note='Explicit present decision.')
    (bundle / 'labels.json').write_text(json.dumps(labels))
    derived = tmp_path / 'annotated-rows.json'
    AnnotationExchange().import_labels(tmp_path, bundle, bundle / 'labels.json', derived)
    subprocess.run([sys.executable, '-m', 'experiments.model_transfer.analyse', str(tmp_path),
                    '--rows', str(derived)], check=True)
    analysed = read_json(tmp_path / 'analysis.json')
    assert analysed['status'] == 'complete' and analysed['pending_annotation_sessions'] == 0
    assert analysed['api_attempts'] == 56
    assert read_json(tmp_path / 'rows.json') == rows


def test_manipulation_failure_does_not_become_successful_component_evidence(tmp_path):
    plan = load_diagnostic_plan(PLAN)
    plan.update(cases=['fresh_positive'], recipients=['plain'], contrasts={'reuse': ['fresh_positive']})
    report = DiagnosticPilot(plan, tmp_path, ScriptedTransport()).run()
    rows = read_json(tmp_path / 'rows.json')
    assert report['comparisons'][0]['manipulation']['status'] == 'passed'
    variant = rows[0]['variants'][0]
    variant['input_snapshot']['observations_sha256'] = 'changed'
    variant['result']['task_context']['injected_fact'] = 'different task'
    rebuilt = DiagnosticReportBuilder(plan).build(rows, read_json(tmp_path / 'calls.json'))
    comparison = rebuilt['comparisons'][0]
    assert comparison['manipulation']['status'] == 'invalid'
    assert comparison['decision_difference_right_minus_left'] is None
    assert 'initial_state_differs' in comparison['manipulation']['failures']
    assert 'current_task_information_differs' in comparison['manipulation']['failures']


def test_no_op_reuse_contrast_is_invalid_even_with_complete_answers(tmp_path):
    plan = load_diagnostic_plan(PLAN)
    plan.update(cases=['refresh_negative'], recipients=['plain'], contrasts={'reuse': ['refresh_negative']})
    report = DiagnosticPilot(plan, tmp_path, ScriptedTransport()).run()
    comparison = report['comparisons'][0]
    assert report['execution_status'] == 'complete' and report['status'] == 'invalid_manipulation'
    assert comparison['manipulation']['status'] == 'invalid'
    assert 'acquisition_manipulation_not_delivered' in comparison['manipulation']['failures']
    assert comparison['decision_difference_right_minus_left'] is None


def test_fatal_donor_failure_keeps_planned_sessions_and_unknown_cost(tmp_path):
    class Failure:
        def send(self, payload, timeout):
            raise ExecutionStopped('Provider unavailable')
    plan = load_diagnostic_plan(PLAN)
    report = DiagnosticPilot(plan, tmp_path, Failure()).run()
    assert report['status'] == 'partial'
    assert report['planned_sessions'] == 56 and report['api_attempts'] == 1
    assert report['unknown_cost_attempts'] == 1
    assert all(c['decision_difference_right_minus_left'] is None for c in report['comparisons'])
    assert len(read_json(tmp_path / 'rows.json')) == 10


def test_prompted_format_contrast_requires_neither_reasoning_nor_native_tools(tmp_path):
    plan = read_json(PLAN)
    plan.update(cases=['fresh_positive'], recipients=['plain'], contrasts={'format': ['fresh_positive']},
                response_modes=['prose', 'json_prompted'])
    plan['models']['plain']['supports_structured_output'] = False
    path = tmp_path / 'plan.json'
    path.write_text(json.dumps(plan))
    plan = load_diagnostic_plan(path)
    report = DiagnosticPilot(plan, tmp_path / 'run', ScriptedTransport()).run()
    assert report['execution_status'] == 'complete'
    assert report['comparisons'][0]['manipulation']['status'] == 'passed'
    calls = read_json(tmp_path / 'run' / 'calls.json')
    assert all('text' not in call['request'] and 'reasoning' not in call['request'] for call in calls)
    assert all('tools' not in call['request'] for call in calls if '.donor.' not in call['session_id'])


def test_analysis_rejects_deleted_or_duplicated_planned_variants(tmp_path):
    plan = load_diagnostic_plan(PLAN)
    rows = [{**assignment, 'status': 'not_run'} for assignment in DiagnosticSchedule(plan).allocations()]
    rows[0]['variants'].pop()
    with pytest.raises(ValueError, match='denominator'):
        DiagnosticReportBuilder(plan).build(rows, [])


def test_failed_preparation_retains_elapsed_stage_and_unknown_remaining_work(tmp_path, monkeypatch):
    from experiments.model_transfer import diagnostics

    def fail_construction(*args, **kwargs):
        raise OSError('Cannot create donor workspace')

    monkeypatch.setattr(diagnostics, 'Project', fail_construction)
    plan = load_diagnostic_plan(PLAN)
    report = DiagnosticPilot(plan, tmp_path, ScriptedTransport()).run()
    row = read_json(tmp_path / 'rows.json')[0]
    assert report['status'] == 'partial'
    assert row['preparation']['donor_setup']['status'] == 'failed'
    assert row['preparation']['donor_setup']['elapsed_seconds'] >= 0
    assert row['preparation']['shared_state'] == {'status': 'not_run', 'elapsed_seconds': None}
    assert report['resources']['preparation_timing_complete'] is False
    assert report['resources']['preparation_operations_complete'] is False
    assert report['resources']['unknown_preparation_operations'] == 65
    assert report['resources']['elapsed_with_preparation_complete'] is False


def test_interrupted_preparation_is_unknown_instead_of_measured_zero():
    plan = load_diagnostic_plan(PLAN)
    rows = [{**assignment, 'status': 'not_run'} for assignment in DiagnosticSchedule(plan).allocations()]
    rows[0].update(status='started', preparation={'donor_setup': {'status': 'started', 'elapsed_seconds': None}})
    report = DiagnosticReportBuilder(plan).build(rows, [])
    donor = report['blocks'][0]['shared_donor']['resources']
    assert donor['preparation_status_counts'] == {'started': 1, 'unreported': 1}
    assert donor['preparation_seconds'] == 0  # The available subtotal; no duration was measured.
    assert donor['unknown_preparation_operations'] == 2
    assert donor['preparation_timing_complete'] is False
    assert donor['elapsed_with_preparation_complete'] is False
    assert report['resource_accounting_complete'] is False
    assert all(c['resource_differences_right_minus_left']['preparation_seconds'] is None
               for c in report['comparisons'])


def test_missing_recipient_call_blocks_diagnostic_resource_savings(tmp_path):
    plan = load_diagnostic_plan(PLAN)
    plan.update(cases=['fresh_positive'], recipients=['plain'], contrasts={'reuse': ['fresh_positive']})
    DiagnosticPilot(plan, tmp_path, ScriptedTransport()).run()
    rows, calls = read_json(tmp_path / 'rows.json'), read_json(tmp_path / 'calls.json')
    missing = rows[0]['variants'][0]['session_id']
    calls = [call for call in calls if call['session_id'] != missing]
    report = DiagnosticReportBuilder(plan).build(rows, calls)
    assert report['status'] != 'complete'
    assert report['resource_accounting_complete'] is False
    assert report['estimated_cost_usd'] is None
    assert report['known_cost_usd'] > 0
    assert report['resources']['api_accounting_complete'] is False
    assert report['resource_groups']['shared_donors']['api_accounting_complete'] is True
    assert report['resource_groups']['recipients']['api_accounting_complete'] is False
    assert report['resources']['accounting_errors']
    differences = report['comparisons'][0]['resource_differences_right_minus_left']
    assert all(differences[key] is None for key in
               ('api_attempts', 'input_tokens', 'output_tokens', 'estimated_cost_usd'))


def test_preparation_timer_excludes_persistence_and_retains_failed_duration():
    clock = iter((100.0, 101.5, 200.0, 200.25))
    persisted = []
    record = PreparationTimer.pending()
    timer = PreparationTimer(lambda: persisted.append(dict(record)), clock=lambda: next(clock))
    with timer.measure(record):
        assert persisted[-1] == {'status': 'started', 'elapsed_seconds': None}
    assert record == {'status': 'complete', 'elapsed_seconds': 1.5}
    with pytest.raises(RuntimeError, match='Preparation failed'):
        with timer.measure(record):
            raise RuntimeError('Preparation failed')
    assert record == {'status': 'failed', 'elapsed_seconds': 0.25}
    assert persisted == [
        {'status': 'started', 'elapsed_seconds': None},
        {'status': 'complete', 'elapsed_seconds': 1.5},
        {'status': 'started', 'elapsed_seconds': None},
        {'status': 'failed', 'elapsed_seconds': 0.25},
    ]
