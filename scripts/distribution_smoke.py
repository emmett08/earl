"""Exercise the installed Python, CLI and MCP contracts outside the checkout."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import eal
from eal.formatter import format_source
from eal.knowledge import EALKnowledgeBase, ModelContextAdapter
from eal.parser import parse
from eal.runtime import ReasoningService
from eal.semantics import validate


SOURCE = '''language "EAL/3"
environment lab {
  require "site" == "bench"
}
tool reader {
  version "1"
}
evidence reading {
  tool reader
  kind test
  environment lab
  max_age 3600
  require "passed" == true
}
reasoning measurement {
  method "structured/1"
  rationale "The synthetic observation supplies support."
}
claim works {
  statement "The configured synthetic check passes."
  environment lab
}
argument result = [evidence reading] via measurement => works
'''


def run_json(arguments: list[str], *, workspace: Path, environment: dict[str, str],
             request: dict | None = None) -> dict:
    completed = subprocess.run(arguments, cwd=workspace, env=environment,
                               input=json.dumps(request) if request is not None else None,
                               text=True, capture_output=True, timeout=30)
    if completed.returncode:
        raise RuntimeError(f"Installed command failed: {completed.stdout}\n{completed.stderr}")
    return json.loads(completed.stdout)


def check_http(host: Path, server: Path, *, workspace: Path, registry: Path,
               environment: dict[str, str], request: dict) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    arguments = [str(server), "--workspace", str(workspace), "--registry", str(registry),
                 "--known-entry", "smoke", "--transport", "http", "--port", str(port),
                 "--token-env", "EAL_DISTRIBUTION_TOKEN"]
    with (workspace / "http.log").open("w") as log:
        process = subprocess.Popen(arguments, cwd=workspace, env=environment,
                                   stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 20
            while True:
                if process.poll() is not None:
                    raise RuntimeError("Installed HTTP server exited during startup")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Installed HTTP server did not start")
                    time.sleep(0.05)
            response = run_json(
                [str(host), "--workspace", str(workspace), "--url",
                 f"http://127.0.0.1:{port}/mcp", "--token-env", "EAL_DISTRIBUTION_TOKEN",
                 "--timeout", "20"],
                workspace=workspace, environment=environment, request=request,
            )
            assert response["is_error"] is False
            assert response["result"]["status"] == "supported"
            assert response["result"]["reused_count"] == 1
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--expected-version", required=True)
    arguments = parser.parse_args()
    workspace = arguments.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    assert sys.prefix != sys.base_prefix, "Distribution checks require an isolated virtual environment"
    assert Path(eal.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()), eal.__file__
    assert eal.__version__ == arguments.expected_version
    assert importlib.metadata.version("engineering-argument-language") == arguments.expected_version
    assert validate(parse(SOURCE)) == []
    assert validate(parse(format_source(SOURCE))) == []

    (workspace / "source.eal").write_text(SOURCE, encoding="utf-8")
    collector = workspace / "collector.py"
    collector.write_text(
        "import json, pathlib, sys\njson.load(sys.stdin)\n"
        "counter = pathlib.Path('calls.txt')\n"
        "counter.write_text(counter.read_text() + 'x' if counter.exists() else 'x')\n"
        "print(json.dumps({'value': {'passed': True}}))\n", encoding="utf-8",
    )
    registry = workspace / "tools.toml"
    registry.write_text(
        '[tools.reader]\nkind = "command"\nversion = "1"\ninherit_env = []\n'
        'timeout_seconds = 5\nargv = ' + json.dumps([sys.executable, str(collector)]) + "\n",
        encoding="utf-8",
    )
    knowledge = EALKnowledgeBase(workspace, registry)
    knowledge.register("source.eal", entry_id="smoke", claims=["works"], context={"site": "bench"})
    assert knowledge.find(claim="works")
    assessed = knowledge.assess("smoke", "works")
    assert assessed["status"] == "supported"
    assert assessed["collected_count"] == 1
    assert assessed["packet"]["schema"] == "EAL/assessment-packet/2"
    restarted = EALKnowledgeBase(workspace, registry)
    prepared = ModelContextAdapter(restarted).prepare("Did the synthetic check pass?", "smoke", "works")
    assert prepared["schema"] == "EAL/model-context/2"
    assert prepared["assessment"]["reused_count"] == 1
    assert ReasoningService(workspace, registry).validate(SOURCE)["valid"] is True

    executable_directory = Path(sys.executable).parent
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"PYTHONPATH", "PYTHONHOME"} and not key.startswith("EAL_MCP_")
                   and key.lower() not in {"http_proxy", "https_proxy", "all_proxy"}}
    environment["NO_PROXY"] = "127.0.0.1,localhost,::1"
    environment["EAL_DISTRIBUTION_TOKEN"] = "distribution-check-token"
    for name in ("eal", "eal-mcp", "eal-host"):
        subprocess.run([str(executable_directory / name), "--help"], cwd=workspace,
                       env=environment, check=True, capture_output=True, timeout=15)
    cli = run_json([str(executable_directory / "eal"), "--workspace", str(workspace),
                    "validate", "source.eal"], workspace=workspace, environment=environment)
    assert cli["valid"] is True
    request = {"operation": "assess_known", "entry_id": "smoke", "claim": "works"}
    response = run_json(
        [str(executable_directory / "eal-host"), "--workspace", str(workspace),
         "--registry", str(registry), "--known-entry", "smoke", "--timeout", "20"],
        workspace=workspace, environment=environment, request=request,
    )
    assert response["is_error"] is False
    assert response["result"]["status"] == "supported"
    assert response["result"]["reused_count"] == 1
    check_http(executable_directory / "eal-host", executable_directory / "eal-mcp",
               workspace=workspace, registry=registry, environment=environment, request=request)
    assert (workspace / "calls.txt").read_text() == "x", "A compatible observation was collected twice"
    print(f"Installed {arguments.expected_version}: Python/CLI/stdio/HTTP and cross-session reuse passed")


if __name__ == "__main__":
    main()
