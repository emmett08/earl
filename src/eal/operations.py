"""Bind the shared MCP operation catalogue to one EAL application service."""

from __future__ import annotations

from collections.abc import Callable, Collection
from inspect import Parameter, signature
from typing import Any

from .runtime import ReasoningService
from .catalogue import WorkspaceKnowledgeCatalogue
from .registered_assessment import RegisteredAssessmentHost
from .operation_contracts import OPERATION_FIELDS


def create_operations(service: ReasoningService, *,
                      known_entries: Collection[str] | None = None,
                      exposure: str | None = None) -> dict[str, Callable[..., dict[str, Any]]]:
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
    selected_exposure = exposure or ("registered" if selected_known else "operator")
    if selected_exposure not in {"operator", "registered"}:
        raise ValueError("exposure must be operator or registered")
    if selected_exposure == "registered" and not selected_known:
        raise ValueError("Registered exposure requires at least one known entry")
    if selected_exposure == "operator" and selected_known:
        raise ValueError("Operator exposure conflicts with known entries")
    catalogue = WorkspaceKnowledgeCatalogue(service) if selected_known else None
    for identifier in selected_known:
        catalogue.get(identifier)
    known = RegisteredAssessmentHost(service, catalogue) if catalogue else None

    operations: dict[str, Callable[..., dict[str, Any]]] = {}

    def register(handler):
        name = handler.__name__
        short_name = name.removeprefix("eal_")
        required, optional = OPERATION_FIELDS[short_name]
        parameters = signature(handler).parameters
        actual_required = {key for key, value in parameters.items() if value.default is Parameter.empty}
        if actual_required != required or set(parameters) != required | optional:
            raise ValueError(f"Operation signature disagrees with its catalogue: {name}")
        operations[name] = handler
        return handler

    if selected_known:
        def source_summary(entry: dict[str, Any]) -> dict[str, Any]:
            """Expose discoverable claim metadata without the registered context or source."""
            return {"entry_id": entry["entry_id"], "path": entry["path"],
                    "label": entry["label"], "source_digest": entry["source_digest"],
                    "claims": entry["claims"], "claim_metadata": entry["claim_metadata"]}

        @register
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

        @register
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

        @register
        def eal_assess_known(entry_id: str, claim: str) -> dict[str, Any]:
            """Reuse compatible observations or collect missing evidence for a registered claim."""
            if entry_id not in selected_known:
                raise ValueError("Registered source is not exposed by this server")
            return known.assess(entry_id, claim)

    if not selected_known:

        @register
        def eal_describe() -> dict[str, Any]:
            """Discover supported language versions, syntax, method contracts and interpretation limits."""
            return service.describe()

        @register
        def eal_format(source: str) -> dict[str, Any]:
            """Return canonical checked EAL source; changed source bytes require new collection bindings."""
            return service.format(source)

        @register
        def eal_validate(source: str) -> dict[str, Any]:
            """Parse EAL and check names, types and dependency structure without running tools."""
            return service.validate(source)

        @register
        def eal_plan(source: str, claim: str) -> dict[str, Any]:
            """Plan all evidence for a claim, including alternative supports and objections."""
            return service.plan(source, claim)

        @register
        def eal_collect(source: str, context: dict, evidence_ids: list[str] | None = None) -> dict[str, Any]:
            """Run the configured collectors for selected evidence; return collection_id."""
            return service.collect(source, context, evidence_ids)

        @register
        def eal_collect_claim(source: str, context: dict, claim: str) -> dict[str, Any]:
            """Collect the complete declared evidence closure for a claim."""
            return service.collect_claim(source, context, claim)

        @register
        def eal_reason(source: str, context: dict, collection_id: str | None = None, now: str | None = None) -> dict[str, Any]:
            """Evaluate declared support and objections at an explicit or current UTC time."""
            return service.reason(source, context, collection_id, now)

        @register
        def eal_compile_aspic(source: str, context: dict, collection_id: str,
                              goal: str, now: str | None = None, semantics: str = 'grounded',
                              query_mode: str = 'sceptical', preference: str | None = None) -> dict[str, Any]:
            """Compile checked EAL routes to an opt-in bounded ASPIC+ snapshot with a source map."""
            return service.compile_aspic(source, context, collection_id, goal, now,
                                         semantics=semantics, query_mode=query_mode, preference=preference)

        @register
        def eal_explain(assessment_id: str, claim: str | None = None) -> dict[str, Any]:
            """Retrieve a persisted reasoning result and its dependency explanations."""
            return service.explain(assessment_id, claim)

        @register
        def eal_packet(assessment_id: str, claim: str | None = None) -> dict[str, Any]:
            """Return compact claim results with a reference to the full explanation."""
            return service.packet(assessment_id, claim)

        @register
        def eal_grounded(arguments: list[str], attacks: list[list[str]]) -> dict[str, Any]:
            """Compute Dung grounded semantics for an explicitly supplied finite attack graph."""
            from .dialectic import solve_grounded
            from .limits import using_limits
            with using_limits(service.limits):
                return solve_grounded(arguments, attacks)

    return operations
