"""Analytic and adversarial checks for the study's inferential claims."""

from itertools import product

import pytest

from experiments.transfer_study.inference import BoundedPairedEstimator, OutcomeBounds


def test_four_perfect_pairs_do_not_establish_superiority():
    result = BoundedPairedEstimator().estimate([OutcomeBounds(1, 1)] * 4)
    assert result["estimate"] == 1
    assert result["interval"][0] < 0
    assert result["interval"][1] == 1


def test_exact_null_coverage_over_all_eight_pair_assignments():
    estimator = BoundedPairedEstimator()
    misses = positives = 0
    # Fully discordant paired binary outcomes under fair independent assignment.
    for assignment in product((-1, 1), repeat=8):
        interval = estimator.estimate([OutcomeBounds(x, x) for x in assignment])["interval"]
        misses += not interval[0] <= 0 <= interval[1]
        positives += interval[0] > .10
    assert misses / 256 <= .05
    assert positives / 256 <= .025


def test_known_nonzero_effect_and_adversarial_missingness():
    estimator = BoundedPairedEstimator()
    result = estimator.estimate([OutcomeBounds(1, 1)] * 120)
    assert result["interval"][0] > .10
    missing = estimator.estimate([OutcomeBounds(-1, 1)] * 120)
    assert missing["estimate"] is None
    assert missing["interval"] == [-1, 1]
    assert missing["pairs"] == missing["unknown_pairs"] == 120
    dependent = estimator.estimate([OutcomeBounds(1, 1)] * 120, independent=False)
    assert dependent["interval"] is None


def test_precision_planning_and_support_validation():
    estimator = BoundedPairedEstimator()
    assert estimator.required_pairs(.10) == 738
    assert estimator.half_width(738) <= .10 < estimator.half_width(737)
    with pytest.raises(ValueError, match="outside declared support"):
        estimator.estimate([OutcomeBounds(0, 2)])
    with pytest.raises(ValueError, match="ordered and finite"):
        OutcomeBounds(float("nan"), 1)
