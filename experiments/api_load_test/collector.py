"""Trusted command collector used by both experimental routes."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from eal.tool_acquisition import strict_json

from .api import measure


def collect(request: dict, config: dict, report_path: Path) -> dict:
    expected = {"tool": "api_load_test", "tool_version": "1", "mode": "nondeterministic",
                "input": config["input"], "context": config["context"]}
    if {key: request.get(key) for key in expected} != expected:
        raise ValueError("Collection request differs from the host-selected workload")
    if report_path.exists():
        raise ValueError("A trial may collect only once; existing report is immutable")
    report = measure(config)
    raw = (json.dumps(report, sort_keys=True, allow_nan=False) + "\n").encode()
    with report_path.open("xb") as stream:
        stream.write(raw)
    rows = report["requests"]
    count = len(rows)
    ordered = sorted(row["elapsed_ms"] for row in rows)
    failed = sum(not 200 <= row["status_code"] < 300 for row in rows)
    return {
        "value": {"request_count": count, "p95_ms": ordered[(95 * count + 99) // 100 - 1],
                  "failed_requests": failed, "error_rate_percent": failed * 100 / count,
                  "identity_matches": all(row["identity_matches"] for row in rows)},
        "observed_at": report["observed_at"], "context": report["context"], "request": expected,
        "details": {"dataset": report["dataset"], "report_sha256": hashlib.sha256(raw).hexdigest(),
                    "percentile": "nearest-rank over all attempted requests"},
    }


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
