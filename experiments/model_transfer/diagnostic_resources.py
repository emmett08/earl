"""Unique diagnostic resources and duration coverage, separate from report layout."""
from __future__ import annotations

import math
from collections import Counter

from .resources import ResourceSummary


class DiagnosticResources:
    """Decorate shared accounting with bounded preparation timing and contrasts."""

    @staticmethod
    def summarise(sessions: list[dict], calls: list[dict], ids: set[str],
                   preparation: list[dict], *, include_unassigned: bool = False) -> dict:
        resources = ResourceSummary().summarise(sessions, calls, session_ids=ids,
                                                 include_unassigned=include_unassigned)
        durations = [stage.get('elapsed_seconds') for stage in preparation]
        known = [value for value in durations
                 if type(value) in (int, float) and math.isfinite(value) and value >= 0]
        timing_complete = len(known) == len(preparation)
        resources.update(
            preparation_seconds=sum(known), preparation_timing_complete=timing_complete,
            preparation_operations_complete=all(stage.get('status') == 'complete' for stage in preparation),
            preparation_status_counts=dict(sorted(Counter(stage.get('status', 'unreported')
                                                           for stage in preparation).items())),
            unknown_preparation_operations=len(preparation) - len(known),
            elapsed_with_preparation_seconds=resources['elapsed_seconds'] + sum(known),
            elapsed_with_preparation_complete=resources['session_coverage_complete'] and timing_complete)
        return resources

    @staticmethod
    def differences(resources: list[dict]) -> dict:
        left, right = resources
        accounted = all(item['api_accounting_complete'] for item in resources)
        known_tokens = accounted and all(item['token_usage_complete'] for item in resources)
        timed = all(item['session_coverage_complete'] for item in resources)
        return {**{key: right[key] - left[key] if known_tokens and all(item[flag] for item in resources) else None
                   for key, flag in (('input_tokens', 'token_usage_complete'), ('output_tokens', 'token_usage_complete'),
                                     ('reasoning_tokens', 'reasoning_usage_complete'), ('cached_input_tokens', 'cached_usage_complete'))},
                'api_attempts': right['api_attempts'] - left['api_attempts'] if accounted else None,
                'estimated_cost_usd': (right['known_cost_usd'] - left['known_cost_usd']
                    if all(item['cost_accounting_complete'] for item in resources) else None),
                'elapsed_seconds': right['elapsed_seconds'] - left['elapsed_seconds'] if timed else None,
                'preparation_seconds': (right['preparation_seconds'] - left['preparation_seconds']
                    if all(item['preparation_timing_complete'] for item in resources) else None),
                'elapsed_with_preparation_seconds': (right['elapsed_with_preparation_seconds'] - left['elapsed_with_preparation_seconds']
                    if all(item['elapsed_with_preparation_complete'] for item in resources) else None),
                'total_collector_calls': (right['total_collector_calls'] - left['total_collector_calls']
                    if all(item['collection_counts_complete'] for item in resources) else None)}
