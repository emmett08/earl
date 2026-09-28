"""Describe paired session outcomes and full resource use without population claims."""
from __future__ import annotations

from collections import defaultdict
from itertools import product
import statistics

from .resources import ResourceSummary
from .design import AssignmentSchedule

SCORES = ('decision_match', 'decision_and_basis_match', 'grounded_match',
          'internally_consistent', 'false_definitive', 'abstention_when_reference_decisive', 'no_answer')


class ReportBuilder:
    def __init__(self, plan: dict):
        self.plan = plan
        self.resources = ResourceSummary()

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
                known = [s for s in observed if 'score' in s]
                correct = sum(s['score']['grounded_match'] for s in known)
                resources = self.resources.summarise(observed, calls, session_ids={
                    f"{r['sequence_id']}.session-{session}" for r in selected})
                summaries.append({
                    'receiver': receiver, 'native_tools': tools, 'arm': arm, 'session': session, 'cohort': cohort,
                    'planned': len(selected), 'observed': len(observed), 'scored': len(known),
                    'unobserved': len(selected) - len(observed),
                    **{key: sum(s['score'][key] for s in known) for key in SCORES},
                    'format_failures': sum(not s.get('format_valid', False) for s in observed),
                    'file_failures': sum(s.get('file_result', {}).get('status') == 'rejected' for s in observed),
                    'grounded_rate_bounds': [correct / len(selected),
                        (correct + len(selected) - len(known)) / len(selected)],
                    'resources': resources,
                    'cost_per_grounded_answer_usd': (resources['known_cost_usd'] / correct
                        if correct and len(known) == len(selected) and not resources['unknown_cost_attempts'] else None),
                    'seconds_per_grounded_answer': (resources['elapsed_seconds'] / correct
                        if correct and len(known) == len(selected) else None),
                })
        paired = self.pairs(rows, calls)
        by_case = defaultdict(list)
        for pair in paired:
            if pair['grounded_difference'] is not None:
                by_case[(pair['case'], pair['cohort'], pair['contrast'], pair['session'])].append(pair['grounded_difference'])
        case_summaries = [{'case': key[0], 'cohort': key[1], 'contrast': key[2], 'session': key[3],
                           'observed_pairs': len(values), 'mean_grounded_difference': statistics.mean(values),
                           'min_grounded_difference': min(values), 'max_grounded_difference': max(values)}
                          for key, values in sorted(by_case.items())]
        stages = {}
        for arm in self.plan['arms']:
            selected = [r for r in rows if r['arm'] == arm]
            sessions = [s for r in selected for s in r['sessions']]
            stages[arm] = {}
            for stage in ('initial', 'recipients', 'total'):
                indices = [i for i in range(1 + self.plan['recipient_sessions'])
                           if stage == 'total' or (i == 0) == (stage == 'initial')]
                ids = {f"{r['sequence_id']}.session-{i}" for r in selected for i in indices}
                stages[arm][stage] = self.resources.summarise(
                    [s for s in sessions if s['session'] in indices], calls, session_ids=ids)
            stages[arm]['setup_seconds'] = sum(r.get('setup_seconds', 0) for r in selected)
        return {
            'schema': 'EAL/model-transfer-result/2', 'status': 'partial' if stop_reason else 'complete',
            'stop_reason': stop_reason, 'planned_sequences': len(rows),
            'planned_sessions': len(rows) * (1 + self.plan['recipient_sessions']),
            'summaries': summaries, 'paired_comparisons': paired, 'case_summaries': case_summaries,
            'resources': stages, 'api_attempts': len(calls),
            'estimated_cost_usd': sum(c['cost_estimate_usd'] or 0 for c in calls),
            'unknown_cost_attempts': sum(c['cost_estimate_usd'] is None for c in calls),
            'charged_or_reserved_usd': sum(c['charged_or_reserved_usd'] for c in calls),
            'scope': 'Fixed-case exploratory model-session comparison with pre-authored EAL. '
                     'Report diagnostic and additional cases separately. Repetitions and sessions '
                     'are dependent within cases. No human-developer, isolated reasoning, notation '
                     'or population model-class effect. Timing includes local synthetic collectors; '
                     'API prices ignore cached discounts and exclude host and human costs.',
        }

    def pairs(self, rows: list[dict], calls: list[dict]) -> list[dict]:
        blocks = defaultdict(dict)
        for row in rows:
            blocks[row['pair_id']][row['arm']] = row
        contrasts = [('eal', 'ordinary')]
        if 'eal_fresh' in self.plan['arms']:
            contrasts.append(('eal', 'eal_fresh'))
        paired = []
        for pair_id, arms in sorted(blocks.items()):
            for treatment, comparator in contrasts:
                a, b = arms[treatment], arms[comparator]
                for session in range(1, self.plan['recipient_sessions'] + 1):
                    aa = next((s for s in a['sessions'] if s['session'] == session), None)
                    bb = next((s for s in b['sessions'] if s['session'] == session), None)
                    measured = aa is not None and bb is not None and 'score' in aa and 'score' in bb
                    differences = {}
                    if measured:
                        ar = self.resources.summarise([aa], calls)
                        br = self.resources.summarise([bb], calls)
                        differences = {key: ar[key] - br[key] for key in
                                       ('elapsed_seconds', 'api_attempts')}
                        differences['total_collector_calls'] = (ar['total_collector_calls'] - br['total_collector_calls']
                            if ar['collection_counts_complete'] and br['collection_counts_complete'] else None)
                        differences['known_cost_usd'] = (ar['known_cost_usd'] - br['known_cost_usd']
                            if not ar['unknown_cost_attempts'] and not br['unknown_cost_attempts'] else None)
                    paired.append({**{key: a[key] for key in ('case', 'cohort', 'donor', 'receiver', 'native_tools', 'repeat')},
                        'pair_id': pair_id, 'session': session, 'contrast': f'{treatment}-{comparator}',
                        'transition': 'same_model' if a['donor'] == a['receiver'] else 'different_model',
                        'observed_pair': measured,
                        'grounded_difference': (int(aa['score']['grounded_match']) - int(bb['score']['grounded_match'])
                                                if measured else None),
                        'resource_differences': differences})
        return paired
