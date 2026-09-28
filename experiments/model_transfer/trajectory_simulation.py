"""Resample paired whole-session trajectories and replay bounded expenditure."""
from __future__ import annotations

from collections import defaultdict
import random
import statistics

from .decision_statistics import SequenceOutcome
from .pilot_data import PairedTrajectory


class TrajectorySimulator:
    """Resample matched complete trajectories inside fixed allocation cells.

    The hypothetical effect rescales EAL token use; costs scale with a fixed token
    mix. A single quality/missingness draw per arm trajectory permits perfect
    within-trajectory dependence. Actual reservation-then-charge order is replayed.
    """

    def __init__(self, pilot: list[PairedTrajectory], budget_usd: float, time_limit_seconds: float = 7200,
                 workflow_overhead_seconds: float = 0):
        self.strata = defaultdict(list)
        for pair in pilot:
            self.strata[pair.stratum].append(pair)
        self.budget_usd = budget_usd
        self.time_limit_seconds = time_limit_seconds
        self.workflow_overhead_seconds = workflow_overhead_seconds
        self._complete_arm_cache = {}

    def _complete_arm(self, pair: PairedTrajectory, arm: str, factor: float, scenario: dict) -> dict:
        """Cache sufficient summaries; inspect every request when computing a peak.

        A fitting arm can be advanced at once. An arm that could cross either
        limit still uses the session/request loop, retaining partial outcomes.
        """
        key = pair.pair_id, arm, factor, scenario['cost_multiplier'], scenario.get('elapsed_multiplier', 1)
        if key not in self._complete_arm_cache:
            sessions = getattr(pair, arm)
            charged = peak = 0.
            for session in sessions:
                for reservation, cost in session.requests:
                    peak = max(peak, charged + reservation * max(1, factor) * scenario['cost_multiplier'])
                    charged += cost * factor * scenario['cost_multiplier']
            self._complete_arm_cache[key] = {
                'tokens': sum(s.tokens for s in sessions) * factor if all(s.tokens is not None for s in sessions) else None,
                'elapsed': sum(s.elapsed_seconds or 0 for s in sessions) * scenario.get('elapsed_multiplier', 1),
                'timing_known': all(s.elapsed_seconds is not None for s in sessions),
                'charged': charged, 'peak': max(peak, charged),
                'correct': sum(s.correctness is True for s in sessions[1:]),
                'incorrect': sum(s.correctness is False for s in sessions[1:]),
                'unknown': sum(s.correctness is None for s in sessions[1:]), 'horizon': len(sessions) - 1}
        return self._complete_arm_cache[key]

    def simulate(self, case_ids: list[str], repetitions: int, scenario: dict,
                 rng: random.Random) -> tuple[list[SequenceOutcome], dict]:
        cells = sorted(key for key in self.strata if key[0] in case_ids)
        selected = [rng.choice(self.strata[cell]) for cell in cells for _ in range(repetitions)]
        rng.shuffle(selected)
        # Effects are centred on the pilot distribution, never on a resampled
        # trial's realised mean: re-centring each trial would erase uncertainty.
        reference = [p for cell in cells for p in self.strata[cell]]
        eal_tokens = sum(s.tokens or 0 for p in reference for s in p.eal)
        ordinary_tokens = sum(s.tokens or 0 for p in reference for s in p.ordinary)
        scale = (1 - scenario['token_reduction']) * ordinary_tokens / eal_tokens if eal_tokens else None
        observed_e = [s.correctness for p in reference for s in p.eal[1:] if s.correctness is not None]
        observed_o = [s.correctness for p in reference for s in p.ordinary[1:] if s.correctness is not None]
        base = statistics.mean(observed_e) if observed_e else None
        desired = statistics.mean(observed_o) + scenario['correctness_difference'] if observed_o else None
        attainable = scale is not None and base is not None and desired is not None and 0 <= desired <= 1
        spent, elapsed, stopped, output = 0., self.workflow_overhead_seconds, False, []
        budget_stopped = time_stopped = False
        timing_known = True
        for pair in selected:
            if stopped:
                output.append(SequenceOutcome(pair.stratum, -1, 1, None, None, 0, 1))
                continue
            arms = {}
            arm_order = ['ordinary', 'eal']
            rng.shuffle(arm_order)
            for arm in arm_order:
                setup = pair.setup_seconds[arm == 'eal']
                timing_known &= setup is not None
                elapsed += (setup or 0) * scenario.get('elapsed_multiplier', 1)
                if elapsed > self.time_limit_seconds:
                    stopped = time_stopped = True
                quality_draw, missing_draw = rng.random(), rng.random()
                factor = scale if arm == 'eal' and scale is not None else 1
                if arm == 'eal':
                    probability = scenario.get('resource_tail_probability', 0)
                    multiplier = scenario.get('resource_tail_multiplier', 1)
                    factor *= (multiplier if rng.random() < probability else 1) / (1 + probability * (multiplier - 1))
                summary = self._complete_arm(pair, arm, factor, scenario)
                if (not stopped and spent + summary['peak'] <= self.budget_usd
                        and elapsed + summary['elapsed'] <= self.time_limit_seconds):
                    spent += summary['charged']
                    elapsed += summary['elapsed']
                    timing_known &= summary['timing_known']
                    correct = summary['correct']
                    if arm == 'eal' and attainable:
                        if desired > base and quality_draw < (desired - base) / (1 - base):
                            correct += summary['incorrect']
                        elif desired < base and quality_draw < (base - desired) / base:
                            correct = 0
                    missing = missing_draw < scenario['missing_probability']
                    arms[arm] = (0 if missing else correct / summary['horizon'],
                        1 if missing else (correct + summary['unknown']) / summary['horizon'],
                        None if missing and scenario.get('missing_usage', False) else summary['tokens'])
                    continue
                lower = upper = token_total = 0.
                tokens_complete = True
                for index, session in enumerate(getattr(pair, arm)):
                    if not stopped:
                        timing_known &= session.elapsed_seconds is not None
                        elapsed += (session.elapsed_seconds or 0) * scenario.get('elapsed_multiplier', 1)
                        if elapsed > self.time_limit_seconds:
                            stopped = time_stopped = True
                    quality = session.correctness
                    if arm == 'eal' and index and attainable and quality is not None:
                        if desired > base and not quality and quality_draw < (desired - base) / (1 - base):
                            quality = True
                        elif desired < base and quality and quality_draw < (base - desired) / base:
                            quality = False
                    for reservation, charged in session.requests:
                        reservation *= max(1, factor) * scenario['cost_multiplier']
                        charged *= factor * scenario['cost_multiplier']
                        if stopped:
                            break
                        if spent + reservation > self.budget_usd:
                            stopped = budget_stopped = True
                            break
                        spent += charged
                        if spent > self.budget_usd:
                            stopped = budget_stopped = True
                            break
                    # Annotation missingness does not erase retained API usage.
                    # Missing usage is a separate, explicitly named stress.
                    missing_answer = stopped or missing_draw < scenario['missing_probability']
                    missing_usage = stopped or (scenario.get('missing_usage', False)
                                                and missing_draw < scenario['missing_probability'])
                    if index:
                        lower += int(quality) if not missing_answer and quality is not None else 0
                        upper += int(quality) if not missing_answer and quality is not None else 1
                    if missing_usage or session.tokens is None:
                        tokens_complete = False
                    else:
                        token_total += session.tokens * factor
                horizon = len(getattr(pair, arm)) - 1
                arms[arm] = lower / horizon, upper / horizon, token_total if tokens_complete else None
            eal, ordinary = arms['eal'], arms['ordinary']
            output.append(SequenceOutcome(pair.stratum, eal[0] - ordinary[1], eal[1] - ordinary[0],
                                          ordinary[2], eal[2], eal[0], eal[1]))
        return output, {'charged_usd': spent, 'elapsed_seconds': elapsed, 'budget_stopped': budget_stopped,
                        'time_stopped': time_stopped, 'timing_known': timing_known,
                        'effect_attainable': attainable, 'eal_correctness_truth': desired}
