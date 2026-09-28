"""Bound quality and estimate resource precision for paired whole sequences.

Quality bounds use Hoeffding's inequality for independent bounded sequence
differences, allowing different fixed-case means. Resource intervals use the
stratified delta method; they are an approximation, conditional on independent
reruns within the declared fixed case/model/tool cells.

Sources: Hoeffding (1963), Theorem 2, doi:10.1080/01621459.1963.10500830;
Deng, Knoblich and Lu (2018), section 2 equations (3)-(4),
doi:10.1145/3219819.3219919. The stratification, conservative quality bound,
three-endpoint split and decision thresholds are this investigation's choices.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
import statistics

from .pilot_data import PairedTrajectory
from .statistical_quantiles import student_t_quantile


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
    def __init__(self, confidence: float = .95):
        self.confidence = confidence

    def calculate(self, outcomes: list[SequenceOutcome]) -> dict:
        if not outcomes:
            return {'quality_difference_bounds': None, 'quality_interval': None,
                    'eal_correctness_bounds': None, 'eal_correctness_interval': None,
                    'token_reduction': None, 'token_reduction_interval': None,
                    'token_interval_reason': 'No paired sequences'}
        count = len(outcomes)
        # Bonferroni split across the three co-required endpoints; the resource
        # interval remains approximate rather than inheriting Hoeffding's guarantee.
        alpha = (1 - self.confidence) / 3
        lower = statistics.mean(row.quality_lower for row in outcomes)
        upper = statistics.mean(row.quality_upper for row in outcomes)
        radius = math.sqrt(2 * math.log(2 / alpha) / count)
        absolute_lower = statistics.mean(row.eal_correctness_lower for row in outcomes)
        absolute_upper = statistics.mean(row.eal_correctness_upper for row in outcomes)
        result = {'paired_sequences': count, 'quality_difference_bounds': [lower, upper],
                  'quality_interval': [max(-1, lower - radius), min(1, upper + radius)],
                  'eal_correctness_bounds': [absolute_lower, absolute_upper],
                  'eal_correctness_interval': [max(0, absolute_lower - radius / 2), min(1, absolute_upper + radius / 2)],
                  'quality_sampling_half_width': radius,
                  'token_reduction': None, 'token_reduction_interval': None,
                  'token_interval_reason': None}
        if any(row.ordinary_tokens is None or row.eal_tokens is None for row in outcomes):
            result['token_interval_reason'] = 'Missing cumulative token measurements'
            return result
        ordinary = statistics.mean(row.ordinary_tokens for row in outcomes)
        eal = statistics.mean(row.eal_tokens for row in outcomes)
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
        components = [(len(values) / count) ** 2 * statistics.variance(values) / len(values)
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
        return result


class PracticalDecision:
    """Keep practical magnitude, precision and independent evaluation distinct."""

    def __init__(self, specification: dict):
        self.specification = specification

    def evaluate(self, trajectories: list[PairedTrajectory], *, study_role: str,
                 independent_evaluation: bool, confidence: float = .95) -> dict:
        spec = self.specification
        if any(len(p.eal) != spec['recipient_horizon'] + 1 or len(p.ordinary) != len(p.eal) for p in trajectories):
            raise ValueError('Practical decision requires the actual declared recipient horizon in both arms')
        statistics_result = DecisionStatistics(confidence).calculate([sequence_outcome(p) for p in trajectories])
        quality = statistics_result['quality_difference_bounds']
        reduction = statistics_result['token_reduction']
        point = (quality is not None and quality[0] >= -spec['correctness_margin']
                 and statistics_result['eal_correctness_bounds'][0] >= spec['minimum_correctness']
                 and reduction is not None and reduction >= spec['minimum_token_reduction'])
        qi, ti = statistics_result['quality_interval'], statistics_result['token_reduction_interval']
        supported = (qi is not None and ti is not None and qi[0] >= -spec['correctness_margin']
                     and statistics_result['eal_correctness_interval'][0] >= spec['minimum_correctness']
                     and ti[0] >= spec['minimum_token_reduction'])
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
                'quality_interval_method': 'Hoeffding bound on independent whole-paired-sequence differences; '
                    'all planned pairs retained and missing correctness bounded adversely.',
                'resource_interval_method': 'Approximate stratified paired delta-method interval with t correction; '
                    'independent reruns, stable finite variance and adequate within-cell replication assumed.',
                'scope': 'Fixed selected tasks and model/tool configurations; no task-population, human productivity '
                    'or pure model-capability inference. Cost and elapsed time cannot substitute for the joint endpoints.'}
