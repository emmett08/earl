"""MCP stdio server using the official SDK's lifecycle and typed tools."""

from __future__ import annotations

import argparse
from collections.abc import Collection
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from jsonschema import Draft202012Validator

from .runtime import ReasoningService, load_method_registry
from .catalogue import WorkspaceKnowledgeCatalogue
from .registered_assessment import RegisteredAssessmentHost


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


def create_server(service: ReasoningService, *,
                  known_entries: Collection[str] | None = None) -> FastMCP:
    """Expose generic language tools or a selected registered-source catalogue."""
    if (known_entries is not None and
            (isinstance(known_entries, (str, bytes)) or
             not isinstance(known_entries, Collection))):
        raise ValueError("Known entries must be a bounded collection of registered IDs")
    selected_known = tuple(known_entries or ())
    if (len(selected_known) > 128
            or any(not isinstance(identifier, str) or not identifier for identifier in selected_known)
            or len(set(selected_known)) != len(selected_known)):
        raise ValueError("Known entries must contain up to 128 unique registered IDs")
    catalogue = WorkspaceKnowledgeCatalogue(service) if selected_known else None
    for identifier in selected_known:
        catalogue.get(identifier)
    known = RegisteredAssessmentHost(service, catalogue) if catalogue else None

    server = StrictFastMCP(
        "EAL engineering reasoning",
        instructions="Validate explicit engineering arguments, collect configured observations, reason over their declared scope, and explain results. Support is relative to declared inference rationales, not a proof of prose truth.",
        log_level="WARNING",
    )

    if selected_known:
        def source_summary(entry: dict[str, Any]) -> dict[str, Any]:
            """Expose discoverable claim metadata without the registered context or source."""
            return {"entry_id": entry["entry_id"], "path": entry["path"],
                    "label": entry["label"], "source_digest": entry["source_digest"],
                    "claims": entry["claims"], "claim_metadata": entry["claim_metadata"]}

        @server.tool(structured_output=True)
        def eal_sources(limit: int = 50, offset: int = 0) -> dict[str, Any]:
            """List developer-registered EAL sources and their selectable claims."""
            if type(limit) is not int or not 1 <= limit <= 100:
                raise ValueError("limit must be an integer from 1 through 100")
            if type(offset) is not int or not 0 <= offset <= 10_000:
                raise ValueError("offset must be an integer from 0 through 10000")
            visible = sorted((catalogue.get(identifier) for identifier in selected_known),
                             key=lambda item: item["path"])
            return {"sources": [source_summary(item) for item in visible[offset:offset + limit]],
                    "limit": limit, "offset": offset}

        @server.tool(structured_output=True)
        def eal_find_claims(query: str | None = None, claim: str | None = None,
                            limit: int = 50) -> dict[str, Any]:
            """Find registered claim metadata; use an exact entry ID and claim to assess."""
            if type(limit) is not int or not 1 <= limit <= 100:
                raise ValueError("limit must be an integer from 1 through 100")
            matches = []
            for identifier in selected_known:
                entry = catalogue.get(identifier)
                matches.extend(catalogue.find(query, claim=claim, path=entry["path"], limit=1))
            return {"matches": [source_summary(item) for item in
                                sorted(matches, key=lambda item: item["path"])[:limit]]}

        @server.tool(structured_output=True)
        def eal_assess_known(entry_id: str, claim: str) -> dict[str, Any]:
            """Reuse compatible observations or collect missing evidence for a registered claim."""
            if entry_id not in selected_known:
                raise ValueError("Registered source is not exposed by this server")
            return known.assess(entry_id, claim)

    if not selected_known:

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
        def eal_plan(source: str, claim: str) -> dict[str, Any]:
            """Plan all evidence for a claim, including alternative supports and objections."""
            return service.plan(source, claim)

        @server.tool(structured_output=True)
        def eal_collect(source: str, context: dict, evidence_ids: list[str] | None = None) -> dict[str, Any]:
            """Run the configured collectors for selected evidence; return collection_id."""
            return service.collect(source, context, evidence_ids)

        @server.tool(structured_output=True)
        def eal_collect_claim(source: str, context: dict, claim: str) -> dict[str, Any]:
            """Collect the complete declared evidence closure for a claim."""
            return service.collect_claim(source, context, claim)

        @server.tool(structured_output=True)
        def eal_reason(source: str, context: dict, collection_id: str | None = None, now: str | None = None) -> dict[str, Any]:
            """Evaluate declared support and objections at an explicit or current UTC time."""
            return service.reason(source, context, collection_id, now)

        @server.tool(structured_output=True)
        def eal_compile_aspic(source: str, context: dict, collection_id: str,
                              goal: str, now: str | None = None) -> dict[str, Any]:
            """Compile checked EAL routes to an opt-in bounded ASPIC+ snapshot with a source map."""
            return service.compile_aspic(source, context, collection_id, goal, now)

        @server.tool(structured_output=True)
        def eal_explain(assessment_id: str, claim: str | None = None) -> dict[str, Any]:
            """Retrieve a persisted reasoning result and its dependency explanations."""
            return service.explain(assessment_id, claim)

        @server.tool(structured_output=True)
        def eal_packet(assessment_id: str, claim: str | None = None) -> dict[str, Any]:
            """Return compact claim results with a reference to the full explanation."""
            return service.packet(assessment_id, claim)

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
    parser.add_argument("--methods", help="Trusted host method-registry factory: package.module:function")
    parser.add_argument("--known-entry", action="append", default=[], metavar="ENTRY_ID",
                        help="Expose a registered source to the model; may be repeated")
    args = parser.parse_args()
    service = ReasoningService(
        args.workspace, args.registry, args.database,
        method_registry=load_method_registry(args.methods),
    )
    create_server(service, known_entries=args.known_entry).run(transport="stdio")


if __name__ == "__main__":
    main()
