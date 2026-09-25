"""Inspect immutable measured evidence; shared by direct and MCP routes."""
from __future__ import annotations
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sys
from eal.tool_acquisition import strict_json
from .cases import canonical_bytes, digest


def inspect(report: dict, target: dict, assessment_time: str) -> dict:
    """Compute measurement facts, never a direct-arm acceptance verdict."""
    rows = report.get("requests")
    valid = (report.get("schema") == "eal-live-api-report/2" and isinstance(rows, list)
             and isinstance(report.get("input"), dict) and isinstance(report.get("context"), dict))
    if valid:
        valid = all(isinstance(row, dict)
                    and type(row.get("request_id")) is int and row["request_id"] >= 0
                    and type(row.get("elapsed_ms")) in (int, float)
                    and math.isfinite(row["elapsed_ms"]) and row["elapsed_ms"] >= 0
                    and type(row.get("status_code")) is int and (row["status_code"] == 0 or 100 <= row["status_code"] <= 599)
                    and type(row.get("identity_matches")) is bool for row in rows)
    workload = target["input"]
    ids = [row.get("request_id") for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    complete = (len(ids) == workload["request_count"] and all(type(value) is int for value in ids)
                and sorted(ids) == list(range(workload["request_count"])))
    identities = report.get("input") == workload and report.get("context") == target["context"]
    if valid:
        for row in rows:
            response = row.get("response_identity")
            if not isinstance(response, dict):
                identities = False
                continue
            identities = identities and (
                response.get("header_build_id") == workload["build_id"]
                and response.get("header_run_id") == workload["run_id"]
                and response.get("body_build_id") == workload["build_id"]
                and response.get("body_run_id") == workload["run_id"]
                and response.get("body_request_id") == row["request_id"]
                and response.get("total_pence") == 748)
    else:
        identities = False
    seen, consistent = {}, True
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict) or type(row.get("request_id")) is not int:
                continue
            key = row["request_id"]
            if key in seen and seen[key] != row:
                consistent = False
            seen[key] = row
    try:
        assessed = datetime.fromisoformat(assessment_time.replace("Z", "+00:00"))
        observed = datetime.fromisoformat(report["observed_at"].replace("Z", "+00:00"))
        if assessed.utcoffset() is None or observed.utcoffset() is None:
            raise ValueError("Timestamp requires timezone")
        age = (assessed - observed).total_seconds()
    except (ValueError, KeyError, TypeError, AttributeError):
        age, valid = None, False
    if valid:
        count = len(rows)
        ordered = sorted(row["elapsed_ms"] for row in rows)
        failed = sum(not 200 <= row["status_code"] < 300 for row in rows)
        metrics = {"request_count": count, "p95_ms": ordered[(95 * count + 99) // 100 - 1] if count else None,
                   "error_rate_percent": failed * 100 / count if count else None}
    else:
        metrics = {"request_count": None, "p95_ms": None, "error_rate_percent": None}
    return {"metrics": metrics, "facts": {"report_valid": bool(valid), "identity_matches": bool(identities) if valid else None,
            "complete_records": bool(complete) if valid else None, "consistent_records": bool(consistent) if valid else None,
            "age_seconds": age if valid else None}}


def collect(request: dict, config: dict, report_path: Path) -> dict:
    case = config["case"]
    report_id = request.get("input", {}).get("report_id")
    if report_id not in case["reports"]:
        raise ValueError("Choose a report_id from the provided catalogue")
    expected = {"tool": "api_load_test", "tool_version": "2", "mode": "deterministic",
                "input": {**case["target"]["input"], "report_id": report_id}, "context": case["target"]["context"]}
    if {key: request.get(key) for key in expected} != expected:
        raise ValueError("Collection request differs from the fixed target and selected report")
    report = case["reports"][report_id]
    # The controlled catalogue freezes a bound report envelope. Corrupt raw
    # measurements are scored unavailable, but missing acquisition metadata is
    # an apparatus failure: never invent an observation time to package it.
    try:
        if (not isinstance(report, dict) or report.get("schema") != "eal-live-api-report/2"
                or not isinstance(report.get("input"), dict) or not isinstance(report.get("context"), dict)
                or not isinstance(report.get("dataset"), str) or not report["dataset"]
                or not isinstance(report.get("observed_at"), str)):
            raise ValueError("Required report binding is absent")
        observed = datetime.fromisoformat(report["observed_at"].replace("Z", "+00:00"))
        if observed.utcoffset() is None:
            raise ValueError("Observation timestamp requires a timezone")
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Invalid report envelope metadata") from exc
    if digest(report) != case["audit"]["report_sha256"][report_id]:
        raise ValueError("Immutable report digest mismatch")
    raw = canonical_bytes(report)
    if report_path.exists():
        if report_path.read_bytes() != raw:
            raise ValueError("Existing selected-report artifact differs")
    else:
        with report_path.open("xb") as stream:
            stream.write(raw)
    measured = inspect(report, case["target"], case["assessment_time"])
    return {"value": {**measured["metrics"], **measured["facts"]},
            "observed_at": report["observed_at"], "context": expected["context"], "request": expected,
            "details": {"dataset": report["dataset"], "report_id": report_id,
                        "report_sha256": hashlib.sha256(raw).hexdigest(),
                        "reported_input": report["input"], "reported_context": report["context"],
                        "claimed_summary": report.get("claimed_summary"),
                        "assessment_time": case["assessment_time"],
                        "percentile": "nearest-rank over every recorded request"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        request = strict_json(sys.stdin.buffer.read(65537).decode())
        config = strict_json(args.config.read_text())
        print(json.dumps(collect(request, config, args.report), allow_nan=False))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Collection failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
