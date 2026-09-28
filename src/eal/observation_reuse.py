"""Explicit, source-bound reuse of previously collected observations.

Rebinding is an operator action on a named collection. It neither calls a tool
nor turns an old measurement into a new one. The evaluator checks the newly
bound observation's predicates and original measurement time at assessment.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Mapping
from uuid import uuid4

from .evaluator import canonical_digest, environment_fingerprint
from .semantics import parse_time
from .store import RunStore, utc_now


class ObservationRebinder:
    """Validate acquisition identity and make immutable derived records."""

    def __init__(self, store: RunStore):
        self.store = store

    @staticmethod
    def _expected(program: Any, evidence_id: str, context: Mapping[str, Any],
                  binding_digest: str | None,
                  execution_digest: str | None) -> dict[str, Any]:
        from .runtime import acquisition_request

        if evidence_id not in program.evidence:
            raise ValueError(f"Undeclared evidence identifier {evidence_id!r}")
        if not isinstance(binding_digest, str) or re.fullmatch(r"[0-9a-f]{64}", binding_digest) is None:
            raise ValueError(f"No current tool binding for evidence {evidence_id!r}")
        evidence = program.evidence[evidence_id]
        acquisition = acquisition_request(program, evidence_id, context)
        expected = {
            "evidence_id": evidence_id,
            "tool": acquisition["tool"],
            "tool_version": acquisition["tool_version"],
            "evidence_kind": evidence.kind,
            "environment": evidence.environment,
            "environment_fingerprint": environment_fingerprint(evidence.environment, context),
            "input": evidence.input,
            "input_digest": canonical_digest(evidence.input),
            "context": dict(context),
            "acquisition_request": acquisition,
            "acquisition_request_digest": canonical_digest(acquisition),
            "request_digest": canonical_digest({"evidence_id": evidence_id,
                                                "environment": evidence.environment,
                                                **acquisition}),
            "tool_binding_digest": binding_digest,
        }
        if execution_digest is not None:
            if (not isinstance(execution_digest, str)
                    or re.fullmatch(r"[0-9a-f]{64}", execution_digest) is None):
                raise ValueError(f"Invalid current process environment for evidence {evidence_id!r}")
            expected["process_environment_digest"] = execution_digest
        return expected

    @staticmethod
    def _verify(record: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
        if record.get("status") != "ok":
            raise ValueError("Only a successful observation can be rebound")
        if record.get("schema") != "EAL/observation-record/1":
            raise ValueError("Rebinding requires an EAL/observation-record/1 observation")
        if ("process_environment_digest" in record
                and "process_environment_digest" not in expected):
            raise ValueError("Current process environment identity is required for command reuse")
        for key, value in expected.items():
            if key not in record or canonical_digest(record[key]) != canonical_digest(value):
                raise ValueError(f"Observation {key} differs from the requested acquisition")
        run_id = record.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("Observation requires a run_id")
        parse_time(record.get("collected_at"))
        if "observed_at" in record:
            parse_time(record["observed_at"])
        if "value" not in record or record.get("data_digest") != canonical_digest(record["value"]):
            raise ValueError("Observation data digest differs from its value")

    def candidates(self, program: Any, context: Mapping[str, Any], evidence_id: str, *,
                   current_binding_digest: str,
                   current_execution_digest: str | None = None,
                   limit: int = 100) -> list[dict[str, Any]]:
        """Find exact-identity records; a caller still names a collection to rebind."""
        expected = self._expected(program, evidence_id, context, current_binding_digest,
                                  current_execution_digest)
        indexed = self.store.find_observations(
            evidence_id=evidence_id, environment=expected["environment"],
            request_digest=expected["request_digest"],
            tool_binding_digest=current_binding_digest, limit=limit,
        )
        compatible = []
        for record in indexed:
            try:
                self._verify(record, expected)
            except (TypeError, ValueError, OverflowError):
                continue
            compatible.append(record)
        return compatible

    def prepare_record(self, program: Any, context: Mapping[str, Any], evidence_id: str,
                       original: Mapping[str, Any], *, current_binding_digest: str | None,
                       current_execution_digest: str | None = None,
                       from_collection_id: str | None = None) -> dict[str, Any]:
        """Prepare one exact-identity source-bound reuse, without writing it.

        A caller may combine independently collected evidence in one new
        collection. ``RunStore.put_rebound_batch`` performs the final
        invalidation check atomically with persistence.
        """
        expected = self._expected(program, evidence_id, context, current_binding_digest,
                                  current_execution_digest)
        if not isinstance(original, Mapping) or not isinstance(original.get("run_id"), str):
            raise ValueError(f"Observation {evidence_id!r} has no run_id")
        stored = self.store.get(original["run_id"], kind="observation")
        if stored != original:
            raise ValueError(f"Observation {evidence_id!r} differs from stored acquisition")
        self._verify(original, expected)
        if self.store.reuse_invalidated(stored):
            raise ValueError(f"Observation {original['run_id']!r} was invalidated for reuse")
        copy = deepcopy(stored)
        copy.pop("stdout", None)
        copy.pop("stderr", None)
        copy["run_id"] = str(uuid4())
        copy["source_digest"] = program.source_digest
        copy["origin_run_id"] = stored.get("origin_run_id", stored["run_id"])
        copy["reused_from_run_id"] = stored["run_id"]
        if from_collection_id is not None:
            copy["reused_from_collection_id"] = from_collection_id
        copy["rebound_at"] = utc_now()
        return copy

    def rebind_collection(self, program: Any, context: Mapping[str, Any], *,
                          from_collection_id: str,
                          current_binding_digests: Mapping[str, str | None],
                          current_execution_digests: Mapping[str, str | None] | None = None,
                          evidence_ids: list[str] | None = None) -> dict[str, Any]:
        """Persist a new collection without altering its source observations.

        Every selected observation must come from the named collection, exist
        as a separate stored observation and match the current declaration,
        context and operator tool binding. Validation precedes the atomic write.
        """
        if not isinstance(from_collection_id, str) or not from_collection_id.strip():
            raise ValueError("from_collection_id must be a nonempty string")
        if not isinstance(context, Mapping):
            raise ValueError("context must be a JSON object")
        canonical_digest(dict(context))
        old = self.store.get(from_collection_id, kind="collection")
        if canonical_digest(old.get("context")) != canonical_digest(dict(context)):
            raise ValueError("Collection context differs from requested context")
        names = list(old.get("records", {})) if evidence_ids is None else evidence_ids
        if (not isinstance(names, list) or not names or any(not isinstance(n, str) for n in names)
                or len(set(names)) != len(names)):
            raise ValueError("evidence_ids must be a nonempty list of unique identifiers")
        rebound: dict[str, dict[str, Any]] = {}
        for name in names:
            if name not in old.get("records", {}):
                raise ValueError(f"Collection has no observation for {name!r}")
            original = old["records"][name]
            if not isinstance(original, Mapping) or original.get("source_digest") != old.get("source_digest"):
                raise ValueError("Original observation source differs from its collection")
            rebound[name] = self.prepare_record(
                program, context, name, original,
                current_binding_digest=current_binding_digests.get(name),
                current_execution_digest=(None if current_execution_digests is None
                                          else current_execution_digests.get(name)),
                from_collection_id=from_collection_id,
            )
        collection = {"source_digest": program.source_digest, "context": dict(context),
                      "records": rebound, "reused_from_collection_id": from_collection_id}
        entries: list[tuple[str, dict[str, Any], str | None]] = [
            ("observation", record, record["run_id"]) for record in rebound.values()
        ]
        entries.append(("collection", collection, None))
        collection_id = self.store.put_rebound_batch(
            entries, source_run_ids=[old["records"][name]["run_id"] for name in names],
        )[-1]
        return {"collection_id": collection_id, **collection}
