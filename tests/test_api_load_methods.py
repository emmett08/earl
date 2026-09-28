"""Boundary and missing-statistic cases for the installed API example method."""
from __future__ import annotations

from eal.api_load_methods import CONTRACT, registry
from eal.modes import assess_mode


def computed(report):
    result = assess_mode(CONTRACT.identifier, [{"id": "run", "kind": "api_report", "value": report}],
                         [], registry=registry())
    assert result["status"] == "supported", result
    return result["details"]


def test_inclusive_boundaries_and_independent_failure_results():
    limit = {"request_count": 100, "p95_ms": 200, "error_rate_percent": 1}
    assert computed(limit)["passes"] is True
    for change in ({"request_count": 99}, {"p95_ms": 200.001}, {"error_rate_percent": 1.001}):
        result = computed({**limit, **change})
        assert result["passes"] is False and result["fails"] is True
    empty = computed({"request_count": 0, "p95_ms": None, "error_rate_percent": None})
    assert empty["sample_size_met"] is False and empty["fails"] is True
    assert empty["latency_met"] is empty["error_limit_met"] is None


def test_malformed_or_incomplete_statistics_never_become_a_negative_result():
    for report in ({"request_count": None, "p95_ms": None, "error_rate_percent": None},
                   {"request_count": 100, "p95_ms": None, "error_rate_percent": 0},
                   {"request_count": True, "p95_ms": 200, "error_rate_percent": 0},
                   {"request_count": 100, "p95_ms": float("nan"), "error_rate_percent": 0},
                   {"request_count": 100, "p95_ms": 200, "error_rate_percent": 101},
                   {"request_count": 0, "p95_ms": 0, "error_rate_percent": None}):
        result = assess_mode(CONTRACT.identifier, [{"id": "run", "kind": "api_report", "value": report}],
                             [], registry=registry())
        assert result["status"] == "unsupported"
