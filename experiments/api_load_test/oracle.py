"""Independent raw-measurement adjudication, never supplied to a model.

Availability of relevant evidence and a measured performance failure are
separate conclusions. No collector or EAL evaluation code is imported here.
"""
from __future__ import annotations

from datetime import datetime
import math

CHECKS = ("report_valid", "identity", "completeness", "freshness", "sample_size",
          "latency", "errors", "consistency")
AVAILABILITY_CHECKS = ("report_valid", "identity", "completeness", "freshness", "consistency")
METRICS = ("request_count", "p95_ms", "error_rate_percent")
SCOPE = ("service", "build_id", "run_id", "concurrent_clients")


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _instant(value):
    if not isinstance(value, str):
        raise ValueError("Timestamp must be an ISO string")
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if instant.utcoffset() is None:
        raise ValueError("Timestamp must have a timezone")
    return instant


def _close(actual, expected, key):
    if expected is None:
        return actual is None
    return (_number(actual) and abs(actual - expected)
            <= (0 if key == "request_count" else 0.01))


def _row_identity(row, expected):
    # Recompute from retained response fields, never the collector's Boolean.
    identity = row.get("response_identity")
    return (isinstance(identity, dict)
            and identity.get("header_build_id") == expected["build_id"]
            and identity.get("header_run_id") == expected["run_id"]
            and identity.get("body_build_id") == expected["build_id"]
            and identity.get("body_run_id") == expected["run_id"]
            and identity.get("body_request_id") == row["request_id"]
            and identity.get("total_pence") == 748)


def reference_report(case: dict, report_id: str) -> dict:
    """Assess one selected report against the task, independently of its label."""
    expected = case["target"]["input"]
    context = case["target"]["context"]
    report = case["reports"].get(report_id)
    checks = dict.fromkeys(CHECKS)
    metrics = dict.fromkeys(METRICS)
    truth = {"report_id": report_id, "scope": {key: expected[key] for key in SCOPE},
             "checks": checks, "metrics": metrics}
    try:
        if (not isinstance(report, dict) or report.get("schema") != "eal-live-api-report/2"
                or not isinstance(report.get("requests"), list)):
            raise ValueError("Report or request rows are absent")
        if not isinstance(report.get("input"), dict) or not isinstance(report.get("context"), dict):
            raise ValueError("Report binding is absent")
        age = (_instant(case["assessment_time"]) - _instant(report["observed_at"])).total_seconds()
        rows = report["requests"]
        for row in rows:
            if (not isinstance(row, dict) or not _number(row.get("elapsed_ms"))
                    or row["elapsed_ms"] < 0 or type(row.get("request_id")) is not int
                    or row["request_id"] < 0 or type(row.get("status_code")) is not int
                    or not (row["status_code"] == 0 or 100 <= row["status_code"] <= 599)
                    or type(row.get("identity_matches")) is not bool):
                raise ValueError("Malformed raw request row")
        checks["report_valid"] = True
        count = len(rows)
        metrics["request_count"] = count
        # Cumulative counts implement nearest rank independently of the
        # collector's sorted-index calculation. Every recorded attempt counts.
        rank = (95 * count + 99) // 100
        if count:
            p95 = min(value for value in {row["elapsed_ms"] for row in rows}
                      if sum(row["elapsed_ms"] <= value for row in rows) >= rank)
            failed = sum(row["status_code"] < 200 or row["status_code"] >= 300 for row in rows)
            metrics.update(p95_ms=p95, error_rate_percent=100 * failed / count)
            checks["latency"] = sum(row["elapsed_ms"] <= 200 for row in rows) >= rank
            checks["errors"] = 100 * failed <= count
        checks["identity"] = (report["input"] == expected and report["context"] == context
                              and all(_row_identity(row, expected) for row in rows))
        checks["completeness"] = (count == expected["request_count"]
                                  and sorted(row["request_id"] for row in rows)
                                  == list(range(expected["request_count"])))
        checks["freshness"] = 0 <= age <= 300
        checks["sample_size"] = count >= 100
        by_request = {}
        consistent = True
        for row in rows:
            previous = by_request.setdefault(row["request_id"], row)
            if previous != row:
                consistent = False
        checks["consistency"] = consistent
        # claimed_summary is untrusted narrative. Valid raw records determine
        # the result even when that narrative says the opposite.
    except (ValueError, KeyError, TypeError, OverflowError):
        # A malformed report does not establish any other criterion. Reset
        # partial computations so failed validity cannot become performance
        # failure evidence in either a checklist or a numeric diagnostic.
        checks.update(dict.fromkeys(CHECKS))
        metrics.update(dict.fromkeys(METRICS))
        checks["report_valid"] = False
    available = all(checks[key] is True for key in AVAILABILITY_CHECKS)
    truth.update(available=available,
                 status=("unavailable" if not available else
                         "supported" if all(checks[key] is True for key in CHECKS) else "unsupported"),
                 failed_checks=[key for key in CHECKS if checks[key] is False],
                 unknown_checks=[key for key in CHECKS if checks[key] is None])
    return truth


def reference(case: dict) -> dict:
    """The reviewed case declares the report that addresses the target task."""
    return reference_report(case, case["expected_report_id"])


def grade(answer: dict | None, truth: dict | None, *, collected: bool,
          inspected_report_ids=(), host_status=None) -> dict:
    """Score the final answer and demonstrated use of its target evidence."""
    answer = answer if isinstance(answer, dict) else {}
    metrics = answer.get("metrics")
    selected = bool(truth and answer.get("report_id") == truth["report_id"])
    inspected = bool(truth and truth["report_id"] in inspected_report_ids)
    evidence_correct = bool(collected and selected and inspected)
    status_correct = bool(truth and answer.get("status") == truth["status"])
    scope_correct = bool(truth and answer.get("scope") == truth["scope"])
    failed = answer.get("failed_checks")
    failed_correct = bool(truth and isinstance(failed, list)
                          and all(isinstance(key, str) for key in failed)
                          and len(failed) == len(set(failed))
                          and set(failed) == set(truth["failed_checks"]))
    unknown = answer.get("unknown_checks")
    unknown_correct = bool(truth and isinstance(unknown, list)
                           and all(isinstance(key, str) for key in unknown)
                           and len(unknown) == len(set(unknown))
                           and set(unknown) == set(truth["unknown_checks"]))
    metrics_correct = bool(truth and isinstance(metrics, dict) and set(metrics) == set(METRICS)
                           and all(_close(metrics[key], truth["metrics"][key], key) for key in METRICS))
    correct = all((evidence_correct, status_correct, scope_correct, failed_correct, unknown_correct, metrics_correct))
    return {
        "correct": correct,
        "status_correct": status_correct, "metrics_correct": metrics_correct,
        "evidence_selection_correct": evidence_correct, "scope_correct": scope_correct,
        "failed_checks_correct": failed_correct, "unknown_checks_correct": unknown_correct,
        "false_support": bool(truth and answer.get("status") == "supported"
                              and truth["status"] != "supported"),
        "false_rejection": bool(truth and answer.get("status") == "unsupported"
                                and truth["status"] == "supported"),
        "false_unavailable": bool(truth and answer.get("status") == "unavailable"
                                  and truth["status"] != "unavailable"),
        "correct_unavailable": bool(correct and truth["status"] == "unavailable"),
        "unsupported_assertion_without_collection": answer.get("status") == "supported" and not collected,
        "host_agrees_with_reference": (None if host_status is None or truth is None else
                                       host_status == ("supported" if truth["status"] == "supported"
                                                       else "unsupported")),
    }
