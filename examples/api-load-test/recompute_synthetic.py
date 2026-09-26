"""Recompute a pinned teaching fixture now; do not claim new measurements."""

from __future__ import annotations

import json
import hashlib
import math
from pathlib import Path
import sys

REPORT = Path(__file__).with_name("report.json")
MAX_BYTES = 1024 * 1024
IDENTITY = ("service", "build_id", "run_id", "concurrent_clients", "dataset")


def main() -> None:
    try:
        request = json.loads(sys.stdin.buffer.read(MAX_BYTES + 1).decode("utf-8"))
        if (request.get("tool"), request.get("tool_version")) != ("fixture_recompute", "1"):
            raise ValueError("Expected the reviewed fixture_recompute/1 request")
        if set(request) != {"evidence_id", "environment", "tool", "tool_version", "input", "context"}:
            raise ValueError("Unexpected collection request fields")
        raw = REPORT.read_bytes()
        expected = request["input"]
        if (len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != expected["report_sha256"]
                or set(expected) != {*IDENTITY, "report_sha256"}):
            raise ValueError("The bundled report differs from the pinned request")
        report = json.loads(raw)
        if (report["schema"] != "eal-api-load-test-report/1"
                or any(report[key] != expected[key] for key in IDENTITY)
                or request["context"] != {key: report[key] for key in ("service", "build_id", "dataset")}
                or report["dataset"] != "synthetic"):
            raise ValueError("Bundled report identity or synthetic context differs")
        rows = report["requests"]
        if not isinstance(rows, list) or not rows:
            raise ValueError("The bundled report needs recorded requests")
        latencies, failures = [], 0
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {"elapsed_ms", "status_code"}
                    or type(row["elapsed_ms"]) not in (int, float)
                    or not math.isfinite(row["elapsed_ms"]) or row["elapsed_ms"] < 0
                    or type(row["status_code"]) is not int
                    or not (row["status_code"] == 0 or 100 <= row["status_code"] <= 599)):
                raise ValueError("A request result has invalid latency or status")
            latencies.append(row["elapsed_ms"])
            failures += not 200 <= row["status_code"] < 300
        count = len(rows)
        values = {"request_count": count,
                  "p95_ms": sorted(latencies)[math.ceil(0.95 * count) - 1],
                  "failed_requests": failures, "error_rate_percent": 100 * failures / count}
        # This observation is the computation performed now. The report's
        # original observation time is retained as detail, never re-dated.
        result = {
            "value": values, "context": request["context"],
            "request": {key: request[key] for key in
                        ("tool", "tool_version", "input", "context")},
            "details": {"dataset": "synthetic", "assessment_kind": "recomputation",
                        "source_report_observed_at": report["observed_at"],
                        "report_sha256": expected["report_sha256"]},
        }
        print(json.dumps(result, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Synthetic fixture recomputation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
