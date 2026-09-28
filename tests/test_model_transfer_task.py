"""Independent task adapter checks; no model output enters these tests."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from eal.knowledge import EALKnowledgeBase
from experiments.model_transfer.calibration import ContractCalibration, assess_project
from experiments.model_transfer.cases import CASES, FIRST
from experiments.model_transfer.project import Project
from experiments.model_transfer.task_context import TaskContract, TaskContextBuilder, TaskCorrespondenceError
from experiments.model_transfer.threshold_method import registry
from experiments.transfer_study.workspace import read_json


def assess(tmp_path, case=CASES[0], *, report=None):
    project = Project(tmp_path, case, 'eal')
    assessment = assess_project(project, now=FIRST, report=report)
    binding = TaskContextBuilder(TaskContract.from_case(case), case.source())
    return binding, assessment


def test_task_contract_contains_only_specification_metadata():
    metadata = SimpleNamespace(metric='latency', unit='ms', threshold=200, direction='at_most',
                               assumption_from=FIRST, assumption_until=None)
    assert TaskContract.from_case(metadata).threshold == 200


def test_task_context_uses_collected_reading_instead_of_fixture_answer(tmp_path):
    project = Project(tmp_path, CASES[0], 'eal')
    report = read_json(project.state)
    report['value']['reading'] = 320
    assessment = assess_project(project, now=FIRST, report=report)
    result = TaskContextBuilder(TaskContract.from_case(CASES[0]), CASES[0].source()).build(assessment)
    assert (result['decision'], result['basis'], result['reading']) == ('not_ready', 'criterion_failed', 320)
    assert result['criterion']['unit'] == 'ms'
    assert result['prose_verified'] is False
    assert result['physical_interpretation_verified'] is False


@pytest.mark.parametrize('old,new', [
    ('meets establishes ready', 'meets establishes not_ready'),
    ('require "reading" >= 0;', ''),
    ('"direction" == "at_most"', '"direction" == "at_least"'),
    ('"threshold" == 200', '"threshold" == 201'),
    ('"unit" == "ms"', '"unit" == "s"'),
    ('"service" == "orders"', '"service" == "payments"'),
])
def test_changed_source_is_not_silently_treated_as_same_task(old, new):
    source = CASES[0].source().replace(old, new, 1)
    with pytest.raises(TaskCorrespondenceError):
        TaskContextBuilder(TaskContract.from_case(CASES[0]), source)


def test_identifiers_do_not_determine_the_task_decision(tmp_path):
    project = Project(tmp_path, CASES[0], 'eal')
    source = CASES[0].source().replace('criterion_evaluated', 'not_ready_identifier')
    (project.workspace / 'renamed.eal').write_text(source)
    knowledge = EALKnowledgeBase(project.workspace, project.workspace / 'tools.toml', method_registry=registry())
    knowledge.register('renamed.eal', entry_id='renamed', context={'service': 'orders'}, claims=['not_ready_identifier'])
    assessment = knowledge.assess('renamed', 'not_ready_identifier', now=FIRST)
    contract = replace(TaskContract.from_case(CASES[0]), claim_id='not_ready_identifier')
    result = TaskContextBuilder(contract, source).build(assessment)
    assert result['decision'] == 'ready'


def test_source_digest_and_incomplete_projection_cannot_supply_definite_answer(tmp_path):
    binding, assessment = assess(tmp_path)
    incomplete = deepcopy(assessment)
    incomplete['packet']['summary_complete'] = False
    assert binding.build(incomplete)['decision'] == 'undetermined'
    unrelated = deepcopy(assessment)
    unrelated['source_digest'] = '0' * 64
    with pytest.raises(TaskCorrespondenceError, match='does not match'):
        binding.build(unrelated)


def test_independent_calibration_covers_all_task_and_adversarial_cases():
    result = ContractCalibration().check({'cases': [case.identifier for case in CASES], 'recipient_sessions': 2})
    assert result['status'] == 'passed', [check for check in result['checks'] if not check['passed']]
    assert len(result['checks']) == 41
    assert {check['kind'] for check in result['checks']} == {'task_outcome', 'source_mutation', 'boundary'}
    assert sum(check['kind'] == 'source_mutation' for check in result['checks']) == 7
    threshold = next(check for check in result['checks'] if check['case'] == 'changed_threshold')
    assert threshold['correspondence_rejected'] is True
