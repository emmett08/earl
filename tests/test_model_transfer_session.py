"""Retain measurable response text and request identity across unfinished sessions."""
import copy
import json
from pathlib import Path

import pytest

from experiments.model_transfer.annotations import AnnotationExchange
from experiments.model_transfer.cases import CASES, FIRST
from experiments.model_transfer.design import load_plan
from experiments.model_transfer.project import Project
from experiments.model_transfer.provider import BudgetedClient, ExecutionStopped
from experiments.model_transfer.scoring import ReferenceScorer
from experiments.model_transfer.session import SessionRunner


PLAN = Path(__file__).resolve().parents[1] / 'experiments/model_transfer/plan.json'


def message(text):
    return {'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}


def probe(arguments='{}'):
    return {'type': 'function_call', 'name': 'probe', 'arguments': arguments, 'call_id': 'probe-1'}


def structured_answer(decision='ready', filename='unfinished.md'):
    return json.dumps({'decision': decision,
                       'basis': 'criterion_met' if decision == 'ready' else 'criterion_failed',
                       'reading': 180, 'observed_at': FIRST, 'explanation': 'Scripted task response.',
                       'files': [{'name': filename, 'content': 'Keep only a complete final response.'}]})


class Responses:
    """A deterministic transport supplies task text, calls or provider failures."""

    def __init__(self, *steps):
        self.steps = iter(steps)

    def send(self, payload, timeout):
        step = next(self.steps)
        if isinstance(step, Exception):
            raise step
        output, status = step if isinstance(step, tuple) else (step, 'completed')
        return {'model': payload['model'], 'status': status, 'output': copy.deepcopy(output),
                'usage': {'input_tokens': 80, 'output_tokens': 30}}


def setup(tmp_path, *steps, max_calls=3):
    plan = {**load_plan(PLAN), 'max_calls_per_session': max_calls}
    project = Project(tmp_path / 'sequence', CASES[0], 'ordinary')
    project.remember_answer('Previous complete answer.')
    client = BudgetedClient(tmp_path, plan, Responses(*steps))
    return plan, project, client, SessionRunner(client, plan)


def assert_unfinished(result, project, text):
    assert result['raw_answer'] == text
    assert result['answer'] is None and result['format_valid'] is None
    assert result['annotation']['status'] == 'pending'
    assert result['file_result'] == {'status': 'not_requested', 'written': []}
    assert result['handoff']['status'] == 'not_retained'
    assert (project.workspace / 'latest-answer.md').read_text() == 'Previous complete answer.'
    assert not (project.workspace / 'unfinished.md').exists()
    score = ReferenceScorer().score(CASES[0], 0, result)
    assert score['task_match'] is None and score['no_answer'] is False


@pytest.mark.parametrize('mode,text', [('prose', 'The service is ready.'),
                                       ('json_schema', structured_answer())])
def test_text_accompanying_last_tool_call_is_retained_for_annotation(tmp_path, mode, text):
    plan, project, client, runner = setup(tmp_path, [message(text), probe()], max_calls=1)
    result = runner.run(project, plan['models']['plain'], True, 'last-tool', response_mode=mode)
    assert result['status'] == 'incomplete' and result['error']['type'] == 'CallLimit'
    assert result['api_attempt_ids'] == [0]
    assert result['response_texts'] == [text]
    assert_unfinished(result, project, text)
    assert sum(event['kind'] == 'native_probe' for event in project.events) == 1
    assert client.records[0]['status'] == 'completed'
    assert json.loads((project.root / 'session-0.json').read_text()) == result
    (tmp_path / 'rows.json').write_text(json.dumps([{'sessions': [result]}]))
    exported = AnnotationExchange().export(tmp_path, tmp_path / 'annotations')
    assert exported['exported'] == 1
    assert json.loads((tmp_path / 'annotations/items.json').read_text())['items'][0]['text'] == text


@pytest.mark.parametrize('arguments,native_tools,error', [('{', True, 'JSONDecodeError'),
                                                        ('{}', False, 'ValueError')])
def test_tool_processing_failure_keeps_text_without_file_effects(tmp_path, arguments, native_tools, error):
    text = structured_answer()
    plan, project, client, runner = setup(tmp_path, [message(text), probe(arguments)])
    result = runner.run(project, plan['models']['plain'], native_tools, 'bad-tool',
                        response_mode='json_prompted')
    assert result['status'] == 'failed' and result['error']['type'] == error
    assert result['api_attempt_ids'] == [0]
    assert_unfinished(result, project, text)
    assert not any(event['kind'] == 'native_probe' for event in project.events)


@pytest.mark.parametrize('error', [RuntimeError('Transport failed'), ExecutionStopped('Provider unavailable')])
def test_later_request_failure_keeps_previous_text_and_attempt_ids(tmp_path, error):
    text = structured_answer()
    plan, project, client, runner = setup(tmp_path, [message(text), probe()], error)
    result = runner.run(project, plan['models']['plain'], True, 'later-failure', response_mode='json_schema')
    assert result['status'] == 'failed' and result['api_attempt_ids'] == [0, 1]
    assert [row['status'] for row in client.records] == ['completed', 'failed']
    assert_unfinished(result, project, text)


def test_incomplete_later_response_preserves_both_texts_for_independent_interpretation(tmp_path):
    first, second = 'Ready, pending the probe.', 'The probe contradicts that conclusion.'
    plan, project, client, runner = setup(tmp_path, [message(first), probe()], ([message(second)], 'incomplete'))
    result = runner.run(project, plan['models']['plain'], True, 'later-incomplete')
    assert result['status'] == 'incomplete' and result['api_attempt_ids'] == [0, 1]
    assert result['response_texts'] == [first, second]
    assert_unfinished(result, project, first + '\n\n' + second)


def test_complete_final_answer_overrides_earlier_text_and_is_the_only_file_effect(tmp_path):
    first, final = structured_answer(), structured_answer('not_ready', 'final.md')
    plan, project, client, runner = setup(tmp_path, [message(first), probe()], [message(final)])
    result = runner.run(project, plan['models']['plain'], True, 'complete-final', response_mode='json_schema')
    assert result['status'] == 'submitted' and result['raw_answer'] == final
    assert result['answer']['decision'] == 'not_ready'
    assert result['annotation']['status'] == 'pending'
    assert result['response_texts'] == [first, final] and result['api_attempt_ids'] == [0, 1]
    assert not (project.workspace / 'unfinished.md').exists()
    assert (project.workspace / 'final.md').read_text() == 'Keep only a complete final response.'
    assert (project.workspace / 'latest-answer.md').read_text() == final


def test_empty_terminal_response_cannot_discard_text_from_a_previous_tool_response(tmp_path):
    text = 'The service is ready.'
    plan, project, client, runner = setup(tmp_path, [message(text), probe()], [])
    result = runner.run(project, plan['models']['plain'], True, 'empty-final')
    assert result['status'] == 'incomplete' and result['error']['type'] == 'MissingFinalAnswer'
    assert result['api_attempt_ids'] == [0, 1]
    assert_unfinished(result, project, text)


@pytest.mark.parametrize('failure', ['preparation', 'request'])
def test_confirmed_pre_request_failure_records_empty_attempt_list(tmp_path, monkeypatch, failure):
    plan, project, client, runner = setup(tmp_path)
    model = {**plan['models']['plain'], 'supports_structured_output': False}
    if failure == 'preparation':
        def fail(*args, **kwargs):
            raise ValueError('Prompt preparation failed')
        monkeypatch.setattr(runner.prompts, 'prepare', fail)
    result = runner.run(project, model, False, 'no-transmission', response_mode='json_schema')
    assert result['status'] == 'failed'
    assert result['api_attempt_ids'] == [] and client.records == []


def test_reused_session_identifier_does_not_capture_prior_invocations_attempts(tmp_path):
    final = structured_answer()
    plan, project, client, runner = setup(tmp_path, [message(final)], [message(final)])
    first = runner.run(project, plan['models']['plain'], False, 'same-id', response_mode='json_schema')
    project.set_session(1)
    second = runner.run(project, plan['models']['plain'], False, 'same-id', response_mode='json_schema')
    assert first['api_attempt_ids'] == [0] and second['api_attempt_ids'] == [1]
