"""Evaluate precision, joint decisions and calibration for a simulated allocation."""
from __future__ import annotations

import math
import random
import statistics

from .decision_statistics import DecisionStatistics, joint_supported


def monte_carlo_interval(successes: int, count: int, confidence: float = .95) -> dict:
    if not 0 <= successes <= count or count < 1 or not 0 < confidence < 1:
        raise ValueError('Invalid binomial simulation summary')
    z = statistics.NormalDist().inv_cdf((1 + confidence) / 2)
    rate = successes / count
    denominator = 1 + z * z / count
    centre = (rate + z * z / (2 * count)) / denominator
    radius = z / denominator * math.sqrt(rate * (1 - rate) / count + z * z / (4 * count * count))
    return {'estimate': rate, 'mc_interval': [max(0, centre - radius), min(1, centre + radius)],
            'mc_confidence': confidence, 'mcse': math.sqrt(rate * (1 - rate) / count),
            'successes': successes, 'replications': count}


class ScenarioAssessment:
    def __init__(self, config: dict, simulator):
        self.config, self.simulator = config, simulator

    def run(self, cases: list[str], repetitions: int, scenario: dict, rng: random.Random,
            simulations: int, *, mc_confidence: float = .95, screening: bool = False) -> dict:
        target, decision = self.config['information_target'], self.config['practical_decision']
        counters = dict.fromkeys(('precision', 'quality_precision', 'absolute_quality_precision',
            'token_precision', 'practical_support', 'false_success', 'budget_complete', 'deadline_complete',
            'effect_attainable', 'quality_coverage', 'absolute_quality_coverage', 'token_coverage',
            'joint_coverage', 'token_interval_available'), 0)
        spends, elapsed = [], []
        truth_known = True
        for _ in range(simulations):
            trial, execution = self.simulator.simulate(cases, repetitions, scenario, rng)
            result = DecisionStatistics(target['confidence'], target.get('quality_method', 'empirical_bernstein')).calculate(trial)
            qi, ti, ai = result['quality_interval'], result['token_reduction_interval'], result['eal_correctness_interval']
            bounds, absolute = result['quality_difference_bounds'], result['eal_correctness_bounds']
            qp = bool(qi and result['quality_sampling_half_width'] + (bounds[1] - bounds[0]) / 2 <= target['correctness_half_width'])
            ap = bool(ai and result['absolute_quality_sampling_half_width'] + (absolute[1] - absolute[0]) / 2 <= target['correctness_half_width'])
            tp = bool(ti and result['token_sampling_half_width'] <= target['token_reduction_half_width'])
            counters['quality_precision'] += qp
            counters['absolute_quality_precision'] += ap
            counters['token_precision'] += tp
            counters['precision'] += qp and ap and tp and not execution['budget_stopped'] and not execution['time_stopped'] and execution['timing_known']
            supported = joint_supported(result, decision)
            counters['practical_support'] += supported
            known = execution['effect_attainable']
            truth_known &= known
            true_q, true_e, true_t = scenario['correctness_difference'], execution['eal_correctness_truth'], scenario['token_reduction']
            partial_null = known and (true_q <= -decision['correctness_margin'] or true_e <= decision['minimum_correctness'] or true_t <= decision['minimum_token_reduction'])
            counters['false_success'] += bool(supported and partial_null)
            counters['budget_complete'] += not execution['budget_stopped']
            counters['deadline_complete'] += not execution['time_stopped'] and execution['timing_known']
            counters['effect_attainable'] += known
            qc = bool(known and qi and qi[0] <= true_q <= qi[1])
            ac = bool(known and ai and ai[0] <= true_e <= ai[1])
            tc = bool(ti and ti[0] <= true_t <= ti[1])
            counters['quality_coverage'] += qc
            counters['absolute_quality_coverage'] += ac
            counters['token_coverage'] += tc
            counters['joint_coverage'] += qc and ac and tc
            counters['token_interval_available'] += ti is not None
            spends.append(execution['charged_usd'])
            elapsed.append(execution['elapsed_seconds'])
        return {'scenario': scenario, **{key: monte_carlo_interval(value, simulations, mc_confidence)
            for key, value in counters.items()}, 'mean_charged_usd': statistics.mean(spends),
            'mean_elapsed_seconds': statistics.mean(elapsed), 'coverage_truth_available': truth_known,
            'coverage_denominator': 'All simulated trials, including unavailable intervals.',
            'stage': 'screening' if screening else 'validation',
            'calibration_failures': self.failures(counters, simulations, scenario, mc_confidence, truth_known, screening=screening)}

    def failures(self, counters: dict, n: int, scenario: dict, confidence: float, truth_known: bool, *, screening: bool = False) -> list[str]:
        target = self.config['information_target']
        tolerance = self.config.get('calibration_tolerance', .01)
        bounds = {key: monte_carlo_interval(value, n, confidence)['mc_interval'] for key, value in counters.items()}
        failures = []
        if not truth_known:
            failures.append('generating_truth_unattainable')
        # Screening only rejects demonstrably inadequate candidates. Uncertain
        # boundary calibration advances to independent, multiplicity-adjusted
        # validation; 200 screening draws cannot certify a 5% boundary test.
        # Every plausible scenario must control false success, including loss of
        # measurement. Measurement-failure scenarios need not yield narrow CIs.
        if bounds['false_success'][0 if screening else 1] > 1 - target['confidence'] + tolerance:
            failures.append('false_success')
        if scenario.get('require_information', scenario.get('purpose', 'design') == 'design'):
            if bounds['joint_coverage'][1 if screening else 0] < target['confidence'] - tolerance:
                failures.append('joint_coverage')
            if bounds['precision'][1 if screening else 0] < target['assurance']:
                failures.append('precision_or_feasibility')
        if target['method'] == 'decision_and_precision' and scenario.get('decision_role') == 'benefit' and bounds['practical_support'][1 if screening else 0] < target.get('joint_power', .8):
            failures.append('joint_power')
        return failures
