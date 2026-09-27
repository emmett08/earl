#!/usr/bin/env python3
"""Deterministic, synthetic refund-status observations for a bounded EAL case.

Provider and reconciliation records are separate, pinned files. This is a
decision-table experiment, not an observation of a payment service or of debt.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
CASES = HERE / "cases"
CASE_IDS = ("applied_ready", "applied_unreconciled", "not_applied",
            "unknown", "unavailable", "stale_applied", "tool_error")
RECORDS = ("provider", "ledger", "freshness")
MAX_AGE = 60
KEY = "refund:order-7:request-r"


def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def read(case: str, kind: str) -> tuple[dict[str, Any], str]:
    if case not in CASE_IDS or kind not in ("provider", "ledger"):
        raise ValueError("unrecognised synthetic case or record")
    path = CASES / case / f"{kind}.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        raise ValueError("synthetic record is missing, linked, or oversized")
    raw = path.read_bytes()
    data = json.loads(raw, object_pairs_hook=unique)
    common = {"schema", "basis", "operation_key", "age_seconds"}
    extra = {"status"} if kind == "provider" else {"inventory_reconciled", "event_reconciled"}
    if (set(data) != common | extra or data["schema"] != f"refund-{kind}-simulation/1"
            or data["basis"] != "synthetic" or data["operation_key"] != KEY
            or type(data["age_seconds"]) is not int
            or not 0 <= data["age_seconds"] <= 3600):
        raise ValueError("synthetic record has an invalid schema, identity or age")
    if kind == "provider":
        if data["status"] not in ("applied", "not_applied", "unknown", "unavailable", "tool_error"):
            raise ValueError("invalid provider status")
    elif any(type(data[name]) is not bool for name in ("inventory_reconciled", "event_reconciled")):
        raise ValueError("reconciliation fields must be Boolean")
    return data, hashlib.sha256(raw).hexdigest()


def observe(case: str, kind: str, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    provider, provider_sha = read(case, "provider")
    ledger, ledger_sha = read(case, "ledger")
    if kind not in RECORDS:
        raise ValueError("unknown record kind")
    if provider["status"] == "tool_error" and kind in ("provider", "freshness"):
        raise ValueError("synthetic provider acquisition failure before any status observation")
    if kind == "provider":
        source, sha = provider, provider_sha
    elif kind == "ledger":
        source, sha = ledger, ledger_sha
    else:
        source, sha = {"age_seconds": provider["age_seconds"]}, provider_sha
    value = {"schema": "refund-status-observation/1", "basis": "synthetic",
             "case_id": case, "operation_key": KEY, "record": kind,
             "source_sha256": sha, "age_seconds": source["age_seconds"]}
    if kind == "provider":
        value["status"] = provider["status"]
    elif kind == "ledger":
        value.update(inventory_reconciled=ledger["inventory_reconciled"],
                     event_reconciled=ledger["event_reconciled"])
    else:
        value["fresh"] = provider["age_seconds"] <= MAX_AGE
    observed_at = now if kind == "freshness" else now - timedelta(seconds=source["age_seconds"])
    return {"value": value, "observed_at": observed_at.isoformat(),
            "details": {"schema": "refund-status-observation/1",
                        "source_role": "provider" if kind != "ledger" else "separate ledger"}}


def collect(request: Any) -> dict[str, Any]:
    if not isinstance(request, dict) or set(request) != {
            "evidence_id", "environment", "tool", "tool_version", "input", "context"}:
        raise ValueError("invalid EAL tool request")
    if request["environment"] != "refund_case" or request["tool"] != "refund_status" or request["tool_version"] != "1":
        raise ValueError("unexpected EAL tool identity")
    context, input_data = request["context"], request["input"]
    if (not isinstance(context, dict) or set(context) != {"experiment", "case_id"}
            or context["experiment"] != "architecture-extension-v3-release-gate"
            or context["case_id"] not in CASE_IDS or not isinstance(input_data, dict)
            or set(input_data) != {"record"} or input_data["record"] not in RECORDS):
        raise ValueError("invalid synthetic context or request input")
    result = observe(context["case_id"], input_data["record"])
    result["context"] = context
    result["request"] = {key: request[key] for key in ("tool", "tool_version", "input", "context")}
    return result


def plain_decision(case: str, now: datetime | None = None) -> dict[str, Any]:
    """Strong plain-rule comparator over exactly the EAL collector's facts."""
    try:
        observations = {kind: observe(case, kind, now)["value"] for kind in RECORDS}
    except (OSError, ValueError) as exc:
        return {"schema": "refund-decision/1", "case_id": case, "basis": "synthetic",
                "action": "BLOCK_COMPLETION", "reason": "provider acquisition failed; status unavailable",
                "acquisition_error": str(exc),
                "qualification": "No live provider, code quality or future-debt outcome was measured."}
    status = observations["provider"]["status"]
    fresh = observations["freshness"]["fresh"]
    reconciled = (observations["ledger"]["inventory_reconciled"]
                  and observations["ledger"]["event_reconciled"]
                  and observations["ledger"]["age_seconds"] <= MAX_AGE)
    if not fresh:
        action, reason = "BLOCK_COMPLETION", "provider observation stale; obtain a current status"
    elif status == "not_applied":
        action, reason = "RETRY_SAME_KEY", "provider reports no refund; retain the stable key"
    elif status == "applied" and reconciled:
        action, reason = "COMPLETE", "applied status and distinct inventory/event records reconciled"
    else:
        action, reason = "BLOCK_COMPLETION", "unknown/unavailable status or incomplete reconciliation"
    return {"schema": "refund-decision/1", "case_id": case, "basis": "synthetic",
            "action": action, "reason": reason, "observations": observations,
            "qualification": "No live provider, code quality or future-debt outcome was measured."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plain", choices=CASE_IDS)
    args = parser.parse_args()
    try:
        if args.plain:
            result = plain_decision(args.plain)
        else:
            raw = sys.stdin.buffer.read(8193)
            if len(raw) > 8192:
                raise ValueError("tool request exceeds 8192 bytes")
            result = collect(json.loads(raw, object_pairs_hook=unique))
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Refund-status collection failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
