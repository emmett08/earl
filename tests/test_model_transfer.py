"""Verification of measurement validity; scripted replies are not model evidence."""
import copy
from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest

from experiments.model_transfer.answers import AnswerParser, response_format
from experiments.model_transfer.annotations import AnnotationExchange
from experiments.model_transfer.calibration import ContractCalibration
from experiments.model_transfer.cases import CASES, CALIBRATION_CASES, Case, FIRST, EARLY
from experiments.model_transfer.design import AssignmentSchedule, load_plan
from experiments.model_transfer.project import Project
from experiments.model_transfer.prompts import SessionPromptBuilder
from experiments.model_transfer.provider import BudgetedClient, ExecutionStopped
from experiments.model_transfer.reporting import ReportBuilder
from experiments.model_transfer.resources import ResourceSummary
from experiments.model_transfer.runner import Pilot
from experiments.model_transfer.scoring import ReferenceScorer
from experiments.model_transfer.session import SessionRunner
from experiments.transfer_study.workspace import read_json

PLAN = Path(__file__).resolve().parents[1] / 'experiments/model_transfer/plan.json'


def answer(**overrides):
    return {'decision': 'ready', 'basis': 'criterion_met', 'reading': 180,
            'observed_at': FIRST, 'explanation': 'Synthetic response for harness checks.',
            'files': [], **overrides}


class ScriptedTransport:
    def __init__(self, final=None):
        self.requests = []
        self.final = answer() if final is None else final

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
            text = self.final if isinstance(self.final, str) else json.dumps(self.final)
            output = [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}]
        return {'model': payload['model'], 'status': 'completed', 'output': output,
                'usage': {'input_tokens': 80, 'output_tokens': 30,
                          'output_tokens_details': {'reasoning_tokens': 10 if 'reasoning' in payload else 0}}}


def small_plan():
    return {**load_plan(PLAN), 'cases': ['fresh_positive', 'refresh_negative'],
            'repetitions': 1, 'recipient_sessions': 2, 'workers': 1, 'arms': ['ordinary', 'eal']}


def test_schedule_crosses_donors_repeats_and_preserves_pairs():
    plan = load_plan(PLAN)
    allocations = AssignmentSchedule(plan).allocations()
    assert len(allocations) == len(plan['cases']) * 2 * 2 * 2 * plan['repetitions'] * 2
    assert allocations == AssignmentSchedule(plan).allocations()
    assert len({r['sequence_id'] for r in allocations}) == len(allocations)
    for case in plan['cases']:
        assert {r['donor'] for r in allocations if r['case'] == case} == {'plain', 'reasoning'}
    for pair in {r['pair_id'] for r in allocations}:
        block = [r for r in allocations if r['pair_id'] == pair]
        assert {r['arm'] for r in block} == {'ordinary', 'eal'}
        assert len({(r['case'], r['donor'], r['receiver'], r['native_tools'], r['repeat']) for r in block}) == 1


def test_independent_oracles_and_complete_context_calibration():
    scorer = ReferenceScorer()
    assert [scorer.reference(c, 1)['decision'] for c in CALIBRATION_CASES] == [
        'ready', 'not_ready', 'ready', 'not_ready', 'undetermined', 'undetermined', 'ready', 'not_ready']
    check = ContractCalibration().check({**load_plan(PLAN), 'recipient_sessions': 2,
                                        'cases': [case.identifier for case in CALIBRATION_CASES]})
    assert check['status'] == 'passed'
    assert len([c for c in check['checks'] if c['kind'] == 'task_outcome']) == 24
    assert len([c for c in check['checks'] if c['kind'] == 'source_mutation']) == 7
    assert len([c for c in check['checks'] if c['kind'] == 'boundary']) == 10


@pytest.mark.parametrize('offset,basis', [(299, 'criterion_met'), (300, 'criterion_met'), (301, 'stale_measurement')])
def test_freshness_boundaries_are_independent_of_eal(offset, basis):
    from datetime import timedelta
    from experiments.model_transfer.scoring import instant
    class BoundaryCase(Case):
        def time(self, session):
            return (instant(FIRST) + timedelta(seconds=offset)).isoformat()
        def measurement(self, session):
            return {'value': {'reading': 200}, 'observed_at': FIRST}
    assert ReferenceScorer().reference(BoundaryCase('boundary', 200, 200, EARLY), 1)['basis'] == basis


def test_assumption_end_is_exclusive_and_threshold_equality_is_inclusive(tmp_path):
    case = replace(CASES[0], initial_reading=200, later_reading=200, assumption_until=EARLY)
    assert ReferenceScorer().reference(case, 0)['decision'] == 'ready'
    assert ReferenceScorer().reference(case, 1)['basis'] == 'assumption_expired'
    project = Project(tmp_path, case, 'eal')
    project.context('Assess')
    project.set_session(1)
    context = json.loads(project.context('Assess')[1]['content'].split('\n', 1)[1])
    assert context['assumptions']['window']['time_status'] == 'expired'
    assert context['claim_status'] == 'unsupported'


def test_negative_measurements_remain_available_and_output_both_findings(tmp_path):
    project = Project(tmp_path, CASES[1], 'eal')
    context = json.loads(project.context('Assess')[1]['content'].split('\n', 1)[1])
    assert context['claim_status'] == 'supported'
    assert context['evidence']['report']['status'] == 'available'
    outputs = context['arguments']['result']['method_result']['outputs']
    assert outputs == {'reading': 240, 'threshold': 200, 'meets': False, 'fails': True}
    project.set_session(1)
    project.context('Assess again')
    assessment = project.events[-1]['assessment']
    assert assessment['reused_count'] == 1 and assessment['collected_count'] == 0


def test_current_context_retains_negative_result_alongside_natural_stale_notes(tmp_path):
    project = Project(tmp_path, CASES[3], 'eal')
    project.context('Assess')
    project.persist([{'name': 'notes.md', 'content': 'At 10:00 the service was ready with reading 180.'}])
    project.set_session(1)
    context = json.loads(project.context('Assess now')[1]['content'].split('\n', 1)[1])
    assert context['arguments']['result']['method_result']['outputs']['fails'] is True
    assert context['assessed_at'].startswith('2026-09-28T10:10:00')
    assert '180' in project.files()['notes.md']
    assert set(project.files()) == {'specification.txt', 'notes.md'}


def test_complete_pipeline_retains_fresh_sessions_native_masks_and_all_stages(tmp_path):
    plan = small_plan()
    transport = ScriptedTransport('The service is ready.')
    report = Pilot(plan, tmp_path, transport).run()
    assert report['status'] == 'complete'
    assert report['planned_sequences'] == 32 and report['planned_sessions'] == 96
    rows, calls = read_json(tmp_path / 'rows.json'), read_json(tmp_path / 'calls.json')
    assert len(report['paired_comparisons']) == 32
    assert report['resources']['eal']['recipients']['host_reuses'] == 24
    assert report['resources']['eal']['recipients']['host_collections'] == 8
    for row in rows:
        assert len(row['sessions']) == 3
        for session in row['sessions'][1:]:
            selected = [c for c in calls if c['session_id'] == session['session_id']]
            request = selected[0]['request']
            assert bool(request.get('tools')) == row['native_tools']
            assert not any(x.get('type') in ('function_call', 'function_call_output', 'reasoning') for x in request['input'])
            if row['arm'] == 'ordinary':
                assert 'The service is ready.' in json.dumps(request['input'])
                assert 'latest-answer.md' in json.dumps(request['input'])
                assert 'specification.txt' in json.dumps(request['input'])
            else:
                assert 'The service is ready.' not in json.dumps(request['input'])
                assert 'latest-answer.md' not in json.dumps(request['input'])
                assert 'specification.txt' not in json.dumps(request['input'])
            assert 'Synthetic response for harness checks.' not in json.dumps(request['input'])
            assert 'collector-state.json' not in json.dumps(request['input'])
            assert 'text' not in request
            assert session['format_valid'] is None
            assert session['annotation']['status'] == 'automatic'
            if row['receiver'] == 'reasoning':
                assert request['include'] == ['reasoning.encrypted_content']
    assert report['charged_or_reserved_usd'] <= 2
    assert len((tmp_path / 'calls.jsonl').read_text().splitlines()) == 2 * len(calls)
    from experiments.model_transfer.journal import AttemptJournal
    assert AttemptJournal(tmp_path).read() == calls
    (tmp_path / 'plan.json').write_text(json.dumps(plan))
    import subprocess
    import sys
    subprocess.run([sys.executable, '-m', 'experiments.model_transfer.analyse', str(tmp_path)], check=True)
    rebuilt = read_json(tmp_path / 'analysis.json')
    rebuilt.pop('interpretation')
    assert rebuilt.pop('rows_source') == str(tmp_path / 'rows.json')
    # Offline reconstruction adds measurement and processor identity without
    # changing any of the retained collection report's scientific results.
    annotation = rebuilt.pop('annotation_provenance')
    assert annotation['session_counts'] == {'automatic': 96}
    assert annotation['contains_ai_assessment'] is False
    assert annotation['assessors'] == []
    processing = rebuilt.pop('processing_provenance')
    from eal import __version__
    from experiments.model_transfer.run_state import implementation_digest
    import os
    assert processing['package_version'] == __version__
    assert processing['implementation_sha256'] == implementation_digest()
    assert processing['revision'] == os.environ.get('GITHUB_SHA')
    assert processing['python'] == sys.version
    assert rebuilt == {k: v for k, v in report.items() if k != 'created_at'}


def test_bad_optional_file_does_not_change_correct_answer(tmp_path):
    plan = load_plan(PLAN)
    project = Project(tmp_path / 'sequence', CASES[0], 'ordinary')
    original = project.files()['specification.txt']
    client = BudgetedClient(tmp_path, plan, ScriptedTransport(answer(files=[{'name': 'specification.txt', 'content': 'bad'}])))
    result = SessionRunner(client, plan).run(project, plan['models']['plain'], False, 'file-error',
                                            response_mode='json_schema')
    assert result['status'] == 'submitted'
    assert result['file_result']['status'] == 'rejected'
    assert ReferenceScorer().score(CASES[0], 0, result)['task_match'] is None
    result['annotation'] = {'status': 'human', 'annotator': 'fixture-coder'}
    assert ReferenceScorer().score(CASES[0], 0, result)['grounded_match']
    assert project.files()['specification.txt'] == original


@pytest.mark.parametrize('files', [[{'name': '../answer.md', 'content': 'bad'}],
                                   [{'name': 'argument.eal', 'content': 'bad'}],
                                   [{'name': 'ok.md', 'content': 'ok'}, {'name': 'tools.toml', 'content': 'bad'}]])
def test_file_batch_validation_precedes_any_write(tmp_path, files):
    project = Project(tmp_path, CASES[0], 'ordinary')
    assert project.persist(files)['status'] == 'rejected'
    assert set(project.files()) == {'specification.txt'}


def test_scoring_distinguishes_false_assertion_abstention_basis_and_grounding():
    scorer = ReferenceScorer()
    wrong = {'answer': answer(decision='ready', basis='measurement_missing')}
    score = scorer.score(CASES[1], 1, wrong)
    assert score['false_definitive'] and not score['internally_consistent']
    abstained = scorer.score(CASES[1], 1, {'answer': answer(decision='undetermined', basis='evidence_unavailable')})
    assert abstained['abstention_when_reference_decisive'] and not abstained['false_definitive']
    wrong_fact = scorer.score(CASES[0], 1, {'answer': answer(reading=179)})
    assert wrong_fact['decision_and_basis_match'] and not wrong_fact['grounded_match']
    missing = scorer.score(CASES[4], 1, {'answer': answer(decision='undetermined', basis='measurement_missing', reading=None, observed_at=None)})
    assert missing['grounded_match']
    assert scorer.score(CASES[0], 1, {'answer': None})['no_answer']


def test_parser_separates_content_from_file_schema_without_prose_salvage():
    parsed = AnswerParser().parse(json.dumps(answer(files={'bad': 'mapping'})))
    assert parsed['answer']['decision'] == 'ready' and not parsed['format_valid']
    with pytest.raises(json.JSONDecodeError):
        AnswerParser().parse('Answer follows: ' + json.dumps(answer()))


def test_budget_records_request_before_send_and_reserves_unknown_cost(tmp_path):
    class Failing:
        calls = 0
        def send(self, payload, timeout):
            self.calls += 1
            assert json.loads((tmp_path / 'calls.jsonl').read_text().splitlines()[0])['event'] == 'started'
            raise ExecutionStopped('Provider unavailable')
    plan, transport = load_plan(PLAN), Failing()
    client = BudgetedClient(tmp_path, plan, transport)
    with pytest.raises(ExecutionStopped, match='unavailable'):
        client.request(plan['models']['plain'], [{'role': 'user', 'content': 'test'}], [], 'session')
    row = client.records[0]
    assert row['status'] == 'failed' and row['cost_estimate_usd'] is None
    client.plan['budget_usd'] = row['reserved_usd']
    with pytest.raises(ExecutionStopped, match='budget exhausted'):
        client.request(plan['models']['plain'], [], [], 'session')
    assert transport.calls == 1


def test_fatal_provider_failure_preserves_attempt_and_planned_denominators(tmp_path):
    class Failing:
        def send(self, payload, timeout):
            raise ExecutionStopped('Provider HTTP 401')
    report = Pilot(small_plan(), tmp_path, Failing()).run()
    rows = read_json(tmp_path / 'rows.json')
    assert report['status'] == 'partial' and len(rows) == 32
    assert sum(r['status'] == 'stopped' for r in rows) == 1
    assert sum(r['status'] == 'not_run' for r in rows) == 31
    assert sum(len(r['sessions']) for r in rows) == 1
    assert report['api_attempts'] == report['unknown_cost_attempts'] == 1
    assert all(s['task_rate_bounds'] == [0, 1] for s in report['summaries'])
    assert all(p['task_difference'] is None for p in report['paired_comparisons'])


def test_resource_count_includes_host_and_native_calls_without_fake_cost_precision():
    sessions = [{'session_id': 'one', 'elapsed_seconds': 2, 'events': [
        {'kind': 'eal_assess', 'assessment': {'collected_count': 1, 'reused_count': 0}},
        {'kind': 'native_probe'}]}]
    summary = ResourceSummary().summarise(sessions, [{'session_id': 'one', 'cost_estimate_usd': None}])
    assert summary['total_collector_calls'] == 2 and summary['unknown_cost_attempts'] == 1


def test_incomplete_response_keeps_usage_and_no_answer(tmp_path):
    class Incomplete:
        def send(self, payload, timeout):
            return {'model': payload['model'], 'status': 'incomplete', 'output': [],
                    'usage': {'input_tokens': 80, 'output_tokens': 4096}}
    plan = load_plan(PLAN)
    project = Project(tmp_path / 'sequence', CASES[0], 'ordinary')
    client = BudgetedClient(tmp_path, plan, Incomplete())
    result = SessionRunner(client, plan).run(project, plan['models']['reasoning'], False, 'incomplete')
    assert result['status'] == 'incomplete' and result['answer'] is None
    assert result['provider_status'] == 'incomplete' and result['raw_answer'] == ''
    score = ReferenceScorer().score(CASES[0], 0, result)
    assert score['task_match'] is False and score['no_answer'] is True
    assert client.records[0]['status'] == 'incomplete'
    assert client.records[0]['cost_estimate_usd'] > 0


@pytest.mark.parametrize('mode,text', [
    ('prose', 'Ready. The measured latency is below the criterion.'),
    ('json_prompted', json.dumps(answer(files=[{'name': 'partial.md', 'content': 'Do not persist'}]))),
])
def test_incomplete_text_remains_pending_without_file_effects_or_complete_handoff(tmp_path, mode, text):
    class Incomplete:
        def send(self, payload, timeout):
            return {'model': payload['model'], 'status': 'incomplete',
                    'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}],
                    'usage': {'input_tokens': 80, 'output_tokens': 30}}

    plan = load_plan(PLAN)
    project = Project(tmp_path / 'sequence', CASES[0], 'ordinary')
    project.remember_answer('Previous complete handoff.')
    client = BudgetedClient(tmp_path, plan, Incomplete())
    result = SessionRunner(client, plan).run(project, plan['models']['plain'], False,
                                           'partial-text', response_mode=mode)
    score = ReferenceScorer().score(CASES[0], 0, result)
    assert result['status'] == 'incomplete' and result['provider_status'] == 'incomplete'
    assert result['raw_answer'] == text and result['answer'] is None
    assert result['annotation']['status'] == 'pending' and result['format_valid'] is None
    assert score['task_match'] is None and score['no_answer'] is False
    assert result['handoff']['status'] == 'not_retained'
    assert result['file_result']['status'] == 'not_requested'
    assert (project.workspace / 'latest-answer.md').read_text() == 'Previous complete handoff.'
    assert not (project.workspace / 'partial.md').exists()
    assert read_json(project.root / 'session-0.json')['raw_answer'] == text
    assert len(client.records) == 1 and client.records[0]['status'] == 'incomplete'
    assert client.records[0]['charged_or_reserved_usd'] == client.records[0]['cost_estimate_usd'] > 0


def test_incomplete_function_calls_are_retained_without_execution(tmp_path):
    class Incomplete:
        def send(self, payload, timeout):
            return {'model': payload['model'], 'status': 'incomplete',
                    'output': [{'type': 'function_call', 'name': 'probe', 'arguments': '{}', 'call_id': 'c1'},
                               {'type': 'message', 'content': [{'type': 'output_text', 'text': 'Ready.'}]}],
                    'usage': {'input_tokens': 80, 'output_tokens': 30}}

    plan = load_plan(PLAN)
    project = Project(tmp_path / 'sequence', CASES[0], 'ordinary')
    client = BudgetedClient(tmp_path, plan, Incomplete())
    result = SessionRunner(client, plan).run(project, plan['models']['plain'], True, 'partial-tool')
    assert result['raw_answer'] == 'Ready.' and result['annotation']['status'] == 'pending'
    assert not project.events
    assert len(client.records) == 1
    assert client.records[0]['response']['output'][0]['type'] == 'function_call'


@pytest.mark.parametrize('invalid', ['usage', 'output'])
def test_matched_response_validation_failure_retains_available_task_text(tmp_path, invalid):
    class Invalid:
        def send(self, payload, timeout):
            response = {'model': payload['model'], 'status': 'completed',
                        'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'Ready.'}]}],
                        'usage': {'input_tokens': 80, 'output_tokens': 30}}
            if invalid == 'usage':
                response['usage'] = None
            else:
                response['output'].append('malformed output item')
            return response

    plan = load_plan(PLAN)
    project = Project(tmp_path / 'sequence', CASES[0], 'ordinary')
    client = BudgetedClient(tmp_path, plan, Invalid())
    result = SessionRunner(client, plan).run(project, plan['models']['plain'], False, 'invalid-response')
    assert result['status'] == 'failed' and result['provider_status'] == 'completed'
    assert result['raw_answer'] == 'Ready.' and result['annotation']['status'] == 'pending'
    score = ReferenceScorer().score(CASES[0], 0, result)
    assert score['task_match'] is None and score['no_answer'] is False
    assert client.records[0]['status'] == 'failed'
    if invalid == 'usage':
        assert client.records[0]['cost_estimate_usd'] is None
        assert client.records[0]['charged_or_reserved_usd'] == client.records[0]['reserved_usd']
    else:
        assert client.records[0]['cost_estimate_usd'] > 0
    assert not (project.workspace / 'latest-answer.md').exists()


def test_wrong_model_response_remains_fatal_even_with_text_and_invalid_usage(tmp_path):
    class WrongModel:
        def send(self, payload, timeout):
            return {'model': 'different-model', 'status': 'incomplete', 'usage': None,
                    'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'Ready.'}]}]}

    plan = load_plan(PLAN)
    project = Project(tmp_path / 'sequence', CASES[0], 'ordinary')
    client = BudgetedClient(tmp_path, plan, WrongModel())
    result = SessionRunner(client, plan).run(project, plan['models']['plain'], True, 'wrong-model')
    assert 'different model snapshot' in result['stop_reason']
    assert result['status'] == 'failed' and result.get('raw_answer') is None
    assert client.records[0]['cost_estimate_usd'] is None and client.records[0]['status'] == 'failed'
    assert client.records[0]['response']['output'][0]['content'][0]['text'] == 'Ready.'
    assert not project.events


def test_calibration_failure_is_recorded_before_provider_use(monkeypatch):
    import experiments.model_transfer.calibration as module
    def broken(*args, **kwargs):
        raise ValueError('Invalid source fixture')
    monkeypatch.setattr(module, 'Project', broken)
    result = ContractCalibration().check(small_plan())
    assert result['status'] == 'failed'
    assert len(result['checks']) == 19
    assert all(c['error']['type'] == 'ValueError' for c in result['checks'])


def test_project_note_budget_applies_across_sessions(tmp_path):
    project = Project(tmp_path, CASES[0], 'ordinary')
    assert project.persist([{'name': 'first.md', 'content': 'a' * 8000}])['status'] == 'accepted'
    assert project.persist([{'name': 'second.md', 'content': 'a' * 300}])['status'] == 'rejected'
    assert 'second.md' not in project.files()


def test_journal_recovers_interrupted_attempt_without_zero_cost(tmp_path):
    from experiments.model_transfer.journal import AttemptJournal
    journal = AttemptJournal(tmp_path)
    start = {'event': 'started', 'attempt': 0, 'session_id': 'one', 'status': 'started',
             'request': {'model': 'test'}, 'cost_estimate_usd': None, 'charged_or_reserved_usd': .01}
    journal.append(start)
    with journal.path.open('a') as f:
        f.write('{"event":"finished",')
    records = journal.read()
    assert records[0]['status'] == 'started'
    assert records[0]['cost_estimate_usd'] is None
    assert records[0]['charged_or_reserved_usd'] == .01


def test_paired_analysis_detects_known_effect_and_retains_complete_denominator():
    plan = small_plan()
    rows = []
    for allocation in AssignmentSchedule(plan).allocations():
        sessions = []
        good = allocation['arm'] == 'eal'
        case = next(c for c in CASES if c.identifier == allocation['case'])
        for i in range(3):
            ref = ReferenceScorer().reference(case, i)
            a = answer(**ref) if good else answer(decision='undetermined', basis='evidence_unavailable')
            s = {'session_id': f"{allocation['sequence_id']}.session-{i}", 'session': i,
                 'answer': a, 'elapsed_seconds': 1, 'events': [], 'format_valid': True}
            s['score'] = ReferenceScorer().score(case, i, s)
            sessions.append(s)
        rows.append({**allocation, 'status': 'complete', 'cohort': 'diagnostic', 'sessions': sessions})
    report = ReportBuilder(plan).build(rows, [], None)
    assert all(p['task_difference'] == 1 for p in report['paired_comparisons'])
    assert all(s['mean_task_difference'] == 1 for s in report['case_summaries'])
    for row in rows:
        for s in row['sessions']:
            s['score']['task_match'] = True
            s['score']['decision_match'] = True
    zero = ReportBuilder(plan).build(rows, [], None)
    assert all(p['task_difference'] == 0 for p in zero['paired_comparisons'])
    with pytest.raises(ValueError, match='denominator'):
        ReportBuilder(plan).build(rows[:-1], [], None)


def test_interrupted_session_cost_is_attributed_even_without_session_result():
    plan = small_plan()
    rows = [{**r, 'cohort': 'diagnostic', 'status': 'not_run', 'sessions': []}
            for r in AssignmentSchedule(plan).allocations()]
    row = rows[0]
    calls = [{'session_id': row['sequence_id'] + '.session-1', 'cost_estimate_usd': None,
              'charged_or_reserved_usd': .01}]
    report = ReportBuilder(plan).build(rows, calls, 'interrupted')
    cell = next(s for s in report['summaries'] if (s['arm'], s['receiver'], s['native_tools'], s['session']) ==
                (row['arm'], row['receiver'], row['native_tools'], 1))
    assert cell['resources']['unknown_cost_attempts'] == 1
    assert cell['resources']['timed_sessions'] == 0
    assert cell['cost_per_task_answer_usd'] is None
    assert report['resources'][row['arm']]['total']['unknown_cost_attempts'] == 1


def test_unknown_usage_and_failed_host_assessment_are_not_fabricated_zeroes():
    sessions = [{'session_id': 'one', 'elapsed_seconds': 1, 'events': [
        {'kind': 'eal_assess', 'assessment': None}]}]
    calls = [{'session_id': 'one', 'cost_estimate_usd': None,
              'response': {'usage': {'input_tokens': None, 'output_tokens': 'unknown'}}}]
    summary = ResourceSummary().summarise(sessions, calls)
    assert not summary['token_usage_complete'] and not summary['collection_counts_complete']
    assert summary['unknown_host_assessments'] == summary['unknown_cost_attempts'] == 1
    calls[0]['response']['usage'] = 'unavailable'
    assert not ResourceSummary().summarise(sessions, calls)['token_usage_complete']


def test_partial_content_is_scored_without_conflating_explanation_format():
    parsed = AnswerParser().parse(json.dumps({'decision': 'ready', 'basis': 'criterion_met',
                                            'reading': 180, 'observed_at': FIRST}))
    assert not parsed['format_valid']
    assert parsed['annotation']['status'] == 'pending'
    parsed['annotation'] = {'status': 'human', 'annotator': 'fixture-coder'}
    score = ReferenceScorer().score(CASES[0], 0, parsed)
    assert score['grounded_match']
    assert not score['no_answer']
    assert ReferenceScorer().score(CASES[0], 0, {'answer': {'decision': []}})['no_answer']


def test_correct_abstention_does_not_excuse_an_invented_measurement():
    score = ReferenceScorer().score(CASES[5], 1, {'answer': answer(
        decision='undetermined', basis='assumption_expired', reading=999)})
    assert score['decision_and_basis_match'] and not score['grounded_match']


@pytest.mark.parametrize('text', ['{"decision":"ready","decision":"not_ready"}',
                                '{"reading":1e309}', '{"reading":NaN}'])
def test_ambiguous_or_non_finite_json_is_not_accepted(text):
    with pytest.raises(ValueError):
        AnswerParser().parse(text)


def test_compact_and_full_prompts_preserve_identical_host_decision_without_old_notes(tmp_path):
    project = Project(tmp_path / 'donor', CASES[3], 'eal')
    project.context('Initial assessment')
    project.remember_answer('The service is ready. This is the old decision at 10:00.')
    project.set_session(1)
    compact_project = project.fork(tmp_path / 'compact', 1)
    full_project = project.fork(tmp_path / 'full', 1)
    prompts = SessionPromptBuilder()
    compact = prompts.prepare(compact_project, 'Assess readiness now.', response_mode='prose',
                              context_style='compact', include_notes=False, reuse='compatible')
    full = prompts.prepare(full_project, 'Assess readiness now.', response_mode='prose',
                           context_style='full', include_notes=False, reuse='compatible')
    assert compact.task_context == full.task_context
    assert compact.task_context['decision'] == 'not_ready'
    assert compact.task_context['reading'] == 240
    assert compact.task_context['prose_verified'] is False
    assert compact.visible_files == full.visible_files == {}
    assert 'specification.txt' not in json.dumps(compact.messages)
    assert 'The service is ready. This is the old decision' not in json.dumps(compact.messages)
    assert len(json.dumps(compact.messages).encode()) < len(json.dumps(full.messages).encode())


@pytest.mark.parametrize('reasoning', ['plain', 'reasoning'])
@pytest.mark.parametrize('tools', [False, True])
def test_prose_task_responses_do_not_need_schema_support_or_native_tools(tmp_path, reasoning, tools):
    plan = load_plan(PLAN)
    profile = {**plan['models'][reasoning], 'supports_structured_output': False}
    transport = ScriptedTransport('The service is not ready. The current measurement exceeds the limit.')
    client = BudgetedClient(tmp_path, plan, transport)
    project = Project(tmp_path / 'sequence', CASES[1], 'eal')
    result = SessionRunner(client, plan).run(project, profile, tools, 'natural-response')
    assert result['status'] == 'submitted' and result['format_valid'] is None
    assert result['raw_answer'] == transport.final
    assert result['annotation']['status'] == 'pending'
    assert ReferenceScorer().score(CASES[1], 0, result)['task_match'] is None
    assert all('text' not in request for request in transport.requests)
    assert bool(transport.requests[0].get('reasoning')) == (reasoning == 'reasoning')
    assert bool(transport.requests[0].get('tools')) == tools


def test_unsupported_schema_stops_before_request_but_prompted_json_can_run(tmp_path):
    plan = load_plan(PLAN)
    profile = {**plan['models']['plain'], 'supports_structured_output': False}
    transport = ScriptedTransport()
    client = BudgetedClient(tmp_path, plan, transport)
    with pytest.raises(ValueError, match='schema-output support'):
        client.request(profile, [{'role': 'user', 'content': 'Assess'}], [], 'unsupported',
                       response_mode='json_schema')
    assert client.records == [] and transport.requests == []
    client.request(profile, [{'role': 'user', 'content': 'Assess'}], [], 'prompted',
                   response_mode='json_prompted')
    assert 'text' not in transport.requests[0]


def test_pending_primary_measurements_survive_report_and_blind_annotation_reanalysis(tmp_path):
    plan = {**small_plan(), 'cases': ['fresh_positive']}
    rows = []
    calls = []
    text = 'The service is ready. The available measurement meets the criterion.'
    parsed = response_format('prose').parse(text)
    for allocation in AssignmentSchedule(plan).allocations():
        sessions = []
        for index in range(3):
            result = {**copy.deepcopy(parsed), 'session': index,
                      'session_id': f"{allocation['sequence_id']}.session-{index}",
                      'raw_answer': text, 'elapsed_seconds': 1, 'events': [],
                      'api_attempt_ids': [len(calls)]}
            calls.append({'attempt': len(calls), 'session_id': result['session_id'],
                          'status': 'completed', 'cost_estimate_usd': .001,
                          'charged_or_reserved_usd': .001,
                          'response': {'usage': {'input_tokens': 20, 'output_tokens': 10,
                                                'input_tokens_details': {'cached_tokens': 0},
                                                'output_tokens_details': {'reasoning_tokens': 0}}}})
            result['score'] = ReferenceScorer().score(CASES[0], index, result)
            sessions.append(result)
        rows.append({**allocation, 'status': 'complete', 'cohort': 'diagnostic', 'sessions': sessions})
    report = ReportBuilder(plan).build(rows, calls, None)
    assert report['status'] == 'pending_annotation' and report['execution_status'] == 'complete'
    assert report['pending_task_annotations'] == len(rows) * 3
    assert all(cell['task_rate_bounds'] == [0, 1] for cell in report['summaries'])
    assert all(cell['format_failures'] == 0 for cell in report['summaries'])
    assert all(pair['task_difference'] is None for pair in report['paired_comparisons'])
    for name, contents in [('rows.json', rows), ('plan.json', plan),
                           ('cases.json', [asdict(CASES[0])]), ('calls.json', calls)]:
        (tmp_path / name).write_text(json.dumps(contents))
    from experiments.model_transfer.journal import AttemptJournal
    journal = AttemptJournal(tmp_path)
    for call in calls:
        journal.append({**call, 'event': 'started', 'status': 'started', 'cost_estimate_usd': None})
        journal.append({**call, 'event': 'finished'})
    raw_rows = (tmp_path / 'rows.json').read_bytes()
    exchange = AnnotationExchange()
    bundle = tmp_path / 'blinded'
    exchange.export(tmp_path, bundle)
    labels = read_json(bundle / 'items.json')
    labels['annotator'] = 'scripted assessor for software verification only'
    for item in labels['items']:
        item.update(decision='ready', quote=text, note='Synthetic coding to exercise the import path.')
    label_file = tmp_path / 'labels.json'
    label_file.write_text(json.dumps(labels))
    annotated = tmp_path / 'annotated-rows.json'
    exchange.import_labels(tmp_path, bundle, label_file, annotated)
    import subprocess
    import sys
    subprocess.run([sys.executable, '-m', 'experiments.model_transfer.analyse', str(tmp_path),
                    '--rows', str(annotated)], check=True, capture_output=True)
    reanalysed = read_json(tmp_path / 'analysis.json')
    assert reanalysed['status'] == 'complete'
    assert reanalysed['pending_task_annotations'] == 0
    assert all(cell['task_rate_bounds'] == [1, 1] for cell in reanalysed['summaries'])
    assert all(cell['diagnostics']['grounded_match']['unknown'] == cell['planned']
               for cell in reanalysed['summaries'])
    assert (tmp_path / 'rows.json').read_bytes() == raw_rows
