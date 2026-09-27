#!/usr/bin/env python3
"""Collect bounded pre-A facts from the frozen fulfilment baseline.

This host command deliberately knows nothing about feature A or B. It checks
the recorded baseline file digest before each acquisition; the returned test
verdict is local to named tests and the port check is syntactic. A failed test
is a usable negative finding, while a missing fixture or changed digest is a
collection error.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


HERE = Path(__file__).resolve().parent
BASE = HERE / "materials" / "base"
FREEZE = HERE / "materials" / "freeze-base.json"
CONTEXT = {"experiment": "architecture-extension-v2", "stage": "pre-A"}
TOOL = "baseline_probe"
VERSION = "1"
ACQUISITION = ("tool", "tool_version", "input", "context")
SCHEMA = "fulfilment-baseline-probe/1"

# These names are part of the prespecified check, not discovered from a
# successful output. A renamed or unexecuted test makes the check fail.
STAGE_TESTS = (
    "test_quote_reserve_capture_dispatch_and_event",
    "test_failed_event_delivery_keeps_order_and_preserves_event_order",
    "test_multi_depot_configuration_exposes_primary_only_in_baseline",
)
ROLLBACK_TESTS = (
    "test_successful_replay_has_no_duplicate_effects_and_conflict_is_rejected",
    "test_atomic_out_of_stock_rejects_whole_order",
    "test_payment_failure_releases_inventory_then_retry_uses_new_attempt",
    "test_carrier_failure_refunds_and_releases_then_retry_recaptures",
    "test_transaction_failure_cancels_dispatch_refunds_and_releases",
    "test_unreconciled_refund_failure_is_explicit",
    "test_carrier_failure_injection_contract",
    "test_input_validation_and_canonical_request_scope",
)
PORT_METHODS = {
    "PricingPort": {"quote"},
    "StockPort": {"reserve", "release"},
    "PaymentPort": {"capture", "refund"},
    "ShippingPort": {"dispatch", "cancel"},
    "OrderStore": {"get", "begin_attempt", "save", "pending_events", "ack"},
    "EventSink": {"publish"},
}


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON key {key!r}")
        value[key] = item
    return value


def baseline_digest(base: Path = BASE) -> str:
    if not base.is_dir():
        raise ValueError("Baseline directory absent")
    digest = hashlib.sha256()
    files = sorted(path for path in base.rglob("*") if path.is_file()
                   and (path.suffix == ".py" or path.name == "ARCHITECTURE.md")
                   and "__pycache__" not in path.parts)
    if not files:
        raise ValueError("Baseline has no source files")
    for path in files:
        if path.is_symlink():
            raise ValueError("Baseline contains a symbolic link")
        digest.update(str(path.relative_to(base)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _frozen_digest() -> str:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    if (type(freeze) is not dict or freeze.get("schema") != "fulfilment-baseline-freeze/1"
            or not isinstance(freeze.get("source_sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", freeze["source_sha256"]) is None):
        raise ValueError("Malformed baseline freeze")
    actual = baseline_digest()
    if actual != freeze["source_sha256"]:
        raise ValueError("Baseline source differs from pre-A freeze")
    return actual


def _run_tests(selected: tuple[str, ...]) -> tuple[bool, str, dict]:
    cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests",
           "-p", "test_baseline.py", "-v"]
    for name in selected:
        cmd.extend(("-k", name))
    result = subprocess.run(cmd, cwd=BASE, text=True, capture_output=True, timeout=30,
                            check=False)
    output = result.stdout + result.stderr
    if len(output.encode("utf-8")) > 65536:
        raise ValueError("Test output exceeds collector bound")
    match = re.search(r"Ran (\d+) tests? in ", output)
    observed = int(match.group(1)) if match else -1
    executed = [name for name in selected if re.search(rf"^{re.escape(name)} \(", output, re.M)]
    passed = (result.returncode == 0 and observed == len(selected)
              and len(executed) == len(selected) and re.search(r"^OK$", output, re.M) is not None)
    detail = (f"{len(executed)}/{len(selected)} named tests appeared, "
              f"{observed} tests ran, exit {result.returncode}")
    return passed, detail, {
        "test_names": list(selected), "executed_names": executed,
        "observed_count": observed, "exit_code": result.returncode,
        "command": "python -m unittest discover -s tests -p test_baseline.py -v "
                   + " ".join(f"-k {name}" for name in selected),
        "output": output[-12000:],
    }


def _port_contract() -> tuple[bool, str, dict]:
    path = BASE / "fulfilment" / "ports.py"
    service = BASE / "fulfilment" / "service.py"
    ports_tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    service_tree = ast.parse(service.read_text(encoding="utf-8"), filename=str(service))
    found: dict[str, list[str]] = {}
    for node in ports_tree.body:
        if not isinstance(node, ast.ClassDef) or node.name not in PORT_METHODS:
            continue
        if not any(isinstance(base, ast.Name) and base.id == "Protocol" for base in node.bases):
            continue
        found[node.name] = [method.name for method in node.body
                            if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))]
    expected = {name: sorted(methods) for name, methods in PORT_METHODS.items()}
    actual = {name: sorted(methods) for name, methods in found.items()}
    checkout = next((node for node in service_tree.body
                     if isinstance(node, ast.ClassDef) and node.name == "CheckoutService"), None)
    init = next((node for node in checkout.body if isinstance(node, ast.FunctionDef)
                 and node.name == "__init__"), None) if checkout else None
    annotations = {
        argument.arg: argument.annotation.id
        for argument in init.args.args if isinstance(argument.annotation, ast.Name)
    } if init else {}
    injected = {
        "pricing": "PricingPort", "stock": "StockPort", "payments": "PaymentPort",
        "shipping": "ShippingPort", "orders": "OrderStore", "events": "EventSink",
    }
    passed = actual == expected and all(annotations.get(key) == value
                                        for key, value in injected.items())
    detail = "six Protocol declarations and CheckoutService injection signatures match" if passed else (
        "a Protocol or CheckoutService injection signature differs")
    return passed, detail, {"expected": expected, "actual": actual,
                            "injected_annotations": annotations}


def collect(request: object) -> dict:
    if (type(request) is not dict
            or set(request) != {"evidence_id", "environment", *ACQUISITION}
            or not isinstance(request["evidence_id"], str)
            or request["environment"] != "fulfilment_baseline"
            or request["tool"] != TOOL or request["tool_version"] != VERSION
            or request["context"] != CONTEXT):
        raise ValueError("Unexpected baseline-probe request or context")
    source_sha256 = _frozen_digest()
    query = request["input"]
    if type(query) is not dict:
        raise ValueError("Input must identify one check or design flag")
    if set(query) == {"check_id"} and query["check_id"] == "stage_contract":
        passed, detail, record = _run_tests(STAGE_TESTS)
    elif set(query) == {"check_id"} and query["check_id"] == "rollback_idempotency":
        passed, detail, record = _run_tests(ROLLBACK_TESTS)
    elif set(query) == {"check_id"} and query["check_id"] == "ports":
        passed, detail, record = _port_contract()
    elif set(query) == {"design_flag"} and query["design_flag"] == "longitudinal_followup":
        passed, detail, record = False, "No subsequent-change follow-up exists at pre-A", {
            "design_flag": "longitudinal_followup"}
    else:
        raise ValueError("Unknown pre-A check or design flag")

    now = datetime.now(timezone.utc).isoformat()
    value = {"schema": SCHEMA, "passed": passed, "detail": detail,
             "source_sha256": source_sha256, "query": query, "record": record}
    return {"value": value, "observed_at": now, "context": CONTEXT,
            "request": {key: request[key] for key in ACQUISITION},
            "details": {"schema": SCHEMA, "source_sha256": source_sha256}}


if __name__ == "__main__":
    try:
        request = json.load(sys.stdin, object_pairs_hook=_unique_object,
                            parse_constant=lambda value: (_ for _ in ()).throw(
                                ValueError(f"Nonfinite JSON number {value}")))
        print(json.dumps(collect(request), allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired,
            SyntaxError, UnicodeError) as exc:
        print(f"Baseline collection failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
