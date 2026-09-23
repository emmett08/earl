"""The continuation cannot allocate a phase beyond the cumulative allowance."""
import importlib.util
from pathlib import Path

import pytest

_path = Path(__file__).resolve().parents[1] / 'scripts/run_relay_completion.py'
_spec = importlib.util.spec_from_file_location('relay_completion', _path)
module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(module)


@pytest.fixture
def ledger():
    return {'known_prior_model_cost_usd': 1.91203171, 'prior_unknown_reserve_usd': 4.5,
            'maximum_single_response_allowance_usd': 2.12792, 'user_stop_threshold_usd': 12}


def test_prior_unknown_charges_and_response_allowance_are_reserved(ledger):
    assert module.phase_exposure(ledger, 0, 3) == pytest.approx(11.53995171)
    with pytest.raises(ValueError, match='cumulative'):
        module.phase_exposure(ledger, 0, 5)


def test_repair_uses_actual_numerical_phase_charges(ledger):
    assert module.phase_exposure(ledger, 1, 1) < 12
    with pytest.raises(ValueError, match='cumulative'):
        module.phase_exposure(ledger, 3, 1)


@pytest.mark.parametrize('amount', [None, float('nan'), float('inf'), -1, True])
def test_unknown_or_invalid_spending_cannot_be_treated_as_zero(ledger, amount):
    with pytest.raises(ValueError):
        module.phase_exposure(ledger, amount, 1)
