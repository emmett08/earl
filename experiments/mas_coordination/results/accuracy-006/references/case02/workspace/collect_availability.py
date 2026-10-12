"""Read one pinned synthetic snapshot; observe no deployed service."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
from eal.tool_acquisition import strict_json

MAX_BYTES = 16384

def collect(request, raw):
    if not isinstance(request, dict) or set(request) != {
        "evidence_id", "environment", "tool", "tool_version", "input", "context"
    }:
        raise ValueError("Unexpected collection request fields")
    if (request["tool"], request["tool_version"]) != ("synthetic_availability", "1"):
        raise ValueError("Expected synthetic_availability/1")
    if len(raw) > MAX_BYTES:
        raise ValueError("Synthetic snapshot is too large")
    fixture = strict_json(raw.decode("utf-8"))
    if not isinstance(fixture, dict) or set(fixture) != {"schema", "observed_at", "context", "value"}:
        raise ValueError("Unexpected synthetic snapshot fields")
    if fixture["schema"] != "EAL/synthetic-availability-snapshot/1":
        raise ValueError("Unexpected synthetic snapshot schema")
    if request["input"] != {"snapshot": fixture["schema"], "snapshot_sha256": hashlib.sha256(raw).hexdigest()}:
        raise ValueError("Synthetic snapshot identity differs")
    if request["context"] != fixture["context"] or request["context"].get("dataset") != "synthetic":
        raise ValueError("Synthetic snapshot context differs")
    if request["environment"] != "demo":
        raise ValueError("Synthetic snapshot environment differs")
    value = fixture["value"]
    if not isinstance(value, dict) or set(value) != {"heartbeats", "responsive_nodes", "outage_count"}:
        raise ValueError("Unexpected synthetic snapshot values")
    if any(type(item) is not int or item < 0 for item in value.values()):
        raise ValueError("Snapshot counters must be nonnegative integers")
    return {"value": value, "observed_at": fixture["observed_at"], "context": request["context"],
            "request": {key: request[key] for key in ("tool", "tool_version", "input", "context")},
            "details": {"dataset": "synthetic", "snapshot_sha256": request["input"]["snapshot_sha256"]}}

if __name__ == "__main__":
    try:
        request = strict_json(sys.stdin.buffer.read(MAX_BYTES + 1).decode("utf-8"))
        raw = Path(__file__).with_name("availability.json").read_bytes()
        print(json.dumps(collect(request, raw), allow_nan=False))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"Synthetic snapshot collection failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
