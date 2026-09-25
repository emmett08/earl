"""Replay a SHA-256 pinned, explicitly historical GitHub API projection."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from collect_workflow import _ROOT, _parse_json, collect


RECEIPT = Path(__file__).with_name("receipt.json")
RECEIPT_SHA256 = "5af7e43b779e01419821d5996596f1887a027bff871c0e55c7b66aef3c19d0c4"


def captured(request):
    raw = RECEIPT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != RECEIPT_SHA256:
        raise ValueError("The reviewed GitHub API projection changed")
    fixture = _parse_json(raw)
    if fixture.get("schema") != "eal2-github-workflow-receipt/1":
        raise ValueError("Wrong captured receipt schema")
    data = request["input"]
    base = f"/repos/{data['repository']}/actions/runs/{data['run_id']}"
    paths = [base, f"{base}/attempts/{data['run_attempt']}",
             f"{base}/attempts/{data['run_attempt']}/jobs?per_page=100&page=1"]
    if fixture["provenance"]["urls"] != [_ROOT + path for path in paths]:
        raise ValueError("Captured API endpoints differ from request")
    responses = fixture["responses"]
    mapping = dict(zip(paths, (responses["current_run"], responses["attempt"], responses["jobs"])))
    result = collect(request, mapping.__getitem__, acquisition_label="captured_api",
                     observed_at=fixture["provenance"]["projection_recorded_at"],
                     expected_mode="deterministic")
    result["details"].update({"offline_receipt": True, "receipt_sha256": RECEIPT_SHA256,
                              "historical_projection_at": fixture["provenance"]["projection_recorded_at"]})
    return result


def main():
    try:
        request = _parse_json(sys.stdin.buffer.read(2 * 1024 * 1024 + 1))
        result = captured(request)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Historical projection collection failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
