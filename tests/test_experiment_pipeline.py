"""Money, continuation and assessor boundaries in the ordered wrapper."""
from copy import deepcopy
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from experiments.model_transfer.journal import AttemptJournal
from experiments.model_transfer.provider import ExecutionStopped
from experiments.model_transfer.rehearse import PipelineRehearsal, ScriptedTransport
from experiments.model_transfer.runner import Pilot
from experiments.model_transfer.run_state import digest
from experiments.transfer_study.workspace import read_json, write_json
from scripts import experiment_pipeline as pipeline

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('PYTHONPATH', os.pathsep.join([str(REPO), str(REPO / 'src')]))
    for key in ('OPENAI_API_KEY', 'SOURCE_ARTIFACT_ID', 'PLAN_PATH', 'INFORMATION_CONFIG',
                'ANNOTATION_LABELS', 'GITHUB_OUTPUT', 'GITHUB_STEP_SUMMARY'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('GITHUB_RUN_ATTEMPT', '1')
    monkeypatch.setenv('EXPERIMENT_WORKERS', '0')
    plan = read_json(REPO / 'experiments/model_transfer/plan.json')
    plan.update(cases=plan['cases'][:1], repetitions=1)
    write_json(tmp_path / 'pilot.json', plan)
    return plan


def retained_state(plan, *, reason=pipeline.TIME_STOP, used=6000, complete=False):
    root = pipeline.LIVE
    write_json(root / 'plan.json', plan)
    write_json(root / 'report.json', {'execution_status': 'complete' if complete else 'partial', 'stop_reason': reason})
    write_json(root / 'segments.json', [{'allowance_seconds': 6000, 'elapsed_seconds': used}])
    return root


@pytest.mark.parametrize(('reason', 'expected'), [
    (pipeline.TIME_STOP, True), ('ExecutionStopped: ' + pipeline.TIME_STOP, True),
    ('Provider HTTP 429; inspect access, model availability or quota', False),
    ('Provider reported a different model snapshot', False),
    ('Cancellation signal 15; resume retained run', False),
    ('API budget exhausted before sending the next request', False),
    ('unexpected exception', False), (None, False),
])
def test_only_an_ordinary_deadline_automatically_continues(workspace, reason, expected):
    root = retained_state(workspace, reason=reason)
    assert pipeline.collection_state(root)['can_collect'] is expected


def test_unknown_charge_and_elapsed_limits_are_cumulative(workspace):
    root = retained_state(workspace)
    journal = AttemptJournal(root)
    journal.append({'event': 'started', 'attempt': 0, 'session_id': 'interrupted',
                    'status': 'started', 'charged_or_reserved_usd': 2.0})
    state = pipeline.collection_state(root, explicit_resume=True)
    assert state['state'] == 'budget_exhausted' and not state['can_collect']
    assert state['charged_or_reserved_usd'] == 2.0
    write_json(root / 'segments.json', [{'allowance_seconds': 6000}] * 4)
    state = pipeline.collection_state(root, explicit_resume=True)
    assert state['state'] == 'time_exhausted' and state['remaining_seconds'] == 0


def test_complete_run_never_starts_another_collection_job(workspace):
    root = retained_state(workspace, complete=True)
    assert pipeline.collection_state(root, explicit_resume=True)['state'] == 'collection_complete'
    assert not pipeline.collection_state(root, explicit_resume=True)['can_collect']


def test_explicit_resume_can_continue_after_interruption_without_extending_lease(workspace):
    root = retained_state(workspace, reason='Cancellation signal 15; resume retained run')
    assert not pipeline.collection_state(root)['can_collect']
    assert pipeline.collection_state(root, explicit_resume=True)['remaining_seconds'] == 15600
    assert pipeline.collection_state(root, explicit_resume=True)['can_collect']


def test_rerunning_paid_jobs_is_rejected_before_restore_or_api(monkeypatch, workspace):
    monkeypatch.setenv('GITHUB_RUN_ATTEMPT', '2')
    monkeypatch.setattr(pipeline, 'restore_run', lambda *args: pytest.fail('Restored an ancestor for a paid rerun'))
    monkeypatch.setattr(pipeline, 'command', lambda *args: pytest.fail('Paid command invoked'))
    with pytest.raises(ValueError, match='Dispatch resume'):
        pipeline.collect()


def test_free_preflight_freezes_workers_and_never_runs_live_collection(monkeypatch, workspace):
    monkeypatch.setenv('TRANSFER_PLAN', 'custom')
    monkeypatch.setenv('PLAN_PATH', 'pilot.json')
    monkeypatch.setenv('EXPERIMENT_WORKERS', '8')
    calls = []
    def fake_command(module, *args):
        calls.append((module, args))
        if module == 'runner':
            assert '--calibrate-only' in args
            write_json(pipeline.PREFLIGHT / 'calibration/calibration.json', {'status': 'passed'})
        elif module == 'rehearse':
            write_json(pipeline.PREFLIGHT / 'rehearsal/rehearsal.json', {'status': 'passed'})
        else:
            pytest.fail('Unexpected stage')
    monkeypatch.setattr(pipeline, 'command', fake_command)
    pipeline.prepare('rehearse')
    frozen = read_json(pipeline.PREPARED / 'plan.json')
    assert frozen['workers'] == 8 and read_json(Path('pilot.json'))['workers'] == 4
    assert not read_json(pipeline.PREPARED / 'pipeline-status.json')['can_collect']
    assert [module for module, _ in calls] == ['runner', 'rehearse']


def test_failed_calibration_prevents_rehearsal_and_paid_work(monkeypatch, workspace):
    monkeypatch.setenv('TRANSFER_PLAN', 'custom')
    monkeypatch.setenv('PLAN_PATH', 'pilot.json')
    def fail(module, *args):
        assert module == 'runner' and '--calibrate-only' in args
        raise subprocess.CalledProcessError(1, 'calibration')
    monkeypatch.setattr(pipeline, 'command', fail)
    with pytest.raises(subprocess.CalledProcessError):
        pipeline.prepare('start')
    assert not (pipeline.PREPARED / 'preflight.json').exists()


def test_new_collection_rejects_a_plan_changed_after_preflight(monkeypatch, workspace):
    def restore(root):
        write_json(root / 'plan.json', workspace)
        write_json(root / 'preflight.json', {'plan_sha256': 'changed', 'operation': 'start',
                   'calibration': {'status': 'passed'}, 'rehearsal': {'status': 'passed'}})
        return {}
    monkeypatch.setattr(pipeline, 'restore_run', restore)
    monkeypatch.setattr(pipeline, 'command', lambda *args: pytest.fail('Paid command invoked'))
    with pytest.raises(ValueError, match='matching passed preflight'):
        pipeline.collect()


def test_initial_collection_uses_frozen_plan_and_6000_second_segment(monkeypatch, workspace):
    def restore(root):
        write_json(root / 'plan.json', workspace)
        write_json(root / 'preflight.json', {'plan_sha256': digest(workspace), 'operation': 'start',
                   'calibration': {'status': 'passed'}, 'rehearsal': {'status': 'passed'}})
        return {'artifact_id': '42'}
    calls = []
    def run(module, *args):
        calls.append((module, args))
        retained_state(workspace)
    monkeypatch.setattr(pipeline, 'restore_run', restore)
    monkeypatch.setattr(pipeline, 'command', run)
    pipeline.collect()
    assert calls[0][0] == 'runner' and calls[0][1][-2:] == ('--segment-seconds', '6000')
    assert '--resume' not in calls[0][1] and '--workers' not in calls[0][1]
    assert read_json(pipeline.LIVE / 'pipeline-status.json')['can_collect']
    assert read_json(pipeline.LIVE / 'restore-receipt.json')['artifact_id'] == '42'


def test_evaluation_keeps_allocation_and_does_not_copy_pilot_rows(monkeypatch, workspace):
    evaluation = {**workspace, 'study_role': 'evaluation', 'pilot_run_ids': ['test-only-pilot']}
    def restore(root):
        write_json(root / 'plan.json', workspace)
        write_json(root / 'evaluation-plan.json', evaluation)
        write_json(root / 'rows.json', [{'pilot': 'must not become evaluation data'}])
        return {'artifact_id': '99'}
    def free(module, *args):
        assert module in {'runner', 'rehearse'}
        if module == 'runner':
            assert '--calibrate-only' in args
            write_json(pipeline.PREFLIGHT / 'calibration/calibration.json', {'status': 'passed'})
        else:
            write_json(pipeline.PREFLIGHT / 'rehearsal/rehearsal.json', {'status': 'passed'})
    monkeypatch.setattr(pipeline, 'restore_run', restore)
    monkeypatch.setattr(pipeline, 'command', free)
    pipeline.prepare('evaluate')
    assert read_json(pipeline.PREPARED / 'plan.json') == evaluation
    assert not (pipeline.PREPARED / 'rows.json').exists()
    assert read_json(pipeline.PREPARED / 'source-plan-receipt.json')['artifact_id'] == '99'


def test_evaluation_without_a_supported_plan_stops_before_any_collection(monkeypatch, workspace):
    def restore(root):
        write_json(root / 'plan.json', workspace)
        return {}
    monkeypatch.setattr(pipeline, 'restore_run', restore)
    monkeypatch.setattr(pipeline, 'command', lambda *args: pytest.fail('Runner invoked'))
    with pytest.raises(ValueError, match='did not produce'):
        pipeline.prepare('evaluate')


def test_two_collection_jobs_retain_attempts_and_one_frozen_budget(monkeypatch, workspace):
    """Run the real collector across two artefact transfers with scripted I/O."""
    artifact = Path('artifact-prepared')
    write_json(artifact / 'plan.json', workspace)
    write_json(artifact / 'preflight.json', {'plan_sha256': digest(workspace), 'operation': 'start',
               'calibration': {'status': 'passed'}, 'rehearsal': {'status': 'passed'}})
    class StopAfterFive(ScriptedTransport):
        count = 0
        def send(self, payload, timeout):
            self.count += 1
            if self.count >= 5:
                raise ExecutionStopped(pipeline.TIME_STOP)
            return super().send(payload, timeout)
    transport = StopAfterFive()
    def restore(root):
        shutil.copytree(artifact, root)
        return {'artifact_id': str(artifact)}
    def run(module, *args):
        assert module == 'runner'
        plan = read_json(Path(args[args.index('--plan') + 1]))
        Pilot(plan, pipeline.LIVE, transport, resume='--resume' in args,
              segment_seconds=int(args[args.index('--segment-seconds') + 1])).run()
    monkeypatch.setattr(pipeline, 'restore_run', restore)
    monkeypatch.setattr(pipeline, 'command', run)
    pipeline.collect()
    first = AttemptJournal(pipeline.LIVE).read()
    assert first and read_json(pipeline.LIVE / 'pipeline-status.json')['can_collect']
    contract = (pipeline.LIVE / 'execution-contract.json').read_bytes()
    artifact = Path('artifact-first')
    shutil.copytree(pipeline.LIVE, artifact)
    shutil.rmtree(pipeline.LIVE)
    shutil.rmtree(pipeline.BASE / 'source')
    transport = ScriptedTransport()
    monkeypatch.setenv('EXPERIMENT_WORKERS', '8')  # A resume cannot use this override.
    pipeline.collect()
    final = AttemptJournal(pipeline.LIVE).read()
    assert final[:len(first)] == first
    assert [row['attempt'] for row in final] == list(range(len(final)))
    assert (pipeline.LIVE / 'execution-contract.json').read_bytes() == contract
    assert read_json(pipeline.LIVE / 'plan.json') == workspace
    state = read_json(pipeline.LIVE / 'pipeline-status.json')
    assert state['state'] == 'collection_complete' and not state['can_collect']
    assert state['charged_or_reserved_usd'] == sum(row['charged_or_reserved_usd'] for row in final)
    assert len(read_json(pipeline.LIVE / 'segments.json')) == 2


@pytest.mark.parametrize('diagnostic', [False, True])
def test_real_export_import_analysis_roundtrip_and_annotation_gate(monkeypatch, workspace, diagnostic):
    """Actual free runner and offline commands; synthetic coding is identified."""
    plan = REPO / 'experiments/model_transfer/diagnostic-plan.json' if diagnostic else Path('pilot.json')
    original = Path('original').resolve()
    PipelineRehearsal().run(plan, original)
    # Retain raw observations, then exercise a new public annotation exchange.
    shutil.rmtree(original / 'annotation-bundle')
    (original / 'annotated-rows.json').unlink()
    raw, journal = (original / 'rows.json').read_bytes(), (original / 'calls.jsonl').read_bytes()
    def restore(root):
        shutil.copytree(original, root)
        return {'artifact_id': '101'}
    monkeypatch.setattr(pipeline, 'restore_run', restore)
    pipeline.export()
    assert read_json(pipeline.LIVE / 'pipeline-status.json')['state'] == 'awaiting_annotations'
    assert (pipeline.LIVE / 'analysis-collection.json').exists()
    assert not (pipeline.LIVE / 'annotated-rows.json').exists()
    labels = read_json(pipeline.LIVE / 'annotation-bundle/items.json')
    assert set(labels) == {'schema', 'rubric', 'annotator', 'items'}
    labels['annotator'] = 'scripted-workflow-test-not-human-evidence'
    for item in labels['items']:
        item.update(decision='ready', quote=item['text'], note='Explicit scripted answer; test data only.')
    write_json(Path('labels.json'), labels)
    monkeypatch.setenv('ANNOTATION_LABELS', 'labels.json')
    # Simulate transfer between jobs using a full export artefact.
    shutil.rmtree(original)
    shutil.copytree(pipeline.LIVE, original)
    shutil.rmtree(pipeline.LIVE)
    partial = deepcopy(labels)
    partial['items'].pop()
    write_json(Path('labels.json'), partial)
    with pytest.raises(ValueError, match='every exported answer'):
        pipeline.finish()
    assert not (pipeline.LIVE / 'annotated-rows.json').exists()
    shutil.rmtree(pipeline.LIVE)
    write_json(Path('labels.json'), labels)
    pipeline.finish()
    result = read_json(pipeline.LIVE / 'pipeline-status.json')
    assert result['state'] == 'processing_complete'
    assert result['planning'] == ('not_applicable_to_diagnostics' if diagnostic else 'no_supported_allocation')
    assert not result['evaluation_available']
    assert (pipeline.LIVE / 'rows.json').read_bytes() == raw
    assert (pipeline.LIVE / 'calls.jsonl').read_bytes() == journal
    assert read_json(pipeline.LIVE / 'analysis-annotated.json')['api_attempts'] == read_json(original / 'report.json')['api_attempts']
    # A corrected offline finish keeps earlier results and cannot select an old
    # allocation after the current attempt finds no supported allocation.
    write_json(pipeline.LIVE / 'evaluation-plan.json', {'test_only': 'stale allocation'})
    shutil.rmtree(original)
    shutil.copytree(pipeline.LIVE, original)
    shutil.rmtree(pipeline.LIVE)
    pipeline.finish()
    assert (pipeline.LIVE / 'processing/0000/annotated-rows.json').is_file()
    assert (pipeline.LIVE / 'processing/0000/evaluation-plan.json').is_file()
    assert not (pipeline.LIVE / 'evaluation-plan.json').exists()
    assert (pipeline.LIVE / 'calls.jsonl').read_bytes() == journal


def test_main_retains_failure_status_and_disables_continuation(monkeypatch, workspace):
    root = retained_state(workspace)
    monkeypatch.setattr(sys, 'argv', ['pipeline', 'export'])
    monkeypatch.setattr(pipeline, 'export', lambda: (_ for _ in ()).throw(ValueError('test failure')))
    with pytest.raises(ValueError, match='test failure'):
        pipeline.main()
    assert read_json(root / 'pipeline-status.json')['state'] == 'failed'
    assert not read_json(root / 'pipeline-status.json')['can_collect']
