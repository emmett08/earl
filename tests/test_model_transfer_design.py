"""Check run identity, planned follow-up and saved randomisation contracts."""
import copy
import json
from pathlib import Path

import pytest

from experiments.model_transfer.design import AssignmentSchedule, load_plan
from experiments.model_transfer.provenance import RunIdentity


PLAN = Path('experiments/model_transfer/plan.json')


def test_saved_model_key_order_does_not_change_assignment():
    plan = load_plan(PLAN)
    reordered = copy.deepcopy(plan)
    reordered['models'] = dict(reversed(list(plan['models'].items())))
    assert AssignmentSchedule(plan).allocations() == AssignmentSchedule(reordered).allocations()


def test_pilot_declares_ten_recipient_positions_and_replicates_cells():
    plan = load_plan(PLAN)
    assert plan['recipient_sessions'] == 10
    assert plan['repetitions'] >= 2
    assert plan['study_role'] == 'pilot'
    assert plan['budget_usd'] == 2


@pytest.mark.parametrize('change', [
    {'recipient_sessions': 11}, {'repetitions': 0}, {'budget_usd': 2.01},
    {'study_role': 'confirmation'}, {'study_role': 'evaluation', 'pilot_run_ids': []},
    {'study_id': 'old', 'pilot_run_ids': ['old']},
    {'practical_decision': None}, {'information_target': {'method': 'precision', 'confidence': True}},
])
def test_invalid_execution_or_independence_contract_is_rejected(tmp_path, change):
    plan = {**load_plan(PLAN), **change}
    path = tmp_path / 'plan.json'
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError):
        load_plan(path)


def test_rehearsal_provenance_cannot_be_promoted_to_live_or_reused_as_pilot(tmp_path):
    plan = load_plan(PLAN)
    first = RunIdentity.record(tmp_path, plan, object())
    assert first['execution_kind'] == 'scripted'
    assert RunIdentity.record(tmp_path, plan, object())['run_id'] == first['run_id']
    with pytest.raises(ValueError, match='reuse'):
        RunIdentity.record(tmp_path, {**plan, 'pilot_run_ids': [first['run_id']]}, object())
    path = tmp_path / 'provenance.json'
    path.write_text(json.dumps({**first, 'execution_kind': 'live'}))
    with pytest.raises(ValueError, match='mix'):
        RunIdentity.record(tmp_path, plan, object())
