"""MCP stdio server using the official SDK's lifecycle and typed tools."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .runtime import ReasoningService


def create_server(service: ReasoningService) -> FastMCP:
    server = FastMCP(
        "EAL engineering reasoning",
        instructions="Validate explicit engineering arguments, collect configured observations, reason over their declared scope, and explain results. Support is relative to declared inference rationales, not a proof of prose truth.",
        log_level="WARNING",
    )

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

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="EAL MCP server (stdio)")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    service = ReasoningService(args.workspace, args.registry, args.database)
    create_server(service).run(transport="stdio")


if __name__ == "__main__":
    main()
