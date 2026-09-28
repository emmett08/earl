"""Source-bound reuse of previously collected observations.

Rebinding never turns an old measurement into a new one. The evaluator checks
its original measurement time and current predicates when it is assessed.
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
        """Find acquisition-compatible records in newest-first order."""
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
                       current_execution_digest: str | None = None) -> dict[str, Any]:
        """Prepare one exact-identity source-bound reuse, without writing it.

        A caller may combine independently collected evidence in one new
        collection. The returned record retains the original collection time.
        """
        expected = self._expected(program, evidence_id, context, current_binding_digest,
                                  current_execution_digest)
        if not isinstance(original, Mapping) or not isinstance(original.get("run_id"), str):
            raise ValueError(f"Observation {evidence_id!r} has no run_id")
        stored = self.store.get(original["run_id"], kind="observation")
        if stored != original:
            raise ValueError(f"Observation {evidence_id!r} differs from stored acquisition")
        self._verify(original, expected)
        copy = deepcopy(stored)
        copy.pop("stdout", None)
        copy.pop("stderr", None)
        copy["run_id"] = str(uuid4())
        copy["source_digest"] = program.source_digest
        copy["origin_run_id"] = stored.get("origin_run_id", stored["run_id"])
        copy["reused_from_run_id"] = stored["run_id"]
        copy["rebound_at"] = utc_now()
        return copy
