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
from .applicability import TaskApplicabilityRegistry
from .evaluator import canonical_digest
from .families import FamilyRegistry
from .retrieval import CandidateIndex
from .routing import TaskFamilyHost
from .argument_host import ArgumentHost


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
                  recipient_grants: Mapping[str, Collection[str]] | None = None,
                  reviewed_task_host: TaskFamilyHost | None = None,
                  argument_host: ArgumentHost | None = None,
                  bound_prose: str | None = None) -> FastMCP:
    """Create an operator server or a separate, principal-bound recipient server.

    The launcher authenticates the principal before constructing the latter.
    A client request never supplies or changes that identity or its grants.
    """
    checked_grants: dict[str, frozenset[str]] = {}
    if recipient_only and artifacts is not None and artifacts.historical_evaluator:
        raise ValueError("Historical evaluator cannot serve recipient claims")
    if recipient_only:
        if (not isinstance(principal, str)
                or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9.-]{0,127}", principal)
                or (artifacts is None and argument_host is None)):
            raise ValueError("Recipient server requires a trusted principal and a reviewed route")
        if artifacts is not None and (not isinstance(recipient_grants, Mapping)
                                      or not 1 <= len(recipient_grants) <= 512):
            raise ValueError("Artifact recipient requires an artifact catalogue and grants")
        if artifacts is None and recipient_grants not in (None, {}):
            raise ValueError("Artifact grants require an artifact catalogue")
        for artifact_id, claims in (recipient_grants or {}).items():
            if (not isinstance(artifact_id, str) or artifact_id not in artifacts.definitions
                    or not isinstance(claims, (set, frozenset, list, tuple))
                    or not 1 <= len(claims) <= 64
                    or any(type(claim) is not str or claim not in artifacts.definitions[artifact_id].claims
                           for claim in claims)
                    or len(set(claims)) != len(claims)):
                raise ValueError("Recipient grant refers to an unknown registered claim")
            # Snapshot the launcher grant. Later mutation of its mapping or
            # claim collections must not expand a running recipient server.
            checked_grants[artifact_id] = frozenset(claims)
    elif (recipient_grants is not None or
          (principal is not None and (argument_host is None or argument_host.principal != principal))):
        raise ValueError("Recipient identity and grants require recipient-only mode")
    if reviewed_task_host is not None:
        if (not recipient_only or reviewed_task_host.principal != principal
                or reviewed_task_host.families.artifacts is not artifacts
                or reviewed_task_host.applicability is None
                or any(not claims <= checked_grants.get(artifact_id, frozenset())
                       for artifact_id, claims in reviewed_task_host._claims.items())):
            raise ValueError("Reviewed task route requires the same trusted recipient and grants")
    if argument_host is not None and recipient_only and argument_host.principal != principal:
        raise ValueError("Argument host principal differs from the recipient principal")
    if recipient_only and argument_host is not None:
        if (not isinstance(bound_prose, str) or not bound_prose.strip()
                or len(bound_prose.encode("utf-8")) > 4096):
            raise ValueError("Argument recipient requires the launcher's bounded original prose")
    elif bound_prose is not None:
        raise ValueError("Bound prose requires an argument recipient endpoint")
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
        def eal_plan(source: str, claim: str) -> dict[str, Any]:
            """Plan all evidence for a claim, including alternative supports and objections."""
            return service.plan(source, claim)

        @server.tool(structured_output=True)
        def eal_collect(source: str, context: dict, evidence_ids: list[str] | None = None) -> dict[str, Any]:
            """Run tools explicitly granted for general model collection; return collection_id."""
            return service.collect(source, context, evidence_ids, model_access=True)

        @server.tool(structured_output=True)
        def eal_collect_claim(source: str, context: dict, claim: str) -> dict[str, Any]:
            """Collect the complete declared evidence closure for a claim using granted tools."""
            return service.collect_claim(source, context, claim, model_access=True)

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

    if artifacts is not None and reviewed_task_host is None:
        if not recipient_only:
            @server.tool(structured_output=True)
            def eal_assess_artifact(artifact_id: str) -> dict[str, Any]:
                """Collect and assess a pinned host artifact; return its configured claim statuses and trace ID."""
                return artifacts.assess(artifact_id)

        def authorise(artifact_id: str, claim: str) -> None:
            if recipient_only and claim not in checked_grants.get(artifact_id, ()):
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

    if reviewed_task_host is not None:
        @server.tool(structured_output=True)
        def eal_task_candidates() -> dict[str, Any]:
            """Nominate authorised families for the launcher's task; scores cannot authorise an assessment."""
            return {"candidates": reviewed_task_host.candidates(reviewed_task_host.task_text),
                    "meaning": "suggestions_only"}

        @server.tool(structured_output=True)
        def eal_bound_task() -> dict[str, Any]:
            """Discover the unique reviewed question, claim and grants without collecting evidence."""
            return reviewed_task_host.describe_bound_task()

        @server.tool(structured_output=True)
        def eal_assess_bound_task() -> dict[str, Any]:
            """Assess the launcher's exact reviewed question; no model-selected task ID or claim."""
            return reviewed_task_host.assess_bound_task()

        @server.tool(structured_output=True)
        def eal_explain_bound_task(assessment_id: str) -> dict[str, Any]:
            """Retrieve this principal's bounded trace under the same reviewed question and grants."""
            return reviewed_task_host.explain_bound_task(assessment_id)

        @server.tool(structured_output=True)
        def eal_finish_bound_task(assessment_id: str) -> dict[str, Any]:
            """Recover the host-owned packet under the same question, review and principal grant."""
            return reviewed_task_host.finish_bound_task(assessment_id)

    if argument_host is not None:
        if recipient_only:
            @server.tool(structured_output=True)
            def eal_resolve_bound_prose() -> dict[str, Any]:
                """Resolve the launcher's original request without accepting replacement text."""
                return argument_host.resolve(bound_prose)

            @server.tool(structured_output=True)
            def eal_assess_bound_prose() -> dict[str, Any]:
                """Collect and assess the launcher's original request under reviewed forms."""
                return argument_host.assess(bound_prose)
        else:
            @server.tool(structured_output=True)
            def eal_resolve_prose(prose: str, context: dict | None = None,
                                  proposal: dict | None = None,
                                  routing_candidate: dict | None = None) -> dict[str, Any]:
                """Match a claim, decision or proposed action to a reviewed argument form; no collection."""
                return argument_host.resolve(prose, context, proposal, routing_candidate=routing_candidate)

            @server.tool(structured_output=True)
            def eal_assess_prose(prose: str, context: dict | None = None,
                                 proposal: dict | None = None,
                                 routing_candidate: dict | None = None) -> dict[str, Any]:
                """Collect and assess a resolved form with explicit evidence-adequacy obligations."""
                return argument_host.assess(prose, context, proposal, routing_candidate=routing_candidate)

        @server.tool(structured_output=True)
        def eal_finish_prose(assessment_id: str) -> dict[str, Any]:
            """Recover a session-bound checked result without accepting a model-written status."""
            return argument_host.finish(assessment_id)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="EAL MCP server (stdio)")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--methods", help="Trusted host method-registry factory: package.module:function")
    parser.add_argument("--artifacts", type=Path, help="Host-pinned EAL artifact catalogue TOML")
    parser.add_argument("--families", type=Path, help="Reviewed finite task-family catalogue TOML")
    parser.add_argument("--tasks", type=Path, help="Reviewed exact-question applicability catalogue TOML")
    parser.add_argument("--schemes", type=Path, help="Reviewed reusable argument forms TOML")
    parser.add_argument("--session-id", help="Host-assigned argument session ID")
    parser.add_argument("--bound-prose-file", type=Path,
                        help="Original user request supplied by the trusted recipient launcher")
    parser.add_argument("--scheme-grant", action="append", default=[], metavar="SCHEME",
                        help="Reviewed argument form granted to the recipient; may be repeated")
    retrieval = parser.add_mutually_exclusive_group()
    retrieval.add_argument("--aliases", type=Path,
                           help="Optional reviewed candidate-alias catalogue TOML")
    retrieval.add_argument("--rag-catalogue", type=Path,
                           help="Optional reviewed snippet catalogue for advisory local BM25 retrieval")
    parser.add_argument("--recipient-task-file", type=Path,
                        help="Trusted launcher's exact task text, read once at server start")
    parser.add_argument("--recipient-only", action="store_true", help="Expose only authorised pinned claim operations")
    parser.add_argument("--recipient-principal", help="Authenticated identity bound by the trusted launcher")
    parser.add_argument("--recipient-grant", action="append", default=[], metavar="ARTIFACT:CLAIM",
                        help="Trusted launcher grant; may be repeated for one principal")
    parser.add_argument("--recipient-family-grant", action="append", default=[], metavar="FAMILY")
    parser.add_argument("--recipient-task-grant", action="append", default=[], metavar="TASK")
    args = parser.parse_args()
    if args.recipient_grant and not args.recipient_only:
        parser.error("--recipient-grant requires --recipient-only")
    if args.schemes and (not args.recipient_principal or not args.session_id):
        parser.error("Argument forms require a host-assigned principal and session ID")
    if (args.session_id or args.scheme_grant) and not args.schemes:
        parser.error("Argument session and grants require --schemes")
    if args.bound_prose_file and (not args.schemes or not args.recipient_only):
        parser.error("--bound-prose-file requires recipient-only argument schemes")
    if args.schemes and args.recipient_only and (not args.bound_prose_file or not args.scheme_grant):
        parser.error("Argument recipient requires --bound-prose-file and explicit scheme grants")
    task_options = (args.families, args.tasks, args.recipient_task_file)
    if (any(task_options) or args.aliases or args.rag_catalogue
            or args.recipient_family_grant or args.recipient_task_grant):
        if (not all(task_options) or not args.artifacts or not args.recipient_only
                or not args.recipient_principal or not args.recipient_family_grant
                or not args.recipient_task_grant or not args.recipient_grant):
            parser.error("Reviewed task route requires --artifacts, --families, --tasks, "
                         "--recipient-task-file, --recipient-only, principal and all three grants")
    service = ReasoningService(args.workspace, args.registry, args.database, method_registry=load_method_registry(args.methods))
    artifacts = ArtifactRegistry.load(service, args.artifacts) if args.artifacts else None
    grants: dict[str, set[str]] = {}
    for raw in args.recipient_grant:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*:[A-Za-z_][A-Za-z_0-9]*", raw):
            parser.error("--recipient-grant must be ARTIFACT:CLAIM")
        name, claim = raw.split(":", 1)
        grants.setdefault(name, set()).add(claim)
    task_host = None
    if args.tasks:
        if (any(not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", value)
                for value in args.recipient_family_grant + args.recipient_task_grant)):
            parser.error("Family and task grants must be exact identifiers")
        with args.recipient_task_file.open("rb") as stream:
            task_bytes = stream.read(4097)
        if not 1 <= len(task_bytes) <= 4096:
            parser.error("Recipient task text must contain one to 4096 UTF-8 bytes")
        try:
            task_text = task_bytes.decode("utf-8")
        except UnicodeError:
            parser.error("Recipient task text must be UTF-8")
        families = FamilyRegistry.load(artifacts, args.families)
        applicability = TaskApplicabilityRegistry.load(families, args.tasks)
        if args.rag_catalogue:
            from .rag import RagCandidateIndex

            candidate_index = RagCandidateIndex.load(families, args.rag_catalogue)
        else:
            candidate_index = CandidateIndex.load(families, args.aliases) if args.aliases else None
        task_host = TaskFamilyHost(
            families, principal=args.recipient_principal,
            authorised_families=set(args.recipient_family_grant),
            authorised_claims=grants, applicability=applicability,
            task_text=task_text, authorised_tasks=set(args.recipient_task_grant),
            candidate_index=candidate_index,
        )
    argument_host = (ArgumentHost.load(
        service, args.schemes, principal=args.recipient_principal,
        session_id=args.session_id, authorised_schemes=args.scheme_grant or None,
    ) if args.schemes else None)
    bound_prose = None
    if args.bound_prose_file:
        with args.bound_prose_file.open("rb") as stream:
            bound_bytes = stream.read(4097)
        if not 1 <= len(bound_bytes) <= 4096:
            parser.error("Bound prose must contain one to 4096 UTF-8 bytes")
        try:
            bound_prose = bound_bytes.decode("utf-8")
        except UnicodeError:
            parser.error("Bound prose must be UTF-8")
    create_server(service, artifacts, recipient_only=args.recipient_only,
                  principal=args.recipient_principal,
                  recipient_grants=grants if args.recipient_only else None,
                  reviewed_task_host=task_host,
                  argument_host=argument_host, bound_prose=bound_prose).run(transport="stdio")


if __name__ == "__main__":
    main()
