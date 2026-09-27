"""Run the fixed independent v2 oracle on one candidate source tree.

Behavioural findings are separate from conservative static diagnostics.
The diagnostics identify sites needing architectural review; they do not
certify the absence of duplicate routes or dead code.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "architecture-extension-assessment/2"
EFFECTS = {"reserve", "release", "restore", "restock", "capture", "refund",
           "dispatch", "cancel", "publish", "save", "record_return"}
MAX_SECONDS = 90


def source_digest(root: Path) -> tuple[str, list[str]]:
    paths = sorted((*root.rglob("*.py"), *root.rglob("*.md")))
    files = [p.relative_to(root).as_posix() for p in paths
             if "__pycache__" not in p.parts and not any(part.startswith(".") for part in p.parts)]
    digest = hashlib.sha256()
    for relative in files:
        content = (root / relative).read_bytes()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest(), files


def architectural_diagnostics(root: Path, executed: dict[str, int]) -> dict[str, Any]:
    all_functions: set[str] = set()
    effect_sites: dict[str, list[dict[str, Any]]] = defaultdict(list)
    import_edges: dict[str, set[str]] = defaultdict(set)
    parse_errors: list[str] = []
    production = root / "fulfilment"
    for path in sorted(production.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(production).as_posix()
        module = "fulfilment." + ".".join(path.relative_to(production).with_suffix("").parts)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (OSError, UnicodeError, SyntaxError) as exc:
            parse_errors.append(f"{relative}: {type(exc).__name__}: {exc}")
            continue

        class Inspector(ast.NodeVisitor):
            def __init__(self) -> None:
                self.scope: list[str] = []

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self.scope.append(node.name)
                self.generic_visit(node)
                self.scope.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self.scope.append(node.name)
                if not (len(node.body) == 1 and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and node.body[0].value.value is Ellipsis):
                    all_functions.add(f"{relative}:{'.'.join(self.scope)}")
                self.generic_visit(node)
                self.scope.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Call(self, node: ast.Call) -> None:
                if isinstance(node.func, ast.Attribute) and node.func.attr in EFFECTS:
                    effect_sites[node.func.attr].append({
                        "file": relative, "function": ".".join(self.scope) or "<module>",
                        "line": node.lineno,
                    })
                self.generic_visit(node)

            def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
                if node.level:
                    if node.level == 1 and node.module:
                        import_edges[module].add(f"fulfilment.{node.module}")
                    else:
                        import_edges[module].add(f"relative:{node.level}:{node.module or ''}")
                elif node.module and node.module.startswith("fulfilment"):
                    import_edges[module].add(node.module)

            def visit_Import(self, node: ast.Import) -> None:
                for name in node.names:
                    if name.name.startswith("fulfilment"):
                        import_edges[module].add(name.name)

        Inspector().visit(tree)

    # The profile reports only names executed by this fixed probe set.  An
    # uncalled function can still be live under another input, dynamic call
    # site or production integration.  No dead-code verdict is emitted.
    visited = set(executed)
    unexecuted = sorted(all_functions - visited)
    multi_sites = {name: sites for name, sites in effect_sites.items() if len(sites) > 1}
    # Strongly connected import components are review candidates, not a
    # correctness failure.  This linear scan avoids enumerating all cycles.
    nodes = set(import_edges) | {target for values in import_edges.values() for target in values}
    adjacency = {node: import_edges.get(node, set()) & nodes for node in nodes}
    index = 0
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    cycles: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = lowlink[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for successor in sorted(adjacency[node]):
            if successor not in indices:
                visit(successor)
                lowlink[node] = min(lowlink[node], lowlink[successor])
            elif successor in on_stack:
                lowlink[node] = min(lowlink[node], indices[successor])
        if lowlink[node] == indices[node]:
            component: list[str] = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            if len(component) > 1 or node in adjacency[node]:
                cycles.append(sorted(component))

    for node in sorted(nodes):
        if node not in indices:
            visit(node)
    return {
        "status": "invalid" if parse_errors else "diagnostic_only",
        "interpretation": "Call sites and probe execution guide review; neither proves duplicate paths or dead code.",
        "source_parse_errors": parse_errors,
        "effect_call_sites": dict(sorted(effect_sites.items())),
        "effects_with_multiple_static_sites": multi_sites,
        "import_edges": {k: sorted(v) for k, v in sorted(import_edges.items())},
        "import_out_degree": {k: len(v) for k, v in sorted(import_edges.items())},
        "import_cycles_for_review": sorted(cycles),
        "functions_declared": len(all_functions),
        "functions_executed_by_fixed_probes": len(all_functions & visited),
        "functions_not_executed_by_fixed_probes": unexecuted,
    }


def run_command(command: list[str], cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=MAX_SECONDS,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(cwd.resolve())},
        )
    except subprocess.TimeoutExpired as exc:
        return {"status": "invalid", "exit_code": None,
                "stdout": (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
                "stderr": "timed out", "command": command}
    return {"status": "pass" if completed.returncode == 0 else "fail",
            "exit_code": completed.returncode, "stdout": completed.stdout[-24000:],
            "stderr": completed.stderr[-12000:], "command": command}


def assess(candidate: Path, stage: str, arm: str) -> dict[str, Any]:
    candidate = candidate.resolve()
    digest, files = source_digest(candidate)
    probe_path = Path(__file__).with_name("probe.py")
    probe = run_command([sys.executable, str(probe_path), "--candidate", str(candidate),
                         "--stage", stage], candidate)
    expected = 5 + (5 if stage in ("a", "b") else 0) + (5 if stage == "b" else 0)
    try:
        payload = json.loads(probe["stdout"])
        findings = payload["findings"]
        executed = payload.get("executed_functions", {})
        case_effect_calls = payload.get("case_effect_calls", {})
        if len(findings) != expected or not all(
            isinstance(item, dict) and item.get("status") in {"pass", "fail", "invalid"}
            for item in findings.values()
        ):
            raise ValueError("unexpected findings count or status")
    except (ValueError, TypeError, KeyError) as exc:
        findings = {"apparatus": {"status": "invalid", "detail": f"{type(exc).__name__}: {exc}"}}
        executed = {}
        case_effect_calls = {}
    tests = run_command([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], candidate)
    # unittest exits successfully when zero tests were found; that is not a
    # successful candidate suite.
    tests["tests_run"] = None
    import re
    match = re.search(r"Ran (\d+) tests?", tests["stderr"])
    if match:
        tests["tests_run"] = int(match.group(1))
    if tests["status"] == "pass" and not tests["tests_run"]:
        tests["status"] = "invalid"
        tests["detail"] = "No unittest tests were discovered"
    return {
        "schema_version": SCHEMA,
        "arm": arm,
        "stage": stage,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source_digest": digest,
        "source_files": files,
        "findings": findings,
        "candidate_suite": tests,
        "probe_execution": {k: probe[k] for k in ("status", "exit_code", "stderr", "command")},
        "architecture": architectural_diagnostics(candidate, executed),
        "case_effect_calls": case_effect_calls,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--stage", choices=("baseline", "a", "b"), required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = assess(args.candidate, args.stage, args.arm)
    serialised = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialised, encoding="utf-8")
    else:
        print(serialised, end="")


if __name__ == "__main__":
    main()
