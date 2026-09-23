"""Missing-block selection preserves canonical identities and never selects outcomes."""
import importlib.util
from pathlib import Path
import sys

import pytest

_scripts = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(_scripts))
_spec = importlib.util.spec_from_file_location('relay_remaining', _scripts / 'run_relay_remaining.py')
module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(module)


def test_filter_preserves_identity_order_and_all_conditions():
    schedule = [{'block_id': block, 'condition_id': condition, 'schedule_index': i}
                for i, (block, condition) in enumerate([
                    ('a/repeat-0', 'x'), ('a/repeat-0', 'y'),
                    ('a/repeat-1', 'x'), ('a/repeat-1', 'y')])]
    result = module.select_schedule(schedule, ['a/repeat-1'])
    assert result == schedule[2:]
    assert result[0] is schedule[2]


@pytest.mark.parametrize('blocks', [[], ['missing'], ['a', 'a']])
def test_invalid_selection_fails(blocks):
    with pytest.raises(ValueError):
        module.select_schedule([{'block_id': 'a'}], blocks)


def test_schedule_adapter_is_restored_after_failure():
    original = module.relay.make_schedule
    with pytest.raises(RuntimeError):
        with module.selected_schedule(['a']):
            assert module.relay.make_schedule is not original
            raise RuntimeError('interrupted before generation')
    assert module.relay.make_schedule is original
