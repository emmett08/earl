"""MCP stdio server using the official SDK's lifecycle and typed tools."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from jsonschema import Draft202012Validator

from .runtime import ReasoningService, load_method_registry
from .artifacts import ArtifactRegistry


class StrictFastMCP(FastMCP):
    """Enforce advertised JSON types before the SDK's permissive coercion."""

    async def list_tools(self):
        tools = await super().list_tools()
        for tool in tools:
            tool.inputSchema = {**tool.inputSchema, "additionalProperties": False}
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        tool = next((tool for tool in await self.list_tools() if tool.name == name), None)
        if tool is not None:
            errors = list(Draft202012Validator(tool.inputSchema).iter_errors(arguments))
            if errors:
                raise ValueError("Tool input schema rejected request: " + errors[0].message)
        return await super().call_tool(name, arguments)


def create_server(service: ReasoningService, artifacts: ArtifactRegistry | None = None) -> FastMCP:
    server = StrictFastMCP(
        "EAL engineering reasoning",
        instructions="Validate explicit engineering arguments, collect configured observations, reason over their declared scope, and explain results. Support is relative to declared inference rationales, not a proof of prose truth.",
        log_level="WARNING",
    )

    @server.tool(structured_output=True)
    def eal_describe() -> dict[str, Any]:
        """Discover supported language versions, syntax, method contracts and interpretation limits."""
        return service.describe()

    @server.tool(structured_output=True)
    def eal_format(source: str) -> dict[str, Any]:
        """Return canonical checked EAL source; changed source bytes require new collection bindings."""
        return service.format(source)

    @server.tool(structured_output=True)
    def eal_validate(source: str) -> dict[str, Any]:
        """Parse EAL and check names, types and dependency structure without running tools."""
        return service.validate(source)

    @server.tool(structured_output=True)
    def eal_collect(source: str, context: dict, evidence_ids: list[str] | None = None) -> dict[str, Any]:
        """Run operator-configured tools and store observations; return collection_id for reasoning."""
        return service.collect(source, context, evidence_ids)

    @server.tool(structured_output=True)
    def eal_reason(source: str, context: dict, collection_id: str | None = None, now: str | None = None) -> dict[str, Any]:
        """Evaluate declared support and objections at an explicit or current UTC time."""
        return service.reason(source, context, collection_id, now)

    @server.tool(structured_output=True)
    def eal_explain(assessment_id: str, claim: str | None = None) -> dict[str, Any]:
        """Retrieve a persisted reasoning result and its dependency explanations."""
        return service.explain(assessment_id, claim)

    @server.tool(structured_output=True)
    def eal_grounded(arguments: list[str], attacks: list[list[str]]) -> dict[str, Any]:
        """Compute Dung grounded semantics for an explicitly supplied finite attack graph."""
        from .dialectic import solve_grounded

        return solve_grounded(arguments, attacks)

    if artifacts is not None:
        @server.tool(structured_output=True)
        def eal_assess_artifact(artifact_id: str) -> dict[str, Any]:
            """Collect and assess a pinned host artifact; return its configured claim statuses and trace ID."""
            return artifacts.assess(artifact_id)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="EAL MCP server (stdio)")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--methods", help="Trusted host method-registry factory: package.module:function")
    parser.add_argument("--artifacts", type=Path, help="Host-pinned EAL artifact catalogue TOML")
    args = parser.parse_args()
    service = ReasoningService(args.workspace, args.registry, args.database, method_registry=load_method_registry(args.methods))
    artifacts = ArtifactRegistry.load(service, args.artifacts) if args.artifacts else None
    create_server(service, artifacts).run(transport="stdio")


if __name__ == "__main__":
    main()
