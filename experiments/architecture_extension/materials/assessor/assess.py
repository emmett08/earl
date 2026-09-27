"""Fixed structural and behavioural assessor for one coding-session output.

No input from a candidate's own tests is used as an oracle. Structural checks
are deliberately narrow and their exact criteria are reported in the result.
"""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "base" / "notification_service"


def digest(path):
    h = hashlib.sha256()
    for file in sorted(path.rglob("*")):
        if file.is_file() and "__pycache__" not in file.parts and file.suffix in (".py", ".md"):
            h.update(str(file.relative_to(path)).encode())
            h.update(b"\0")
            h.update(file.read_bytes())
            h.update(b"\0")
    return h.hexdigest()


def finding(passed, detail, source, command=None):
    return {"passed": bool(passed), "detail": detail, "source": source, "command": command}


def method_ast(file, name):
    tree = ast.parse(file.read_text())
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "NotificationService":
            for method in node.body:
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name == name:
                    return ast.dump(method, include_attributes=False)
    return None


def structural(case_dir, imported):
    package = case_dir / "notification_service"
    result = {}
    same_send = method_ast(package / "service.py", "send") == method_ast(BASE / "service.py", "send")
    same_register = method_ast(package / "service.py", "register") == method_ast(BASE / "service.py", "register")
    calls = []
    for file in sorted(package.rglob("*.py")):
        for node in ast.walk(ast.parse(file.read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("deliver", "prepare"):
                    calls.append((str(file.relative_to(case_dir)), node.func.attr, node.lineno))
    deliveries = [call for call in calls if call[1] == "deliver"]
    preparations = [call for call in calls if call[1] == "prepare"]
    result["single_dispatch_path"] = finding(
        same_send and len(deliveries) == 1 and deliveries[0][0] == "notification_service/service.py",
        "NotificationService.send AST matches frozen baseline; package-wide .deliver() calls: " + repr(deliveries),
        "AST of production Python files",
    )
    result["single_format_path"] = finding(
        same_send and len(preparations) == 1 and preparations[0][0] == "notification_service/service.py",
        "Dispatch continues to call one Channel.prepare; package-wide .prepare() calls: " + repr(preparations) + ". This syntax check cannot exclude semantically duplicate formatters.",
        "AST of production Python files",
    )
    result["registry_extension"] = finding(
        same_register and same_send,
        "register/send AST matches baseline; channel registration and behaviour are separately checked at runtime",
        "notification_service/service.py",
    )
    all_modules = sorted("notification_service." + ".".join(file.relative_to(package).with_suffix("").parts)
                         for file in package.rglob("*.py") if file.name != "__init__.py")
    missing = sorted(set(all_modules) - set(imported))
    result["reachable_code"] = finding(
        not missing,
        "Production modules imported by fixed behavioural probes; unimported: " + repr(missing) + ". Import coverage does not rule out unreachable functions or unused branches.",
        "sys.modules after fixed probes",
    )
    return result


def assess(case_dir, case):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(case_dir)
    env["ARCH_CASE"] = case
    try:
        probe = subprocess.run([sys.executable, str(HERE / "probe.py")], env=env, capture_output=True, text=True, timeout=30)
        probe_exit, probe_stdout, probe_stderr = probe.returncode, probe.stdout, probe.stderr
    except subprocess.TimeoutExpired as exc:
        probe_exit = -1
        probe_stdout = (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        probe_stderr = "fixed probe exceeded 30 seconds"
    payload = None
    if probe_exit == 0:
        try:
            payload = json.loads(probe_stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            probe_exit = -2
            probe_stderr = f"fixed probe did not return one JSON object: {exc}; stdout={probe_stdout[-1500:]}"
    if payload is None:
        checks = {key: finding(False, probe_stderr[-2000:] or "probe failed", "fixed probe") for key in
                  ["baseline_contract", "feature_behaviour", "registry_extension", "single_dispatch_path", "single_format_path", "reachable_code"]}
        if case == "b":
            checks.update({key: finding(False, "probe failed", "fixed probe") for key in ["email_regression", "payload_cap"]})
    else:
        checks = {key: {**value, "source": "materials/assessor/probe.py", "command": f"ARCH_CASE={case} python materials/assessor/probe.py"}
                  for key, value in payload["checks"].items()}
        try:
            checks.update(structural(case_dir, payload["imported_modules"]))
            expected = {"console", "email"} | ({"sms"} if case == "b" else set())
            channels = set(payload["registered_channels"])
            checks["registry_extension"] = finding(
                checks["registry_extension"]["passed"] and expected.issubset(channels),
                f"register/send AST unchanged; expected channels {sorted(expected)}; observed {sorted(channels)}",
                "NotificationService AST and fixed runtime probe",
            )
        except (SyntaxError, OSError, KeyError, TypeError, ValueError) as exc:
            checks.update({key: finding(False, str(exc), "AST assessor") for key in
                           ["registry_extension", "single_dispatch_path", "single_format_path", "reachable_code"]})
    try:
        suite = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test*.py"],
                               cwd=case_dir, env=env, capture_output=True, text=True, timeout=30)
        suite_exit, suite_output = suite.returncode, suite.stdout + suite.stderr
    except subprocess.TimeoutExpired as exc:
        suite_exit, suite_output = -1, "candidate suite exceeded 30 seconds"
    checks["all_tests"] = finding(suite_exit == 0 and probe_exit == 0 and
                                  all(value["passed"] for value in checks.values()),
                                  f"candidate suite rc={suite_exit}; fixed probe rc={probe_exit}; " +
                                  suite_output[-1500:],
                                  "candidate tests plus fixed assessor",
                                  "python -m unittest discover -s tests -p 'test*.py'")
    return {"case": case, "source_sha256": digest(case_dir), "checks": checks,
            "probe_exit": probe_exit, "probe_stderr": probe_stderr,
            "suite_exit": suite_exit, "candidate_suite_output": suite_output}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case_dir", type=Path)
    parser.add_argument("--case", choices=("a", "b"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = assess(args.case_dir.resolve(), args.case)
    text = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text)
    return 0 if result["checks"]["all_tests"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
