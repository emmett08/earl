"""Synthetic report-envelope controls, not experimental observations."""
from __future__ import annotations

import copy

import pytest

from experiments.api_load_test.cases import digest
from experiments.api_load_test.collector import collect


def collector_fixture():
    workload = {"service": "orders-api", "build_id": "build-a", "run_id": "run-a",
                "concurrent_clients": 5, "request_count": 1, "timeout_seconds": 3}
    context = {"service": "orders-api", "build_id": "build-a", "run_id": "run-a",
               "dataset": "measured_controlled_api"}
    report = {"schema": "eal-live-api-report/2", "dataset": "measured_controlled_api",
              "input": copy.deepcopy(workload), "context": copy.deepcopy(context),
              "observed_at": "2026-09-25T12:00:00Z", "requests": [{
                  "request_id": 0, "status_code": 200, "elapsed_ms": "missing", "identity_matches": True}]}
    case = {"target": {"input": workload, "context": context},
            "assessment_time": "2026-09-25T12:01:00Z", "reports": {"selected": report},
            "audit": {"report_sha256": {"selected": digest(report)}}}
    request = {"evidence_id": "load_test", "environment": "test_run",
               "tool": "api_load_test", "tool_version": "2",
               "input": {**workload, "report_id": "selected"}, "context": context}
    return request, case, report


@pytest.mark.parametrize("field,value", [
    ("observed_at", None), ("observed_at", "not-an-instant"),
    ("observed_at", "2026-09-25T12:00:00"), ("input", None), ("context", None),
    ("dataset", None), ("dataset", ""), ("schema", "unrecognised")])
def test_invalid_envelope_is_an_explicit_instrument_rejection(tmp_path, field, value):
    request, case, report = collector_fixture()
    if value is None:
        report.pop(field)
    else:
        report[field] = value
    case["audit"]["report_sha256"]["selected"] = digest(report)
    path = tmp_path / "report.json"
    with pytest.raises(ValueError, match="Invalid report envelope metadata"):
        collect(request, {"case": case}, path)
    assert not path.exists()


def test_malformed_rows_keep_null_metrics_and_original_observation_time(tmp_path):
    request, case, report = collector_fixture()
    envelope = collect(request, {"case": case}, tmp_path / "report.json")
    assert envelope["observed_at"] == report["observed_at"]
    assert envelope["observed_at"] != case["assessment_time"]
    assert envelope["value"]["report_valid"] is False
    assert all(envelope["value"][key] is None for key in
               ("request_count", "p95_ms", "error_rate_percent", "age_seconds", "identity_matches"))
