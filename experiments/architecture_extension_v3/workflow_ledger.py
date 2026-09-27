"""Extract an episode's reported usage without inventing missing charges.

The coding runner records an invocation manifest and the provider CLI's JSONL
stream. This parser runs later in the host-only job, where the independent
assessor is available. It never sends assessor findings back to an agent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens",
          "reasoning_output_tokens", "cache_creation_input_tokens")


def _count(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"trace line {line_number} is not an object")
        records.append(value)
    return records


def _codex_usage(events: list[dict[str, Any]]) -> dict[str, Any]:
    turns = [record["usage"] for record in events
             if record.get("type") == "turn.completed" and isinstance(record.get("usage"), dict)]
    if not turns:
        return {"status": "missing", "reason": "no turn.completed usage event"}
    totals = {key: 0 for key in FIELDS}
    for usage in turns:
        for field in FIELDS:
            totals[field] += _count(usage.get(field, 0), field)
    return {"status": "reported", "turns": len(turns), "totals": totals,
            "accounting": "sum of completed-turn usage events; provider bill not independently verified"}


def _claude_usage(events: list[dict[str, Any]]) -> dict[str, Any]:
    final = next((record for record in reversed(events) if record.get("type") == "result"), None)
    if final is None:
        return {"status": "missing", "reason": "no result event"}
    usage = final.get("usage")
    if not isinstance(usage, dict):
        return {"status": "missing", "reason": "result has no usage object"}
    totals = {key: _count(usage.get(key, 0), key) for key in FIELDS}
    totals["cached_input_tokens"] = _count(
        usage.get("cache_read_input_tokens", usage.get("cached_input_tokens", 0)),
        "cache_read_input_tokens")
    client_cost = final.get("total_cost_usd")
    if client_cost is not None and (type(client_cost) not in (int, float) or client_cost < 0):
        raise ValueError("total_cost_usd is invalid")
    models = final.get("modelUsage")
    return {"status": "reported", "totals": totals,
            "client_estimated_cost_usd": client_cost,
            "client_model_usage": models if isinstance(models, dict) else None,
            "accounting": "CLI result; client cost estimate can differ from provider bill"}


def extract(trace: Path, invocation: Path) -> dict[str, Any]:
    metadata = json.loads(invocation.read_text(encoding="utf-8"))
    if metadata.get("schema") != "architecture-v3-agent-invocation/1":
        raise ValueError("unexpected invocation schema")
    kind = metadata.get("agent_class")
    if kind not in ("codex_cli", "claude_cli"):
        raise ValueError("unknown agent class")
    events = _events(trace)
    usage = _codex_usage(events) if kind == "codex_cli" else _claude_usage(events)
    raw = trace.read_bytes() if trace.is_file() else b""
    return {"schema": "architecture-v3-workflow-ledger/1",
            "invocation": metadata,
            "trace_sha256": hashlib.sha256(raw).hexdigest() if raw else None,
            "trace_bytes": len(raw), "events": len(events), "usage": usage,
            "model_revision": "unknown unless independently exposed by the runner",
            "monetary_cost": None,
            "monetary_cost_reason": "requires dated provider rates, billing classes and runner rate"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--invocation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = extract(args.trace, args.invocation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["usage"]["status"], "trace_sha256": result["trace_sha256"]}))


if __name__ == "__main__":
    main()
