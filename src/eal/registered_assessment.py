"""One-call assessment of a developer-registered EAL claim.

The catalogue selects trusted source and claims. A caller names an entry and
claim; the host plans acquisition, reuses only eligible observations, collects
the remainder and returns a bounded packet. The stored assessment and
collection retain the full explanation and observations by ID.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from .catalogue import WorkspaceKnowledgeCatalogue
from .evaluator import assess_environment, assess_evidence_record, canonical_digest
from .observation_reuse import ObservationRebinder
from .parser import parse
from .runtime import MAX_COLLECTION_BYTES, MAX_COLLECTION_EVIDENCE, ReasoningService
from .semantics import parse_time
from .store import utc_now


class RegisteredAssessmentHost:
    """Execute one registered claim without requiring model tool orchestration."""

    def __init__(self, service: ReasoningService, catalogue: WorkspaceKnowledgeCatalogue):
        if catalogue.service is not service:
            raise ValueError("Catalogue and assessment host must use the same service")
        self.service = service
        self.catalogue = catalogue
        self.rebinder = ObservationRebinder(service.store)

    def _candidate(self, program: Any, context: dict, name: str, *, instant: datetime,
                   binding_digest: str | None, execution_digest: str | None) -> dict | None:
        if binding_digest is None:
            return None
        environment = program.environments[program.evidence[name].environment]
        if assess_environment(environment, context)["status"] != "matched":
            return None
        for original in self.rebinder.candidates(
            program, context, name, current_binding_digest=binding_digest,
            current_execution_digest=execution_digest,
        ):
            try:
                derived = self.rebinder.prepare_record(
                    program, context, name, original,
                    current_binding_digest=binding_digest,
                    current_execution_digest=execution_digest,
                )
            except (ValueError, TypeError, OverflowError):
                continue
            verdict = assess_evidence_record(
                program, name, derived, instant=instant, context=context,
                environment_matched=True, expected_tool_binding_digest=binding_digest,
                check_current_binding=True,
            )
            # A comparable negative measurement is reusable. Missing fields,
            # failed tools, future/stale readings and invalid payloads are not.
            if verdict.complete:
                return derived
        return None

    def _persist_mixed(self, program: Any, context: dict, names: list[str],
                       reused: dict[str, dict],
                       fresh: dict[str, dict]) -> str:
        records = {name: (reused[name] if name in reused else fresh[name]) for name in names}
        collection = {"source_digest": program.source_digest, "context": dict(context),
                      "records": records}
        if len(json.dumps(collection, ensure_ascii=False, sort_keys=True,
                          allow_nan=False).encode("utf-8")) > MAX_COLLECTION_BYTES:
            raise ValueError(f"Collection exceeds {MAX_COLLECTION_BYTES} stored bytes")
        if not reused:
            return self.service.store.put("collection", collection)
        entries = [("observation", record, record["run_id"])
                   for record in reused.values()]
        entries.append(("collection", collection, None))
        return self.service.store.put_batch(entries)[-1]

    def assess(self, entry_id: str, claim: str, *, context: dict | None = None,
               now: str | None = None,
               reuse: Literal["compatible", "fresh"] = "compatible") -> dict:
        """Collect the complete claim graph and assess it under a pinned revision.

        ``context`` is an operator-side override. Model-facing routes should
        pass only the registered entry ID and claim, using its default context.
        ``fresh`` forces acquisition of every planned evidence declaration.
        """
        if reuse not in ("compatible", "fresh"):
            raise ValueError("reuse must be 'compatible' or 'fresh'")
        if now is not None and not isinstance(now, str):
            raise ValueError("now must be an ISO-8601 timestamp with a timezone")
        instant = parse_time(utc_now() if now is None else now)
        entry = self.catalogue.get(entry_id, include_source=True)
        if not isinstance(claim, str) or claim not in entry["claims"]:
            raise ValueError(f"Claim {claim!r} is not selected in registered entry {entry_id!r}")
        if entry["method_registry_fingerprint"] != self.service.method_registry.fingerprint:
            raise ValueError("Registered source method registry differs from the current host")
        selected_context = entry["context"] if context is None else context
        if not isinstance(selected_context, dict):
            raise ValueError("context must be a JSON object")
        canonical_digest(selected_context)

        source = entry["source"]
        plan = self.service.plan(source, claim)
        names = plan["evidence_ids"]
        if len(names) > MAX_COLLECTION_EVIDENCE:
            raise ValueError(f"Collection exceeds {MAX_COLLECTION_EVIDENCE} evidence requests")
        program = parse(source)
        if program.source_digest != entry["source_digest"]:
            raise ValueError("Registered source digest differs from its snapshot")

        reused: dict[str, dict] = {}
        bindings: dict[str, str | None] = {}
        executions: dict[str, str | None] = {}
        if reuse == "compatible":
            bindings = self.service.current_binding_digests(program)
            executions = self.service.current_execution_digests(program)
            for name in names:
                candidate = self._candidate(
                    program, selected_context, name, instant=instant,
                    binding_digest=bindings[name], execution_digest=executions[name],
                )
                if candidate is not None:
                    reused[name] = candidate

        missing = [name for name in names if name not in reused]
        collection = (self.service.collect(source, selected_context, missing)
                      if missing or not reused else None)
        fresh = {} if collection is None else dict(collection["records"])
        if reused:
            # Acquisition can take long enough for a reading to expire or the
            # operator's tool/process environment to change. Recheck before
            # binding old records to the new collection.
            if now is None:
                instant = parse_time(utc_now())
            current_bindings = self.service.current_binding_digests(program)
            current_executions = self.service.current_execution_digests(program)
            expired = [name for name, record in reused.items()
                       if bindings[name] != current_bindings[name]
                       or executions[name] != current_executions[name]
                       or not assess_evidence_record(
                           program, name, record, instant=instant, context=selected_context,
                           environment_matched=True,
                           expected_tool_binding_digest=current_bindings[name],
                           check_current_binding=True,
                       ).complete]
            if expired:
                for name in expired:
                    reused.pop(name)
                replacement = self.service.collect(
                    source, selected_context, expired,
                )
                fresh.update(replacement["records"])

        if reused:
            collection_id = self._persist_mixed(program, selected_context, names, reused, fresh)
        elif collection is not None and set(collection["records"]) == set(names) and set(fresh) == set(names):
            collection_id = collection["collection_id"]
        else:
            # Multiple partial acquisitions form one source-bound collection.
            collection_id = self._persist_mixed(program, selected_context, names, {}, fresh)

        assessed_at = now if now is not None else utc_now()
        assessment = self.service.reason(source, selected_context, collection_id, now=assessed_at)
        packet = self.service.packet(assessment["assessment_id"], claim)
        return {
            "schema": "EAL/registered-assessment/1", "entry_id": entry_id,
            "claim": claim, "source_digest": program.source_digest,
            "context_fingerprint": assessment["context_fingerprint"],
            "collection_id": collection_id, "assessment_id": assessment["assessment_id"],
            "assessed_at": assessment["assessed_at"],
            "status": assessment["claims"][claim]["status"],
            "reused_count": len(reused), "collected_count": len(fresh),
            "packet": packet, "full_explanation": packet["full_explanation"],
        }

    def history(self, entry_id: str, *, source_digest: str | None = None,
                limit: int = 50) -> dict:
        """Find prior exact-source/context assessments by durable IDs."""
        return self.catalogue.runs(entry_id, source_digest=source_digest, limit=limit)
