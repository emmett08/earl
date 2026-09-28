"""Report task outcomes and resource profiles with explicit annotation uncertainty."""
from __future__ import annotations

from collections import defaultdict
from itertools import product
import statistics

from .comparisons import PairedComparisons
from .design import AssignmentSchedule
from .outcomes import OutcomeSummary
from .resources import ResourceSummary


class ReportBuilder:
    def __init__(self, plan: dict):
        self.plan = plan
        self.resources = ResourceSummary()
        self.outcomes = OutcomeSummary()

    def build(self, rows: list[dict], calls: list[dict], stop_reason: str | None) -> dict:
        expected = {r['sequence_id']: r for r in AssignmentSchedule(self.plan).allocations()}
        if len(rows) != len(expected) or {r['sequence_id'] for r in rows} != set(expected):
            raise ValueError('Report must retain exactly the planned sequence denominator')
        for row in rows:
            if any(row.get(k) != v for k, v in expected[row['sequence_id']].items()):
                raise ValueError('Observed allocation differs from the saved plan')
            indices = [s['session'] for s in row['sessions']]
            if len(set(indices)) != len(indices) or any(i not in range(1 + self.plan['recipient_sessions']) for i in indices):
                raise ValueError('Duplicate or unknown session in a sequence')
        summaries = []
        cohorts = sorted({r['cohort'] for r in rows})
        for receiver, tools, arm, cohort in product(self.plan['models'], (False, True), self.plan['arms'], cohorts):
            selected = [r for r in rows if (r['receiver'], r['native_tools'], r['arm'], r['cohort']) == (receiver, tools, arm, cohort)]
            for session in range(1, self.plan['recipient_sessions'] + 1):
                observed = [s for r in selected for s in r['sessions'] if s['session'] == session]
                outcomes = self.outcomes.summarise(observed, len(selected))
                resources = self.resources.summarise(observed, calls, session_ids={
                    f"{r['sequence_id']}.session-{session}" for r in selected})
                correct = outcomes['task_match']
                complete = outcomes['task_unknown'] == 0
                summaries.append({
                    'receiver': receiver, 'native_tools': tools, 'arm': arm, 'session': session, 'cohort': cohort,
                    **outcomes, 'resources': resources,
                    'cost_per_task_answer_usd': (resources['known_cost_usd'] / correct
                        if correct and complete and not resources['unknown_cost_attempts'] else None),
                    'seconds_per_task_answer': (resources['elapsed_seconds'] / correct if correct and complete else None),
                })
        paired, cumulative = PairedComparisons(self.plan).build(rows, calls)
        by_case = defaultdict(list)
        for pair in paired:
            if pair['task_difference'] is not None:
                by_case[(pair['case'], pair['cohort'], pair['session'])].append(pair['task_difference'])
        case_summaries = [{'case': key[0], 'cohort': key[1], 'session': key[2],
                           'observed_pairs': len(values), 'mean_task_difference': statistics.mean(values),
                           'min_task_difference': min(values), 'max_task_difference': max(values)}
                          for key, values in sorted(by_case.items())]
        stages, trajectories = {}, {}
        for arm in self.plan['arms']:
            selected = [r for r in rows if r['arm'] == arm]
            sessions = [s for r in selected for s in r['sessions']]
            stages[arm], trajectories[arm] = {}, []
            for stage in ('initial', 'recipients', 'total'):
                indices = [i for i in range(1 + self.plan['recipient_sessions'])
                           if stage == 'total' or (i == 0) == (stage == 'initial')]
                ids = {f"{r['sequence_id']}.session-{i}" for r in selected for i in indices}
                stages[arm][stage] = self.resources.summarise(
                    [s for s in sessions if s['session'] in indices], calls, session_ids=ids)
            stages[arm]['setup_seconds'] = sum(r.get('setup_seconds', 0) for r in selected)
            stages[arm]['total']['elapsed_with_setup_seconds'] = stages[arm]['total']['elapsed_seconds'] + stages[arm]['setup_seconds']
            for last in range(1 + self.plan['recipient_sessions']):
                ss = [s for s in sessions if s['session'] <= last]
                ids = {f"{r['sequence_id']}.session-{i}" for r in selected for i in range(last + 1)}
                resources = self.resources.summarise(ss, calls, session_ids=ids)
                resources['elapsed_with_setup_seconds'] = resources['elapsed_seconds'] + stages[arm]['setup_seconds']
                trajectories[arm].append({'through_session': last, 'resources': resources,
                    'recipient_outcomes': self.outcomes.summarise([s for s in ss if s['session'] > 0], len(selected) * last)})
        all_sessions = [s for r in rows for s in r['sessions']]
        pending = sum(s.get('score', {}).get('task_match') is None for s in all_sessions)
        incomplete = stop_reason is not None or any(r['status'] != 'complete' for r in rows)
        return {
            'schema': 'EAL/model-transfer-result/3',
            'status': 'partial' if incomplete else 'pending_annotation' if pending else 'complete',
            'execution_status': 'partial' if incomplete else 'complete', 'pending_task_annotations': pending,
            'stop_reason': stop_reason, 'planned_sequences': len(rows),
            'planned_sessions': len(rows) * (1 + self.plan['recipient_sessions']),
            'summaries': summaries, 'paired_comparisons': paired, 'case_summaries': case_summaries,
            'cumulative_comparisons': cumulative, 'cumulative_resources': trajectories,
            'resources': stages, 'api_attempts': len(calls),
            'estimated_cost_usd': sum(c['cost_estimate_usd'] or 0 for c in calls),
            'unknown_cost_attempts': sum(c['cost_estimate_usd'] is None for c in calls),
            'charged_or_reserved_usd': sum(c['charged_or_reserved_usd'] for c in calls),
            'scope': 'Selected-case workflow comparison with ordinary prose and pre-authored EAL. '
                     'Task decision is primary; evidence citations and format are separate optional diagnostics. '
                     'Unknown annotations remain bounded; no population inference or unmeasured authoring savings. '
                     'Cumulative profiles include initial model use; no extrapolated break-even. '
                     'API prices exclude cached discounts, host infrastructure and human costs.',
        }
