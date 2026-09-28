"""Extract complete paired trajectories without converting missing records to zero."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
import statistics

from .resources import ResourceSummary


@dataclass(frozen=True)
class SessionMeasure:
    correctness: bool | None
    tokens: int | None
    cost_usd: float | None
    elapsed_seconds: float | None
    requests: tuple[tuple[float, float], ...]
    budget_accounting_complete: bool = True


@dataclass(frozen=True)
class PairedTrajectory:
    pair_id: str
    case: str
    donor: str
    receiver: str
    native_tools: bool
    repeat: int
    ordinary: tuple[SessionMeasure, ...]
    eal: tuple[SessionMeasure, ...]
    arm_order: tuple[str, str]
    setup_seconds: tuple[float | None, float | None] = (0., 0.)

    @property
    def stratum(self) -> tuple:
        return self.case, self.donor, self.receiver, self.native_tools


class PilotExtractor:
    """One paired sequence is the stochastic unit; sessions remain together."""

    def extract(self, rows: list[dict], calls: list[dict], horizon: int) -> list[PairedTrajectory]:
        pairs: dict[str, dict[str, dict]] = defaultdict(dict)
        order: dict[str, list[str]] = defaultdict(list)
        units = set()
        by_session, by_attempt = defaultdict(list), defaultdict(list)
        for index, call in enumerate(calls):
            by_session[call.get('session_id')].append(index)
            by_attempt[call.get('attempt')].append(index)
        call_index = calls, by_session, by_attempt
        for row in rows:
            arm, pair = row['arm'], row['pair_id']
            if arm not in ('ordinary', 'eal') or arm in pairs[pair]:
                raise ValueError('Every pair requires exactly one row per comparison arm')
            pairs[pair][arm] = row
            order[pair].append(arm)
            unit = tuple(row[key] for key in ('case', 'donor', 'receiver', 'native_tools', 'repeat', 'arm'))
            if unit in units:
                raise ValueError('Duplicate experimental unit cannot increase the information count')
            units.add(unit)
        result = []
        for pair_id, arms in sorted(pairs.items()):
            if set(arms) != {'ordinary', 'eal'}:
                raise ValueError('Unpaired rows cannot be used for allocation planning')
            a, b = arms['ordinary'], arms['eal']
            keys = ('case', 'donor', 'receiver', 'native_tools', 'repeat')
            if any(a[key] != b[key] for key in keys):
                raise ValueError('Pair identities differ between arms')
            result.append(PairedTrajectory(pair_id, *(a[key] for key in keys),
                self._sessions(a, call_index, horizon), self._sessions(b, call_index, horizon), tuple(order[pair_id]),
                (a.get('setup_seconds'), b.get('setup_seconds'))))
        return result

    @staticmethod
    def _sessions(row: dict, call_index: tuple, horizon: int) -> tuple[SessionMeasure, ...]:
        observed = {s['session']: s for s in row['sessions']}
        if len(observed) != len(row['sessions']):
            raise ValueError('Duplicate session index in pilot trajectory')
        result = []
        for index in range(horizon + 1):
            sid = f"{row['sequence_id']}.session-{index}"
            ss = [observed[index]] if index in observed else []
            all_calls, by_session, by_attempt = call_index
            indices = set(by_session[sid])
            for receipt in ss[0].get('api_attempt_ids', []) if ss else []:
                indices.update(by_attempt[receipt])
            calls = [all_calls[i] for i in sorted(indices)]
            resource = ResourceSummary().summarise(ss, calls, session_ids={sid})
            score = ss[0].get('score', {}).get('task_match') if ss else None
            if score is not None and type(score) is not bool:
                raise ValueError('Correctness must be boolean or missing')
            records = [c for c in calls if c.get('session_id') == sid]
            valid_budget = all(type(c.get(k)) in (int, float) and math.isfinite(c[k]) and c[k] >= 0
                               for c in records for k in ('reserved_usd', 'charged_or_reserved_usd'))
            requests = tuple((c['reserved_usd'], c['charged_or_reserved_usd']) for c in records) if valid_budget else ()
            result.append(SessionMeasure(score,
                resource['input_tokens'] + resource['output_tokens'] if resource['token_usage_complete'] else None,
                resource['known_cost_usd'] if resource['cost_accounting_complete'] else None,
                resource['elapsed_seconds'] if resource['session_coverage_complete'] else None, requests, valid_budget))
        return tuple(result)


def _correlation(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 3:
        return None
    left, right = zip(*pairs)
    if not statistics.pvariance(left) or not statistics.pvariance(right):
        return None
    return statistics.correlation(left, right)


class PilotSummary:
    def describe(self, trajectories: list[PairedTrajectory]) -> dict:
        strata = defaultdict(list)
        differences, disagreements, adjacent = [], [], []
        missing = total = 0
        for pair in trajectories:
            strata[pair.stratum].append(pair)
            tokens = [[s.tokens for s in getattr(pair, arm)] for arm in ('eal', 'ordinary')]
            if all(x is not None for arm in tokens for x in arm):
                differences.append(sum(tokens[0]) - sum(tokens[1]))
            deltas = []
            for eal, ordinary in zip(pair.eal[1:], pair.ordinary[1:]):
                total += 1
                if eal.correctness is None or ordinary.correctness is None:
                    missing += 1
                    deltas.append(None)
                else:
                    disagreements.append(eal.correctness != ordinary.correctness)
                    deltas.append(int(eal.correctness) - int(ordinary.correctness))
            adjacent.extend((a, b) for a, b in zip(deltas, deltas[1:]) if a is not None and b is not None)
        sizes = [sum(all(s.tokens is not None and s.cost_usd is not None for arm in (p.ordinary, p.eal) for s in arm)
                     and all(s.correctness is not None for arm in (p.ordinary, p.eal) for s in arm[1:])
                     for p in values) for values in strata.values()]
        within_variances, residual_adjacent = [], []
        for members in strata.values():
            totals, vectors = [], []
            for pair in members:
                if all(s.tokens is not None for arm in (pair.eal, pair.ordinary) for s in arm):
                    totals.append(sum(s.tokens for s in pair.eal) - sum(s.tokens for s in pair.ordinary))
                vectors.append([int(a.correctness) - int(b.correctness)
                    if a.correctness is not None and b.correctness is not None else None
                    for a, b in zip(pair.eal[1:], pair.ordinary[1:])])
            if len(totals) >= 2:
                within_variances.append(statistics.variance(totals))
            for vector in vectors:
                residuals = []
                for index, value in enumerate(vector):
                    observed = [v[index] for v in vectors if v[index] is not None]
                    residuals.append(value - statistics.mean(observed) if value is not None and len(observed) >= 2 else None)
                residual_adjacent.extend((a, b) for a, b in zip(residuals, residuals[1:]) if a is not None and b is not None)
        return {'paired_sequences': len(trajectories), 'cases': len({p.case for p in trajectories}),
                'strata': len(strata), 'minimum_complete_repetitions_per_stratum': min(sizes, default=0),
                'within_cell_variance_identified': bool(sizes) and min(sizes) >= 2,
                'paired_cumulative_token_difference_mean': statistics.mean(differences) if differences else None,
                'paired_cumulative_token_difference_sd': statistics.stdev(differences) if len(differences) > 1 else None,
                'mean_within_cell_paired_token_variance': statistics.mean(within_variances) if within_variances else None,
                'cells_with_resource_variance_estimate': len(within_variances),
                'recipient_correctness_disagreement_rate': statistics.mean(disagreements) if disagreements else None,
                'lag_one_correctness_difference_correlation': _correlation(adjacent),
                'lag_one_correlation_pairs': len(adjacent),
                'within_cell_position_adjusted_lag_one_correlation': _correlation(residual_adjacent),
                'within_cell_position_adjusted_lag_one_pairs': len(residual_adjacent),
                'missing_paired_recipient_fraction': missing / total if total else None,
                'temporal_dependence_method': 'Pooled descriptive adjacent differences, potentially confounded by fixed-case '
                    'and position heterogeneity; additionally report correlation after subtracting each cell/position mean. '
                    'The adjusted estimate is unstable with few repetitions and null when variance is unidentified. '
                    'Whole trajectories are resampled together.',
                'variance_scope': 'Across-pair SD includes fixed-case/configuration heterogeneity; '
                                  'within-cell replication is separately required for stochastic precision.'}


def data_fingerprint(plan: dict, rows: list[dict], calls: list[dict]) -> str:
    payload = json.dumps({'plan': plan, 'rows': rows, 'calls': calls}, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode()).hexdigest()
