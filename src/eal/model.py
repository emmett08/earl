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
    method: str
    rationale: str
    backing: tuple[str, ...]
    predicates: tuple[Predicate, ...]


@dataclass(frozen=True)
class Proposition:
    subject: str
    quantity: str
    unit: str
    scope: str
    valid_from: str
    valid_until: str
    result: Predicate
    query: Any


@dataclass(frozen=True)
class Claim:
    name: str
    statement: str
    environment: str
    proposition: Proposition | None = None


@dataclass(frozen=True)
class ArgumentOrigin:
    """Authored pattern and application that produced a lowered argument."""

    pattern: str
    application: str


@dataclass(frozen=True)
class Argument:
    name: str
    conclusion: str
    reasoning: str
    evidence: tuple[str, ...]
    assumptions: tuple[str, ...]
    premises: tuple[str, ...]
    binding: str | None = None
    origin: ArgumentOrigin | None = None


@dataclass(frozen=True)
class PatternParameter:
    name: str
    kind: str


@dataclass(frozen=True)
class Pattern:
    """One closed argument template; references name typed parameters only."""

    name: str
    parameters: tuple[PatternParameter, ...]
    conclusion: str
    reasoning: str
    evidence: tuple[str, ...]
    assumptions: tuple[str, ...]
    premises: tuple[str, ...]
    binding: str | None = None


@dataclass(frozen=True)
class PatternBinding:
    name: str
    reference: str


@dataclass(frozen=True)
class Application:
    name: str
    pattern: str
    arguments: tuple[PatternBinding, ...]


@dataclass(frozen=True)
class Objection:
    name: str
    target_kind: str
    target: str
    evidence: tuple[str, ...]
    premises: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceSpan:
    """One-based source positions; the end position is exclusive."""

    line: int
    column: int
    end_line: int
    end_column: int


@dataclass(frozen=True)
class ArgumentationDirective:
    """Reviewed EAL argumentation directive, never inferred from prose.

    ``other`` is the target claim of a directed contrary; ``rank`` is an
    integer from 0 through 1000. Exactly one is set when applicable.
    """

    kind: str
    name: str
    other: str | None
    rank: int | None
    review: str
    span: SourceSpan


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    declaration: str | None = None
    span: SourceSpan | None = None
    expected: str | None = None
    actual: str | None = None


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
    patterns: dict[str, Pattern] = field(default_factory=dict)
    applications: dict[str, Application] = field(default_factory=dict)
    argumentation_directives: tuple[ArgumentationDirective, ...] = ()
    duplicates: tuple[str, ...] = ()
    declaration_count: int = 0
    locations: dict[str, SourceSpan] = field(default_factory=dict)
    lowering_diagnostics: tuple[Diagnostic, ...] = ()
