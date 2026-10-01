"""Developer-facing EAL knowledge base and prompt adapter.

The application chooses a registered entry and claim. The host selects the
source, reuses eligible observations, runs missing collectors, evaluates the
declared method and produces a bounded packet. A text model receives that
packet as context, without needing EAL parsing, tool use or model reasoning.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from .catalogue import WorkspaceKnowledgeCatalogue
from .registered_assessment import RegisteredAssessmentHost
from .runtime import ReasoningService
from .model_context import CONTEXT_INSTRUCTION, ModelContextBuilder


class EALKnowledgeBase:
    """Compose the persistent catalogue and assessment path for an application."""

    def __init__(self, workspace: str | Path, registry_path: str | Path | None = None,
                 database_path: str | Path | None = None, *, method_registry: Any = None, limits=None):
        self.service = ReasoningService(
            workspace, registry_path, database_path, method_registry=method_registry, limits=limits,
        )
        self.catalogue = WorkspaceKnowledgeCatalogue(self.service)
        self.host = RegisteredAssessmentHost(self.service, self.catalogue)

    def register(self, path: str, *, entry_id: str | None = None,
                 context: dict[str, Any] | None = None,
                 claims: list[str] | tuple[str, ...] | None = None,
                 label: str | None = None) -> dict[str, Any]:
        return self.catalogue.register(
            path, entry_id=entry_id, context=context, claims=claims, label=label,
        )

    def register_tree(self, directory: str = ".", *, context: dict[str, Any] | None = None,
                      limit: int = 512) -> dict[str, Any]:
        return self.catalogue.register_tree(directory, context=context, limit=limit)

    def sources(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return self.catalogue.list(limit=limit, offset=offset)

    def find(self, query: str | None = None, *, claim: str | None = None,
             context: dict[str, Any] | None = None, path: str | None = None,
             limit: int = 50) -> list[dict[str, Any]]:
        return self.catalogue.find(query, claim=claim, context=context, path=path, limit=limit)

    def assess(self, entry_id: str, claim: str, *, context: dict | None = None,
               now: str | None = None,
               reuse: Literal["compatible", "fresh"] = "compatible") -> dict[str, Any]:
        return self.host.assess(entry_id, claim, context=context, now=now, reuse=reuse)

    def history(self, entry_id: str, *, source_digest: str | None = None,
                limit: int = 50) -> dict[str, Any]:
        return self.host.history(entry_id, source_digest=source_digest, limit=limit)

    def explain(self, assessment_id: str, claim: str | None = None) -> dict[str, Any]:
        return self.service.explain(assessment_id, claim)


class ModelContextAdapter:
    """Build a checked prompt context for a model with no tool or reasoning API.

    The caller selects a claim by exact ID; free-form questions do not choose
    sources or change an assessment's status. The host's returned assessment
    remains the authoritative result if a model paraphrases it incorrectly.
    """

    def __init__(self, knowledge: EALKnowledgeBase):
        self.knowledge = knowledge

    def prepare(self, question: str, entry_id: str, claim: str, *,
                context: dict | None = None, now: str | None = None,
                reuse: Literal["compatible", "fresh"] = "compatible") -> dict[str, Any]:
        if not isinstance(question, str) or not question.strip() or len(question.encode("utf-8")) > 8192:
            raise ValueError("question must contain one to 8192 UTF-8 bytes")
        assessment = self.knowledge.assess(
            entry_id, claim, context=context, now=now, reuse=reuse,
        )
        host_context = ModelContextBuilder().build(assessment)
        return {
            "schema": "EAL/model-context/2", "assessment": assessment,
            "context": host_context,
            "messages": [
                {"role": "system", "content": (
                    CONTEXT_INSTRUCTION
                    + json.dumps(host_context, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":"), allow_nan=False)
                )},
                {"role": "user", "content": question},
            ],
        }
