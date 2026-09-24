"""Principal-bound route from reviewed task families to claim assessments.

The application authenticates a caller and constructs one route with its grant.
Recipient text may supply a query or propose a family and bindings, but may not
change that grant or turn a retrieval suggestion into an assessment.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from threading import RLock
from typing import Any

from .families import FamilyRegistry, authorised_ids
from .retrieval import CandidateIndex


MAX_ISSUED_ASSESSMENTS = 512


class TaskFamilyHost:
    """Assess an exact reviewed case under a trusted caller's claim grant.

    Construct this object in the authenticated host, never from a recipient
    request. ``principal`` is a host audit label, not a bearer credential.
    Instances keep their own issued assessment IDs so a leaked ID from another
    caller cannot retrieve a trace through this route.
    """

    def __init__(self, families: FamilyRegistry, *, principal: str,
                 authorised_families: Collection[str],
                 authorised_claims: Mapping[str, Collection[str]]):
        if not isinstance(principal, str) or not principal.strip() or len(principal.encode("utf-8")) > 128:
            raise ValueError("Principal must be a nonempty host-assigned label of at most 128 bytes")
        family_ids = authorised_ids(authorised_families)
        if family_ids - families.families.keys():
            raise ValueError("Grant contains an unknown family")
        if not isinstance(authorised_claims, Mapping) or len(authorised_claims) > 512:
            raise ValueError("Claim grant must be a bounded artifact-to-claims mapping")
        artifact_ids = authorised_ids(set(authorised_claims))
        if artifact_ids - families.artifacts.definitions.keys():
            raise ValueError("Grant contains an unknown artifact")
        claims = {}
        for artifact_id, selected in authorised_claims.items():
            claim_ids = authorised_ids(selected)
            if claim_ids - set(families.artifacts.definitions[artifact_id].claims):
                raise ValueError("Grant contains an unregistered claim")
            if claim_ids:
                claims[artifact_id] = frozenset(claim_ids)
        self.principal = principal
        self.families = families
        self._claims = claims
        self._families = frozenset(family_ids)
        self._index = CandidateIndex(families)
        self._lock = RLock()
        # Assessment IDs are opaque but are not themselves authorization.
        self._issued: dict[str, tuple[str, str, str]] = {}

    def candidates(self, query: str, *, limit: int = 8) -> list[dict]:
        """Suggest accessible families; no bindings, verdicts or tool execution."""
        available = {
            name for name in self._families
            if any(case.claims and set(case.claims) & self._claims.get(case.artifact_id, frozenset())
                   for case in self.families.families[name].cases)
        }
        return self._index.search(query, authorised_families=available, limit=limit)

    def _selected(self, family_id: str, bindings: dict[str, Any], claim: str) -> str:
        if not isinstance(claim, str):
            raise ValueError("Claim must be an exact registered identifier")
        resolved = self.families.resolve(
            family_id, bindings, authorised_families=self._families,
            authorised_artifacts=frozenset(self._claims))
        artifact_id = resolved["artifact_id"]
        if claim not in resolved["claims"] or claim not in self._claims[artifact_id]:
            raise ValueError("Claim is not reviewed and granted for this family case")
        return artifact_id

    def assess(self, family_id: str, bindings: dict[str, Any], claim: str) -> dict[str, Any]:
        """Check exactly one reviewed, granted claim in its pinned artefact."""
        artifact_id = self._selected(family_id, bindings, claim)
        packet = self.families.artifacts.assess_claim(artifact_id, claim)
        if packet.get("artifact_id") != artifact_id or packet.get("claim") != claim:
            raise ValueError("Host assessment differs from the resolved family case")
        assessment_id = packet.get("assessment_id")
        if not isinstance(assessment_id, str) or not assessment_id:
            raise ValueError("Host assessment has no assessment ID")
        with self._lock:
            if len(self._issued) >= MAX_ISSUED_ASSESSMENTS:
                self._issued.pop(next(iter(self._issued)))
            self._issued[assessment_id] = (family_id, artifact_id, claim)
        return packet

    def _addressed(self, family_id: str, bindings: dict[str, Any], claim: str,
                   assessment_id: str) -> str:
        artifact_id = self._selected(family_id, bindings, claim)
        if not isinstance(assessment_id, str) or len(assessment_id) > 256:
            raise ValueError("Assessment ID must be a bounded string")
        with self._lock:
            issued = self._issued.get(assessment_id)
        if issued != (family_id, artifact_id, claim):
            raise ValueError("Assessment was not issued for this caller and family claim")
        return artifact_id

    def explain(self, family_id: str, bindings: dict[str, Any], claim: str,
                assessment_id: str) -> dict[str, Any]:
        """Retrieve the claim's checked direct trace after the same grant check."""
        artifact_id = self._addressed(family_id, bindings, claim, assessment_id)
        return self.families.artifacts.explain_claim(artifact_id, assessment_id, claim)

    def finish(self, family_id: str, bindings: dict[str, Any], claim: str,
               assessment_id: str) -> dict[str, Any]:
        """Return the checked status; recipient wording cannot change it."""
        artifact_id = self._addressed(family_id, bindings, claim, assessment_id)
        return self.families.artifacts.finish_claim(artifact_id, assessment_id, claim)
