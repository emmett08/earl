"""Summarise one host-selected load-test report; never run a load test."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

from eal.semantics import parse_time
from eal.tool_acquisition import strict_json


MAX_BYTES = 1024 * 1024
IDENTITY = ("service", "build_id", "run_id", "concurrent_clients", "dataset")


def summarise(request: dict, raw: bytes) -> dict:
    """Bind report bytes and identity before computing the sample statistics."""
    if not isinstance(request, dict) or not isinstance(request.get("input"), dict):
        raise ValueError("Expected an EAL collection request with input")
    if (request.get("tool"), request.get("tool_version"), request.get("mode")) != (
        "load_test_report", "1", "deterministic"
    ):
        raise ValueError("Expected load_test_report/1 in deterministic mode")
    expected = request["input"]
    if set(expected) != {*IDENTITY, "report_sha256"}:
        raise ValueError("Input must identify the report and its SHA-256 digest")
    if len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != expected["report_sha256"]:
        raise ValueError("Report size or SHA-256 digest differs from the requested report")
    report = strict_json(raw.decode("utf-8"))
    if not isinstance(report, dict) or set(report) != {
        "schema", *IDENTITY, "observed_at", "requests"
    }:
        raise ValueError("Unexpected load-test report fields")
    if report["schema"] != "eal-api-load-test-report/1":
        raise ValueError("Unsupported load-test report schema")
    for key in IDENTITY:
        if type(report[key]) is not type(expected[key]) or report[key] != expected[key]:
            raise ValueError(f"Report identity differs: {key}")
    if any(not isinstance(report[key], str) or not report[key] for key in IDENTITY if key != "concurrent_clients"):
        raise ValueError("Report identifiers must be nonempty strings")
    if report["dataset"] not in {"synthetic", "measured"}:
        raise ValueError("Dataset must be labelled synthetic or measured")
    if type(report["concurrent_clients"]) is not int or report["concurrent_clients"] < 1:
        raise ValueError("Concurrent clients must be a positive integer")
    context = {key: report[key] for key in ("service", "build_id", "dataset")}
    if request.get("context") != context:
        raise ValueError("Report context differs from the assessment context")
    if not isinstance(report["observed_at"], str):
        raise ValueError("Report time must be an ISO-8601 string")
    parse_time(report["observed_at"])
    rows = report["requests"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Report must contain request results")
    latencies = []
    failures = 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"elapsed_ms", "status_code"}:
            raise ValueError("Each request needs elapsed_ms and status_code")
        latency, status = row["elapsed_ms"], row["status_code"]
        if type(latency) not in (int, float) or not math.isfinite(latency) or latency < 0:
            raise ValueError("Elapsed milliseconds must be finite and nonnegative")
        # Zero represents a transport failure or timeout, with its elapsed time.
        if type(status) is not int or not (status == 0 or 100 <= status <= 599):
            raise ValueError("Status must be an HTTP status code or zero for transport failure")
        latencies.append(latency)
        failures += not 200 <= status < 300
    count = len(rows)
    values = {
        "request_count": count,
        "p95_ms": sorted(latencies)[math.ceil(0.95 * count) - 1],
        "failed_requests": failures,
        "error_rate_percent": 100 * failures / count,
    }
    return {
        "value": values,
        "observed_at": report["observed_at"],
        "context": context,
        "request": {key: request[key] for key in ("tool", "tool_version", "mode", "input", "context")},
        "details": {"report_sha256": expected["report_sha256"], "dataset": report["dataset"],
                    "percentile": "nearest-rank over all recorded requests"},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path(__file__).with_name("report.json"))
    args = parser.parse_args()
    try:
        request = strict_json(sys.stdin.buffer.read(MAX_BYTES + 1).decode("utf-8"))
        with args.report.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        print(json.dumps(summarise(request, raw), allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Load-test report collection failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
