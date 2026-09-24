"""Exact, reviewed task-to-family applicability contracts.

A retrieval candidate or model-generated family ID cannot authorise an
assessment. A trusted caller supplies the full original question. The host
finds its unique reviewed task under an explicit grant, binding and claim.
Paraphrases need their own review entry; a semantic match is never inferred.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Collection

from .evaluator import canonical_digest
from .families import FamilyRegistry, authorised_ids
from .semantics import parse_time


SCHEMA = "eal2-task-applicability/1"
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z", re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


class NoApplicableTask(ValueError):
    """No authorised reviewed contract covers the supplied exact question."""


class AmbiguousTask(ValueError):
    """More than one task contract claims the same exact question."""


@dataclass(frozen=True)
class ReviewedTask:
    question: str
    family_id: str
    bindings: dict[str, str | int | bool]
    claim: str
    reviewed_by: str
    reviewed_at: str
    review_contract_sha256: str


def _checked_question(question: str) -> None:
    if (not isinstance(question, str) or not question.strip()
            or not 1 <= len(question.encode("utf-8")) <= 4096):
        raise ValueError("Reviewed question must contain one to 4096 UTF-8 bytes")


def review_applicability_digest(families: FamilyRegistry, task_id: str, question: str,
                                family_id: str, bindings: dict[str, Any], claim: str) -> str:
    """Pin the exact question to one already reviewed family case and source.

    This detects a changed review contract; a deployment must authenticate the
    reviewer outside this checksum, as with FamilyRegistry's case review.
    """
    _checked_question(question)
    if not isinstance(task_id, str) or not _IDENTIFIER.fullmatch(task_id):
        raise ValueError("Task ID must be an EAL identifier")
    if not isinstance(family_id, str) or family_id not in families.families:
        raise ValueError("Task requires an existing family")
    if not isinstance(claim, str) or not _IDENTIFIER.fullmatch(claim):
        raise ValueError("Task requires one claim ID")
    family = families.families[family_id]
    # Exact reviewed case resolution enforces the finite typed binding domain,
    # context scope and current source digest before calculating the task seal.
    all_artifacts = set(families.artifacts.definitions)
    selected = families.resolve(family_id, bindings, authorised_families={family_id},
                                authorised_artifacts=all_artifacts)
    if claim not in selected["claims"]:
        raise ValueError("Task claim is absent from its reviewed family case")
    case = next(row for row in family.cases if row.bindings == bindings
                and row.artifact_id == selected["artifact_id"])
    artifact = families.artifacts.definitions[selected["artifact_id"]]
    return canonical_digest({
        "schema": SCHEMA, "task_id": task_id, "question": question,
        "family_id": family_id, "bindings": bindings, "claim": claim,
        "family_case_review_contract_sha256": case.review_contract_sha256,
        "artifact_id": selected["artifact_id"], "source_sha256": artifact.sha256,
        "method_registry_fingerprint": artifact.method_registry_fingerprint,
    })


class TaskApplicabilityRegistry:
    def __init__(self, families: FamilyRegistry, tasks: dict[str, ReviewedTask]):
        self.families = families
        self.tasks = dict(tasks)

    @classmethod
    def load(cls, families: FamilyRegistry, path: str | Path) -> "TaskApplicabilityRegistry":
        with Path(path).open("rb") as stream:
            document = tomllib.load(stream)
        if (set(document) != {"schema", "tasks"} or document["schema"] != SCHEMA
                or not isinstance(document["tasks"], dict)
                or not 1 <= len(document["tasks"]) <= 512):
            raise ValueError("Expected a bounded eal2-task-applicability/1 catalogue")
        tasks = {}
        questions: set[str] = set()
        fields = {"question", "family_id", "bindings", "claim", "reviewed_by",
                  "reviewed_at", "review_contract_sha256"}
        for task_id, entry in document["tasks"].items():
            if (not _IDENTIFIER.fullmatch(task_id) or not isinstance(entry, dict)
                    or set(entry) != fields):
                raise ValueError("Task entry requires an EAL ID and exact review fields")
            question = entry["question"]
            _checked_question(question)
            if question in questions:
                raise AmbiguousTask("Duplicate exact question has multiple task contracts")
            questions.add(question)
            if (not isinstance(entry["bindings"], dict)
                    or not isinstance(entry["reviewed_by"], str)
                    or not entry["reviewed_by"].strip()
                    or len(entry["reviewed_by"].encode("utf-8")) > 128
                    or not isinstance(entry["reviewed_at"], str)
                    or not isinstance(entry["review_contract_sha256"], str)
                    or not _SHA256.fullmatch(entry["review_contract_sha256"])):
                raise ValueError("Task entry requires typed bindings and bounded review metadata")
            parse_time(entry["reviewed_at"])
            digest = review_applicability_digest(families, task_id, question,
                                                  entry["family_id"], entry["bindings"],
                                                  entry["claim"])
            if entry["review_contract_sha256"] != digest:
                raise ValueError(f"Task {task_id!r} review contract differs from its question or case")
            tasks[task_id] = ReviewedTask(question, entry["family_id"],
                                          dict(entry["bindings"]), entry["claim"],
                                          entry["reviewed_by"], entry["reviewed_at"], digest)
        return cls(families, tasks)

    def resolve(self, question: str, *, task_id: str,
                authorised_tasks: Collection[str], authorised_families: Collection[str],
                authorised_artifacts: Collection[str]) -> dict[str, Any]:
        """Resolve a reviewed exact question; abstain on absence or drift.

        The task ID and question must come from the trusted application path.
        Calling this with a model's proposal alone does not establish that the
        user's task was accurately represented.
        """
        _checked_question(question)
        if (not isinstance(task_id, str) or task_id not in authorised_ids(authorised_tasks)
                or task_id not in self.tasks or self.tasks[task_id].question != question):
            raise NoApplicableTask("No authorised task covers this exact question")
        task = self.tasks[task_id]
        digest = review_applicability_digest(self.families, task_id, question, task.family_id,
                                              task.bindings, task.claim)
        if digest != task.review_contract_sha256:
            raise NoApplicableTask("Reviewed task contract changed")
        selected = self.families.resolve(task.family_id, task.bindings,
                                         authorised_families=authorised_families,
                                         authorised_artifacts=authorised_artifacts)
        if task.claim not in selected["claims"]:
            raise NoApplicableTask("Reviewed task claim is unavailable")
        return {"task_id": task_id, "family_id": task.family_id,
                "bindings": dict(task.bindings), "artifact_id": selected["artifact_id"],
                "claim": task.claim, "review_contract_sha256": task.review_contract_sha256}

    def resolve_bound(self, question: str, *, authorised_tasks: Collection[str],
                      authorised_families: Collection[str],
                      authorised_artifacts: Collection[str]) -> dict[str, Any]:
        """Select only the unique reviewed contract for the trusted original text.

        Candidate retrieval does not enter this decision. A duplicated exact
        question is ambiguous even if only one of its task IDs was granted.
        The ordinary resolver then checks the task and downstream grants and
        rechecks the reviewed source and case before the host collects anything.
        """
        _checked_question(question)
        matches = [task_id for task_id, task in self.tasks.items()
                   if task.question == question]
        if not matches:
            raise NoApplicableTask("No reviewed task covers this exact question")
        if len(matches) != 1:
            raise AmbiguousTask("Multiple task contracts cover this exact question")
        return self.resolve(question, task_id=matches[0],
                            authorised_tasks=authorised_tasks,
                            authorised_families=authorised_families,
                            authorised_artifacts=authorised_artifacts)
