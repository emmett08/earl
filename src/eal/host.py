"""Strict JSON adapter for clients which cannot call MCP tools directly."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from jsonschema import Draft202012Validator

from .runtime import strict_json


OPERATIONS = {
    "describe": (set(), set()),
    "format": ({"source"}, set()),
    "validate": ({"source"}, set()),
    "plan": ({"source", "claim"}, set()),
    "collect": ({"source", "context"}, {"evidence_ids"}),
    "collect_claim": ({"source", "context", "claim"}, set()),
    "reason": ({"source", "context"}, {"collection_id", "now"}),
    "explain": ({"assessment_id"}, {"claim"}),
    "packet": ({"assessment_id"}, {"claim"}),
    "sources": (set(), {"limit", "offset"}),
    "find_claims": (set(), {"query", "claim", "limit"}),
    "assess_known": ({"entry_id", "claim"}, set()),
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
    for key in ("source", "assessment_id", "entry_id"):
        if key in arguments and not isinstance(arguments[key], str):
            raise ValueError(f"{key} must be a string")
    if operation == "assess_known" and not arguments["entry_id"]:
        raise ValueError("assess_known requires a non-empty registered entry ID")
    for key in ("claim", "collection_id", "now"):
        if key in arguments and arguments[key] is not None and not isinstance(arguments[key], str):
            raise ValueError(f"{key} must be a string or null")
    if operation in {"plan", "collect_claim", "assess_known"} and not arguments["claim"]:
        raise ValueError(f"{operation} requires a non-empty claim identifier")
    if "query" in arguments and arguments["query"] is not None and not isinstance(arguments["query"], str):
        raise ValueError("query must be a string or null")
    for key in ("limit", "offset"):
        if key in arguments and type(arguments[key]) is not int:
            raise ValueError(f"{key} must be an integer")
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


async def _dispatch_tool(tool: str, arguments: dict[str, Any], parameters: StdioServerParameters,
                         *, timeout_seconds: float = 120.0) -> dict[str, Any]:
    """Send a host-selected operation over a real MCP stdio connection."""
    if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
        raise ValueError("Host timeout must be positive and finite")
    async with asyncio.timeout(timeout_seconds):
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                initialised = await session.initialize()
                available = await session.list_tools()
                schema = next((entry.inputSchema for entry in available.tools if entry.name == tool), None)
                if schema is None:
                    raise ValueError(f"MCP server does not offer {tool}")
                errors = list(Draft202012Validator(schema).iter_errors(arguments))
                if errors:
                    raise ValueError("Discovered input schema rejected request: " + errors[0].message)
                result = await session.call_tool(tool, arguments=arguments)
                content = [item.model_dump(mode="json", exclude_none=True) for item in result.content]
                return {
                    "operation": tool.removeprefix("eal_"), "protocol_version": initialised.protocolVersion,
                    "is_error": bool(result.isError), "result": result.structuredContent,
                    "content": content,
                }


async def dispatch_request(text: str, parameters: StdioServerParameters, *, timeout_seconds: float = 120.0) -> dict[str, Any]:
    """Send one strict JSON request over MCP."""
    tool, arguments = parse_request(text)
    return await _dispatch_tool(tool, arguments, parameters, timeout_seconds=timeout_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send one JSON request to the EAL MCP server")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--methods", help="Trusted host method-registry factory: package.module:function")
    parser.add_argument("--limits", type=Path, help="Host-owned execution budget TOML file")
    parser.add_argument("--known-entry", action="append", default=[], metavar="ENTRY_ID",
                        help="Registered source selected by the launcher; may be repeated")
    parser.add_argument("--timeout", type=float, default=120.0, help="Total MCP session deadline in seconds")
    args = parser.parse_args()
    server_args = ["-m", "eal.server", "--workspace", str(args.workspace.resolve())]
    if args.registry:
        server_args.extend(["--registry", str(args.registry.resolve())])
    if args.database:
        server_args.extend(["--database", str(args.database.resolve())])
    if args.methods:
        server_args.extend(["--methods", args.methods])
    if args.limits:
        server_args.extend(["--limits", str(args.limits.resolve())])
    for identifier in args.known_entry:
        server_args.extend(["--known-entry", identifier])
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES:
            raise ValueError("Host input exceeds its configured byte limit")
        # MCP stdio's default allowlist does not carry PYTHONPATH; use the
        # launcher's environment so a source checkout loads its matching server.
        parameters = StdioServerParameters(command=sys.executable, args=server_args,
                                            env=dict(os.environ))
        result = asyncio.run(dispatch_request(raw.decode("utf-8"), parameters,
                                              timeout_seconds=args.timeout))
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        if result.get("is_error"):
            raise SystemExit(1)
    except Exception as exc:
        # Keep the one-request/one-JSON-response contract on transport failures.
        def describe(error):
            if isinstance(error, BaseExceptionGroup):
                return "; ".join(describe(child) for child in error.exceptions)
            if isinstance(error, TimeoutError):
                return "MCP session exceeded its configured deadline"
            return str(error)

        print(json.dumps({"is_error": True, "error": describe(exc)}))
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
