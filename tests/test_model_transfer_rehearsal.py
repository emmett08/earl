"""Pipeline verification distinguishes derived decisions from raw resources."""
from copy import deepcopy
import hashlib

import pytest

from experiments.model_transfer.rehearse import PipelineRehearsal
from experiments.transfer_study.workspace import write_json


def completed_stages(root):
    root.joinpath('annotation-bundle').mkdir()
    write_json(root / 'rows.json', [])
    write_json(root / 'annotation-bundle' / 'mapping.json', {
        'rows_sha256': hashlib.sha256((root / 'rows.json').read_bytes()).hexdigest()})
    write_json(root / 'annotation-bundle' / 'items.json', {'items': [{}]})
    write_json(root / 'calibration.json', {'checks': [{}]})
    report = {'api_attempts': 2, 'known_cost_usd': .01,
              'resources': {'input_tokens': 80},
              'cumulative_resources': {'eal': [
                  {'resources': {'input_tokens': 80}, 'recipient_outcomes': {'task_scored': 0}}]}}
    write_json(root / 'report.json', report)
    analysis = deepcopy(report)
    analysis['cumulative_resources']['eal'][0]['recipient_outcomes']['task_scored'] = 1
    write_json(root / 'analysis.json', analysis)
    return analysis


def test_rehearsal_allows_annotation_to_change_decisions(tmp_path):
    completed_stages(tmp_path)
    assert PipelineRehearsal().verify(tmp_path)['resources_reproduced']


def test_rehearsal_rejects_changed_cumulative_measurement(tmp_path):
    analysis = completed_stages(tmp_path)
    analysis['cumulative_resources']['eal'][0]['resources']['input_tokens'] = 81
    write_json(tmp_path / 'analysis.json', analysis)
    with pytest.raises(AssertionError, match='cumulative'):
        PipelineRehearsal().verify(tmp_path)
