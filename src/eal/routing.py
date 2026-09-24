"""Principal-bound route from reviewed tasks and families to claim assessments.

The application authenticates a caller and constructs one route with its grant.
Recipient text may nominate a task ID. The host binds the original task and
refuses an inapplicable nomination before it can run an assessment.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from threading import RLock
from typing import Any

from .applicability import TaskApplicabilityRegistry
from .evaluator import canonical_digest
from .families import FamilyRegistry, authorised_ids
from .retrieval import CandidateIndex


MAX_ISSUED_ASSESSMENTS = 512


class TaskFamilyHost:
    """Assess an exact reviewed case under a trusted caller's claim grant.

    Construct this object in the authenticated host, never from a recipient
    request. ``principal`` is a host audit label, not a bearer credential.
    The store retains issued assessment identities across process restarts;
    an opaque assessment ID alone never grants access to a trace.
    """

    def __init__(self, families: FamilyRegistry, *, principal: str,
                 authorised_families: Collection[str],
                 authorised_claims: Mapping[str, Collection[str]],
                 applicability: TaskApplicabilityRegistry | None = None,
                 task_text: str | None = None,
                 authorised_tasks: Collection[str] = (),
                 candidate_index: CandidateIndex | None = None):
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
        if applicability is None:
            if task_text is not None or authorised_tasks:
                raise ValueError("Reviewed task grants require an applicability catalogue")
            self._tasks = frozenset()
        else:
            if applicability.families is not families:
                raise ValueError("Task catalogue must use this family registry")
            if (not isinstance(task_text, str) or not task_text.strip()
                    or len(task_text.encode("utf-8")) > 4096):
                raise ValueError("Reviewed task text must be bound by the authenticated host")
            task_ids = authorised_ids(authorised_tasks)
            if task_ids - applicability.tasks.keys():
                raise ValueError("Grant contains an unknown reviewed task")
            self._tasks = frozenset(task_ids)
        self.applicability = applicability
        self.task_text = task_text
        if candidate_index is not None and candidate_index.families is not families:
            raise ValueError("Candidate index must use this family registry")
        self._index = candidate_index or CandidateIndex(families)
        self._lock = RLock()
        # This bounded cache is diagnostic only; SQLite is the authority.
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

    def _issue_key(self, family_id: str, artifact_id: str, claim: str,
                   assessment_id: str) -> str:
        return "family-issue:" + canonical_digest({
            "principal": self.principal, "family_id": family_id,
            "artifact_id": artifact_id, "claim": claim,
            "assessment_id": assessment_id,
        })

    def _assess_selected(self, family_id: str, artifact_id: str, claim: str, *,
                         task_id: str | None = None,
                         task_review: str | None = None) -> dict[str, Any]:
        packet = self.families.artifacts.assess_claim(artifact_id, claim)
        if packet.get("artifact_id") != artifact_id or packet.get("claim") != claim:
            raise ValueError("Host assessment differs from the resolved family case")
        assessment_id = packet.get("assessment_id")
        if not isinstance(assessment_id, str) or not assessment_id:
            raise ValueError("Host assessment has no assessment ID")
        self.families.artifacts.service.store.put("family_issuance", {
            "principal": self.principal, "family_id": family_id,
            "artifact_id": artifact_id, "claim": claim,
            "assessment_id": assessment_id, "packet_digest": canonical_digest(packet),
            "task_id": task_id, "task_review": task_review,
        }, record_id=self._issue_key(family_id, artifact_id, claim, assessment_id))
        with self._lock:
            if len(self._issued) >= MAX_ISSUED_ASSESSMENTS:
                self._issued.pop(next(iter(self._issued)))
            self._issued[assessment_id] = (family_id, artifact_id, claim)
        return packet

    def assess(self, family_id: str, bindings: dict[str, Any], claim: str) -> dict[str, Any]:
        """Check a trusted caller's exact reviewed family case.

        The caller must already establish applicability to the actual task.
        Model-facing endpoints should use ``assess_task`` instead.
        """
        if self.applicability is not None:
            raise ValueError("Reviewed task route requires assess_task")
        artifact_id = self._selected(family_id, bindings, claim)
        return self._assess_selected(family_id, artifact_id, claim)

    def _reviewed(self, task_id: str) -> dict[str, Any]:
        if self.applicability is None or self.task_text is None:
            raise ValueError("Host has no bound reviewed task")
        selected = self.applicability.resolve(
            self.task_text, task_id=task_id, authorised_tasks=self._tasks,
            authorised_families=self._families,
            authorised_artifacts=frozenset(self._claims),
        )
        if selected["claim"] not in self._claims[selected["artifact_id"]]:
            raise ValueError("Reviewed task claim is not granted to this caller")
        return selected

    def assess_task(self, task_id: str) -> dict[str, Any]:
        """Assess only a reviewed contract for the launcher's immutable task."""
        selected = self._reviewed(task_id)
        return self._assess_selected(
            selected["family_id"], selected["artifact_id"], selected["claim"],
            task_id=task_id, task_review=selected["review_contract_sha256"],
        )

    def _addressed(self, family_id: str, bindings: dict[str, Any], claim: str,
                   assessment_id: str, *, task_id: str | None = None,
                   task_review: str | None = None) -> str:
        artifact_id = self._selected(family_id, bindings, claim)
        if not isinstance(assessment_id, str) or not 1 <= len(assessment_id) <= 256:
            raise ValueError("Assessment ID must be a nonempty bounded string")
        try:
            issued = self.families.artifacts.service.store.get(
                self._issue_key(family_id, artifact_id, claim, assessment_id),
                kind="family_issuance",
            )
        except KeyError as exc:
            raise ValueError("Assessment was not issued for this caller and family claim") from exc
        packet = self.families.artifacts.finish_claim(artifact_id, assessment_id, claim)
        if issued != {
            "principal": self.principal, "family_id": family_id,
            "artifact_id": artifact_id, "claim": claim,
            "assessment_id": assessment_id, "packet_digest": canonical_digest(packet),
            "task_id": task_id, "task_review": task_review,
        }:
            raise ValueError("Issued assessment differs from its reviewed task or host packet")
        return artifact_id

    def explain(self, family_id: str, bindings: dict[str, Any], claim: str,
                assessment_id: str) -> dict[str, Any]:
        """Retrieve the claim's checked direct trace after the same grant check."""
        if self.applicability is not None:
            raise ValueError("Reviewed task route requires explain_task")
        artifact_id = self._addressed(family_id, bindings, claim, assessment_id)
        return self.families.artifacts.explain_claim(artifact_id, assessment_id, claim)

    def finish(self, family_id: str, bindings: dict[str, Any], claim: str,
               assessment_id: str) -> dict[str, Any]:
        """Return the checked status; recipient wording cannot change it."""
        if self.applicability is not None:
            raise ValueError("Reviewed task route requires finish_task")
        artifact_id = self._addressed(family_id, bindings, claim, assessment_id)
        return self.families.artifacts.finish_claim(artifact_id, assessment_id, claim)

    def explain_task(self, task_id: str, assessment_id: str) -> dict[str, Any]:
        selected = self._reviewed(task_id)
        artifact_id = self._addressed(
            selected["family_id"], selected["bindings"], selected["claim"],
            assessment_id, task_id=task_id,
            task_review=selected["review_contract_sha256"],
        )
        return self.families.artifacts.explain_claim(
            artifact_id, assessment_id, selected["claim"])

    def finish_task(self, task_id: str, assessment_id: str) -> dict[str, Any]:
        """Recover the historical checked packet under the same reviewed task."""
        selected = self._reviewed(task_id)
        artifact_id = self._addressed(
            selected["family_id"], selected["bindings"], selected["claim"],
            assessment_id, task_id=task_id,
            task_review=selected["review_contract_sha256"],
        )
        return self.families.artifacts.finish_claim(
            artifact_id, assessment_id, selected["claim"])
