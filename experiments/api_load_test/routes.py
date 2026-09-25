"""Two acquisition routes: direct command, or the actual EAL MCP server."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from eal.tool_acquisition import strict_json

from .api import utc_now
from .materials import CLAIM


ROOT = Path(__file__).resolve().parents[2]


def child_environment() -> dict:
    # Collectors and MCP do not need the paid provider token or runner secrets.
    return {"PATH": str(Path(sys.executable).parent) + os.pathsep + os.defpath,
            "PYTHONPATH": os.pathsep.join((str(ROOT), str(ROOT / "src"))),
            "PYTHONIOENCODING": "utf-8", "LANG": "C.UTF-8"}


class TrialTools:
    def __init__(self, workspace: Path, source: str, config: dict):
        self.workspace, self.source, self.config = workspace, source, config
        self.report_path = workspace / "report.json"
        self.trace = []
        self.packet = None
        self.host_status = None
        self.assessed_at = None
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "source.eal").write_text(source)
        (workspace / "config.json").write_text(json.dumps(config, sort_keys=True))
        self.argv = [sys.executable, "-m", "experiments.api_load_test.collector", "--config",
                     str(workspace / "config.json"), "--report", str(self.report_path)]
        self.registry = workspace / "tools.toml"
        self.registry.write_text('[tools.api_load_test]\nkind="command"\nversion="1"\n'
                                 'mode="nondeterministic"\ntimeout_seconds=60\nmax_output_bytes=16384\n'
                                 f'argv={json.dumps(self.argv)}\n')

    async def execute(self, arm: str) -> dict:
        if self.packet is not None:
            return self.packet  # one actual load test per assigned trial
        if self.trace:
            raise ValueError("Collection already attempted; failed trials are not rerun")
        self.packet = await self._mcp() if arm == "eal_mcp" else self._direct()
        return self.packet

    def _direct(self):
        request = {"evidence_id": "load_test", "environment": "test_run",
                   "tool": "api_load_test", "tool_version": "1", "mode": "nondeterministic",
                   "input": self.config["input"], "context": self.config["context"]}
        # This route uses the same collector but never invokes ReasoningService,
        # the parser, the evaluator, or MCP.
        self.trace.append({"route": "direct_command", "request": request, "started_at": utc_now()})
        result = subprocess.run(self.argv, input=json.dumps(request), text=True, capture_output=True,
                                env=child_environment(), cwd=self.workspace, timeout=65)
        self.trace[-1].update(returncode=result.returncode, stderr=result.stderr, stdout=result.stdout)
        if result.returncode:
            raise ValueError("Direct load-test collector failed")
        envelope = strict_json(result.stdout)
        self.assessed_at = utc_now()
        return {"metrics": envelope["value"], "observed_at": envelope["observed_at"],
                "assessed_at": self.assessed_at, "context": envelope["context"],
                "input": envelope["request"]["input"], "provenance": envelope["details"]}

    async def _mcp(self):
        settings = StdioServerParameters(command=sys.executable,
            args=["-m", "eal.server", "--workspace", str(self.workspace), "--registry", str(self.registry)],
            env=child_environment())
        self.trace.append({"route": "mcp_stdio", "started_at": utc_now()})
        async with stdio_client(settings) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()

                async def call(name, arguments):
                    result = await session.call_tool(name, arguments)
                    self.trace.append({"tool": name, "arguments": arguments,
                                       "is_error": result.isError, "result": result.structuredContent})
                    if result.isError or not isinstance(result.structuredContent, dict):
                        raise ValueError(f"MCP {name} failed")
                    return result.structuredContent

                valid = await call("eal_validate", {"source": self.source})
                if not valid["valid"]:
                    raise ValueError("Pinned argument is invalid")
                collected = await call("eal_collect", {"source": self.source, "context": self.config["context"]})
                record = collected["records"]["load_test"]
                if record["status"] != "ok":
                    raise ValueError("MCP load-test collector failed")
                self.assessed_at = utc_now()
                assessed = await call("eal_reason", {"source": self.source, "context": self.config["context"],
                                      "collection_id": collected["collection_id"], "now": self.assessed_at})
                explanation = await call("eal_explain", {"assessment_id": assessed["assessment_id"], "claim": CLAIM})
                expected_digest = hashlib.sha256(self.source.encode()).hexdigest()
                if (assessed["source_digest"] != expected_digest
                    or assessed["collection_id"] != collected["collection_id"]
                    or explanation["assessment_id"] != assessed["assessment_id"]
                    or explanation["result"]["status"] != assessed["claims"][CLAIM]["status"]):
                    raise ValueError("MCP assessment identity or explanation differs")
                self.host_status = assessed["claims"][CLAIM]["status"]
                return {"metrics": record["value"], "observed_at": record["collected_at"],
                        "assessed_at": self.assessed_at, "context": record["context"],
                        "input": record["input"], "provenance": record["details"],
                        "claim": CLAIM, "status": self.host_status,
                        "source_digest": expected_digest,
                        "method_registry_fingerprint": assessed["method_registry_fingerprint"],
                        "reasoning": assessed["reasoning"], "evidence": assessed["evidence"],
                        "collection_id": collected["collection_id"], "assessment_id": assessed["assessment_id"]}
