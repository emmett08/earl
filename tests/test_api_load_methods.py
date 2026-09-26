"""Boundary and missing-statistic cases for the host-installed API method."""
from __future__ import annotations

from eal.api_load_methods import CONTRACT, registry
from eal.methods import schema_errors
from eal.modes import assess_mode
from eal.parser import parse
from eal.semantics import validate
from experiments.api_load_test.materials import CLAIM, FAILED_CLAIM, source_for


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


def test_source_declares_admissibility_separately_from_two_computed_claims():
    workload = {"run_id": "run-1", "build_id": "build-1", "concurrent_clients": 10,
                "service": "orders-api", "request_count": 100, "timeout_seconds": 3}
    source = source_for(workload, {"run_id": "run-1", "build_id": "build-1", "service": "orders-api"})
    program = parse(source)
    assert not validate(program, registry=registry())
    assert set(program.claims) == {CLAIM, FAILED_CLAIM}
    assert {predicate.path for predicate in program.evidence["load_test"].predicates} == {
        "report_valid", "identity_matches", "complete_records", "consistent_records", "age_seconds"}
    assert {value.method for value in program.reasoning.values()} == {CONTRACT.identifier}
    assert {predicate.path for value in program.reasoning.values() for predicate in value.predicates} == {
        "passes", "fails"}
    assert schema_errors({"request_count": 100, "p95_ms": 200, "error_rate_percent": 1},
                         CONTRACT.input_schema) == []
