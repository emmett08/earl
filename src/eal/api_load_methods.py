"""Optional host-installed, typed method for a finite API load-test report.

The source and acquisition host decide whether a report applies to the target
run. This method only computes three inclusive sample criteria from statistics.
"""
from __future__ import annotations

from eal.methods import MethodContract, default_registry


NUMBER = {"type": "number", "minimum": 0, "maximum": 1e100}
OPTIONAL_NUMBER = {"anyOf": [NUMBER, {"type": "null"}]}
OPTIONAL_PERCENT = {"anyOf": [{"type": "number", "minimum": 0, "maximum": 100},
                              {"type": "null"}]}
OPTIONAL_INTEGER = {"anyOf": [{"type": "integer", "minimum": 0, "maximum": 1_000_000_000},
                              {"type": "null"}]}
OPTIONAL_BOOLEAN = {"anyOf": [{"type": "boolean"}, {"type": "null"}]}
REPORT_FIELDS = {
    "request_count": OPTIONAL_INTEGER,
    "p95_ms": OPTIONAL_NUMBER,
    "error_rate_percent": OPTIONAL_PERCENT,
    "report_valid": {"type": "boolean"},
    "identity_matches": OPTIONAL_BOOLEAN,
    "complete_records": OPTIONAL_BOOLEAN,
    "consistent_records": OPTIONAL_BOOLEAN,
    "age_seconds": OPTIONAL_NUMBER,
    "failed_requests": {"type": "integer", "minimum": 0, "maximum": 1_000_000_000},
}
RESULT_FIELDS = {"sample_size_met": {"type": "boolean"},
                 "latency_met": OPTIONAL_BOOLEAN, "error_limit_met": OPTIONAL_BOOLEAN,
                 "passes": {"type": "boolean"}, "fails": {"type": "boolean"}}


def assess_api_limits(report: dict) -> dict:
    """Interpret finite sample statistics; negative findings are results.

    An empty but otherwise complete requested run fails the sample-size
    condition. Nonempty runs must have computed finite statistics. The caller's
    evidence predicates decide report validity, identity and freshness.
    """
    count = report["request_count"]
    if count is None:
        raise ValueError("An admitted report requires a measured request count")
    if count:
        if report["p95_ms"] is None or report["error_rate_percent"] is None:
            raise ValueError("A nonempty report requires both measured statistics")
        latency = report["p95_ms"] <= 200
        errors = report["error_rate_percent"] <= 1
    else:
        # No observed latency or error rate is asserted for an empty run.
        if report["p95_ms"] is not None or report["error_rate_percent"] is not None:
            raise ValueError("An empty report cannot carry latency or error-rate statistics")
        latency = errors = None
    sample = count >= 100
    results = {"sample_size_met": sample, "latency_met": latency,
               "error_limit_met": errors}
    return {**results, "passes": all(value is True for value in results.values()),
            "fails": any(value is False for value in results.values())}


CONTRACT = MethodContract(
    identifier="engineering/api-load-criteria/1", evidence_kind="api_report",
    input_schema={"type": "object", "properties": REPORT_FIELDS,
                  "required": ["request_count", "p95_ms", "error_rate_percent"],
                  "additionalProperties": False},
    query_schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    output_schema={"type": "object", "properties": RESULT_FIELDS,
                   "required": list(RESULT_FIELDS), "additionalProperties": False},
    outputs={name: "boolean" for name in ("sample_size_met", "passes", "fails")},
    quantities=(), exact_unit=False, implementation=assess_api_limits,
    implementation_version="eal-api-load-criteria-1",
)


def registry():
    """Trusted MCP operator factory; the EAL source only names the method."""
    return default_registry().with_method(CONTRACT)
