"""Count model and collector resources without treating unknown usage as zero."""
from __future__ import annotations


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


class ResourceSummary:
    def summarise(self, sessions: list[dict], calls: list[dict], *, session_ids: set[str] | None = None) -> dict:
        ids = {s['session_id'] for s in sessions} if session_ids is None else session_ids
        selected = [c for c in calls if c['session_id'] in ids]
        events = [e for s in sessions for e in s.get('events', [])]
        host_events = [e for e in events if e['kind'] == 'eal_assess']
        host = [e['assessment'] for e in host_events if e.get('assessment') is not None]
        native = sum(e['kind'] == 'native_probe' for e in events)
        result = {
            'elapsed_seconds': sum(s['elapsed_seconds'] for s in sessions),
            'timed_sessions': len(sessions),
            'attempted_sessions': len({c['session_id'] for c in selected}),
            'context_seconds': sum(s.get('context_seconds', 0) for s in sessions),
            'api_attempts': len(selected),
            'known_cost_usd': sum(c['cost_estimate_usd'] or 0 for c in selected),
            'unknown_cost_attempts': sum(c['cost_estimate_usd'] is None for c in selected),
            'native_tool_calls': native,
            'host_collections': sum(a['collected_count'] for a in host),
            'host_reuses': sum(a['reused_count'] for a in host),
            'unknown_host_assessments': len(host_events) - len(host),
            'collection_counts_complete': len(host_events) == len(host) and len(sessions) == len(ids),
        }
        result['total_collector_calls'] = native + result['host_collections']
        usage = [_mapping(_mapping(c.get('response')).get('usage')) for c in selected]
        count = lambda value: value if type(value) is int and value >= 0 else 0
        result['input_tokens'] = sum(count(u.get('input_tokens')) for u in usage)
        result['output_tokens'] = sum(count(u.get('output_tokens')) for u in usage)
        result['reasoning_tokens'] = sum(count(_mapping(u.get('output_tokens_details')).get('reasoning_tokens')) for u in usage)
        result['cached_input_tokens'] = sum(count(_mapping(u.get('input_tokens_details')).get('cached_tokens')) for u in usage)
        result['token_usage_complete'] = all(type(u.get(k)) is int and u[k] >= 0
                                             for u in usage for k in ('input_tokens', 'output_tokens'))
        return result
