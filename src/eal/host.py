"""Strict JSON host adapter for models which can emit text but cannot call tools.

The host performs MCP initialisation and tool calls. A model merely emits a JSON
request; it does not acquire tool capability by mentioning an MCP operation.
"""

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
    """Send a strict model-generated operator request over MCP."""
    tool, arguments = parse_request(text)
    return await _dispatch_tool(tool, arguments, parameters, timeout_seconds=timeout_seconds)


async def dispatch_pinned_task(task: str, parameters: StdioServerParameters, *,
                               artifact_id: str, claim: str, timeout_seconds: float = 120.0) -> dict[str, Any]:
    """Preassess a trusted selection before passing text to a tool-free model.

    The model's text cannot select source, claim, evidence, method, or tool.
    A separate recipient server must bind its authenticated principal and grant.
    """
    if not isinstance(task, str) or len(task.encode("utf-8")) > 4096:
        raise ValueError("Task must be UTF-8 text of at most 4096 bytes")
    result = await _dispatch_tool("eal_assess_artifact_claim",
                                  {"artifact_id": artifact_id, "claim": claim}, parameters,
                                  timeout_seconds=timeout_seconds)
    if result["is_error"]:
        return result
    packet = result["result"]
    if not isinstance(packet, dict) or packet.get("artifact_id") != artifact_id or packet.get("claim") != claim:
        raise ValueError("MCP assessment does not match the host-selected claim")
    return {"checked_answer": packet, "model_input": {"task": task, "checked_assessment": packet}}


async def finalise_pinned_task(output: str, assessment_id: str, parameters: StdioServerParameters, *,
                               artifact_id: str, claim: str, timeout_seconds: float = 120.0) -> dict[str, Any]:
    """Ignore generated status and recover the stored host decision."""
    if not isinstance(output, str) or len(output.encode("utf-8")) > 16384:
        raise ValueError("Recipient output must be UTF-8 text of at most 16384 bytes")
    if not isinstance(assessment_id, str) or not assessment_id:
        raise ValueError("assessment_id must be a nonempty string")
    result = await _dispatch_tool("eal_finish_artifact_claim",
                                  {"artifact_id": artifact_id, "claim": claim,
                                   "assessment_id": assessment_id}, parameters,
                                  timeout_seconds=timeout_seconds)
    if result["is_error"]:
        return result
    packet = result["result"]
    if not isinstance(packet, dict) or packet.get("assessment_id") != assessment_id:
        raise ValueError("MCP final result does not match the host-selected assessment")
    return {"checked_answer": packet, "recipient_output_unverified": output}


def main() -> None:
    parser = argparse.ArgumentParser(description="Send one text-model JSON request to the EAL MCP server")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--methods", help="Trusted host method-registry factory: package.module:function")
    parser.add_argument("--artifacts", type=Path, help="Trusted pinned EAL artifact catalogue")
    parser.add_argument("--artifact-id", help="Artifact chosen by the trusted host")
    parser.add_argument("--claim", help="Registered claim chosen by the trusted host")
    parser.add_argument("--recipient-principal", help="Principal authenticated by the trusted launcher")
    parser.add_argument("--assessment-id", help="Finalise a prior pinned assessment with recipient text on stdin")
    parser.add_argument("--timeout", type=float, default=120.0, help="Total MCP session deadline in seconds")
    args = parser.parse_args()
    server_args = ["-m", "eal.server", "--workspace", str(args.workspace.resolve())]
    if args.registry:
        server_args.extend(["--registry", str(args.registry.resolve())])
    if args.database:
        server_args.extend(["--database", str(args.database.resolve())])
    if args.methods:
        server_args.extend(["--methods", args.methods])
    pinned = any((args.artifacts, args.artifact_id, args.claim, args.recipient_principal, args.assessment_id))
    if pinned:
        if not all((args.artifacts, args.artifact_id, args.claim, args.recipient_principal)):
            parser.error("Pinned host mode requires --artifacts, --artifact-id, --claim and --recipient-principal")
        server_args.extend(["--artifacts", str(args.artifacts.resolve()), "--recipient-only",
                            "--recipient-principal", args.recipient_principal,
                            "--recipient-grant", f"{args.artifact_id}:{args.claim}"])
    try:
        limit = 16384 if args.assessment_id else 4096 if pinned else MAX_REQUEST_BYTES
        raw = sys.stdin.buffer.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("Host input exceeds its configured byte limit")
        # MCP stdio's default allowlist does not carry PYTHONPATH; use the
        # launcher's environment so a source checkout loads its matching server.
        parameters = StdioServerParameters(command=sys.executable, args=server_args,
                                            env=dict(os.environ))
        if args.assessment_id:
            result = asyncio.run(finalise_pinned_task(raw.decode("utf-8"), args.assessment_id,
                                                      parameters, artifact_id=args.artifact_id, claim=args.claim,
                                                      timeout_seconds=args.timeout))
        elif pinned:
            result = asyncio.run(dispatch_pinned_task(raw.decode("utf-8"), parameters,
                                                      artifact_id=args.artifact_id, claim=args.claim,
                                                      timeout_seconds=args.timeout))
        else:
            result = asyncio.run(dispatch_request(raw.decode("utf-8"), parameters,
                                                  timeout_seconds=args.timeout))
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        if result.get("is_error"):
            raise SystemExit(1)
    except Exception as exc:
        # The MCP SDK can group transport failures raised by its async tasks.
        # Keep the one-request/one-JSON-response host contract on that boundary.
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
