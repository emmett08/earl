"""Reviewed finite task families over operator-pinned EAL artefacts.

An instance binds typed parameters to an exact, reviewed artefact. No source
text or context is templated at request time. A new tuple needs another
reviewed instance, including a new source when its claim scope changes.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Collection

from .artifacts import Artifact, ArtifactRegistry
from .evaluator import canonical_digest
from .parser import parse
from .semantics import parse_time


SCHEMA = "eal2-task-families/1"
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z", re.ASCII)
_PATH = re.compile(r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*\Z", re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


@dataclass(frozen=True)
class Parameter:
    kind: str
    values: tuple[str | int | bool, ...]


@dataclass(frozen=True)
class ReviewedCase:
    bindings: dict[str, str | int | bool]
    artifact_id: str
    claims: tuple[str, ...]
    reviewed_by: str
    reviewed_at: str
    review_contract_sha256: str


@dataclass(frozen=True)
class TaskFamily:
    description: str
    terms: tuple[str, ...]
    parameters: dict[str, Parameter]
    context_paths: dict[str, str]
    cases: tuple[ReviewedCase, ...]


def _value_matches(value: Any, kind: str) -> bool:
    if kind == "string":
        return type(value) is str and 0 < len(value.encode("utf-8")) <= 256
    if kind == "integer":
        return type(value) is int and -(2**53 - 1) <= value <= 2**53 - 1
    return kind == "boolean" and type(value) is bool


def _at_path(context: dict[str, Any], path: str) -> Any:
    current: Any = context
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            raise ValueError(f"Registered context is missing path {path!r}")
        current = current[key]
    return current


def review_binding_digest(family_id: str, parameters: dict[str, Parameter],
                          context_paths: dict[str, str], bindings: dict[str, Any],
                          artifact_id: str, artifact: Artifact, claims: Collection[str]) -> str:
    """Digest the precise applicability contract presented to a reviewer.

    A checksum detects a changed contract; the host operator remains
    responsible for authenticating the human review decision.
    """
    return canonical_digest({
        "schema": SCHEMA, "family_id": family_id,
        "parameters": {key: {"type": value.kind, "values": list(value.values)}
                       for key, value in sorted(parameters.items())},
        "context_paths": context_paths, "bindings": bindings,
        "artifact_id": artifact_id, "path": artifact.path,
        "source_sha256": artifact.sha256, "assessment_time": artifact.now,
        "method_registry_fingerprint": artifact.method_registry_fingerprint,
        "context_sha256": canonical_digest(artifact.context),
        "claims": list(claims),
    })


def _parameters(raw: Any, family_id: str) -> dict[str, Parameter]:
    if not isinstance(raw, dict) or not 1 <= len(raw) <= 8:
        raise ValueError(f"Family {family_id!r} requires one to eight typed parameters")
    result = {}
    for name, specification in raw.items():
        if not isinstance(name, str) or not _IDENTIFIER.fullmatch(name):
            raise ValueError(f"Family {family_id!r} has an invalid parameter ID")
        if not isinstance(specification, dict) or set(specification) != {"type", "values"}:
            raise ValueError(f"Parameter {name!r} requires only type and values")
        kind, values = specification["type"], specification["values"]
        if kind not in {"string", "integer", "boolean"} or not isinstance(values, list) or not 1 <= len(values) <= 128:
            raise ValueError(f"Parameter {name!r} requires a finite typed value set")
        if any(not _value_matches(value, kind) for value in values):
            raise ValueError(f"Parameter {name!r} contains a value of the wrong type or size")
        if len({canonical_digest(value) for value in values}) != len(values):
            raise ValueError(f"Parameter {name!r} contains duplicate values")
        result[name] = Parameter(kind, tuple(values))
    return result


def _checked_bindings(bindings: Any, parameters: dict[str, Parameter]) -> dict[str, Any]:
    if not isinstance(bindings, dict) or set(bindings) != set(parameters):
        raise ValueError("Family bindings must name every parameter exactly once")
    for name, specification in parameters.items():
        value = bindings[name]
        if not _value_matches(value, specification.kind) or value not in specification.values:
            raise ValueError(f"Binding {name!r} is not an allowed typed value")
    return dict(bindings)


def authorised_ids(values: Collection[str]) -> set[str]:
    """Require a finite set of exact IDs, never substring permission checks."""
    if (not isinstance(values, (set, frozenset, list, tuple)) or len(values) > 512
            or any(not isinstance(value, str) or not _IDENTIFIER.fullmatch(value) for value in values)):
        raise ValueError("Permissions must be a bounded collection of exact IDs")
    return set(values)


class FamilyRegistry:
    """Map exact authorised bindings to checked artefact IDs and claims."""

    def __init__(self, artifacts: ArtifactRegistry, families: dict[str, TaskFamily]):
        self.artifacts = artifacts
        self.families = dict(families)

    @classmethod
    def load(cls, artifacts: ArtifactRegistry, path: str | Path) -> "FamilyRegistry":
        with Path(path).open("rb") as stream:
            document = tomllib.load(stream)
        if (set(document) != {"schema", "families"} or document["schema"] != SCHEMA
                or not isinstance(document["families"], dict)
                or not 1 <= len(document["families"]) <= 256):
            raise ValueError("Expected a nonempty eal2-task-families/1 catalogue")
        families = {}
        total_cases = 0
        for family_id, raw in document["families"].items():
            if not _IDENTIFIER.fullmatch(family_id) or not isinstance(raw, dict) or set(raw) != {
                "description", "terms", "parameters", "context_paths", "cases"
            }:
                raise ValueError(f"Invalid settings for family {family_id!r}")
            description, terms = raw["description"], raw["terms"]
            if (not isinstance(description, str) or not description.strip()
                    or len(description.encode("utf-8")) > 512 or not isinstance(terms, list)
                    or not 1 <= len(terms) <= 32 or any(not isinstance(term, str) or not term.strip()
                                                       or len(term.encode("utf-8")) > 64 for term in terms)):
                raise ValueError(f"Family {family_id!r} requires bounded retrieval metadata")
            parameters = _parameters(raw["parameters"], family_id)
            paths = raw["context_paths"]
            if (not isinstance(paths, dict) or set(paths) != set(parameters)
                    or any(not isinstance(p, str) or not _PATH.fullmatch(p) for p in paths.values())
                    or len(set(paths.values())) != len(paths)):
                raise ValueError(f"Family {family_id!r} must map each parameter to a distinct context path")
            rows = raw["cases"]
            if not isinstance(rows, list) or not 1 <= len(rows) <= 128:
                raise ValueError(f"Family {family_id!r} needs one to 128 reviewed cases")
            total_cases += len(rows)
            if total_cases > 512:
                raise ValueError("Family catalogue exceeds 512 reviewed cases")
            cases = []
            seen = set()
            for row in rows:
                if not isinstance(row, dict) or set(row) != {
                    "bindings", "artifact_id", "claims", "reviewed_by", "reviewed_at", "review_contract_sha256"
                }:
                    raise ValueError(f"Family {family_id!r} has an incomplete reviewed case")
                bindings = _checked_bindings(row["bindings"], parameters)
                key = canonical_digest(bindings)
                if key in seen:
                    raise ValueError(f"Family {family_id!r} has ambiguous duplicate bindings")
                seen.add(key)
                artifact_id = row["artifact_id"]
                claims = row["claims"]
                if (not isinstance(artifact_id, str) or artifact_id not in artifacts.definitions
                        or not isinstance(claims, list) or not 1 <= len(claims) <= 64
                        or any(not isinstance(claim, str) or not _IDENTIFIER.fullmatch(claim) for claim in claims)
                        or len(set(claims)) != len(claims)
                        or not set(claims) <= set(artifacts.definitions[artifact_id].claims)):
                    raise ValueError(f"Family {family_id!r} selects an unregistered artefact or claim")
                reviewer, reviewed_at, digest = (row["reviewed_by"], row["reviewed_at"],
                                                  row["review_contract_sha256"])
                if (not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 128
                        or not isinstance(reviewed_at, str) or not isinstance(digest, str)
                        or not _SHA256.fullmatch(digest)):
                    raise ValueError(f"Family {family_id!r} needs reviewer, time and contract digest")
                parse_time(reviewed_at)
                case = ReviewedCase(bindings, artifact_id, tuple(claims), reviewer, reviewed_at, digest)
                cls._check_case(artifacts, family_id, parameters, paths, case)
                cases.append(case)
            families[family_id] = TaskFamily(description, tuple(terms), parameters, dict(paths), tuple(cases))
        return cls(artifacts, families)

    @staticmethod
    def _check_case(artifacts: ArtifactRegistry, family_id: str, parameters: dict[str, Parameter],
                    paths: dict[str, str], case: ReviewedCase) -> None:
        artifact = artifacts.definitions[case.artifact_id]
        expected = review_binding_digest(family_id, parameters, paths, case.bindings,
                                         case.artifact_id, artifact, case.claims)
        if case.review_contract_sha256 != expected:
            raise ValueError(f"Family {family_id!r} review contract differs from its pinned artefact")
        program = parse(artifacts._source(case.artifact_id))
        for claim_id in case.claims:
            environment = program.environments[program.claims[claim_id].environment]
            for name, path in paths.items():
                value = case.bindings[name]
                actual = _at_path(artifact.context, path)
                if type(actual) is not type(value) or actual != value:
                    raise ValueError(f"Family {family_id!r} binding {name!r} differs from artefact context")
                if not any(predicate.path == path and predicate.operator == "=="
                           and type(predicate.expected) is type(value) and predicate.expected == value
                           for predicate in environment.predicates):
                    raise ValueError(f"Claim {claim_id!r} does not constrain family binding {name!r} in its environment")

    def resolve(self, family_id: str, bindings: dict[str, Any], *,
                authorised_families: Collection[str], authorised_artifacts: Collection[str]) -> dict[str, Any]:
        """Resolve one reviewed tuple; never choose by similarity or fill gaps."""
        if (not isinstance(family_id, str) or family_id not in authorised_ids(authorised_families)
                or family_id not in self.families):
            raise ValueError("Unknown or unauthorised family")
        family = self.families[family_id]
        values = _checked_bindings(bindings, family.parameters)
        case = next((row for row in family.cases if row.bindings == values), None)
        if case is None:
            raise ValueError("No reviewed case exists for these family bindings")
        if case.artifact_id not in authorised_ids(authorised_artifacts):
            raise ValueError("Family case selects an unauthorised artefact")
        self._check_case(self.artifacts, family_id, family.parameters, family.context_paths, case)
        return {"artifact_id": case.artifact_id, "claims": list(case.claims)}
