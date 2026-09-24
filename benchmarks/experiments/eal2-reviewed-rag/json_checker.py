"""Reviewed-task gate for the independent, hand-authored JSON graph checker.

The executable graph semantics live in ``benchmarks.equal_checker`` and do not
import EAL. This adapter binds a launcher's exact question, task and grants to
one frozen graph. It refuses a recipient status when any record in the claim's
complete graph is missing, stale, wrongly scoped or structurally incomplete,
including records for currently inactive objections and their answers.

The cross-model fixtures are developmental and await independent human review.
A matching digest detects drift; it does not authenticate a reviewer or a tool.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Collection, Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from benchmarks import equal_checker


GRAPH_DIR = Path(__file__).resolve().parents[2] / "equal_checker_graphs"
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z", re.ASCII)


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _finite_number(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


def _same_type(actual: Any, expected: Any) -> bool:
    if _finite_number(actual) is not None and _finite_number(expected) is not None:
        return True
    return type(actual) is type(expected)


def _grants(values: Collection[str]) -> frozenset[str]:
    if (not isinstance(values, (set, frozenset, list, tuple)) or len(values) > 512
            or any(not isinstance(value, str) or not _IDENTIFIER.fullmatch(value)
                   for value in values)):
        raise ValueError("Grants must contain at most 512 exact task identifiers")
    return frozenset(values)


def _paths(graph: Mapping[str, Any]):
    for route in graph["routes"]:
        yield from route["all"]
    for objection in graph.get("objections", []):
        yield from objection["when"]
        for answer in objection.get("answers", []):
            yield from answer["all"]


def _malformed_predicate(record: Mapping[str, Any], predicate: Mapping[str, Any]) -> str | None:
    """Distinguish a valid negative observation from a missing or wrong type.

    The base checker evaluates the truth of predicates. Missing fields would
    otherwise be represented as a negative finding, which is insufficient for
    the current claim-scoped host's complete-collection contract.
    """
    op = predicate["op"]
    if op == "affine_at_most":
        value = record.get("value")
        intervention = value.get("intervention") if isinstance(value, dict) else None
        variables = value.get("variables") if isinstance(value, dict) else None
        outcome = value.get("outcome") if isinstance(value, dict) else None
        equation = variables.get(predicate["outcome"]) if isinstance(variables, dict) else None
        coefficients = equation.get("coefficients") if isinstance(equation, dict) else None
        if (not isinstance(intervention, dict)
                or intervention.get("variable") != predicate["intervention"]["variable"]
                or _finite_number(intervention.get("value")) is None
                or _finite_number(intervention["value"]) != _finite_number(predicate["intervention"]["value"])
                or outcome != predicate["outcome"]
                or not isinstance(coefficients, dict)
                or _finite_number(coefficients.get(intervention["variable"])) is None
                or _finite_number(equation.get("intercept")) is None
                or _finite_number(equation.get("noise")) is None):
            return "incomplete affine model or intervention identity"
        return None
    value: Any = record
    for key in predicate["path"]:
        if not isinstance(value, dict) or key not in value:
            return "missing field " + ".".join(predicate["path"])
        value = value[key]
    if op == "eq" and not _same_type(value, predicate["value"]):
        return "wrong value type at " + ".".join(predicate["path"])
    if op == "is_true" and type(value) is not bool:
        return "expected a boolean at " + ".".join(predicate["path"])
    if op in {"lte", "gte"} and _finite_number(value) is None:
        return "expected a finite number at " + ".".join(predicate["path"])
    if op == "has_keys_equal":
        keys = predicate["keys"]
        if not isinstance(value, dict) or any(
            key not in value or not _same_type(value[key], expected)
            for key, expected in keys.items()
        ):
            return "missing key or wrong value type at " + ".".join(predicate["path"])
    return None


class JsonReviewedChecker:
    """A launcher-bound comparator; the recipient has no task-selection method.

    ``reviewed_question`` and grants must come from the operator's frozen task
    catalogue. ``trusted_question`` is the unchanged task text received by the
    launcher. Supplying both from a model defeats the applicability gate.
    """

    def __init__(self, graph: Mapping[str, Any], *, task_id: str,
                 reviewed_question: str, trusted_question: str,
                 family_id: str, artifact_id: str, claim: str,
                 context: Mapping[str, Any], assessment_time: str,
                 authorised_tasks: Collection[str], authorised_families: Collection[str],
                 authorised_artifacts: Collection[str], authorised_claims: Collection[str]):
        # Copy the graph so subsequent caller mutation cannot change the check.
        self.graph = json.loads(json.dumps(graph, allow_nan=False))
        equal_checker.validate_graph(self.graph)
        self.task_id = task_id
        self.reviewed_question = reviewed_question
        self.trusted_question = trusted_question
        self.family_id = family_id
        self.artifact_id = artifact_id
        self.claim = claim
        self.context = dict(context)
        self.assessment_time = assessment_time
        self.authorised_tasks = _grants(authorised_tasks)
        self.authorised_families = _grants(authorised_families)
        self.authorised_artifacts = _grants(authorised_artifacts)
        self.authorised_claims = _grants(authorised_claims)
        self.graph_id = self.graph["id"]
        self.graph_sha256 = _canonical_sha256(self.graph)
        self.contract_sha256 = _canonical_sha256({
            "schema": "json-reviewed-task/1", "task_id": task_id,
            "question": reviewed_question, "family_id": family_id,
            "artifact_id": artifact_id, "claim": claim,
            "context": self.context, "assessment_time": assessment_time,
            "graph_sha256": self.graph_sha256,
        })

    @classmethod
    def from_root(cls, root: Mapping[str, Any], *, trusted_question: str,
                  authorised_tasks: Collection[str],
                  authorised_families: Collection[str],
                  authorised_artifacts: Collection[str],
                  authorised_claims: Collection[str],
                  graph_dir: Path = GRAPH_DIR) -> "JsonReviewedChecker":
        """Bind a frozen cross-model fixture to its separately authored graph."""
        root_id = root["id"]
        if root.get("graph") != f"benchmarks/equal_checker_graphs/{root_id}.json":
            raise ValueError("Frozen root graph path differs from the selected task")
        graph = equal_checker.graph_for_root(root_id, Path(graph_dir))
        return cls(graph, task_id=root_id, reviewed_question=root["brief"],
                   trusted_question=trusted_question, family_id=root_id,
                   artifact_id=root_id, claim=root["claim"],
                   context=root["context"], assessment_time=root["now"],
                   authorised_tasks=authorised_tasks,
                   authorised_families=authorised_families,
                   authorised_artifacts=authorised_artifacts,
                   authorised_claims=authorised_claims)

    def _refuse(self, reason: str, trace: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"status": "refused", "reason": reason, "claim": self.claim,
                "task_id": self.task_id, "graph_id": self.graph_id,
                "graph_sha256": self.graph_sha256,
                "contract_sha256": self.contract_sha256,
                "trace": trace or {"refusal": reason}}

    def _gate(self, now: str) -> str | None:
        if (not isinstance(self.trusted_question, str)
                or self.trusted_question != self.reviewed_question
                or not self.trusted_question.strip()
                or len(self.trusted_question.encode("utf-8")) > 4096):
            return "The launcher's exact question has no reviewed task contract"
        if any(not isinstance(value, str) or not _IDENTIFIER.fullmatch(value) for value in
               (self.task_id, self.family_id, self.artifact_id, self.claim)):
            return "Incomplete task identity"
        if (self.task_id not in self.authorised_tasks
                or self.family_id not in self.authorised_families
                or self.artifact_id not in self.authorised_artifacts
                or self.claim not in self.authorised_claims):
            return "The selected task, family, artefact or claim is not granted"
        try:
            graph_sha256 = _canonical_sha256(self.graph)
        except (TypeError, ValueError):
            return "Pinned argument graph is no longer valid JSON"
        if graph_sha256 != self.graph_sha256:
            return "Pinned argument graph changed during assessment"
        scope = {key: value["equals"] for key, value in self.graph["scope"].items()}
        if (self.graph["id"] != self.task_id or self.graph["claim"] != self.claim
                or not equal_checker._strict_equal(scope, self.context)):
            return "Graph claim or context differs from the task contract"
        if now != self.assessment_time:
            return "Assessment time differs from the pinned task"
        return None

    def assess_bound(self, records: Mapping[str, Any], now: str) -> dict[str, Any]:
        """Assess the bound task; no model-provided question or task ID is used."""
        refused = self._gate(now)
        if refused is not None:
            return self._refuse(refused)
        if not isinstance(records, Mapping):
            return self._refuse("No structured acquisition records")
        if any(not isinstance(key, str) for key in records):
            return self._refuse("Acquisition record IDs must be strings")
        if set(records) != set(self.graph["evidence"]):
            missing = set(self.graph["evidence"]) - set(records)
            extra = set(records) - set(self.graph["evidence"])
            unresolved = ([{"record": key, "reason": "missing"} for key in sorted(missing)]
                          + [{"record": str(key), "reason": "unexpected"}
                             for key in sorted(extra, key=str)])
            return self._refuse("Acquisition records differ from the selected claim graph",
                                {"unresolved_evidence": unresolved})
        result = equal_checker.evaluate(self.graph, records, now)
        rejected = [item for item in result.trace["evidence"] if not item["ok"]]
        if rejected:
            return self._refuse("Required evidence is missing, stale or mismatched",
                                {"unresolved_evidence": rejected})
        malformed = []
        for predicate in _paths(self.graph):
            error = _malformed_predicate(records[predicate["record"]], predicate)
            if error is not None:
                malformed.append({"record": predicate["record"], "reason": error})
        if malformed:
            return self._refuse("Required evidence has an incomplete predicate field",
                                {"unresolved_evidence": malformed})
        return {"status": result.status, "reason": result.trace["reason"],
                "claim": self.claim, "task_id": self.task_id,
                "graph_id": self.graph["id"],
                "graph_sha256": self.graph_sha256,
                "contract_sha256": self.contract_sha256,
                "trace": result.trace}
