"""Actual stdio MCP boundary shared by the EAL text and JSON front ends."""

from __future__ import annotations

import asyncio
from pathlib import Path
import os
import sys
import tempfile
from typing import Any

from jsonschema import Draft202012Validator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from protocol_v1 import Case, ToolGateway, digest, timestamp


OPERATIONS = ("eal_validate", "eal_collect", "eal_reason", "eal_explain")


class MCPCheckError(ValueError):
    pass


class MCPHost:
    def __init__(self, gateway: ToolGateway, *, timeout_seconds: float = 90):
        self.gateway = gateway
        self.timeout_seconds = timeout_seconds

    async def describe(self) -> dict[str, Any]:
        """Discover the actual server's language contract before model authoring."""
        with tempfile.TemporaryDirectory(prefix="eal-ci-discover-") as directory:
            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", "eal.server", "--workspace", str(self.gateway.workspace),
                      "--registry", str(self.gateway.registry_path),
                      "--database", str(Path(directory) / "runs.sqlite3")],
                env=dict(os.environ))
            async with asyncio.timeout(self.timeout_seconds):
                async with stdio_client(parameters) as (read, write):
                    async with ClientSession(read, write) as session:
                        initialised = await session.initialize()
                        tools = {tool.name: tool.inputSchema for tool in (await session.list_tools()).tools}
                        if "eal_describe" not in tools:
                            raise MCPCheckError("EAL server lacks eal_describe")
                        result = await session.call_tool("eal_describe", arguments={})
                        if result.isError or type(result.structuredContent) is not dict:
                            raise MCPCheckError("EAL language discovery failed")
                        return {"description": result.structuredContent,
                                "receipt": {"tool": "eal_describe", "arguments_sha256": digest({}),
                                            "input_schema_sha256": digest(tools["eal_describe"]),
                                            "result_sha256": digest(result.structuredContent),
                                            "protocol_version": initialised.protocolVersion,
                                            "transport": "stdio", "is_error": False}}

    async def check(self, source: str, claim: str, case: Case) -> dict[str, Any]:
        transcript: list[dict[str, Any]] = []
        try:
            return await self._check(source, claim, case, transcript)
        except Exception as exc:
            # A failed source/collector/MCP call is an observed attempt, too.
            exc.mcp_calls = transcript
            raise

    async def _check(self, source: str, claim: str, case: Case,
                     transcript: list[dict[str, Any]]) -> dict[str, Any]:
        # The model cannot grant its own collector, context, method executable,
        # or evidence input. This static boundary precedes the server call.
        self.gateway.authorise_source(case, source, claim)
        with tempfile.TemporaryDirectory(prefix="eal-ci-study-") as directory:
            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", "eal.server", "--workspace", str(self.gateway.workspace),
                      "--registry", str(self.gateway.registry_path),
                      "--database", str(Path(directory) / "runs.sqlite3")],
                env=dict(os.environ),
            )
            async with asyncio.timeout(self.timeout_seconds):
                async with stdio_client(parameters) as (read, write):
                    async with ClientSession(read, write) as session:
                        initialised = await session.initialize()
                        tools = {tool.name: tool.inputSchema for tool in (await session.list_tools()).tools}
                        if any(name not in tools for name in OPERATIONS):
                            raise MCPCheckError("EAL server lacks a required study operation")

                        async def call(name: str, arguments: dict) -> dict:
                            errors = list(Draft202012Validator(tools[name]).iter_errors(arguments))
                            if errors:
                                raise MCPCheckError(f"Advertised MCP schema rejected {name}: {errors[0].message}")
                            result = await session.call_tool(name, arguments=arguments)
                            packet = result.structuredContent
                            transcript.append({"tool": name, "arguments_sha256": digest(arguments),
                                               "is_error": bool(result.isError), "result": packet})
                            if result.isError or type(packet) is not dict:
                                raise MCPCheckError(f"MCP {name} failed")
                            return packet

                        validated = await call("eal_validate", {"source": source})
                        if validated.get("valid") is not True:
                            raise MCPCheckError("Authored source is invalid: " +
                                                str(validated.get("diagnostics", []))[:1000])
                        collection = await call("eal_collect", {"source": source,
                                                                "context": case.scope})
                        collection_id = collection.get("collection_id")
                        if type(collection_id) is not str or not collection_id:
                            raise MCPCheckError("MCP collection lacks its stored identity")
                        records = collection.get("records")
                        if type(records) is not dict or len(records) > len(case.evidence_grants):
                            raise MCPCheckError("MCP collection lacks bounded tool records")
                        for record in records.values():
                            if type(record) is not dict:
                                raise MCPCheckError("MCP tool record is malformed")
                            observed = record.get("collected_at")
                            if record.get("status") == "ok" and (
                                    type(observed) is not str
                                    or timestamp(observed) > timestamp(case.decision_cut)):
                                raise MCPCheckError("MCP observation postdates the decision cut")
                        assessment = await call("eal_reason", {"source": source,
                                                                "context": case.scope,
                                                                "collection_id": collection_id,
                                                                "now": case.decision_cut})
                        assessment_id = assessment.get("assessment_id")
                        if (type(assessment_id) is not str or not assessment_id
                                or assessment.get("collection_id") != collection_id):
                            raise MCPCheckError("Assessment is not bound to its collection")
                        explanation = await call("eal_explain", {"assessment_id": assessment_id,
                                                                 "claim": claim})
                        claims = assessment.get("claims")
                        selected = claims.get(claim) if type(claims) is dict else None
                        if type(selected) is not dict or selected.get("status") not in {
                                "supported", "contested", "unsupported", "out_of_scope"}:
                            raise MCPCheckError("Checked claim status is unavailable")
                        return {"status": selected["status"], "source_sha256": digest(source.encode()),
                                "claim": claim, "collection_id": collection_id,
                                "assessment_id": assessment_id,
                                "protocol_version": initialised.protocolVersion,
                                "collection": collection, "assessment": assessment,
                                "explanation": explanation, "mcp_calls": transcript}
