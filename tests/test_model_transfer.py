"""Checks for the live nano pilot; fake responses are not performance evidence."""
import copy
import json
from pathlib import Path

import pytest

from experiments.model_transfer.cases import CASES, Project
from experiments.model_transfer.provider import BudgetedClient, ExecutionStopped
from experiments.model_transfer.runner import Pilot, SessionRunner, load_plan
from experiments.transfer_study.workspace import read_json

PLAN = Path(__file__).resolve().parents[1] / 'experiments/model_transfer/plan.json'


class ScriptedTransport:
    def __init__(self):
        self.requests = []

    def send(self, payload, timeout):
        self.requests.append(copy.deepcopy(payload))
        assert payload['store'] is False
        assert 'previous_response_id' not in payload and 'conversation' not in payload
        if payload.get('tools') and not any(x.get('type') == 'function_call_output' for x in payload['input']):
            output = [{'type': 'reasoning', 'id': 'opaque', 'encrypted_content': 'test-only', 'summary': []},
                      {'type': 'function_call', 'name': 'probe', 'arguments': '{}', 'call_id': 'call1'}]
        else:
            if payload.get('tools'):
                assert any(x.get('encrypted_content') == 'test-only' for x in payload['input'])
            text = json.dumps({'decision': 'ready', 'basis': 'criterion_met',
                               'explanation': 'Synthetic response for harness checks.',
                               'files': {'notes.md': 'Naturally produced fixture note.'}})
            output = [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}]
        return {'model': payload['model'], 'status': 'completed', 'output': output,
                'usage': {'input_tokens': 80, 'output_tokens': 30,
                          'output_tokens_details': {'reasoning_tokens': 10 if 'reasoning' in payload else 0}}}


def test_six_oracles_are_independent_and_eal_reuse_matches_temporal_conditions(tmp_path):
    expected = [('ready', 1), ('not_ready', 1), ('ready', 0), ('not_ready', 0),
                ('undetermined', 0), ('undetermined', 1)]
    for case, (decision, reused) in zip(CASES, expected):
        assert case.oracle('later')['decision'] == decision
        project = Project(tmp_path / case.identifier, case, 'eal')
        project.context('Assess readiness')
        project.set_stage('later')
        project.context('Assess readiness')
        assessment = project.events[-1]['assessment']
        assert assessment['reused_count'] == reused
        assert assessment['collected_count'] == 1 - reused
        # The hidden current measurement is never included as a project artefact.
        assert 'collector-state.json' not in project.files()


def test_complete_automated_pipeline_and_native_tool_mask(tmp_path):
    plan = load_plan(PLAN)
    transport = ScriptedTransport()
    result = Pilot(plan, tmp_path, transport).run()
    assert result['status'] == 'complete'
    assert len(result['summaries']) == 8
    for summary in result['summaries']:
        assert summary['planned'] == summary['completed'] == 6
        assert summary['reference_decision_and_basis_matches'] == 2
        if summary['arm'] == 'eal':
            assert summary['later_eal_reused'] == 3
            assert summary['later_eal_collected'] == 3
    rows = read_json(tmp_path / 'rows.json')
    calls = read_json(tmp_path / 'calls.json')
    for row in rows:
        later = row['later']
        selected = [call for call in calls if call['session_id'] == later['session_id']]
        assert bool(selected[0]['request'].get('tools')) == row['native_tools']
        assert not any(x.get('type') in ('function_call', 'function_call_output', 'reasoning')
                       for x in selected[0]['request']['input'])
        assert 'Naturally produced fixture note.' in json.dumps(later['initial_messages'])
        assert 'Synthetic response for harness checks.' not in json.dumps(later['initial_messages'])
        expected = {'effort': 'low'} if row['receiver'] == 'reasoning' else None
        assert selected[0]['request'].get('reasoning') == expected
    assert result['charged_or_reserved_usd'] <= 2


def test_budget_reserves_before_send_and_retains_failed_attempt(tmp_path):
    class Failing:
        calls = 0
        def send(self, payload, timeout):
            self.calls += 1
            raise ExecutionStopped('Provider unavailable')
    plan = load_plan(PLAN)
    transport = Failing()
    client = BudgetedClient(tmp_path, plan, transport)
    profile = plan['models']['plain']
    with pytest.raises(ExecutionStopped, match='unavailable'):
        client.request(profile, [{'role': 'user', 'content': 'test'}], [], 'session')
    row = read_json(tmp_path / 'calls.json')[0]
    assert row['status'] == 'failed'
    assert row['cost_estimate_usd'] is None
    assert row['charged_or_reserved_usd'] == row['reserved_usd'] > 0
    client.plan['budget_usd'] = row['reserved_usd']
    with pytest.raises(ExecutionStopped, match='budget exhausted'):
        client.request(profile, [{'role': 'user', 'content': 'test'}], [], 'session')
    assert transport.calls == 1


def test_fatal_provider_failure_retains_all_planned_sequences(tmp_path):
    class Failing:
        def send(self, payload, timeout):
            raise ExecutionStopped('Provider HTTP 401')
    report = Pilot(load_plan(PLAN), tmp_path, Failing()).run()
    assert report['status'] == 'partial'
    rows = read_json(tmp_path / 'rows.json')
    assert len(rows) == 48
    assert sum(row['status'] == 'stopped' for row in rows) == 1
    assert sum(row['status'] == 'not_run' for row in rows) == 47
    assert sum(x['planned'] for x in report['summaries']) == 48
    assert report['api_attempts'] == 1


def test_models_cannot_overwrite_specification_or_escape_project(tmp_path):
    project = Project(tmp_path, CASES[0], 'ordinary')
    for name in ('../answer.md', 'specification.txt', 'tools.toml'):
        with pytest.raises(ValueError):
            project.persist({name: 'changed'})


def test_incomplete_response_is_retained_with_actual_usage(tmp_path):
    class Incomplete:
        def send(self, payload, timeout):
            return {'model': payload['model'], 'status': 'incomplete', 'output': [],
                    'usage': {'input_tokens': 80, 'output_tokens': 4096}}
    plan = load_plan(PLAN)
    project = Project(tmp_path / 'sequence', CASES[0], 'ordinary')
    client = BudgetedClient(tmp_path, plan, Incomplete())
    result = SessionRunner(client, plan).run(project, plan['models']['reasoning'], False, 'incomplete')
    assert result['status'] == 'failed'
    assert client.records[0]['response']['status'] == 'incomplete'
    assert client.records[0]['cost_estimate_usd'] > 0
