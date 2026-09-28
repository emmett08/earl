"""Independent arithmetic for task uncertainty and cumulative model expenditure."""
from pathlib import Path

from experiments.model_transfer.design import AssignmentSchedule, load_plan
from experiments.model_transfer.reporting import ReportBuilder


def fixture():
    plan = load_plan(Path('experiments/model_transfer/plan.json'))
    plan.update(cases=['fresh_positive'], repetitions=1)
    rows, calls = [], []
    for allocation in AssignmentSchedule(plan).allocations():
        sessions = []
        for index in range(3):
            sid = f"{allocation['sequence_id']}.session-{index}"
            sessions.append({'session_id': sid, 'session': index, 'elapsed_seconds': 1,
                             'events': [], 'format_valid': None, 'annotation': {'status': 'automatic'},
                             'score': {'task_match': True, 'grounded_match': None}})
            tokens = (300 if index == 0 else 10) if allocation['arm'] == 'eal' else 100
            calls.append({'session_id': sid, 'cost_estimate_usd': tokens / 1e6,
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
