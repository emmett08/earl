"""Strict JSON adapter for clients which cannot call MCP tools directly."""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import math
import os
import sys
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import ClientTransport
from mcp import StdioServerParameters
from jsonschema import Draft202012Validator

from .client_transports import create_client_transport, create_http_transport, read_bearer_token
from .host_redaction import sanitise_response
from .operation_contracts import OPERATION_FIELDS
from .runtime import strict_json
from .server_settings import ServerSettings, parse_server_settings


MAX_REQUEST_BYTES = 2 * 1024 * 1024


def parse_request(text: str) -> tuple[str, dict[str, Any]]:
    if len(text.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ValueError("Host request exceeds 2 MiB")
    request = strict_json(text)
    if not isinstance(request, dict):
        raise ValueError("Request must be one JSON object")
    operation = request.get("operation")
    if not isinstance(operation, str) or operation not in OPERATION_FIELDS:
        raise ValueError("operation must be " + ", ".join(OPERATION_FIELDS))
    required, optional = OPERATION_FIELDS[operation]
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
    for key in ("claim", "collection_id", "now", "semantics", "query_mode", "preference"):
        if key in arguments and arguments[key] is not None and not isinstance(arguments[key], str):
            raise ValueError(f"{key} must be a string or null")
    if operation in {"plan", "collect_claim", "assess_known"} and not arguments["claim"]:
        raise ValueError(f"{operation} requires a non-empty claim identifier")
    if operation == "compile_aspic":
        if not isinstance(arguments["goal"], str) or not arguments["goal"].strip():
            raise ValueError("compile_aspic requires a non-empty goal string")
        if not isinstance(arguments["collection_id"], str) or not arguments["collection_id"]:
            raise ValueError("compile_aspic requires a non-empty collection_id string")
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


async def _dispatch_tool(tool: str, arguments: dict[str, Any], parameters: StdioServerParameters | ClientTransport,
                         *, timeout_seconds: float = 120.0) -> dict[str, Any]:
    """Send a schema-checked operation through either configured transport."""
    if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
        raise ValueError("Host timeout must be positive and finite")
    async with asyncio.timeout(timeout_seconds):
        async with Client(create_client_transport(parameters)) as client:
            available = await client.list_tools()
            schema = next((entry.input_schema for entry in available if entry.name == tool), None)
            if schema is None:
                raise ValueError(f"MCP server does not offer {tool}")
            errors = list(Draft202012Validator(schema).iter_errors(arguments))
            if errors:
                raise ValueError("Discovered input schema rejected request: " + errors[0].message)
            result = await client.call_tool(tool, arguments=arguments, raise_on_error=False)
            content = [item.model_dump(mode="json", exclude_none=True) for item in result.content]
            return {
                "operation": tool.removeprefix("eal_"), "protocol_version": client.protocol_version,
                "is_error": bool(result.is_error), "result": result.structured_content,
                "content": content,
            }


async def dispatch_request(text: str, parameters: StdioServerParameters | ClientTransport,
                           *, timeout_seconds: float = 120.0) -> dict[str, Any]:
    """Send one strict JSON request over MCP."""
    tool, arguments = parse_request(text)
    return await _dispatch_tool(tool, arguments, parameters, timeout_seconds=timeout_seconds)


def _server_arguments(settings: ServerSettings) -> list[str]:
    """Pass resolved trusted settings to a stdio child without re-reading config."""
    arguments = ["-m", "eal.server", "--workspace", str(settings.workspace),
                 "--transport", "stdio", "--exposure", settings.exposure,
                 "--max-in-flight", str(settings.max_in_flight)]
    for name in ("registry", "database", "methods", "limits"):
        if value := getattr(settings, name):
            arguments.extend(["--" + name, str(value)])
    for identifier in settings.known_entries:
        arguments.extend(["--known-entry", identifier])
    return arguments


def _configured_http_url(settings: ServerSettings) -> str:
    """Use a concrete configured HTTP bind address as a client target."""
    try:
        address = ipaddress.ip_address(settings.host)
    except ValueError:
        address = None
    if address is not None and address.is_unspecified:
        raise ValueError("An HTTP configuration with a wildcard bind address requires --url")
    host = f"[{settings.host}]" if ":" in settings.host else settings.host
    return f"http://{host}:{settings.port}{settings.path}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Send one JSON request to the EAL MCP server", exit_on_error=False,
        epilog="Service settings use the eal-mcp options, including --config, --workspace, "
               "--registry, --database, --methods, --limits, --known-entry and --token-env. "
               "An HTTP transport connects to an existing server.")
    parser.add_argument("--url", help="Existing Streamable HTTP endpoint; overrides the configured transport")
    parser.add_argument("--timeout", type=float, default=120.0, help="Total MCP session deadline in seconds")
    token = None
    try:
        args, service_args = parser.parse_known_args()
        try:
            settings = parse_server_settings(service_args)
        except SystemExit as exc:
            if exc.code == 0:
                raise
            raise ValueError("Invalid server configuration arguments") from exc
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES:
            raise ValueError("Host input exceeds its configured byte limit")
        if args.url is not None or settings.transport == "http":
            token = read_bearer_token(settings.token_env)
            parameters = create_http_transport(args.url if args.url is not None else _configured_http_url(settings),
                                               token_env=settings.token_env)
        else:
            # A source checkout and its child load matching application code.
            parameters = StdioServerParameters(command=sys.executable, args=_server_arguments(settings),
                env={key: value for key, value in os.environ.items() if not key.startswith("EAL_MCP_")})
        result = asyncio.run(dispatch_request(raw.decode("utf-8"), parameters,
                                              timeout_seconds=args.timeout))
        print(json.dumps(sanitise_response(result, token), ensure_ascii=False, allow_nan=False))
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

        print(json.dumps(sanitise_response({"is_error": True, "error": describe(exc)}, token)))
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
