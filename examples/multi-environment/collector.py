"""Read pinned synthetic samples; this collector measures no deployed system."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def collect(request: dict) -> dict:
    if set(request) != {"evidence_id", "environment", "tool", "tool_version", "input", "context"}:
        raise ValueError("Unexpected collection request fields")
    if (request["tool"], request["tool_version"]) != ("temperature_samples", "1"):
        raise ValueError("Expected temperature_samples/1")
    fixture = json.loads(Path(__file__).with_name("fixtures.json").read_text())
    if request["input"] != {"fixture": fixture["schema"], "unit": fixture["unit"]}:
        raise ValueError("Synthetic fixture identity or unit differs")
    context = request["context"]
    if not isinstance(context, dict) or set(context) != {"dataset", "deployment", "sensor", "scenario"}:
        raise ValueError("Expected one explicitly selected environment context")
    if (context["dataset"], context["sensor"]) != (fixture["dataset"], fixture["sensor"]):
        raise ValueError("Synthetic dataset or sensor differs")
    deployment = context["deployment"]
    if request["environment"] != deployment or deployment not in fixture["samples"]:
        raise ValueError("Requested environment differs from the selected deployment")
    scenario = context["scenario"]
    if scenario not in fixture["samples"][deployment]:
        raise ValueError("Unknown synthetic scenario")
    samples = fixture["samples"][deployment][scenario]
    if not samples or any(type(value) not in (int, float) or not math.isfinite(value) for value in samples):
        raise ValueError("Synthetic samples must be finite numbers")
    return {
        "value": {"samples": samples},
        "observed_at": fixture["observed_at"],
        "context": context,
        "request": {key: request[key] for key in ("tool", "tool_version", "input", "context")},
        "details": {"dataset": fixture["dataset"], "deployment": deployment, "scenario": scenario,
                    "unit": fixture["unit"]},
    }


if __name__ == "__main__":
    try:
        print(json.dumps(collect(json.load(sys.stdin)), allow_nan=False))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"Synthetic temperature collection failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
