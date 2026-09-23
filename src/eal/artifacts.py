"""Operator-pinned EAL sources for compact, repeatable recipient assessments.

The catalogue is configured outside EAL source. A client selects only an
operator-approved artifact ID; it cannot supply substitute source, claims,
context or assessment time through this interface.
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
import tomllib
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from .parser import MAX_SOURCE_BYTES
from .evaluator import canonical_digest
from .runtime import ReasoningService, bounded_path
from .semantics import parse_time
from .store import utc_now


@dataclass(frozen=True)
class Artifact:
    path: str
    sha256: str
    method_registry_fingerprint: str
    claims: tuple[str, ...]
    context: dict[str, Any]
    now: str | None


class ArtifactRegistry:
    """A bounded, host-configured catalogue of exact source and task bindings."""

    def __init__(self, service: ReasoningService, definitions: dict[str, Artifact]):
        self.service = service
        self.definitions = dict(definitions)

    @classmethod
    def load(cls, service: ReasoningService, path: str | Path) -> "ArtifactRegistry":
        with Path(path).open("rb") as stream:
            document = tomllib.load(stream)
        if set(document) != {"artifacts"} or not isinstance(document["artifacts"], dict):
            raise ValueError("Artifact catalogue must contain only an [artifacts] table")
        definitions = {}
        if len(document["artifacts"]) > 512:
            raise ValueError("Artifact catalogue exceeds 512 entries")
        fields = {"path", "sha256", "method_registry_fingerprint", "claims", "context", "now"}
        for name, raw in document["artifacts"].items():
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name):
                raise ValueError("Artifact IDs must be EAL identifiers")
            if not isinstance(raw, dict) or set(raw) - fields or not fields.difference({"now"}) <= set(raw):
                raise ValueError(f"Artifact {name!r} has missing or unknown settings")
            relative = raw["path"]
            if (not isinstance(relative, str) or not relative or Path(relative).is_absolute()
                    or ".." in Path(relative).parts or not relative.endswith(".eal")):
                raise ValueError(f"Artifact {name!r} requires a workspace-relative .eal path")
            digest = raw["sha256"]
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError(f"Artifact {name!r} requires a lowercase SHA-256 digest")
            method_id = raw["method_registry_fingerprint"]
            if not isinstance(method_id, str) or not re.fullmatch(r"[0-9a-f]{64}", method_id):
                raise ValueError(f"Artifact {name!r} requires a method-registry fingerprint")
            claims = raw["claims"]
            if (not isinstance(claims, list) or not 1 <= len(claims) <= 64
                    or any(not isinstance(c, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", c) for c in claims)
                    or len(set(claims)) != len(claims)):
                raise ValueError(f"Artifact {name!r} requires one to 64 unique claim IDs")
            context = raw["context"]
            if not isinstance(context, dict):
                raise ValueError(f"Artifact {name!r} requires a context table")
            try:
                encoded_context = json.dumps(context, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
            except (TypeError, ValueError, UnicodeError) as exc:
                raise ValueError(f"Artifact {name!r} has a non-JSON context") from exc
            if len(encoded_context) > 8192:
                raise ValueError(f"Artifact {name!r} context exceeds 8192 bytes")
            now = raw.get("now")
            if now is not None:
                if not isinstance(now, str):
                    raise ValueError(f"Artifact {name!r} now must be an ISO-8601 string")
                parse_time(now)
            definitions[name] = Artifact(relative, digest, method_id, tuple(claims),
                                         json.loads(encoded_context), now)
        registry = cls(service, definitions)
        for name in definitions:
            registry._source(name)
        return registry

    def _source(self, name: str) -> str:
        if name not in self.definitions:
            raise ValueError(f"Unknown registered artifact {name!r}")
        artifact = self.definitions[name]
        if self.service.method_registry.fingerprint != artifact.method_registry_fingerprint:
            raise ValueError(f"Artifact {name!r} method registry differs from its pinned contract")
        path = bounded_path(self.service.workspace, artifact.path)
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError(f"Artifact {name!r} must refer to a regular EAL file")
        with path.open("rb") as stream:
            data = stream.read(MAX_SOURCE_BYTES + 1)
        if len(data) > MAX_SOURCE_BYTES or hashlib.sha256(data).hexdigest() != artifact.sha256:
            raise ValueError(f"Artifact {name!r} source differs from its pinned digest or exceeds the source limit")
        try:
            source = data.decode("utf-8")
        except UnicodeError as exc:
            raise ValueError(f"Artifact {name!r} source is not UTF-8") from exc
        checked = self.service.validate(source)
        if not checked["valid"] or checked.get("source_digest") != artifact.sha256:
            raise ValueError(f"Artifact {name!r} source failed EAL validation")
        from .parser import parse

        declared = parse(source).claims
        if not set(artifact.claims) <= set(declared):
            raise ValueError(f"Artifact {name!r} selects a claim absent from its source")
        if checked.get("method_registry_fingerprint") != artifact.method_registry_fingerprint:
            raise ValueError(f"Artifact {name!r} method registry changed during validation")
        return source

    def assess(self, name: str) -> dict[str, Any]:
        """Collect and assess an immutable source; return only pinned claim statuses."""
        source = self._source(name)
        artifact = self.definitions[name]
        context = artifact.context
        collection = self.service.collect(source, context)
        if collection.get("source_digest") != artifact.sha256 or collection.get("context") != context:
            raise ValueError("Collection identity differs from the registered artifact")
        now = artifact.now or utc_now()
        assessment = self.service.reason(source, context, collection["collection_id"], now)
        expected_time = parse_time(now).isoformat().replace("+00:00", "Z")
        if (assessment.get("valid") is not True or assessment.get("source_digest") != artifact.sha256
                or assessment.get("collection_id") != collection["collection_id"]
                or assessment.get("context_fingerprint") != canonical_digest(context)
                or assessment.get("assessed_at") != expected_time
                or assessment.get("method_registry_fingerprint") != artifact.method_registry_fingerprint):
            raise ValueError("Assessment identity differs from the registered artifact")
        all_claims = assessment.get("claims")
        if not isinstance(all_claims, dict):
            raise ValueError("Assessment did not return claim statuses")
        selected = {}
        for claim in artifact.claims:
            status = all_claims.get(claim, {}).get("status")
            if status not in {"supported", "contested", "unsupported", "out_of_scope"}:
                raise ValueError(f"Assessment did not return a valid status for {claim!r}")
            selected[claim] = status
        packet = {"artifact_id": name, "claims": selected,
                "source_digest": artifact.sha256,
                "method_registry_fingerprint": artifact.method_registry_fingerprint,
                "collection_id": collection["collection_id"],
                "assessment_id": assessment["assessment_id"],
                "assessed_at": assessment["assessed_at"],
                "verification": "server_assessment"}
        self.service.store.put("artifact_packet", packet, record_id=f"artifact:{assessment['assessment_id']}")
        return packet

    def finish(self, name: str, assessment_id: str) -> dict[str, Any]:
        """Host-owned final statuses after an optional tool-free recipient turn.

        The caller may show the compact packet to a model for prose generation.
        Its returned status labels are ignored: this final result comes from
        the addressed server assessment. Distinct concurrent recipients retain
        separate assessments with explicit as-of times.
        """
        self._source(name)
        try:
            packet = self.service.store.get(f"artifact:{assessment_id}", kind="artifact_packet")
        except KeyError as exc:
            raise ValueError("finish requires an artifact assessment created by this host") from exc
        if packet.get("artifact_id") != name or packet.get("assessment_id") != assessment_id:
            raise ValueError("finish artifact ID differs from its assessment")
        saved = self.service.store.get(assessment_id, kind="assessment")
        artifact = self.definitions[name]
        if (saved.get("valid") is not True or saved.get("source_digest") != artifact.sha256
                or saved.get("collection_id") != packet["collection_id"]
                or saved.get("context_fingerprint") != canonical_digest(artifact.context)
                or saved.get("assessed_at") != packet["assessed_at"]
                or saved.get("method_registry_fingerprint") != artifact.method_registry_fingerprint):
            raise ValueError("Stored assessment no longer matches the registered artifact")
        collection = self.service.store.get(packet["collection_id"], kind="collection")
        if collection.get("source_digest") != artifact.sha256 or collection.get("context") != artifact.context:
            raise ValueError("Stored collection no longer matches the registered artifact")
        claims = {claim: saved.get("claims", {}).get(claim, {}).get("status") for claim in artifact.claims}
        if claims != packet["claims"]:
            raise ValueError("Stored statuses differ from the checked artifact packet")
        return json.loads(json.dumps(packet))

    async def assist_text_only(self, name: str, task: str,
                               recipient: Callable[[dict[str, Any]], Awaitable[str]]) -> dict[str, Any]:
        """Assess, ask an optional text-only recipient, then return host statuses.

        The recipient is an application-supplied asynchronous model adapter.
        Its output is retained separately and never supplies the status map.
        The trusted caller must select the artifact ID and enforce model budgets.
        """
        if not isinstance(task, str) or len(task.encode("utf-8")) > 4096:
            raise ValueError("Task must be UTF-8 text of at most 4096 bytes")
        packet = self.assess(name)
        recipient_output = await recipient({"task": task, "checked_assessment": packet})
        if not isinstance(recipient_output, str) or len(recipient_output.encode("utf-8")) > 16384:
            raise ValueError("Recipient output must be UTF-8 text of at most 16384 bytes")
        return {"checked_answer": self.finish(name, packet["assessment_id"]),
                "recipient_output_unverified": recipient_output}


def main() -> None:
    """Assess a pinned artifact before any optional text-only model call.

    Example: python -m eal.artifacts --workspace . --registry tools.toml \\
                 --artifacts artifacts.toml --id sample
    """
    from .runtime import load_method_registry

    parser = argparse.ArgumentParser(description="Assess an operator-pinned EAL artifact")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--methods")
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--id", required=True, help="Registered artifact ID")
    args = parser.parse_args()
    service = ReasoningService(args.workspace, args.registry, args.database,
                               method_registry=load_method_registry(args.methods))
    result = ArtifactRegistry.load(service, args.artifacts).assess(args.id)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
