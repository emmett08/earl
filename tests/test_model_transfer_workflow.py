"""Manual workflow inputs select explicit stages without shell interpolation."""
from pathlib import Path

import pytest

from experiments.model_transfer import workflow
from experiments.transfer_study.workspace import write_json


def setup(monkeypatch, tmp_path, action='collect', **inputs):
    monkeypatch.chdir(tmp_path)
    values = {'EXPERIMENT_ACTION': action, 'TRANSFER_PLAN': 'comparison', 'PLAN_PATH': '',
              'SOURCE_ARTIFACT_ID': '', 'RESUME_RUN': 'false', 'SEGMENT_SECONDS': '6000',
              'ANNOTATION_LABELS': '', 'INFORMATION_CONFIG': '', 'EXPERIMENT_WORKERS': '0',
              'GITHUB_REPOSITORY': 'emmett08/earl', 'GITHUB_RUN_ID': '123', **inputs}
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)
    calls = []
    monkeypatch.setattr(workflow.subprocess, 'run', lambda args, **kwargs: calls.append(args))
    def restore(repo, artifact, destination):
        write_json(destination / 'plan.json', {'cases': ['task'], 'workers': 4})
        return {'artifact_id': artifact, 'digest': 'test-only'}
    monkeypatch.setattr(workflow, 'restore', restore)
    return calls


def test_new_collection_uses_plan_default_and_bounded_segment(monkeypatch, tmp_path):
    calls = setup(monkeypatch, tmp_path)
    workflow.main()
    args = calls[0]
    assert args[2] == 'experiments.model_transfer.runner'
    assert args[-2:] == ['--segment-seconds', '6000']
    assert '--workers' not in args and '--resume' not in args


@pytest.mark.parametrize('action', ['analyse', 'plan', 'export-annotations', 'import-annotations'])
def test_offline_stages_require_retained_observations(monkeypatch, tmp_path, action):
    calls = setup(monkeypatch, tmp_path, action)
    with pytest.raises(ValueError, match='source_artifact_id'):
        workflow.main()
    assert not calls


def test_resume_uses_saved_plan_and_worker_count(monkeypatch, tmp_path):
    calls = setup(monkeypatch, tmp_path, SOURCE_ARTIFACT_ID='10', RESUME_RUN='true', EXPERIMENT_WORKERS='8')
    workflow.main()
    assert '--resume' in calls[0] and '--workers' not in calls[0]
    assert calls[0][4] == 'experiments/model_transfer/runs/live/plan.json'


def test_offline_annotation_import_and_analysis_use_derived_rows(monkeypatch, tmp_path):
    calls = setup(monkeypatch, tmp_path, 'import-annotations', SOURCE_ARTIFACT_ID='10', ANNOTATION_LABELS='labels.json')
    write_json(Path('labels.json'), {})
    workflow.main()
    assert calls[0][2:4] == ['experiments.model_transfer.annotations', 'import']
    assert calls[0][-1].endswith('annotated-rows.json')
    write_json(Path('experiments/model_transfer/runs/live/annotated-rows.json'), [])
    monkeypatch.setenv('EXPERIMENT_ACTION', 'analyse')
    workflow.main()
    assert calls[-1][2] == 'experiments.model_transfer.analyse' and '--rows' in calls[-1]


def test_custom_evaluation_uses_artefact_plan_without_altering_allocation(monkeypatch, tmp_path):
    calls = setup(monkeypatch, tmp_path, SOURCE_ARTIFACT_ID='10', TRANSFER_PLAN='custom', PLAN_PATH='evaluation-plan.json')
    def restore(repo, artifact, destination):
        write_json(destination / 'plan.json', {})
        write_json(destination / 'evaluation-plan.json', {'study_role': 'evaluation', 'workers': 4})
        return {'artifact_id': artifact}
    monkeypatch.setattr(workflow, 'restore', restore)
    # A fake runner still creates its run directory for the source receipt.
    workflow.main()
    assert calls[0][4].endswith('runs/source/evaluation-plan.json')
    assert '--resume' not in calls[0] and '--workers' not in calls[0]
    monkeypatch.setenv('EXPERIMENT_WORKERS', '8')
    with pytest.raises(ValueError, match='Evaluation must retain'):
        workflow.main()


@pytest.mark.parametrize('seconds', ['0', '-1', '6001'])
def test_workflow_preserves_finalisation_margin(monkeypatch, tmp_path, seconds):
    calls = setup(monkeypatch, tmp_path, SEGMENT_SECONDS=seconds)
    with pytest.raises(ValueError, match='20 minutes'):
        workflow.main()
    assert not calls


@pytest.mark.parametrize('action', ['calibrate', 'rehearse', 'analyse', 'plan', 'import-annotations', 'export-annotations'])
def test_resume_flag_cannot_turn_an_offline_stage_into_collection(monkeypatch, tmp_path, action):
    calls = setup(monkeypatch, tmp_path, action, RESUME_RUN='true', SOURCE_ARTIFACT_ID='10')
    with pytest.raises(ValueError, match='only valid for collect'):
        workflow.main()
    assert not calls
