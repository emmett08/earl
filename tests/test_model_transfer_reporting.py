"""Independent arithmetic for task uncertainty and cumulative model expenditure."""
from pathlib import Path
import copy
import json
import subprocess
import sys

from experiments.model_transfer.design import AssignmentSchedule, load_plan
from experiments.model_transfer.reporting import ReportBuilder
from experiments.model_transfer.resources import ResourceSummary


def fixture():
    plan = load_plan(Path('experiments/model_transfer/plan.json'))
    plan.update(cases=['fresh_positive'], repetitions=1)
    rows, calls = [], []
    for allocation in AssignmentSchedule(plan).allocations():
        sessions = []
        for index in range(3):
            sid = f"{allocation['sequence_id']}.session-{index}"
            attempt = len(calls)
            sessions.append({'session_id': sid, 'session': index, 'elapsed_seconds': 1,
                             'api_attempt_ids': [attempt],
                             'events': [], 'format_valid': None, 'annotation': {'status': 'automatic'},
                             'score': {'task_match': True, 'grounded_match': None}})
            tokens = (300 if index == 0 else 10) if allocation['arm'] == 'eal' else 100
            calls.append({'session_id': sid, 'attempt': attempt, 'status': 'completed',
                          'cost_estimate_usd': tokens / 1e6,
                          'charged_or_reserved_usd': tokens / 1e6,
                          'response': {'usage': {'input_tokens': tokens, 'output_tokens': 0}}})
        rows.append({**allocation, 'cohort': 'diagnostic', 'status': 'complete',
                     'setup_seconds': .5, 'sessions': sessions})
    return plan, rows, calls


def test_cumulative_resources_include_initial_overhead_without_extrapolation():
    plan, rows, calls = fixture()
    report = ReportBuilder(plan).build(rows, calls, None)
    assert report['status'] == 'complete'
    assert all(p['resource_differences']['input_tokens'] == -90 for p in report['paired_comparisons'])
    assert {p['through_session']: p['resource_differences']['input_tokens']
            for p in report['cumulative_comparisons']} == {1: 110, 2: 20}
    assert all(p['recipient_task_difference'] == 0 for p in report['cumulative_comparisons'])
    cell = report['summaries'][0]
    assert cell['task_rate_bounds'] == [1, 1]
    assert cell['diagnostics']['grounded_match']['rate_bounds'] == [0, 1]
    assert cell['format_assessed'] == cell['format_failures'] == 0
    assert cell['cost_per_task_answer_usd'] is not None
    assert report['resources']['eal']['total']['elapsed_with_setup_seconds'] == 28


def test_pending_answers_remain_unknown_without_erasing_resource_measurements():
    plan, rows, calls = fixture()
    row = next(r for r in rows if r['arm'] == 'eal')
    row['sessions'][1]['score']['task_match'] = None
    row['sessions'][1]['annotation']['status'] = 'ambiguous'
    report = ReportBuilder(plan).build(rows, calls, None)
    assert report['status'] == 'pending_annotation'
    assert report['execution_status'] == 'complete'
    cell = next(s for s in report['summaries'] if s['arm'] == 'eal' and s['session'] == 1 and
                s['receiver'] == row['receiver'] and s['native_tools'] == row['native_tools'])
    assert cell['task_match'] == 1 and cell['task_unknown'] == 1
    assert cell['task_rate_bounds'] == [.5, 1]
    assert cell['pending_annotation'] == 1
    assert cell['cost_per_task_answer_usd'] is None
    pair = next(p for p in report['paired_comparisons'] if p['pair_id'] == row['pair_id'] and p['session'] == 1)
    assert pair['task_difference'] is None
    assert pair['resource_differences']['input_tokens'] == -90


def test_missing_sessions_cannot_create_zero_cost_cumulative_savings():
    plan, rows, calls = fixture()
    row = next(r for r in rows if r['arm'] == 'eal')
    row['sessions'].pop()
    row['status'] = 'stopped'
    report = ReportBuilder(plan).build(rows, calls, 'interrupted')
    pair = next(p for p in report['cumulative_comparisons'] if p['pair_id'] == row['pair_id'] and p['through_session'] == 2)
    assert pair['resource_differences']['known_cost_usd'] is None
    assert pair['resource_differences']['input_tokens'] is None


def test_missing_reasoning_and_cache_breakdowns_are_unknown_not_zero():
    plan, rows, calls = fixture()
    report = ReportBuilder(plan).build(rows, calls, None)
    resource = report['resources']['eal']['total']
    assert resource['token_usage_complete']
    assert not resource['reasoning_usage_complete'] and not resource['cached_usage_complete']
    for pair in report['paired_comparisons']:
        assert pair['resource_differences']['reasoning_tokens'] is None
        assert pair['resource_differences']['cached_input_tokens'] is None
        assert pair['resource_differences']['input_tokens'] == -90


def test_missing_ledger_cannot_turn_answered_sessions_into_zero_cost_success(tmp_path):
    plan, rows, _ = fixture()
    (tmp_path / 'plan.json').write_text(json.dumps(plan))
    (tmp_path / 'rows.json').write_text(json.dumps(rows))
    subprocess.run([sys.executable, '-m', 'experiments.model_transfer.analyse', str(tmp_path)], check=True)
    report = json.loads((tmp_path / 'analysis.json').read_text())
    assert report['status'] == 'incomplete_accounting'
    assert report['execution_status'] == 'complete'
    assert report['estimated_cost_usd'] is None and report['known_cost_usd'] == 0
    assert not report['accounting_complete']
    assert not report['accounting']['token_usage_complete']
    assert report['accounting']['expected_api_attempts'] > 0
    assert all(cell['cost_per_task_answer_usd'] is None for cell in report['summaries'])
    for pair in report['paired_comparisons']:
        assert pair['task_difference'] == 0
        assert all(pair['resource_differences'][key] is None
                   for key in ('api_attempts', 'known_cost_usd', 'input_tokens', 'output_tokens'))


def test_selectively_missing_calls_cannot_create_eal_savings():
    plan, rows, calls = fixture()
    eal_ids = {session['session_id'] for row in rows if row['arm'] == 'eal' for session in row['sessions']}
    calls = [call for call in calls if call['session_id'] not in eal_ids]
    report = ReportBuilder(plan).build(rows, calls, None)
    assert report['status'] == 'incomplete_accounting'
    assert report['known_cost_usd'] > 0 and report['estimated_cost_usd'] is None
    for pair in report['paired_comparisons'] + report['cumulative_comparisons']:
        assert all(pair['resource_differences'][key] is None
                   for key in ('api_attempts', 'known_cost_usd', 'input_tokens', 'output_tokens'))


def test_reconciliation_detects_duplicates_misattribution_and_missing_receipts():
    _, rows, calls = fixture()
    session = rows[0]['sessions'][0]
    call = calls[0]
    defects = [([session], [call, copy.deepcopy(call)]),
               ([session], [{**call, 'session_id': 'different'}]),
               ([{key: value for key, value in session.items() if key != 'api_attempt_ids'}], [call]),
               ([{**session, 'api_attempt_ids': [call['attempt'], call['attempt']]}], [call]),
               ([session], [{key: value for key, value in call.items() if key != 'attempt'}]),
               ([session, session], [call])]
    for sessions, records in defects:
        result = ResourceSummary().summarise(sessions, records)
        assert not result['api_accounting_complete']
        assert not result['cost_accounting_complete'] and not result['token_usage_complete']
        assert result['accounting_errors']


def test_explicit_zero_attempt_receipt_is_distinct_from_missing_data():
    session = {'session_id': 'pre-request-stop', 'elapsed_seconds': .1, 'api_attempt_ids': [],
               'status': 'failed', 'answer': None, 'response_texts': [], 'raw_answer': ''}
    result = ResourceSummary().summarise([session], [])
    assert result['accounting_complete'] and result['expected_api_attempts'] == 0
    assert result['api_attempts'] == result['known_cost_usd'] == result['input_tokens'] == 0
    assert result['reasoning_usage_complete'] and result['cached_usage_complete']
    del session['api_attempt_ids']
    result = ResourceSummary().summarise([session], [])
    assert not result['accounting_complete'] and result['expected_api_attempts'] is None


def test_zero_attempt_receipt_cannot_contradict_recorded_response():
    session = {'session_id': 'reported-zero', 'elapsed_seconds': .1, 'api_attempt_ids': []}
    for evidence in ({'provider_status': 'completed'}, {'provider_status': None},
                     {'status': 'submitted'}, {'raw_answer': 'The service is ready.'},
                     {'response_texts': ['The service is ready.']}, {'answer': {'decision': 'ready'}},
                     {'answer': {}}):
        result = ResourceSummary().summarise([{**session, **evidence}], [])
        assert not result['api_accounting_complete']
        assert not result['cost_accounting_complete'] and not result['token_usage_complete']
        assert result['expected_api_attempts'] is None
        assert result['accounting_errors'] == [
            {'kind': 'zero_attempt_receipt_contradicts_response', 'session_id': 'reported-zero'}]


def test_interrupted_and_unassigned_requests_retain_reservations():
    plan, rows, calls = fixture()
    row = rows[0]
    session = row['sessions'].pop()
    interrupted = next(call for call in calls if call['session_id'] == session['session_id'])
    interrupted.update(status='started', cost_estimate_usd=None, charged_or_reserved_usd=.02)
    interrupted.pop('response')
    orphan = {'attempt': len(calls), 'session_id': 'unassigned', 'cost_estimate_usd': None,
              'charged_or_reserved_usd': .03, 'status': 'started'}
    calls.append(orphan)
    row['status'] = 'stopped'
    report = ReportBuilder(plan).build(rows, calls, 'interrupted')
    assert report['status'] == 'partial' and not report['accounting_complete']
    assert report['api_attempts'] == len(calls) and report['unknown_cost_attempts'] == 2
    assert report['charged_or_reserved_usd'] == sum(call['charged_or_reserved_usd'] for call in calls)
    assert report['estimated_cost_usd'] is None
    kinds = {error['kind'] for error in report['accounting']['accounting_errors']}
    assert 'missing_or_duplicate_session_result' in kinds and 'unassigned_attempt' in kinds
