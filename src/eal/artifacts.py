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

    def _registered_claim(self, name: str, claim: str) -> None:
        if name not in self.definitions or claim not in self.definitions[name].claims:
            raise ValueError("Unknown or unregistered artifact claim")

    @staticmethod
    def _brief(value: str, limit: int = 240) -> str:
        """Bound recipient text without silently representing an excerpt as complete."""
        encoded = value.encode("utf-8")
        if len(encoded) <= limit:
            return value
        return encoded[:limit - 3].decode("utf-8", errors="ignore") + "…"

    def _claim_packet(self, name: str, claim: str, assessment_id: str) -> dict[str, Any]:
        full = self.finish(name, assessment_id)
        assessment = self.service.store.get(assessment_id, kind="assessment")
        entry = assessment["claims"][claim]
        environment = entry["environment"]
        arguments = [(identifier, value) for identifier, value in assessment["arguments"].items()
                     if value["conclusion"] == claim]
        # The claim's own status chooses the relevant derivations. An unavailable
        # observation is more useful than the generic unsupported summary.
        rank = {"supported": 0, "contested": 1, "unsupported": 2, "out_of_scope": 3}
        arguments.sort(key=lambda item: (rank.get(item[1]["status"], 4), item[0]))

        def evidence_reason(identifier: str, *, available: bool = False) -> str:
            evidence = assessment["evidence"][identifier]
            reasons = evidence["reasons"]
            if not reasons:
                return evidence["status"]
            if available:
                # The final declared predicate usually distinguishes a named
                # challenge from its subject/context identity predicates.
                return reasons[-1]
            return next((reason for reason in reasons if "does not hold" in reason),
                        next((reason for reason in reasons if " holds (" not in reason), reasons[0]))

        def failed_premise(identifier: str, visited: set[str]) -> str | None:
            """Find one failed predicate along a selected premise dependency."""
            if identifier in visited or len(visited) >= 16:
                return None
            visited = visited | {identifier}
            premise_arguments = sorted((key, value) for key, value in assessment["arguments"].items()
                                       if value["conclusion"] == identifier)
            for _, argument in premise_arguments:
                for evidence_id in argument["dependencies"]["evidence"]:
                    if assessment["evidence"][evidence_id]["status"] != "available":
                        return f"{evidence_id}: {evidence_reason(evidence_id)}"
                for assumption_id in argument["dependencies"]["assumptions"]:
                    assumption = assessment["assumptions"][assumption_id]
                    if assumption["status"] != "supported":
                        validation = assumption["validation"]
                        if assessment["evidence"][validation]["status"] != "available":
                            return f"{validation}: {evidence_reason(validation)}"
                        return f"{assumption_id}: {assumption['reasons'][0]}"
                for parent in argument["dependencies"]["premises"]:
                    if assessment["claims"][parent]["status"] != "supported":
                        cause = failed_premise(parent, visited)
                        if cause is not None:
                            return cause
            return None

        causes = []
        for identifier, argument in arguments[:2]:
            detail = None
            for evidence_id in argument["dependencies"]["evidence"]:
                evidence = assessment["evidence"][evidence_id]
                if evidence["status"] != "available":
                    detail = f"{evidence_id}: {evidence_reason(evidence_id)}"
                    break
            if detail is None:
                for assumption_id in argument["dependencies"]["assumptions"]:
                    assumption = assessment["assumptions"][assumption_id]
                    if assumption["status"] != "supported":
                        detail = f"{assumption_id}: " + (assumption["reasons"][0] if assumption["reasons"] else assumption["status"])
                        break
            if detail is None:
                for premise_id, label in argument.get("premise_labels", {}).items():
                    if label != "accepted":
                        detail = f"Premise {premise_id} is {label}"
                        predicate = (failed_premise(premise_id, {claim})
                                     if assessment["claims"][premise_id]["status"] == "unsupported" else None)
                        if predicate is not None:
                            detail += f"; {predicate}"
                        break
            if detail is None:
                computation = argument.get("reasoning_result", {})
                reasons = computation.get("reasons", [])
                detail = reasons[0] if reasons else argument["reasons"][-1] if argument["reasons"] else argument["status"]
            causes.append({"id": identifier, "status": argument["status"],
                           "reason": self._brief(detail, 300),
                           "reason_truncated": len(detail.encode("utf-8")) > 300})
        relevant = {identifier for identifier, _ in arguments}
        objection_ids = [identifier for identifier, value in assessment["objections"].items()
                         if value["environment"] == environment and
                         ((value["target_kind"] == "claim" and value["target"] == claim)
                          or (value["target_kind"] == "argument" and value["target"] in relevant)
                          or (value["target_kind"] == "reasoning" and any(
                              a["dependencies"]["reasoning"] == value["target"] for _, a in arguments))
                          or (value["target_kind"] == "assumption" and any(
                              value["target"] in a["dependencies"]["assumptions"] for _, a in arguments)))]
        objection_ids.sort()
        visible_objections = [identifier for identifier in objection_ids
                              if assessment["objections"][identifier]["status"] != "inactive"]
        objections = []
        for identifier in visible_objections[:2]:
            objection = assessment["objections"][identifier]
            detail = objection["reasons"][0] if objection["reasons"] else objection["status"]
            explanatory_evidence = objection["evidence"]
            if objection["status"] == "defeated":
                counters = sorted((key, value) for key, value in assessment["objections"].items()
                                  if value["target_kind"] == "objection" and value["target"] == identifier
                                  and value["environment"] == environment and value["status"] == "active")
                if counters:
                    counter_id, counter = counters[0]
                    detail = f"Answered by {counter_id}"
                    explanatory_evidence = counter["evidence"]
            for evidence_id in explanatory_evidence:
                if assessment["evidence"][evidence_id]["status"] == "available":
                    finding = f"{evidence_id}: {evidence_reason(evidence_id, available=True)}"
                    detail = f"{detail}; {finding}" if detail.startswith("Answered by ") else finding
                    break
            objections.append({"id": identifier, "status": objection["status"],
                               "reason": self._brief(detail, 240),
                               "reason_truncated": len(detail.encode("utf-8")) > 240,
                               "evidence_count": len(explanatory_evidence),
                               "evidence_truncated": len(explanatory_evidence) > 1})
        environment_reasons = assessment["environments"][environment]["reasons"]
        packet = {
            "schema": "eal2-claim-packet/2", "artifact_id": name, "claim": claim,
            "status": full["claims"][claim],
            "statement_excerpt": self._brief(entry["statement"], 240),
            "scope": {"environment": environment,
                      "status": assessment["environments"][environment]["status"],
                      "conditions": [self._brief(reason, 120) for reason in environment_reasons[:3]],
                      "condition_count": len(environment_reasons),
                      "context_fingerprint": assessment["context_fingerprint"]},
            "decisive": {"summary": self._brief(entry["reasons"][0], 240),
                         "summary_truncated": len(entry["reasons"][0].encode("utf-8")) > 240,
                         "arguments": causes, "argument_count": len(arguments),
                         "objections": objections, "objection_count": len(visible_objections),
                         "details_truncated": (len(arguments) > 2 or len(visible_objections) > 2
                                               or any(item["reason_truncated"] for item in causes + objections)
                                               or any(item["evidence_truncated"] for item in objections))},
            "assessed_at": full["assessed_at"], "assessment_id": assessment_id,
            "collection_id": full["collection_id"], "source_digest": full["source_digest"],
            "method_registry_fingerprint": full["method_registry_fingerprint"],
            "verification": "server_assessment",
            "evidence_integrity": "consistency_checked_not_authenticated",
        }
        if len(json.dumps(packet, ensure_ascii=False, allow_nan=False).encode("utf-8")) > 3072:
            raise ValueError("Claim packet exceeds its 3072-byte recipient limit")
        return packet

    def assess_claim(self, name: str, claim: str) -> dict[str, Any]:
        """Assess before the recipient call and disclose one registered claim."""
        self._registered_claim(name, claim)
        assessment_id = self.assess(name)["assessment_id"]
        packet = self._claim_packet(name, claim, assessment_id)
        self.service.store.put("artifact_claim_packet", packet,
                               record_id=f"artifact-claim:{assessment_id}:{claim}")
        return json.loads(json.dumps(packet))

    def finish_claim(self, name: str, assessment_id: str, claim: str) -> dict[str, Any]:
        """Return the stored host result, never a recipient's generated status."""
        self._registered_claim(name, claim)
        try:
            packet = self.service.store.get(f"artifact-claim:{assessment_id}:{claim}",
                                            kind="artifact_claim_packet")
        except KeyError as exc:
            raise ValueError("Claim requires a prior host assessment") from exc
        if packet != self._claim_packet(name, claim, assessment_id):
            raise ValueError("Stored claim packet differs from its checked assessment")
        return json.loads(json.dumps(packet))

    def explain_claim(self, name: str, assessment_id: str, claim: str) -> dict[str, Any]:
        """Expose a checked claim's direct dependencies, omitting other claim results.

        Premise IDs and labels can occur in direct argument entries; statements
        and traces for those claims remain unavailable through this operation.
        """
        packet = self.finish_claim(name, assessment_id, claim)
        assessment = self.service.store.get(assessment_id, kind="assessment")
        arguments = {identifier: value for identifier, value in assessment["arguments"].items()
                     if value["conclusion"] == claim}
        evidence_ids: set[str] = set()
        assumption_ids: set[str] = set()
        reasoning_ids: set[str] = set()
        for argument in arguments.values():
            deps = argument["dependencies"]
            evidence_ids.update(deps["evidence"])
            assumption_ids.update(deps["assumptions"])
            reasoning_ids.add(deps["reasoning"])
        for identifier in assumption_ids:
            evidence_ids.add(assessment["assumptions"][identifier]["validation"])
        for identifier in reasoning_ids:
            evidence_ids.update(assessment["reasoning"][identifier]["backing"])
        environment = assessment["claims"][claim]["environment"]
        objections = {identifier: value for identifier, value in assessment["objections"].items()
                      if value["environment"] == environment and
                      ((value["target_kind"] == "claim" and value["target"] == claim)
                       or (value["target_kind"] == "argument" and value["target"] in arguments)
                       or (value["target_kind"] == "reasoning" and value["target"] in reasoning_ids)
                       or (value["target_kind"] == "assumption" and value["target"] in assumption_ids))}
        # A counter-objection can determine whether a direct challenge remains
        # active. Include those counter-attacks, but no unrelated objections.
        frontier = set(objections)
        while frontier:
            if len(objections) > 128:
                raise ValueError("Claim explanation exceeds its objection bound")
            added = {identifier: value for identifier, value in assessment["objections"].items()
                     if value["target_kind"] == "objection" and value["target"] in frontier
                     and identifier not in objections and value["environment"] == environment}
            objections.update(added)
            frontier = set(added)
        for value in objections.values():
            evidence_ids.update(value["evidence"])
        explanation = {"packet": packet, "result": assessment["claims"][claim],
                "scope": assessment["environments"][environment],
                "arguments": arguments,
                "evidence": {key: assessment["evidence"][key] for key in sorted(evidence_ids)},
                "assumptions": {key: assessment["assumptions"][key] for key in sorted(assumption_ids)},
                "reasoning": {key: assessment["reasoning"][key] for key in sorted(reasoning_ids)},
                "objections": objections}
        if len(json.dumps(explanation, ensure_ascii=False, allow_nan=False).encode("utf-8")) > 65536:
            raise ValueError("Claim explanation exceeds its 65536-byte limit")
        return explanation

    async def assist_text_only(self, name: str, task: str,
                               recipient: Callable[[dict[str, Any]], Awaitable[str]],
                               *, claim: str | None = None) -> dict[str, Any]:
        """Assess, ask an optional text-only recipient, then return host statuses.

        The recipient is an application-supplied asynchronous model adapter.
        Its output is retained separately and never supplies the status map.
        The trusted caller must select the artifact ID and enforce model budgets.
        """
        if not isinstance(task, str) or len(task.encode("utf-8")) > 4096:
            raise ValueError("Task must be UTF-8 text of at most 4096 bytes")
        packet = self.assess_claim(name, claim) if claim is not None else self.assess(name)
        recipient_output = await recipient({"task": task, "checked_assessment": packet})
        if not isinstance(recipient_output, str) or len(recipient_output.encode("utf-8")) > 16384:
            raise ValueError("Recipient output must be UTF-8 text of at most 16384 bytes")
        checked = (self.finish_claim(name, packet["assessment_id"], claim)
                   if claim is not None else self.finish(name, packet["assessment_id"]))
        return {"checked_answer": checked,
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
