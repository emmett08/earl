"""Cross-check the separately authored corpus against both actual runtime and oracle."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

import pytest

from experiments.model_transfer.calibration import ContractCalibration, assess_project
from experiments.model_transfer.cases import CASES, case_from_record
from experiments.model_transfer.corpus_cases import load_cases, dated
from experiments.model_transfer.corpus_logic import Conjunction, Alternatives, FactSelector
from experiments.model_transfer.corpus_reference import CorpusReference
from experiments.model_transfer.project import Project
from experiments.model_transfer.task_context import TaskContract, TaskContextBuilder, TaskCorrespondenceError


def test_ten_recipient_calibration_uses_authored_keys_and_real_runtime():
    result = ContractCalibration().check({'cases': [case.identifier for case in CASES], 'recipient_sessions': 10})
    failures = [check for check in result['checks'] if not check['passed']]
    assert result['status'] == 'passed', failures
    assert len(result['checks']) == 14 * 11 + 17


@pytest.mark.parametrize('case', load_cases(), ids=lambda case: case.identifier)
def test_rule_source_observations_and_cache_follow_actual_public_runtime(tmp_path, case):
    project = Project(tmp_path, case, 'eal')
    expected = case.expected_decisions
    for session in range(11):
        project.set_session(session)
        project.context('Assess readiness.', style='compact')
        event = project.events[-1]
        assert event['task_context']['decision'] == expected[session]
        assert CorpusReference().reference(case, session)['decision'] == expected[session]
        observed = event['task_context']['observed_at']
        assert observed == case.time(session - session % 2)
    restored = case_from_record(json.loads(json.dumps(asdict(case))))
    assert restored.measurement(10) == case.measurement(10)


def test_answer_keys_and_event_explanations_never_enter_visible_task_information(tmp_path):
    case = load_cases()[0]
    report = case.measurement(0)
    assert set(report['value']) == {'task_id', 'rule_digest', 'rule', 'now_minute', 'scope', 'facts',
                                    'target_identity', 'target_identity_digest'}
    assert 'expected_decisions' not in case.specification()
    project = Project(tmp_path, case, 'ordinary')
    assert 'expected' not in project.probe()['value']


def test_collected_fact_changes_drive_host_result_without_reference_lookup(tmp_path):
    case = load_cases()[0]
    project = Project(tmp_path, case, 'eal')
    report = case.measurement(0)
    requirement = case.rule['requirements'][0]
    fact = next(fact for fact in report['value']['facts'] if fact['key'] == requirement['fact_key'])
    fact['value'] = not requirement['expected_value']
    assessment = assess_project(project, now=case.time(0), report=report)
    result = TaskContextBuilder(TaskContract.from_case(case), case.source(), explain=project.explain).build(assessment)
    assert result['decision'] == 'not_ready'
    assert case.expected_decisions[0] == 'ready'


def test_changed_source_binding_and_tampered_rule_are_not_accepted(tmp_path):
    case = load_cases()[0]
    binding = TaskContract.from_case(case)
    with pytest.raises(TaskCorrespondenceError):
        TaskContextBuilder(binding, case.source().replace('max_age 60;', 'max_age 600;'))
    project = Project(tmp_path, case, 'eal')
    report = deepcopy(case.measurement(0))
    report['value']['rule']['requirements'][0]['expected_value'] = 'tampered'
    assessment = assess_project(project, now=case.time(0), report=report)
    result = TaskContextBuilder(binding, case.source(), explain=project.explain).build(assessment)
    assert result['decision'] == 'undetermined'


def test_false_conjunct_and_true_alternative_dominate_missing_information():
    assert Conjunction().evaluate({}, {'available_failure': False, 'missing': None}) is False
    rule = {'alternatives': [{'requirement_ids': ['available_success']}, {'requirement_ids': ['missing']}]}
    assert Alternatives().evaluate(rule, {'available_success': True, 'missing': None}) is True


def test_numeric_scalar_equality_distinguishes_booleans():
    case = load_cases()[0]
    requirement = deepcopy(case.rule['requirements'][0])
    requirement['expected_value'] = 1
    report = case.measurement(0)['value']
    fact = next(fact for fact in report['facts'] if fact['key'] == requirement['fact_key'])
    fact['value'] = 1.0
    assert FactSelector().state(requirement, report) is True
    fact['value'] = True
    assert FactSelector().state(requirement, report) is False


def test_snapshot_inner_clock_cannot_relabel_old_computation_as_fresh(tmp_path):
    case = load_cases()[0]
    project = Project(tmp_path, case, 'eal')
    report = case.measurement(0)
    report['observed_at'] = dated(10)
    assessment = assess_project(project, now=dated(10), report=report)
    with pytest.raises(TaskCorrespondenceError, match='computation time'):
        TaskContextBuilder(TaskContract.from_case(case), case.source(), explain=project.explain).build(assessment)


def test_changed_target_scope_is_rejected_even_when_all_fact_scopes_agree(tmp_path):
    case = load_cases()[0]
    project = Project(tmp_path, case, 'eal')
    report = case.measurement(0)
    report['value']['scope']['service'] = 'another-service'
    for fact in report['value']['facts']:
        fact['scope']['service'] = 'another-service'
    assessment = assess_project(project, now=case.time(0), report=report)
    context = TaskContextBuilder(TaskContract.from_case(case), case.source(), explain=project.explain).build(assessment)
    assert context['decision'] == 'undetermined'


def test_reuse_assumption_rejects_changed_intervening_scope_even_with_same_decision(tmp_path):
    path = Path(__file__).parents[1] / 'experiments/model_transfer/task_corpus.json'
    payload = json.loads(path.read_text())
    snapshot = payload['cases'][0]['timeline'][1]
    snapshot['scope']['release'] = 'different-release'
    for fact in snapshot['facts']:
        fact['scope']['release'] = 'different-release'
    changed = tmp_path / 'changed-corpus.json'
    changed.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match='Snapshot continuity'):
        load_cases(changed)
