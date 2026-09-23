"""Coverage selection must retain failures and reject ambiguous replacement data."""
from pathlib import Path
import runpy

import pytest


@pytest.fixture
def select(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / 'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    return runpy.run_path(str(scripts / 'analyse_relay_blocks.py'))['select_blocks']


def row(block, condition, reason='finished', correct=True):
    return {'block_id': block, 'condition_id': condition, 'score': {'correct': correct},
            'report': {'stop_reason': reason, 'attempts': [{}]}}


def test_coverage_selection_retains_failed_attempts(select):
    schedule = [row(block, condition) for block in ('a', 'b') for condition in ('x', 'y')]
    first = [row('a', 'x'), row('a', 'y', 'repair_budget_exhausted', False),
             row('b', 'x'), row('b', 'y', 'campaign_cost_unverifiable', False)]
    second = [row('b', 'x', correct=False), row('b', 'y', correct=False)]
    chosen, missing = select(schedule, {'first': first, 'second': second})
    assert not missing
    assert chosen['a'][0] == 'first' and not chosen['a'][1][1]['score']['correct']
    assert chosen['b'] == ('second', second)


def test_partial_coverage_remains_missing(select):
    schedule = [row('a', 'x'), row('a', 'y')]
    chosen, missing = select(schedule, {'partial': [row('a', 'x')]})
    assert not chosen and missing == ['a']


def test_duplicate_complete_blocks_are_not_cherry_picked(select):
    schedule = [row('a', 'x')]
    with pytest.raises(ValueError, match='Multiple fully attempted'):
        select(schedule, {'first': [row('a', 'x', correct=False)], 'second': [row('a', 'x')]})
