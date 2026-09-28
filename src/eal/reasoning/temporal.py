"""Check a property and sampling coverage over a bounded recorded trace."""
from __future__ import annotations

import operator

from .strategy import BuiltinStrategy
from .validation import _list, _number, _object, _result


def _temporal(value):
    _object(value, ("start", "end", "max_gap", "events", "property", "semantics"), "trace")
    if value["semantics"] != "sampled":
        raise ValueError("Temporal mode supports only explicitly sampled semantics")
    start, end, max_gap = [_number(value[key], key) for key in ("start", "end", "max_gap")]
    if start > end or max_gap <= 0:
        raise ValueError("Trace requires start <= end and max_gap > 0")
    _object(value["property"], ("operator", "value"), "trace property")
    comparisons = {"lt": operator.lt, "le": operator.le, "eq": operator.eq,
                   "ne": operator.ne, "ge": operator.ge, "gt": operator.gt}
    op = value["property"]["operator"]
    if not isinstance(op, str) or op not in comparisons:
        raise ValueError("Trace property operator must be lt/le/eq/ne/ge/gt")
    threshold = _number(value["property"]["value"], "property value")
    events = _list(value["events"], "events")
    times, failures = [], []
    for event in events:
        _object(event, ("time", "value"), "trace event")
        time = _number(event["time"], "event time")
        observation = _number(event["value"], "event value")
        if not start <= time <= end or times and time <= times[-1]:
            raise ValueError("Events must be strictly time-ordered and within the declared interval")
        times.append(time)
        if not comparisons[op](observation, threshold):
            failures.append(time)
    largest_gap = max((b - a for a, b in zip(times, times[1:])), default=0.0)
    coverage = times[0] == start and times[-1] == end and largest_gap <= max_gap
    holds = not failures
    return _result(coverage,
                   "The sampled property holds throughout the complete declared sampling contract" if coverage and holds
                   else "The sampling contract has a gap or missing endpoint" if not coverage
                   else "The sampled trace contains a property violation",
                   holds=holds, coverage=coverage, sample_size=len(events), largest_gap=largest_gap,
                   violation_count=len(failures), violation_times=failures,
                   semantics="sampled", continuous_truth_established=False)


STRATEGY = BuiltinStrategy("temporal", _temporal)
