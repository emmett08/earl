"""Publish measured collection progress without implying scientific completion."""
import json
import time

from experiments.transfer_study.workspace import write_json


class Progress:
    def __init__(self, root, rows, client, planned_sessions):
        self.root, self.rows, self.client, self.planned = root, rows, client, planned_sessions
        self.started = time.monotonic()
        self.initial = len(self.sessions())

    def sessions(self):
        return [s for row in self.rows for s in
                (row['sessions'] if 'sessions' in row else
                 ([row['donor_result']] if row.get('donor_result') else []) +
                 [v['result'] for v in row['variants'] if v.get('result')])]

    def __call__(self):
        sessions = self.sessions()
        elapsed = time.monotonic() - self.started
        new = len(sessions) - self.initial
        remaining = (self.planned - len(sessions)) * elapsed / new if new else None
        calls = self.client.records
        result = {'retained_sessions': len(sessions), 'planned_sessions': self.planned,
            'complete_blocks_or_sequences': sum(r['status'] == 'complete' for r in self.rows),
            'planned_blocks_or_sequences': len(self.rows), 'segment_elapsed_seconds': elapsed,
            'estimated_remaining_seconds': remaining, 'api_attempts': len(calls),
            'known_cost_usd': sum(c.get('cost_estimate_usd') or 0 for c in calls),
            'charged_or_reserved_usd': sum(c['charged_or_reserved_usd'] for c in calls),
            'unknown_cost_attempts': sum(c.get('cost_estimate_usd') is None for c in calls),
            'scope': 'Observed throughput estimate; annotation, analysis and future provider latency are excluded.'}
        write_json(self.root / 'progress.json', result)
        print(json.dumps(result), flush=True)
