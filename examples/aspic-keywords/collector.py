"""Return pinned synthetic observations; reject a different run or request."""
from __future__ import annotations

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
CONTEXT = {"device": "synthetic-controller", "run_id": "keywords-001", "dataset": "synthetic"}
FIELDS = ("tool", "tool_version", "input", "context")


def collect(request):
    if (type(request) is not dict or set(request) != {"evidence_id", "environment", *FIELDS}
            or request["tool"] != "fixture" or request["tool_version"] != "1"
            or request["environment"] != "bench" or request["context"] != CONTEXT
            or request["input"] != {"run_id": "keywords-001"}):
        raise ValueError("The requested synthetic run or collector contract differs")
    fixture = json.loads((HERE / "fixture.json").read_text(encoding="utf-8"))
    if fixture["schema"] != "eal-aspic-keywords/1" or fixture["dataset"] != "synthetic":
        raise ValueError("Unexpected fixture identity")
    values = dict(fixture["facts"])
    values["formal_theory"] = {
        "schema": "EAL/typed-input/1", "method": "argumentation/aspic/2",
        "subject": "synthetic-controller", "quantity": "proposition", "unit": "1",
        "scope": "keywords-001", "valid_from": "2026-10-01T07:00:00Z",
        "valid_until": "2026-10-01T07:00:01Z",
        "payload": {"theory": fixture["theory"]},
    }
    if request["evidence_id"] not in values:
        raise ValueError("Undeclared fixture observation")
    return {"value": values[request["evidence_id"]], "observed_at": fixture["observed_at"],
            "context": CONTEXT, "request": {key: request[key] for key in FIELDS}}


if __name__ == "__main__":
    try:
        print(json.dumps(collect(json.load(sys.stdin)), allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Synthetic ASPIC+ keyword fixture failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
