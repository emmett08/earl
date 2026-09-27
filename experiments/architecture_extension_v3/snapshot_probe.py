"""Host-owned EAL collector for an immutable architecture-extension candidate.

The check cache is confined to one host assessment. Its key includes all
source and checker bytes, stage and interpreter identity. Each EAL evidence
still receives its own request-bound observation; a cached check is not a
substitute for an absent observation.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


MAX_FILES = 512
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TREE_BYTES = 16 * 1024 * 1024
EXCLUDED = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SIDECARS = {"AGENTS.md", "architecture-context.json", "FEATURE.md"}
CHECKS = {"source_binding", "visible_tests", "import_cycles", "shared_boundary"}
HEX = re.compile(r"[0-9a-f]{64}\Z")
# These review hypotheses are derived from the published requirement briefs
# and the known A-stage ports. They never read the sealed study assessor.
# They identify likely change surfaces, not prescribed implementation sites.
IMPACT = {
    ("R", "B"): ("CheckoutService.return_items", "StockPort.restore", "PaymentPort.refund",
                 "OrderStore.save_return"),
    ("R", "C"): ("CheckoutService.cancel_order", "ShippingPort.cancel", "PaymentPort.refund",
                 "StockPort.restore"),
    ("R", "D"): ("InMemoryPayments.refund_status", "InMemoryPayments.fail_after_refund",
                 "PaymentPort.refund", "CheckoutService.return_items", "CheckoutService.cancel_order"),
    ("W", "B"): ("InMemoryStock.set_warehouse_open", "StockPort.reserve",
                 "CheckoutService.checkout"),
    ("W", "C"): ("InMemoryShipping.reject_warehouses", "ShippingPort.dispatch",
                 "StockPort.reserve", "StockPort.release", "CheckoutService.checkout"),
    ("W", "D"): ("CheckoutService.retry_events", "OrderStore.pending_events",
                 "OrderStore.ack", "EventSink.publish"),
}


def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_manifest(root: Path) -> dict[str, Any]:
    """Hash all trial files, including tests and configuration, by path and bytes."""
    if not root.is_dir() or root.is_symlink():
        raise ValueError("source tree is absent or a symlink")
    paths: dict[str, str] = {}
    total = 0
    for item in sorted(root.rglob("*")):
        relative = item.relative_to(root)
        if any(part in EXCLUDED for part in relative.parts):
            continue
        if item.is_symlink():
            raise ValueError(f"source symlink: {relative}")
        if item.is_dir():
            continue
        if not item.is_file():
            raise ValueError(f"source entry is not a regular file: {relative}")
        if relative.as_posix() in SIDECARS:
            continue
        data = item.read_bytes()
        total += len(data)
        if len(data) > MAX_FILE_BYTES or total > MAX_TREE_BYTES or len(paths) >= MAX_FILES:
            raise ValueError("source tree exceeds bounded file, count or byte limit")
        paths[relative.as_posix()] = hashlib.sha256(data).hexdigest()
    if not paths or not any(name.startswith("fulfilment/") for name in paths):
        raise ValueError("source tree lacks production package")
    payload = json.dumps(paths, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"schema": "architecture-extension-tree/1", "files": paths,
            "tree_sha256": hashlib.sha256(payload).hexdigest()}


def _checks(request: dict[str, Any], workspace: Path) -> tuple[str, dict[str, Any]]:
    if (set(request) != {"evidence_id", "environment", "tool", "tool_version", "input", "context"}
            or request["environment"] != "fulfilment_change"
            or request["tool"] != "snapshot_probe" or request["tool_version"] != "1"
            or type(request["input"]) is not dict
            or set(request["input"]) != {"check_id"}
            or request["input"]["check_id"] not in CHECKS):
        raise ValueError("unrecognised EAL collector request")
    context = request["context"]
    if (type(context) is not dict
            or set(context) != {"experiment", "stage", "family", "feature", "candidate_sha256",
                                "baseline_sha256"}
            or context["experiment"] != "architecture-extension-v3"
            or context["stage"] != "current-snapshot"
            or context["family"] not in ("R", "W")
            or context["feature"] not in ("B", "C", "D")
            or not all(type(context[k]) is str and HEX.fullmatch(context[k])
                       for k in ("candidate_sha256", "baseline_sha256"))):
        raise ValueError("unrecognised host-bound assessment context")
    candidate = tree_manifest(workspace / "candidate")
    baseline = tree_manifest(workspace / "baseline")
    if (candidate["tree_sha256"] != context["candidate_sha256"]
            or baseline["tree_sha256"] != context["baseline_sha256"]):
        raise ValueError("source changed after host binding")
    check_id = request["input"]["check_id"]
    return check_id, context


def _import_check(root: Path) -> dict[str, Any]:
    production = root / "fulfilment"
    edges: dict[str, set[str]] = {}
    for file in sorted(production.rglob("*.py")):
        module = "fulfilment." + ".".join(file.relative_to(production).with_suffix("").parts)
        tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        deps: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
                deps.add("fulfilment." + node.module.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("fulfilment."):
                deps.add("fulfilment." + node.module.split(".")[1])
            elif isinstance(node, ast.Import):
                deps.update("fulfilment." + name.name.split(".")[1]
                            for name in node.names if name.name.startswith("fulfilment."))
        edges[module] = deps - {module}
    seen: set[str] = set()
    active: set[str] = set()
    cycles: set[tuple[str, ...]] = set()

    def visit(name: str, chain: tuple[str, ...]) -> None:
        if name in active:
            cycles.add(chain[chain.index(name):] + (name,))
            return
        if name in seen or name not in edges:
            return
        active.add(name)
        for child in sorted(edges[name]):
            visit(child, chain + (child,))
        active.remove(name)
        seen.add(name)

    for name in sorted(edges):
        visit(name, (name,))
    return {"passed": not cycles,
            "detail": "no static production import cycle" if not cycles else "static import cycle found",
            "cycles": [list(cycle) for cycle in sorted(cycles)][:8],
            "module_count": len(edges)}


def _boundary_check(root: Path, family: str, feature: str) -> dict[str, Any]:
    """Inspect declared ports and effect calls; do not certify unique effects."""
    boundary_files = (root / "fulfilment" / "ports.py", root / "fulfilment" / "service.py")
    missing_files = [path.relative_to(root).as_posix() for path in boundary_files if not path.is_file()]
    # Absence of an old boundary is an explicit migration finding. A malformed
    # existing source file is an invalid observation and fails collection.
    ports = (ast.parse(boundary_files[0].read_text(encoding="utf-8"))
             if boundary_files[0].is_file() else ast.Module(body=[], type_ignores=[]))
    service = (ast.parse(boundary_files[1].read_text(encoding="utf-8"))
               if boundary_files[1].is_file() else ast.Module(body=[], type_ignores=[]))
    names = ("PricingPort", "StockPort", "PaymentPort", "ShippingPort", "OrderStore", "EventSink")
    declared = {node.name for node in ports.body if isinstance(node, ast.ClassDef)
                and any(isinstance(base, ast.Name) and base.id == "Protocol" for base in node.bases)}
    checkout = next((node for node in service.body if isinstance(node, ast.ClassDef)
                     and node.name == "CheckoutService"), None)
    init = next((node for node in checkout.body if isinstance(node, ast.FunctionDef)
                 and node.name == "__init__"), None) if checkout else None
    annotations = {arg.arg: arg.annotation.id for arg in init.args.args
                   if isinstance(arg.annotation, ast.Name)} if init else {}
    expected = dict(zip(("pricing", "stock", "payments", "shipping", "orders", "events"), names))
    direct_memory = any(isinstance(node, ast.ImportFrom) and node.module == "memory"
                        for node in ast.walk(service))
    effect_methods = {"reserve", "release", "restore", "capture", "refund", "dispatch", "cancel",
                      "save", "save_return", "publish", "ack", "begin_attempt", "begin_return"}
    sites: dict[str, list[str]] = {}
    if checkout:
        for method in checkout.body:
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(method):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in effect_methods):
                    sites.setdefault(node.func.attr, []).append(f"{method.name}:{node.lineno}")
    passed = not missing_files and set(names) <= declared and all(annotations.get(k) == v for k, v in expected.items())
    passed = passed and not direct_memory
    classes: dict[str, set[str]] = {}
    for file in sorted((root / "fulfilment").rglob("*.py")):
        parsed = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        for node in parsed.body:
            if not isinstance(node, ast.ClassDef):
                continue
            members = {child.name for child in node.body
                       if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))}
            members.update(child.attr for child in ast.walk(node)
                           if isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name)
                           and child.value.id == "self")
            classes.setdefault(node.name, set()).update(members)
    impact = IMPACT[(family, feature)]
    present = [symbol for symbol in impact if symbol.split(".", 1)[1] in classes.get(symbol.split(".", 1)[0], ())]
    return {"passed": passed,
            "detail": ("six declared ports remain injected into CheckoutService without a direct memory import"
                       if passed else "shared port declarations/injection differ; review any intentional migration"),
            "missing_ports": sorted(set(names) - declared),
            "missing_boundary_files": missing_files,
            "mismatched_injection": sorted(k for k, v in expected.items() if annotations.get(k) != v),
            "direct_memory_import": direct_memory,
            "effect_call_sites": {key: values[:8] for key, values in sorted(sites.items())},
            "effect_route_certainty": "unknown: static call sites do not establish unique transitions or dead code",
            "impact_schema": "public-feature-surface/1", "impact_symbols": list(impact),
            "impact_present": present,
            "impact_absent": [symbol for symbol in impact if symbol not in present],
            "impact_interpretation": "public brief symbols map a review surface, not a required implementation shape"}


def _visible_test_check(candidate: Path, context: dict[str, Any]) -> dict[str, Any]:
    """Run only tests already visible in the candidate's own source tree."""
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    process = subprocess.run(command, cwd=candidate, capture_output=True, text=True,
                             timeout=120, check=False,
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0",
                                  "PYTHONPATH": str(candidate)})
    if len(process.stdout.encode("utf-8")) + len(process.stderr.encode("utf-8")) > 1024 * 1024:
        raise ValueError("visible test output exceeded the collector bound")
    after = tree_manifest(candidate)["tree_sha256"]
    if after != context["candidate_sha256"]:
        raise ValueError("candidate changed while visible tests ran")
    match = re.search(r"Ran (\d+) tests? in ", process.stderr)
    count = int(match.group(1)) if match else 0
    passed = process.returncode == 0 and count > 0 and re.search(r"^OK$", process.stderr, re.M) is not None
    return {"passed": passed,
            "detail": f"candidate-visible unittest suite: {count} tests, exit {process.returncode}",
            "test_count": count, "exit_code": process.returncode,
            "interpretation": "candidate-visible tests can be edited by the coding agent; sealed final probes are separate"}


def _cached_check(workspace: Path, check_id: str, context: dict[str, Any]) -> tuple[dict, bool]:
    cache = workspace / "cache"
    code_hash = digest_file(Path(__file__).resolve())
    key = hashlib.sha256(json.dumps({"check": check_id, "context": context,
                                     "collector": code_hash, "python": sys.version,
                                     "executable": sys.executable},
                                    sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    path = cache / (key + ".json")
    # Agent-authored tests may depend on time, randomness or external effects.
    # They are rerun for each evidence ID. Only pure static checks are cached.
    cacheable = check_id in {"source_binding", "import_cycles", "shared_boundary"}
    if cacheable and os.getenv("EAL_V3_CACHE") == "1" and path.is_file() and not path.is_symlink():
        saved = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)
        if saved.get("cache_key") != key or not isinstance(saved.get("value"), dict):
            raise ValueError("cached check identity differs")
        return saved["value"], True
    if check_id == "source_binding":
        value = {"passed": True, "detail": "candidate and baseline tree digests match host context"}
    elif check_id == "import_cycles":
        value = _import_check(workspace / "candidate")
    elif check_id == "shared_boundary":
        value = _boundary_check(workspace / "candidate", context["family"], context["feature"])
    else:
        value = _visible_test_check(workspace / "candidate", context)
    if cacheable and os.getenv("EAL_V3_CACHE") == "1":
        cache.mkdir(exist_ok=True)
        if cache.is_symlink():
            raise ValueError("cache directory is a symlink")
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=cache,
                                         delete=False) as stream:
            json.dump({"cache_key": key, "value": value}, stream, sort_keys=True)
            temporary = Path(stream.name)
        temporary.replace(path)
    return value, False


def collect(request: dict[str, Any], workspace: Path) -> dict[str, Any]:
    check_id, context = _checks(request, workspace)
    value, hit = _cached_check(workspace, check_id, context)
    return {"value": {"schema": "architecture-snapshot-check/1", "check_id": check_id,
                      **value, "candidate_sha256": context["candidate_sha256"]},
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "context": context,
            "request": {name: request[name] for name in ("tool", "tool_version", "input", "context")},
            "details": {"schema": "architecture-snapshot-check/1", "cache_hit": hit}}


if __name__ == "__main__":
    try:
        raw = sys.stdin.buffer.read(8193)
        if len(raw) > 8192:
            raise ValueError("collector request exceeds 8192 bytes")
        request = json.loads(raw, object_pairs_hook=unique_pairs)
        print(json.dumps(collect(request, Path.cwd()), sort_keys=True, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError, SyntaxError,
            subprocess.TimeoutExpired, UnicodeError) as exc:
        print(f"Snapshot collection failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
