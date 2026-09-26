"""Immutable evidence inspection through direct commands or actual EAL MCP."""
from __future__ import annotations
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from eal.tool_acquisition import strict_json
from .api import utc_now
from .materials import CLAIM, source_for

ROOT = Path(__file__).resolve().parents[2]


class ToolExecutionError(RuntimeError):
    """Internal collection or assessment failure, never a model argument error."""


def child_environment() -> dict:
    return {"PATH": str(Path(sys.executable).parent) + os.pathsep + os.defpath,
            "PYTHONPATH": os.pathsep.join((str(ROOT), str(ROOT / "src"))),
            "PYTHONIOENCODING": "utf-8", "LANG": "C.UTF-8"}


def checked_decision(packet: dict) -> dict:
    """Ordinary deterministic classification of collector facts, without EAL.

    The MCP route uses the same presentation contract after checking its formal
    host assessment. The raw-measurement oracle is implemented separately.
    """
    facts, metrics = packet["measurement_facts"], packet["metrics"]
    checks = {"report_valid": facts["report_valid"], "identity": None,
              "completeness": None, "freshness": None, "sample_size": None,
              "latency": None, "errors": None, "consistency": None}
    if facts["report_valid"]:
        checks.update(identity=facts["identity_matches"],
                      completeness=facts["complete_records"],
                      consistency=facts["consistent_records"],
                      freshness=(0 <= facts["age_seconds"] <= 300)
                      if facts["age_seconds"] is not None else None,
                      sample_size=metrics["request_count"] >= 100,
                      latency=metrics["p95_ms"] <= 200 if metrics["p95_ms"] is not None else None,
                      errors=metrics["error_rate_percent"] <= 1
                      if metrics["error_rate_percent"] is not None else None)
    available = all(checks[name] is True for name in
                    ("report_valid", "identity", "completeness", "consistency", "freshness"))
    status = ("unavailable" if not available else
              "supported" if all(value is True for value in checks.values()) else "unsupported")
    return {"status": status,
            "failed_checks": sorted(name for name, value in checks.items() if value is False),
            "unknown_checks": sorted(name for name, value in checks.items() if value is None)}


class TrialTools:
    def __init__(self, workspace: Path, source: str, config: dict):
        self.workspace, self.source, self.config = workspace, source, config
        self.case = config["case"]
        self.trace, self.packets, self.inspected_report_ids = [], {}, []
        self.host_assessments = {}
        self.attempted_report_ids = set()
        self.host_status = self.packet = None
        self.assessed_at = self.case["assessment_time"]
        self.report_path = workspace / "report.json"
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "source.template.eal").write_text(source)
        (workspace / "config.json").write_text(json.dumps(config, sort_keys=True))

    async def execute(self, arm: str, report_id: str) -> dict:
        if report_id not in self.case["reports"]:
            raise ValueError("Choose a report_id from the provided catalogue")
        if report_id in self.packets:
            self.packet = self.packets[report_id]
            self.report_path = self.workspace / report_id / "report.json"
            self.host_status = self.host_assessments.get(report_id, {}).get("host_status")
            return self.packet
        if report_id in self.attempted_report_ids:
            raise ValueError("This report inspection already failed; failed attempts are not rerun")
        self.attempted_report_ids.add(report_id)
        directory = self.workspace / report_id
        directory.mkdir(exist_ok=False)
        report_path = directory / "report.json"
        argv = [sys.executable, "-m", "experiments.api_load_test.collector", "--config",
                str(self.workspace / "config.json"), "--report", str(report_path)]
        try:
            if arm == "eal_mcp":
                packet = await self._mcp(report_id, directory, argv)
            else:
                packet = await asyncio.to_thread(self._direct, report_id, directory, argv)
                if arm == "plain_validator":
                    packet.update(checked_decision(packet))
                    self.trace.append({"route": "direct_validator", "report_id": report_id,
                                       "result": {key: packet[key] for key in
                                                  ("status", "failed_checks", "unknown_checks")}})
        except (ValueError, KeyError, TypeError) as exc:
            # Valid report selectors have crossed the host boundary. A broken
            # collector envelope or assessment is an experiment failure; asking
            # the model to repair it would confound infrastructure and behaviour.
            raise ToolExecutionError(f"Report inspection failed: {exc}") from exc
        self.packets[report_id] = self.packet = packet
        self.inspected_report_ids.append(report_id)
        self.report_path = report_path
        self.host_status = self.host_assessments.get(report_id, {}).get("host_status")
        return packet

    def _request(self, report_id):
        return {"evidence_id": "load_test", "environment": "test_run", "tool": "api_load_test",
                "tool_version": "2",
                "input": {**self.case["target"]["input"], "report_id": report_id},
                "context": self.case["target"]["context"]}

    def _packet(self, value, observed_at, details):
        return {"report_id": details["report_id"],
                "metrics": {key: value[key] for key in ("request_count", "p95_ms", "error_rate_percent")},
                "measurement_facts": {key: value[key] for key in
                    ("report_valid", "identity_matches", "complete_records", "consistent_records", "age_seconds")},
                "observed_at": observed_at, "assessment_time": self.assessed_at,
                "reported_input": details["reported_input"], "reported_context": details["reported_context"],
                "claimed_summary": details.get("claimed_summary"), "provenance": details}

    def _direct(self, report_id, directory, argv):
        request = self._request(report_id)
        trace = {"route": "direct_command", "report_id": report_id, "request": request, "started_at": utc_now()}
        self.trace.append(trace)
        result = subprocess.run(argv, input=json.dumps(request), text=True, capture_output=True,
                                env=child_environment(), cwd=directory, timeout=65)
        trace.update(returncode=result.returncode, stderr=result.stderr, stdout=result.stdout)
        if result.returncode:
            raise ValueError("Direct report collector failed")
        envelope = strict_json(result.stdout)
        return self._packet(envelope["value"], envelope["observed_at"], envelope["details"])

    async def _mcp(self, report_id, directory, argv):
        source = source_for(self.case["target"]["input"], self.case["target"]["context"], report_id)
        (directory / "source.eal").write_text(source)
        registry = directory / "tools.toml"
        registry.write_text('[tools.api_load_test]\nkind="command"\nversion="2"\n'
                            'timeout_seconds=60\nmax_output_bytes=32768\n'
                            f'argv={json.dumps(argv)}\n')
        settings = StdioServerParameters(command=sys.executable,
            args=["-m", "eal.server", "--workspace", str(directory), "--registry", str(registry)],
            env=child_environment())
        self.trace.append({"route": "mcp_stdio", "report_id": report_id, "started_at": utc_now()})
        async with stdio_client(settings) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()

                async def call(name, arguments):
                    result = await session.call_tool(name, arguments)
                    self.trace.append({"tool": name, "report_id": report_id, "arguments": arguments,
                                       "is_error": result.isError, "result": result.structuredContent})
                    if result.isError or not isinstance(result.structuredContent, dict):
                        raise ValueError(f"MCP {name} failed")
                    return result.structuredContent

                valid = await call("eal_validate", {"source": source})
                if not valid["valid"]:
                    raise ValueError("Pinned argument is invalid")
                context = self.case["target"]["context"]
                collected = await call("eal_collect", {"source": source, "context": context})
                record = collected["records"]["load_test"]
                if record["status"] != "ok":
                    raise ValueError("MCP report collector failed")
                assessed = await call("eal_reason", {"source": source, "context": context,
                                      "collection_id": collected["collection_id"], "now": self.assessed_at})
                explanation = await call("eal_explain", {"assessment_id": assessed["assessment_id"], "claim": CLAIM})
                expected_digest = hashlib.sha256(source.encode()).hexdigest()
                host_status = assessed["claims"][CLAIM]["status"]
                if (assessed["source_digest"] != expected_digest
                    or assessed["collection_id"] != collected["collection_id"]
                    or explanation["assessment_id"] != assessed["assessment_id"]
                    or explanation["result"]["status"] != host_status):
                    raise ValueError("MCP assessment identity or explanation differs")
                packet = self._packet(record["value"], record["collected_at"], record["details"])
                decision = checked_decision(packet)
                expected_host = "supported" if decision["status"] == "supported" else "unsupported"
                if host_status != expected_host:
                    raise ValueError("MCP assessment differs from the declared decision contract")
                # Raw EAL status and detailed reasoning remain in the audit
                # artefact. Models receive one canonical status field only.
                self.host_assessments[report_id] = {
                    "host_status": host_status, "status": decision["status"],
                    "source_digest": expected_digest, "collection_id": collected["collection_id"],
                    "assessment_id": assessed["assessment_id"]}
                packet.update(**decision, claim=CLAIM, source_digest=expected_digest,
                              method_registry_fingerprint=assessed["method_registry_fingerprint"],
                              collection_id=collected["collection_id"], assessment_id=assessed["assessment_id"])
                return packet
