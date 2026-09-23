"""Strict JSON host adapter for models which can emit text but cannot call tools.

The host performs MCP initialisation and tool calls. A model merely emits a JSON
request; it does not acquire tool capability by mentioning an MCP operation.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .runtime import strict_json


OPERATIONS = {
    "describe": (set(), set()),
    "format": ({"source"}, set()),
    "validate": ({"source"}, set()),
    "collect": ({"source", "context"}, {"evidence_ids"}),
    "reason": ({"source", "context"}, {"collection_id", "now"}),
    "explain": ({"assessment_id"}, {"claim"}),
    "grounded": ({"arguments", "attacks"}, set()),
}
MAX_REQUEST_BYTES = 2 * 1024 * 1024


def parse_request(text: str) -> tuple[str, dict[str, Any]]:
    if len(text.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ValueError("Host request exceeds 2 MiB")
    request = strict_json(text)
    if not isinstance(request, dict):
        raise ValueError("Request must be one JSON object")
    operation = request.get("operation")
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise ValueError("operation must be " + ", ".join(OPERATIONS))
    required, optional = OPERATIONS[operation]
    arguments = {key: value for key, value in request.items() if key != "operation"}
    if missing := required - set(arguments):
        raise ValueError(f"Missing request fields: {', '.join(sorted(missing))}")
    if unknown := set(arguments) - required - optional:
        raise ValueError(f"Unknown request fields: {', '.join(sorted(unknown))}")
    for key in ("source", "assessment_id"):
        if key in arguments and not isinstance(arguments[key], str):
            raise ValueError(f"{key} must be a string")
    for key in ("claim", "collection_id", "now"):
        if key in arguments and arguments[key] is not None and not isinstance(arguments[key], str):
            raise ValueError(f"{key} must be a string or null")
    if "context" in arguments and not isinstance(arguments["context"], dict):
        raise ValueError("context must be an object")
    for key in ("evidence_ids", "arguments"):
        value = arguments.get(key)
        if (value is not None or key in required) and (not isinstance(value, list) or not all(isinstance(item, str) for item in value)):
            raise ValueError(f"{key} must be a list of strings")
    if "attacks" in arguments:
        attacks = arguments["attacks"]
        if not isinstance(attacks, list) or not all(isinstance(edge, list) and len(edge) == 2 and all(isinstance(item, str) for item in edge) for edge in attacks):
            raise ValueError("attacks must be a list of [attacker, target] string pairs")
    return "eal_" + operation, arguments


async def dispatch_request(text: str, parameters: StdioServerParameters) -> dict[str, Any]:
    """Send a strict request over a real MCP stdio client connection."""
    tool, arguments = parse_request(text)
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            initialised = await session.initialize()
            available = await session.list_tools()
            if tool not in {entry.name for entry in available.tools}:
                raise ValueError(f"MCP server does not offer {tool}")
            result = await session.call_tool(tool, arguments=arguments)
            content = [item.model_dump(mode="json", exclude_none=True) for item in result.content]
            return {
                "operation": tool.removeprefix("eal_"), "protocol_version": initialised.protocolVersion,
                "is_error": bool(result.isError), "result": result.structuredContent,
                "content": content,
            }


def main() -> None:
    parser = argparse.ArgumentParser(description="Send one text-model JSON request to the EAL MCP server")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--methods", help="Trusted host method-registry factory: package.module:function")
    args = parser.parse_args()
    server_args = ["-m", "eal.server", "--workspace", str(args.workspace.resolve())]
    if args.registry:
        server_args.extend(["--registry", str(args.registry.resolve())])
    if args.database:
        server_args.extend(["--database", str(args.database.resolve())])
    if args.methods:
        server_args.extend(["--methods", args.methods])
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES:
            raise ValueError("Host request exceeds 2 MiB")
        result = asyncio.run(dispatch_request(raw.decode("utf-8"), StdioServerParameters(command=sys.executable, args=server_args)))
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        if result["is_error"]:
            raise SystemExit(1)
    except Exception as exc:
        # The MCP SDK can group transport failures raised by its async tasks.
        # Keep the one-request/one-JSON-response host contract on that boundary.
        def describe(error):
            if isinstance(error, BaseExceptionGroup):
                return "; ".join(describe(child) for child in error.exceptions)
            return str(error)

        print(json.dumps({"is_error": True, "error": describe(exc)}))
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
