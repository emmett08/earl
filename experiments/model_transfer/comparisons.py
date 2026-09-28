"""Calculate matched marginal and cumulative workflow differences."""
from collections import defaultdict

from .resources import ResourceSummary


class PairedComparisons:
    def __init__(self, plan: dict):
        self.plan = plan
        self.resources = ResourceSummary()

    def build(self, rows: list[dict], calls: list[dict]) -> tuple[list[dict], list[dict]]:
        blocks = defaultdict(dict)
        for row in rows:
            blocks[row['pair_id']][row['arm']] = row
        marginal, cumulative = [], []
        for pair_id, arms in sorted(blocks.items()):
            a, b = arms['eal'], arms['ordinary']
            identity = {**{key: a[key] for key in ('case', 'cohort', 'donor', 'receiver', 'native_tools', 'repeat')},
                        'pair_id': pair_id, 'contrast': 'eal-ordinary',
                        'transition': 'same_model' if a['donor'] == a['receiver'] else 'different_model'}
            for session in range(1, self.plan['recipient_sessions'] + 1):
                selected = [[s for s in row['sessions'] if s['session'] == session] for row in (a, b)]
                scores = [ss[0].get('score', {}).get('task_match') if ss else None for ss in selected]
                resources = [self.resources.summarise(ss, calls, session_ids={f"{row['sequence_id']}.session-{session}"})
                             for row, ss in zip((a, b), selected)]
                marginal.append({**identity, 'session': session, 'observed_pair': all(v is not None for v in scores),
                                 'task_difference': int(scores[0]) - int(scores[1]) if all(v is not None for v in scores) else None,
                                 'resource_differences': self.resource_difference(*resources)})
                totals, success = [], []
                for row in (a, b):
                    ss = [s for s in row['sessions'] if s['session'] <= session]
                    ids = {f"{row['sequence_id']}.session-{i}" for i in range(session + 1)}
                    totals.append(self.resources.summarise(ss, calls, session_ids=ids))
                    values = [s.get('score', {}).get('task_match') for s in ss if s['session'] > 0]
                    success.append(sum(values) if len(values) == session and all(v is not None for v in values) else None)
                cumulative.append({**identity, 'through_session': session,
                                   'recipient_task_difference': success[0] - success[1] if all(v is not None for v in success) else None,
                                   'resource_differences': self.resource_difference(*totals),
                                   'includes_initial_session': True})
        return marginal, cumulative

    @staticmethod
    def resource_difference(a: dict, b: dict) -> dict:
        complete = a['session_coverage_complete'] and b['session_coverage_complete']
        return {
            'elapsed_seconds': a['elapsed_seconds'] - b['elapsed_seconds'] if complete else None,
            'api_attempts': a['api_attempts'] - b['api_attempts'] if complete else None,
            'total_collector_calls': a['total_collector_calls'] - b['total_collector_calls']
                if a['collection_counts_complete'] and b['collection_counts_complete'] else None,
            'known_cost_usd': a['known_cost_usd'] - b['known_cost_usd']
                if complete and not a['unknown_cost_attempts'] and not b['unknown_cost_attempts'] else None,
            **{key: a[key] - b[key] if complete and a[flag] and b[flag] else None
               for key, flag in (('input_tokens', 'token_usage_complete'), ('output_tokens', 'token_usage_complete'),
                                 ('reasoning_tokens', 'reasoning_usage_complete'), ('cached_input_tokens', 'cached_usage_complete'))},
        }
