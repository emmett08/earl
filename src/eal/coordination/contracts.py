"""Closed task and trusted single-host server contracts for coordination.

These contracts select registered EAL arguments. The operator asserts the
correspondence between the question and selected claims; prose is not verified.
EAL's source language and assessment schemas retain their own versions.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any

from eal.evaluator import canonical_digest
from eal.server_settings import ServerSettings

TASK_SCHEMA = "EAL/MAS-coordination-task/3"
FINDING_SCHEMA = "EAL/MAS-coordination-finding/3"
MAX_CLAIMS = 16


def text(value: Any, name: str, maximum: int = 256) -> str:
    if (type(value) is not str or not value or value != value.strip()
            or len(value.encode("utf-8")) > maximum):
        raise ValueError(f"{name} requires nonempty bounded text without surrounding whitespace")
    return value


def json_object(value: Any, name: str, maximum: int = 65536) -> dict:
    """Validate finite JSON without conversion of Python-only types."""
    nodes = 0

    def visit(item, depth=0):
        nonlocal nodes
        nodes += 1
        if depth > 32 or nodes > 4096:
            raise ValueError(f"{name} exceeds structural bounds")
        if type(item) is dict:
            if any(type(key) is not str for key in item):
                raise ValueError(f"{name} requires string object keys")
            return {key: visit(child, depth + 1) for key, child in item.items()}
        if type(item) is list:
            return [visit(child, depth + 1) for child in item]
        if item is None or type(item) in (str, bool, int):
            return item
        if type(item) is float and math.isfinite(item):
            return item
        raise ValueError(f"{name} requires finite JSON values")

    if type(value) is not dict:
        raise ValueError(f"{name} requires a JSON object")
    result = visit(value)
    if len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")) > maximum:
        raise ValueError(f"{name} exceeds its byte bound")
    return result


def freeze(value):
    if type(value) is dict:
        return MappingProxyType({key: freeze(child) for key, child in value.items()})
    if type(value) is list:
        return tuple(freeze(child) for child in value)
    return value


def thaw(value):
    if isinstance(value, Mapping):
        return {key: thaw(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [thaw(child) for child in value]
    return value


@dataclass(frozen=True)
class ServerSpec:
    """Trusted configuration; workers cannot supply executables or overrides."""
    workspace: Path
    registry: Path | None = None
    database: Path | None = None
    methods: str | None = None
    limits: Path | None = None

    def __post_init__(self):
        for name in ("workspace", "registry", "database", "limits"):
            value = getattr(self, name)
            if value is None and name != "workspace":
                continue
            if not isinstance(value, (str, Path)):
                raise ValueError(f"{name} requires a filesystem path")
            if isinstance(value, str):
                text(value, name, 4096)
            object.__setattr__(self, name, Path(value).expanduser().resolve())
        # Resolve the default once rather than inheriting a later working dir.
        if self.database is None:
            object.__setattr__(self, "database", self.workspace / ".eal" / "runs.sqlite3")
        ServerSettings(workspace=self.workspace, registry=self.registry,
                       database=self.database, methods=self.methods, limits=self.limits)

    def to_dict(self):
        return {name: str(value) if isinstance(value, Path) else value
                for name in ("workspace", "registry", "database", "methods", "limits")
                for value in (getattr(self, name),)}

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != {"workspace", "registry", "database", "methods", "limits"}:
            raise ValueError("Server specification requires exactly its declared fields")
        if any(value[name] is not None and type(value[name]) is not str
               for name in ("workspace", "registry", "database", "methods", "limits")):
            raise ValueError("Server JSON paths and method factory require strings")
        return cls(**value)


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    question: str
    entry_id: str
    claims: tuple[str, ...]
    profile: str
    requirements: Mapping[str, Any]

    def __post_init__(self):
        for name, maximum in (("task_id", 128), ("question", 8192), ("entry_id", 256), ("profile", 128)):
            text(getattr(self, name), name, maximum)
        if (type(self.claims) is not tuple or not 1 <= len(self.claims) <= MAX_CLAIMS
                or any(type(claim) is not str for claim in self.claims)
                or len(set(self.claims)) != len(self.claims)):
            raise ValueError(f"claims require one to {MAX_CLAIMS} unique strings")
        for claim in self.claims:
            text(claim, "claim", 128)
        requirements = json_object(thaw(self.requirements) if isinstance(self.requirements, Mapping) else self.requirements,
                                   "requirements")
        from .profiles import validate_requirements
        validate_requirements(self.profile, self.claims, requirements)
        object.__setattr__(self, "requirements", freeze(requirements))

    def to_dict(self):
        return {"task_id": self.task_id, "question": self.question, "entry_id": self.entry_id,
                "claims": list(self.claims), "profile": self.profile, "requirements": thaw(self.requirements)}

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != {"task_id", "question", "entry_id", "claims", "profile", "requirements"}:
            raise ValueError("Task specification requires exactly its declared fields")
        if type(value["claims"]) is not list:
            raise ValueError("Task JSON claims require an array")
        return cls(**{**value, "claims": tuple(value["claims"])})


def validate_anchor(anchor):
    from eal.semantics import parse_time
    fields = {"schema", "task_digest", "task", "source_digest", "method_registry_fingerprint", "registered_context", "pinned_at"}
    if type(anchor) is not dict or set(anchor) != fields or anchor["schema"] != TASK_SCHEMA:
        raise ValueError("Task anchor requires the current closed schema")
    TaskSpec.from_dict(anchor["task"])
    json_object(anchor["registered_context"], "registered_context", 16384)
    for name in ("task_digest", "source_digest", "method_registry_fingerprint"):
        digest = anchor[name]
        if type(digest) is not str or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError(f"{name} requires a SHA-256 digest")
    parse_time(anchor["pinned_at"])
    if canonical_digest({key: value for key, value in anchor.items() if key != "task_digest"}) != anchor["task_digest"]:
        raise ValueError("Task anchor digest differs from its content")
    return TaskSpec.from_dict(anchor["task"])


def make_finding(anchor, check, assessments=None, packets=None, explanations=None, calls=None):
    validate_anchor(anchor)
    value = {"schema": FINDING_SCHEMA, "task_digest": anchor["task_digest"], "check": check,
             "assessments": assessments or {}, "packets": packets or {}, "explanations": explanations or {},
             "mcp": {"transport": "actual_mcp_stdio", "calls": calls or []},
             "collected_count": sum(row["collected_count"] for row in (assessments or {}).values()),
             "reused_count": sum(row["reused_count"] for row in (assessments or {}).values())}
    return {**value, "finding_id": "finding_" + canonical_digest(value)}
