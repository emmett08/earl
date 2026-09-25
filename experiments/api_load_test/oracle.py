"""Independent result adjudication; never exposed to a model or collector."""

from __future__ import annotations

from datetime import datetime
import math


def reference(report: dict, expected_input: dict, context: dict, assessed_at: str) -> dict:
    rows = report["requests"]
    count = len(rows)
    if not count or any(type(row["elapsed_ms"]) not in (int, float)
                        or not math.isfinite(row["elapsed_ms"]) or row["elapsed_ms"] < 0 for row in rows):
        raise ValueError("Invalid measurement record")
    # Count observations on each side of the limit, independently of the
    # collector's sorted-index implementation of the percentile.
    rank = (95 * count + 99) // 100
    within = sum(row["elapsed_ms"] <= 200 for row in rows)
    failed = sum(row["status_code"] < 200 or row["status_code"] >= 300 for row in rows)
    p95 = min(value for value in {row["elapsed_ms"] for row in rows}
              if sum(row["elapsed_ms"] <= value for row in rows) >= rank)
    age = (datetime.fromisoformat(assessed_at.replace("Z", "+00:00"))
           - datetime.fromisoformat(report["observed_at"].replace("Z", "+00:00"))).total_seconds()
    identity = (report["input"] == expected_input and report["context"] == context
                and all(row["identity_matches"] for row in rows)
                and sorted(row["request_id"] for row in rows) == list(range(expected_input["request_count"])))
    checks = {"identity": identity, "age": 0 <= age <= 300, "sample_size": count >= 100,
              "latency": within >= rank, "errors": 100 * failed <= count}
    return {"status": "supported" if all(checks.values()) else "unsupported", "checks": checks,
            "metrics": {"request_count": count, "p95_ms": p95, "failed_requests": failed,
                        "error_rate_percent": 100 * failed / count, "identity_matches": identity}}


def grade(answer: dict | None, truth: dict | None, *, collected: bool, host_status=None) -> dict:
    answer = answer or {}
    numeric = ("request_count", "p95_ms", "error_rate_percent")
    metrics_correct = bool(truth) and all(
        type(answer.get(key)) in (int, float)
        and math.isfinite(answer[key])
        and abs(answer[key] - truth["metrics"][key]) <= (0 if key == "request_count" else 0.01)
        for key in numeric)
    status_correct = bool(collected and truth and answer.get("status") == truth["status"])
    return {"correct": status_correct and metrics_correct, "status_correct": status_correct,
            "metrics_correct": bool(metrics_correct),
            "false_support": bool(truth and answer.get("status") == "supported" and truth["status"] != "supported"),
            "unsupported_assertion_without_collection": answer.get("status") == "supported" and not collected,
            "host_agrees_with_reference": None if host_status is None or truth is None else host_status == truth["status"]}
