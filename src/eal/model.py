"""Typed intermediate representation, independent of ANTLR and execution adapters."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Predicate:
    path: str
    operator: str
    expected: Any


@dataclass(frozen=True)
class Environment:
    name: str
    predicates: tuple[Predicate, ...]


@dataclass(frozen=True)
class Tool:
    name: str
    version: str
    mode: str


@dataclass(frozen=True)
class Evidence:
    name: str
    tool: str
    kind: str
    environment: str
    max_age: float
    input: Any
    predicates: tuple[Predicate, ...]


@dataclass(frozen=True)
class Assumption:
    name: str
    statement: str
    environment: str
    validation: str
    valid_from: str | None = None
    valid_until: str | None = None


@dataclass(frozen=True)
class Reasoning:
    name: str
    mode: str
    rationale: str
    backing: tuple[str, ...]
    predicates: tuple[Predicate, ...]


@dataclass(frozen=True)
class Claim:
    name: str
    statement: str
    environment: str


@dataclass(frozen=True)
class Argument:
    name: str
    conclusion: str
    reasoning: str
    evidence: tuple[str, ...]
    assumptions: tuple[str, ...]
    premises: tuple[str, ...]


@dataclass(frozen=True)
class Objection:
    name: str
    target_kind: str
    target: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    declaration: str | None = None


@dataclass(frozen=True)
class Program:
    language: str
    source_digest: str
    environments: dict[str, Environment] = field(default_factory=dict)
    tools: dict[str, Tool] = field(default_factory=dict)
    evidence: dict[str, Evidence] = field(default_factory=dict)
    assumptions: dict[str, Assumption] = field(default_factory=dict)
    reasoning: dict[str, Reasoning] = field(default_factory=dict)
    claims: dict[str, Claim] = field(default_factory=dict)
    arguments: dict[str, Argument] = field(default_factory=dict)
    objections: dict[str, Objection] = field(default_factory=dict)
    duplicates: tuple[str, ...] = ()
    declaration_count: int = 0
