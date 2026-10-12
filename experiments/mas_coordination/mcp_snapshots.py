"""Retrieve trusted fixture assessments through an actual EAL MCP process."""
from __future__ import annotations

import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def checked_packets(knowledge, assessments: dict) -> tuple[dict, dict]:
    service = knowledge.service
    settings = StdioServerParameters(
        command=sys.executable,
        args=["-m", "eal.server", "--workspace", str(service.workspace),
              "--registry", str(service.registry_path), "--database", str(service.store.path),
              "--methods", "eal.api_load_methods:registry"],
        env={**os.environ, "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")},
    )
    packets = {}
    calls = []
    async with stdio_client(settings) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()

            async def call(name, arguments):
                result = await session.call_tool(name, arguments)
                if result.is_error or result.structured_content is None:
                    raise RuntimeError(f"EAL MCP {name} failed")
                calls.append({"name": name, "arguments": arguments})
                return result.structured_content

            description = await call("eal_describe", {})
            assert "EAL/3" in description["languages"]
            for claim, assessment in assessments.items():
                packet = await call("eal_packet", {"assessment_id": assessment["assessment_id"], "claim": claim})
                if packet != assessment["packet"]:
                    raise ValueError("MCP packet differs from the trusted stored fixture assessment")
                packets[claim] = packet
    # Registered discovery is a different server exposure; operator-only
    # packet lookup must never be invented as a registered operation.
    registered = StdioServerParameters(command=settings.command,
                                       args=[*settings.args, "--known-entry", next(iter(assessments.values()))["entry_id"]],
                                       env=settings.env)
    async with stdio_client(registered) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            listed = await session.call_tool("eal_sources", {})
            if listed.is_error or listed.structured_content is None:
                raise RuntimeError("Registered MCP discovery failed")
            sources = listed.structured_content
            if len(sources["sources"]) != 1:
                raise ValueError("Registered MCP exposure differs from the selected entry")
            calls.append({"name": "eal_sources", "arguments": {}, "exposure": "registered"})
    return packets, {"transport": "actual_mcp_stdio", "initialized": True,
                     "calls": calls, "registered_sources": sources}
