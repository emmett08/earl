"""Count model and collector resources without treating unknown usage as zero."""
from __future__ import annotations

from collections import Counter
import math

from .accounting import AttemptReconciler


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _cost(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


class ResourceSummary:
    def summarise(self, sessions: list[dict], calls: list[dict], *, session_ids: set[str] | None = None,
                  include_unassigned: bool = False) -> dict:
        ids = {s['session_id'] for s in sessions} if session_ids is None else session_ids
        accounting = AttemptReconciler().reconcile(sessions, calls, ids, include_unassigned=include_unassigned)
        selected = accounting.calls
        events = [e for s in sessions for e in s.get('events', [])]
        host_events = [e for e in events if e['kind'] == 'eal_assess']
        host = [e['assessment'] for e in host_events if e.get('assessment') is not None]
        native = sum(e['kind'] == 'native_probe' for e in events)
        result = {
            'elapsed_seconds': sum(s['elapsed_seconds'] for s in sessions),
            'timed_sessions': sum(s.get('timing_complete', True) for s in sessions),
            'session_coverage_complete': accounting.session_coverage_complete and all(s.get('timing_complete', True) for s in sessions),
            'api_accounting_complete': accounting.complete,
            'accounting_errors': accounting.errors,
            'expected_api_attempts': accounting.expected_attempts,
            'attempted_sessions': len({c.get('session_id') for c in selected}),
            'context_seconds': sum(s.get('context_seconds', 0) for s in sessions),
            'api_attempts': len(selected),
            'attempt_status_counts': dict(sorted(Counter(c.get('status', 'unreported') for c in selected).items())),
            'known_cost_usd': sum(c['cost_estimate_usd'] for c in selected if _cost(c.get('cost_estimate_usd'))),
            'unknown_cost_attempts': sum(not _cost(c.get('cost_estimate_usd')) for c in selected),
            'native_tool_calls': native,
            'host_collections': sum(a['collected_count'] for a in host),
            'host_reuses': sum(a['reused_count'] for a in host),
            'unknown_host_assessments': len(host_events) - len(host),
            'collection_counts_complete': (len(host_events) == len(host) and accounting.session_coverage_complete
                                           and all(s.get('timing_complete', True) for s in sessions)),
        }
        result['cost_accounting_complete'] = accounting.complete and result['unknown_cost_attempts'] == 0
        result['total_collector_calls'] = native + result['host_collections']
        usage = [_mapping(_mapping(c.get('response')).get('usage')) for c in selected]
        count = lambda value: value if type(value) is int and value >= 0 else 0
        result['input_tokens'] = sum(count(u.get('input_tokens')) for u in usage)
        result['output_tokens'] = sum(count(u.get('output_tokens')) for u in usage)
        result['reasoning_tokens'] = sum(count(_mapping(u.get('output_tokens_details')).get('reasoning_tokens')) for u in usage)
        result['cached_input_tokens'] = sum(count(_mapping(u.get('input_tokens_details')).get('cached_tokens')) for u in usage)
        result['token_usage_complete'] = accounting.complete and all(type(u.get(k)) is int and u[k] >= 0
                                             for u in usage for k in ('input_tokens', 'output_tokens'))
        for field, container, key in (('reasoning_usage_complete', 'output_tokens_details', 'reasoning_tokens'),
                                      ('cached_usage_complete', 'input_tokens_details', 'cached_tokens')):
            values = [_mapping(u.get(container)).get(key) for u in usage]
            result[field] = accounting.complete and all(type(value) is int and value >= 0 for value in values)
        result['accounting_complete'] = (result['session_coverage_complete'] and result['api_accounting_complete'] and
                                         result['cost_accounting_complete'] and result['token_usage_complete'])
        return result
