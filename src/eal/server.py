"""MCP stdio server using the official SDK's lifecycle and typed tools."""

from __future__ import annotations

import argparse
import re
from collections.abc import Mapping, Collection
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from jsonschema import Draft202012Validator

from .runtime import ReasoningService, load_method_registry
from .artifacts import ArtifactRegistry
from .evaluator import canonical_digest


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


def create_server(service: ReasoningService, artifacts: ArtifactRegistry | None = None, *,
                  recipient_only: bool = False, principal: str | None = None,
                  recipient_grants: Mapping[str, Collection[str]] | None = None) -> FastMCP:
    """Create an operator server or a separate, principal-bound recipient server.

    The launcher authenticates the principal before constructing the latter.
    A client request never supplies or changes that identity or its grants.
    """
    if recipient_only:
        if (artifacts is None or not isinstance(principal, str)
                or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9.-]{0,127}", principal)
                or not recipient_grants):
            raise ValueError("Recipient server requires a trusted principal, artifact catalogue and grants")
        for artifact_id, claims in recipient_grants.items():
            if (artifact_id not in artifacts.definitions or not claims or
                    not set(claims) <= set(artifacts.definitions[artifact_id].claims)):
                raise ValueError("Recipient grant refers to an unknown registered claim")
    elif principal is not None or recipient_grants is not None:
        raise ValueError("Recipient identity and grants require recipient-only mode")
    server = StrictFastMCP(
        "EAL engineering reasoning",
        instructions="Validate explicit engineering arguments, collect configured observations, reason over their declared scope, and explain results. Support is relative to declared inference rationales, not a proof of prose truth.",
        log_level="WARNING",
    )

    if not recipient_only:
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
        if not recipient_only:
            @server.tool(structured_output=True)
            def eal_assess_artifact(artifact_id: str) -> dict[str, Any]:
                """Collect and assess a pinned host artifact; return its configured claim statuses and trace ID."""
                return artifacts.assess(artifact_id)

        def authorise(artifact_id: str, claim: str) -> None:
            if recipient_only and claim not in recipient_grants.get(artifact_id, ()):
                raise ValueError("Recipient is not permitted to access that artifact claim")
            artifacts._registered_claim(artifact_id, claim)

        def issued_packet(artifact_id: str, assessment_id: str, claim: str) -> dict[str, Any]:
            """Require issuance to this principal, including across server restarts."""
            if not recipient_only:
                return artifacts.finish_claim(artifact_id, assessment_id, claim)
            key = f"recipient-issue:{principal}:{assessment_id}:{claim}"
            try:
                issued = service.store.get(key, kind="recipient_issuance")
            except KeyError as exc:
                raise ValueError("This principal did not receive that artifact assessment") from exc
            packet = artifacts.finish_claim(artifact_id, assessment_id, claim)
            if issued != {"principal": principal, "artifact_id": artifact_id, "claim": claim,
                          "assessment_id": assessment_id, "packet_digest": canonical_digest(packet)}:
                raise ValueError("Issued assessment differs from its host-owned packet")
            return packet

        @server.tool(structured_output=True)
        def eal_assess_artifact_claim(artifact_id: str, claim: str) -> dict[str, Any]:
            """Assess a pinned claim before a recipient model call; return a bounded status packet."""
            authorise(artifact_id, claim)
            packet = artifacts.assess_claim(artifact_id, claim)
            if recipient_only:
                assessment_id = packet["assessment_id"]
                service.store.put("recipient_issuance", {
                    "principal": principal, "artifact_id": artifact_id, "claim": claim,
                    "assessment_id": assessment_id, "packet_digest": canonical_digest(packet),
                }, record_id=f"recipient-issue:{principal}:{assessment_id}:{claim}")
            return packet

        @server.tool(structured_output=True)
        def eal_explain_artifact_claim(artifact_id: str, assessment_id: str, claim: str) -> dict[str, Any]:
            """Retrieve only the authorised claim's checked direct dependencies."""
            authorise(artifact_id, claim)
            issued_packet(artifact_id, assessment_id, claim)
            return artifacts.explain_claim(artifact_id, assessment_id, claim)

        @server.tool(structured_output=True)
        def eal_finish_artifact_claim(artifact_id: str, assessment_id: str, claim: str) -> dict[str, Any]:
            """Recover the host-owned status independently of recipient prose."""
            authorise(artifact_id, claim)
            return issued_packet(artifact_id, assessment_id, claim)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="EAL MCP server (stdio)")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--methods", help="Trusted host method-registry factory: package.module:function")
    parser.add_argument("--artifacts", type=Path, help="Host-pinned EAL artifact catalogue TOML")
    parser.add_argument("--recipient-only", action="store_true", help="Expose only authorised pinned claim operations")
    parser.add_argument("--recipient-principal", help="Authenticated identity bound by the trusted launcher")
    parser.add_argument("--recipient-grant", action="append", default=[], metavar="ARTIFACT:CLAIM",
                        help="Trusted launcher grant; may be repeated for one principal")
    args = parser.parse_args()
    if args.recipient_grant and not args.recipient_only:
        parser.error("--recipient-grant requires --recipient-only")
    service = ReasoningService(args.workspace, args.registry, args.database, method_registry=load_method_registry(args.methods))
    artifacts = ArtifactRegistry.load(service, args.artifacts) if args.artifacts else None
    grants: dict[str, set[str]] = {}
    for raw in args.recipient_grant:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*:[A-Za-z_][A-Za-z_0-9]*", raw):
            parser.error("--recipient-grant must be ARTIFACT:CLAIM")
        name, claim = raw.split(":", 1)
        grants.setdefault(name, set()).add(claim)
    create_server(service, artifacts, recipient_only=args.recipient_only,
                  principal=args.recipient_principal,
                  recipient_grants=grants if args.recipient_only else None).run(transport="stdio")


if __name__ == "__main__":
    main()
