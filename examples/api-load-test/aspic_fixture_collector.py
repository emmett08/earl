"""Return fixed, labelled synthetic findings for the optional formal example."""
from __future__ import annotations

import json
from pathlib import Path
import sys

FIXTURE = Path(__file__).with_name("aspic-fixture.json")
CONTEXT = {"service": "orders-api", "build_id": "demo-build-42", "dataset": "synthetic"}
FIELDS = ("tool", "tool_version", "input", "context")


def collect(request):
    if (type(request) is not dict or set(request) != {"evidence_id", "environment", *FIELDS}
            or request["tool"] != "aspic_fixture" or request["tool_version"] != "1"
            or request["environment"] != "test_run" or request["context"] != CONTEXT
            or request["input"] != {"run_id": "demo-load-001"}):
        raise ValueError("The requested synthetic run or collector contract differs")
    fixture = json.loads(FIXTURE.read_text())
    if fixture["schema"] != "eal-aspic-demo/1" or fixture["dataset"] != "synthetic":
        raise ValueError("Unexpected fixture identity")
    identifier = request["evidence_id"]
    values = {"formal_theory": {
        "schema": "EAL/typed-input/1", "method": "argumentation/aspic/1",
        "subject": "orders-api", "quantity": "proposition", "unit": "1",
        "scope": "demo-load-001", "valid_from": "2026-09-25T10:00:00Z",
        "valid_until": "2026-09-25T10:00:01Z",
        "payload": {"theory": fixture["theory"]}},
        "checked_record": fixture["facts"]["report_checked"],
        "latency_record": fixture["facts"]["latency_ok"],
        "gap_record": fixture["facts"]["trace_gap"],
        "probe_record": fixture["facts"]["alternate_probe_ok"]}
    if identifier not in values:
        raise ValueError("Undeclared fixture observation")
    return {"value": values[identifier], "observed_at": fixture["observed_at"],
            "context": CONTEXT, "request": {key: request[key] for key in FIELDS}}


if __name__ == "__main__":
    try:
        print(json.dumps(collect(json.load(sys.stdin)), allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Synthetic ASPIC fixture failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
