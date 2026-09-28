"""Verification of measurement validity; scripted replies are not model evidence."""
import copy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from experiments.model_transfer.answers import AnswerParser
from experiments.model_transfer.calibration import ContractCalibration
from experiments.model_transfer.cases import CASES, Case, FIRST, EARLY
from experiments.model_transfer.design import AssignmentSchedule, load_plan
from experiments.model_transfer.project import Project
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
            output = [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(self.final)}]}]
        return {'model': payload['model'], 'status': 'completed', 'output': output,
                'usage': {'input_tokens': 80, 'output_tokens': 30,
                          'output_tokens_details': {'reasoning_tokens': 10 if 'reasoning' in payload else 0}}}


def small_plan():
    return {**load_plan(PLAN), 'cases': ['fresh_positive', 'refresh_negative'],
            'repetitions': 1, 'arms': ['ordinary', 'eal', 'eal_fresh']}


def test_schedule_crosses_donors_repeats_and_preserves_pairs():
    plan = load_plan(PLAN)
    allocations = AssignmentSchedule(plan).allocations()
    assert len(allocations) == 256
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
    assert [scorer.reference(c, 1)['decision'] for c in CASES] == [
        'ready', 'not_ready', 'ready', 'not_ready', 'undetermined', 'undetermined', 'ready', 'not_ready']
    check = ContractCalibration().check(load_plan(PLAN))
    assert check['status'] == 'passed'
    assert len(check['checks']) == 24


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
    context = json.loads(project.context('Assess')[0]['content'].split('\n', 1)[1])
    assert context['assumptions']['window']['time_status'] == 'expired'
    assert context['claim_status'] == 'unsupported'


def test_negative_measurements_remain_available_and_output_both_findings(tmp_path):
    project = Project(tmp_path, CASES[1], 'eal')
    context = json.loads(project.context('Assess')[0]['content'].split('\n', 1)[1])
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
    context = json.loads(project.context('Assess now')[0]['content'].split('\n', 1)[1])
    assert context['arguments']['result']['method_result']['outputs']['fails'] is True
    assert context['assessed_at'].startswith('2026-09-28T10:10:00')
    assert '180' in project.files()['notes.md']
    assert set(project.files()) == {'specification.txt', 'notes.md'}


def test_complete_pipeline_retains_fresh_sessions_native_masks_and_all_stages(tmp_path):
    plan = small_plan()
    transport = ScriptedTransport(answer(files=[{'name': 'notes.md', 'content': 'Naturally produced fixture note.'}]))
    report = Pilot(plan, tmp_path, transport).run()
    assert report['status'] == 'complete'
    assert report['planned_sequences'] == 48 and report['planned_sessions'] == 144
    rows, calls = read_json(tmp_path / 'rows.json'), read_json(tmp_path / 'calls.json')
    assert len(report['paired_comparisons']) == 64
    assert report['resources']['eal']['recipients']['host_reuses'] == 24
    assert report['resources']['eal']['recipients']['host_collections'] == 8
    assert report['resources']['eal_fresh']['recipients']['host_collections'] == 32
    for row in rows:
        assert len(row['sessions']) == 3
        for session in row['sessions'][1:]:
            selected = [c for c in calls if c['session_id'] == session['session_id']]
            request = selected[0]['request']
            assert bool(request.get('tools')) == row['native_tools']
            assert not any(x.get('type') in ('function_call', 'function_call_output', 'reasoning') for x in request['input'])
            assert 'Naturally produced fixture note.' in json.dumps(request['input'])
            assert 'Synthetic response for harness checks.' not in json.dumps(request['input'])
            assert 'collector-state.json' not in json.dumps(request['input'])
            assert request['text']['format']['strict'] is True
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
    assert rebuilt == {k: v for k, v in report.items() if k != 'created_at'}


def test_bad_optional_file_does_not_change_correct_answer(tmp_path):
    plan = load_plan(PLAN)
    project = Project(tmp_path / 'sequence', CASES[0], 'ordinary')
    original = project.files()['specification.txt']
    client = BudgetedClient(tmp_path, plan, ScriptedTransport(answer(files=[{'name': 'specification.txt', 'content': 'bad'}])))
    result = SessionRunner(client, plan).run(project, plan['models']['plain'], False, 'file-error')
    assert result['status'] == 'submitted'
    assert result['file_result']['status'] == 'rejected'
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
    assert report['status'] == 'partial' and len(rows) == 48
    assert sum(r['status'] == 'stopped' for r in rows) == 1
    assert sum(r['status'] == 'not_run' for r in rows) == 47
    assert sum(len(r['sessions']) for r in rows) == 1
    assert report['api_attempts'] == report['unknown_cost_attempts'] == 1
    assert all(s['grounded_rate_bounds'] == [0, 1] for s in report['summaries'])
    assert all(p['grounded_difference'] is None for p in report['paired_comparisons'])


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
    assert result['status'] == 'failed' and result['answer'] is None
    assert client.records[0]['cost_estimate_usd'] > 0


def test_calibration_failure_is_recorded_before_provider_use(monkeypatch):
    import experiments.model_transfer.calibration as module
    def broken(*args, **kwargs):
        raise ValueError('Invalid source fixture')
    monkeypatch.setattr(module, 'Project', broken)
    result = ContractCalibration().check(small_plan())
    assert result['status'] == 'failed'
    assert len(result['checks']) == 2
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
    assert all(p['grounded_difference'] == 1 for p in report['paired_comparisons'])
    assert all(s['mean_grounded_difference'] == 1 for s in report['case_summaries'])
    for row in rows:
        for s in row['sessions']:
            s['score']['grounded_match'] = True
    zero = ReportBuilder(plan).build(rows, [], None)
    assert all(p['grounded_difference'] == 0 for p in zero['paired_comparisons'])
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
    assert cell['cost_per_grounded_answer_usd'] is None
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
