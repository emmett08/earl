#!/usr/bin/env python3
"""Replay one exploratory, condition-masked architecture-review observation.

This post-run diagnostic is outside the frozen 15 independent assessor probes.
It imports each anonymous candidate in a fresh process and never reads a
condition mapping, EAL packet, agent report or assessment score.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CANDIDATES = ROOT / "review_candidates"
SCHEMA = "architecture-extension-v2/blinded-review-reproduction/1"


def source_digest(candidate: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((candidate / "fulfilment").rglob("*.py")):
        relative = path.relative_to(candidate).as_posix()
        content = path.read_bytes()
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def run_in_candidate() -> dict[str, Any]:
    from fulfilment import (  # type: ignore[import-not-found]
        CheckoutRequest, CheckoutService, InMemoryEventSink, InMemoryOrderStore,
        InMemoryPayments, InMemoryPricing, InMemoryShipping, InMemoryStock,
        RequestedLine, ReturnLine,
    )

    stock = InMemoryStock(
        {"north": {"lamp": 2}, "south": {"lamp": 1}},
        priorities=("north", "south"),
    )
    payments = InMemoryPayments()
    service = CheckoutService(
        InMemoryPricing({"lamp": Decimal("10.00")}), stock, payments,
        InMemoryShipping(), InMemoryOrderStore(), InMemoryEventSink(),
    )
    order = service.checkout(CheckoutRequest(
        "purchase", "customer", (RequestedLine("lamp", 3),),
        "address", "test-token",
    ))
    north = next(shipment for shipment in order.shipments if shipment.warehouse_id == "north")
    lines = (ReturnLine(north.shipment_id, "lamp", 2),)

    payments.fail_refund = True
    initial: dict[str, Any]
    try:
        service.return_items("purchase", "failed-refund", lines)
    except Exception as exc:
        initial = {"outcome": "raised", "error_type": type(exc).__name__,
                   "message": str(exc)}
    else:
        initial = {"outcome": "returned"}
    initial["refund_operations"] = len(payments.refunds)
    initial["north_stock"] = stock.on_hand["north"]["lamp"]

    payments.fail_refund = False
    second: dict[str, Any]
    try:
        receipt = service.return_items("purchase", "new-attempt", lines)
    except Exception as exc:
        second = {"outcome": "raised", "error_type": type(exc).__name__,
                  "message": str(exc)}
    else:
        second = {"outcome": "returned", "refunded_amount": str(receipt.refunded_amount)}
    second["refund_operations"] = len(payments.refunds)
    second["north_stock"] = stock.on_hand["north"]["lamp"]
    return {"initial": initial, "distinct_request_after_known_failure": second}


def child(candidate: Path) -> None:
    sys.path.insert(0, str(candidate.resolve()))
    print(json.dumps(run_in_candidate(), sort_keys=True))


def run_candidate(candidate: Path) -> dict[str, Any]:
    if not (candidate / "fulfilment" / "__init__.py").is_file():
        raise ValueError(f"candidate package is missing: {candidate}")
    command = [sys.executable, str(Path(__file__).resolve()), "--child", str(candidate)]
    completed = subprocess.run(
        command, cwd=candidate, capture_output=True, text=True, timeout=30,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(candidate)},
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"candidate process failed ({completed.returncode}): {completed.stderr[-4000:]}"
        )
    return {"source_digest": source_digest(candidate), **json.loads(completed.stdout)}


def verify(cases: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for label in ("C1", "C2"):
        initial = cases[label]["initial"]
        if (initial["outcome"], initial.get("error_type"), initial["refund_operations"],
                initial["north_stock"]) != ("raised", "RuntimeError", 0, 0):
            errors.append(f"{label}: initial pre-effect refund failure differs")
    accepted = cases["C1"]["distinct_request_after_known_failure"]
    if (accepted["outcome"], accepted.get("refunded_amount"),
            accepted["refund_operations"], accepted["north_stock"]) != (
                "returned", "24.00", 1, 2):
        errors.append("C1: distinct request did not recover the two north units")
    blocked = cases["C2"]["distinct_request_after_known_failure"]
    if (blocked["outcome"], blocked.get("error_type"),
            blocked["refund_operations"], blocked["north_stock"]) != (
                "raised", "ValueError", 0, 0):
        errors.append("C2: pending capacity did not block the distinct request")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path, default=ROOT / "review_reproduction.json")
    args = parser.parse_args()
    if args.child is not None:
        child(args.child)
        return
    cases = {label: run_candidate(CANDIDATES / label) for label in ("C1", "C2")}
    errors = verify(cases)
    report = {
        "schema_version": SCHEMA,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Exploratory post-run diagnostic derived from the masked source review; outside the frozen 15 assessor probes.",
        "source_paths": {
            "C1": "results/review_candidates/C1",
            "C2": "results/review_candidates/C2",
        },
        "scenario": "A two-unit north return fails with the in-memory pre-effect refund switch; after clearing the switch, a distinct request ID asks to return those same two units.",
        "candidates": cases,
        "verification": {"status": "pass" if not errors else "fail", "errors": errors},
        "interpretation_limit": "This reproduces the deterministic in-memory failed-refund branch. It does not identify an experimental treatment effect or decide how an ambiguous external refund failure should reserve capacity.",
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "status": report["verification"]["status"]},
                     sort_keys=True))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
