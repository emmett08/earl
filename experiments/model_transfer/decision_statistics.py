"""Bound quality and estimate resource precision for paired whole sequences.

Quality bounds use empirical Bernstein bounds for independent bounded sequence
differences, allowing different fixed-case means. Resource intervals use the
stratified delta method; they are an approximation, conditional on independent
reruns within the declared fixed case/model/tool cells.

Sources: Maurer and Pontil (2009), Theorem 11, arXiv:0907.3740;
Hoeffding (1963), Theorem 2, doi:10.1080/01621459.1963.10500830;
Deng, Knoblich and Lu (2018), section 2 equations (3)-(4),
doi:10.1145/3219819.3219919. The stratification, conservative quality bound,
three-endpoint split and decision thresholds are this investigation's choices.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math

from .pilot_data import PairedTrajectory
from .statistical_quantiles import student_t_quantile
from .bounded_statistics import bounded_interval, mean, sample_variance


@dataclass(frozen=True)
class SequenceOutcome:
    stratum: tuple
    quality_lower: float
    quality_upper: float
    ordinary_tokens: float | None
    eal_tokens: float | None
    eal_correctness_lower: float
    eal_correctness_upper: float


def sequence_outcome(pair: PairedTrajectory) -> SequenceOutcome:
    lower = upper = eal_lower = eal_upper = 0.0
    horizon = len(pair.eal) - 1
    for eal, ordinary in zip(pair.eal[1:], pair.ordinary[1:]):
        eal_lower += int(eal.correctness) if eal.correctness is not None else 0
        eal_upper += int(eal.correctness) if eal.correctness is not None else 1
        lower += (int(eal.correctness) if eal.correctness is not None else 0) - (
            int(ordinary.correctness) if ordinary.correctness is not None else 1)
        upper += (int(eal.correctness) if eal.correctness is not None else 1) - (
            int(ordinary.correctness) if ordinary.correctness is not None else 0)
    totals = []
    for arm in (pair.ordinary, pair.eal):
        totals.append(sum(s.tokens for s in arm) if all(s.tokens is not None for s in arm) else None)
    return SequenceOutcome(pair.stratum, lower / horizon, upper / horizon, *totals, eal_lower / horizon, eal_upper / horizon)


class DecisionStatistics:
    def __init__(self, confidence: float = .95, quality_method: str = "empirical_bernstein"):
        if not 0 < confidence < 1:
            raise ValueError("Confidence must lie in (0, 1)")
        self.confidence, self.quality_method = confidence, quality_method

    def calculate(self, outcomes: list[SequenceOutcome]) -> dict:
        if not outcomes:
            return {'quality_difference_bounds': None, 'quality_interval': None,
                    'eal_correctness_bounds': None, 'eal_correctness_interval': None,
                    'token_reduction': None, 'token_reduction_interval': None,
                    'token_interval_reason': 'No paired sequences', 'decision_lower_bounds': None}
        count = len(outcomes)
        # Bonferroni split across the three co-required endpoints; the resource
        # interval remains approximate rather than inheriting Hoeffding's guarantee.
        alpha = (1 - self.confidence) / 3
        lower = mean([row.quality_lower for row in outcomes])
        upper = mean([row.quality_upper for row in outcomes])
        qlo = [row.quality_lower for row in outcomes]
        qhi = [row.quality_upper for row in outcomes]
        elo = [row.eal_correctness_lower for row in outcomes]
        ehi = [row.eal_correctness_upper for row in outcomes]
        quality_interval, radius = bounded_interval(qlo, qhi, (-1, 1), alpha / 2, self.quality_method)
        absolute_interval, absolute_radius = bounded_interval(elo, ehi, (0, 1), alpha / 2, self.quality_method)
        # Intersection-union success: each ONE-SIDED component uses alpha, with
        # no claim that these three lower bounds have simultaneous 95% coverage.
        decision_alpha = 1 - self.confidence
        quality_lower = bounded_interval(qlo, qhi, (-1, 1), decision_alpha, self.quality_method)[0][0]
        absolute_lower = bounded_interval(elo, ehi, (0, 1), decision_alpha, self.quality_method)[0][0]
        result = {'paired_sequences': count, 'quality_difference_bounds': [lower, upper],
                  'quality_interval': quality_interval,
                  'eal_correctness_bounds': [mean(elo), mean(ehi)],
                  'eal_correctness_interval': absolute_interval,
                  'quality_sampling_half_width': radius,
                  'absolute_quality_sampling_half_width': absolute_radius,
                  'quality_method': self.quality_method,
                  'decision_lower_bounds': {'quality_difference': quality_lower,
                      'eal_correctness': absolute_lower, 'token_reduction': None},
                  'token_reduction': None, 'token_reduction_interval': None,
                  'token_interval_reason': None}
        if any(row.ordinary_tokens is None or row.eal_tokens is None for row in outcomes):
            result['token_interval_reason'] = 'Missing cumulative token measurements'
            return result
        ordinary = mean([row.ordinary_tokens for row in outcomes])
        eal = mean([row.eal_tokens for row in outcomes])
        if ordinary <= 0:
            result['token_interval_reason'] = 'Ordinary cumulative token mean is not positive'
            return result
        ratio = eal / ordinary
        result['token_reduction'] = 1 - ratio
        strata = defaultdict(list)
        for row in outcomes:
            strata[row.stratum].append((ratio * row.ordinary_tokens - row.eal_tokens) / ordinary)
        if any(len(values) < 2 for values in strata.values()):
            result['token_interval_reason'] = 'At least two independent repetitions are required in every stratum'
            return result
        components = [(len(values) / count) ** 2 * sample_variance(values) / len(values)
                      for values in strata.values()]
        variance = sum(components)
        if not variance:
            result['token_interval_reason'] = ('Zero observed within-cell variation does not identify unobserved '
                                                'resource tails; additional replication or a justified bound is required')
            return result
        degrees = variance ** 2 / sum(value ** 2 / (len(values) - 1)
                                     for value, values in zip(components, strata.values()))
        radius = student_t_quantile(1 - alpha / 2, degrees) * math.sqrt(variance)
        result.update(token_reduction_interval=[1 - ratio - radius, min(1, 1 - ratio + radius)],
                      token_sampling_half_width=radius, resource_degrees_of_freedom=degrees if variance else None)
        result['decision_lower_bounds']['token_reduction'] = 1 - ratio - student_t_quantile(
            self.confidence, degrees) * math.sqrt(variance)
        return result


def joint_supported(result: dict, specification: dict) -> bool:
    bounds = result.get('decision_lower_bounds')
    return bool(bounds and bounds['token_reduction'] is not None
        and bounds['quality_difference'] > -specification['correctness_margin']
        and bounds['eal_correctness'] > specification['minimum_correctness']
        and bounds['token_reduction'] > specification['minimum_token_reduction'])


class PracticalDecision:
    """Keep practical magnitude, precision and independent evaluation distinct."""

    def __init__(self, specification: dict):
        self.specification = specification

    def evaluate(self, trajectories: list[PairedTrajectory], *, study_role: str,
                 independent_evaluation: bool, confidence: float = .95, quality_method: str = 'empirical_bernstein') -> dict:
        spec = self.specification
        if any(len(p.eal) != spec['recipient_horizon'] + 1 or len(p.ordinary) != len(p.eal) for p in trajectories):
            raise ValueError('Practical decision requires the actual declared recipient horizon in both arms')
        statistics_result = DecisionStatistics(confidence, quality_method).calculate([sequence_outcome(p) for p in trajectories])
        quality = statistics_result['quality_difference_bounds']
        reduction = statistics_result['token_reduction']
        point = (quality is not None and quality[0] >= -spec['correctness_margin']
                 and statistics_result['eal_correctness_bounds'][0] >= spec['minimum_correctness']
                 and reduction is not None and reduction >= spec['minimum_token_reduction'])
        qi, ti = statistics_result['quality_interval'], statistics_result['token_reduction_interval']
        supported = joint_supported(statistics_result, spec)
        contradictory = bool(qi and qi[1] < -spec['correctness_margin'] or
                             statistics_result['eal_correctness_interval'] and
                             statistics_result['eal_correctness_interval'][1] < spec['minimum_correctness'] or
                             ti and ti[1] < spec['minimum_token_reduction'])
        status = ('pilot_only' if study_role != 'evaluation' else
                  'needs_independent_evaluation' if not independent_evaluation else
                  'interval_supported_under_assumptions' if supported else
                  'criterion_not_supported' if contradictory else 'inconclusive')
        return {'specification': spec, 'status': status, 'practical_point_criteria_met': point,
                'interval_criteria_met': supported, **statistics_result,
                'threshold_status': 'Prospective engineering choices; not validated developer utility thresholds.',
                'quality_units': 'difference in mean recipient correctness; 0.05 equals five percentage points',
                'resource_units': 'relative reduction in cumulative input plus output tokens, including initial session',
                'decision_method': 'Intersection-union of three one-sided tests; resource test is approximate.',
                'quality_interval_method': ('Empirical Bernstein (Maurer-Pontil Theorem 11)' if quality_method == 'empirical_bernstein' else 'Hoeffding') + ' on independent whole-paired-sequence differences; '
                    'all planned pairs retained and missing correctness bounded adversely.',
                'resource_interval_method': 'Approximate stratified paired delta-method interval with t correction; '
                    'independent reruns, stable finite variance and adequate within-cell replication assumed.',
                'scope': 'Fixed selected tasks and model/tool configurations; no task-population, human productivity '
                    'or pure model-capability inference. Cost and elapsed time cannot substitute for the joint endpoints.'}
