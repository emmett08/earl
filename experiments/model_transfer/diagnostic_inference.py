"""Bound each component contrast at its independent donor-block level."""
from __future__ import annotations

from collections import defaultdict
import statistics

from .bounded_statistics import bounded_interval


def summarise(comparisons: list[dict], confidence: float = .95) -> list[dict]:
    groups = defaultdict(list)
    for row in comparisons:
        groups[(row['factor'], tuple(row['levels']), row['receiver'], row['native_tools'],
                row.get('recipient_session', 1), row.get('evidence_condition', {}).get('task_family'))].append(row)
    output = []
    for (factor, levels, receiver, tools, position, family), rows in sorted(groups.items(), key=lambda item: str(item[0])):
        donors = [row['block_id'] for row in rows]
        if len(donors) != len(set(donors)):
            raise ValueError('A diagnostic donor cannot count twice in one contrast')
        lower, upper = [], []
        for row in rows:
            value = row['decision_difference_right_minus_left']
            lower.append(value if value is not None else -1)
            upper.append(value if value is not None else 1)
        interval, radius = bounded_interval(lower, upper, (-1, 1), (1 - confidence) / (2 * len(groups)))
        output.append({'factor': factor, 'levels': list(levels), 'receiver': receiver, 'native_tools': tools,
            'donor_blocks': len(rows), 'unknown_blocks': sum(a != b for a, b in zip(lower, upper)),
            'difference_bounds': [statistics.mean(lower), statistics.mean(upper)], 'interval': interval,
            'sampling_half_width': radius, 'nominal_family_confidence': confidence,
            'conclusion': 'right_improves_correctness' if interval[0] > 0 else
                'right_reduces_correctness' if interval[1] < 0 else 'unresolved',
            'scope': 'Selected donor blocks; shared recipients across contrasts are not pooled as independent observations.'})
        if any('recipient_session' in row for row in rows):
            output[-1]['recipient_session'] = position
        if family is not None:
            output[-1]['task_family'] = family
    return output
