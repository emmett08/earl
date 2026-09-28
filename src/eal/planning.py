"""Plan the evidence needed to assess a claim's complete argument graph.

Planning reads a validated EAL/2 programme. It has no collection, storage or
reasoning effects: the host decides how to execute the selected requests.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .model import Program
from .semantics import objection_scopes


@dataclass(frozen=True)
class ClaimClosure:
    """Declarations which may affect a claim under the authored calculus."""

    claims: frozenset[str]
    arguments: frozenset[str]
    objections: frozenset[str]
    evidence: frozenset[str]
    assumptions: frozenset[str]
    reasoning: frozenset[str]


@dataclass(frozen=True)
class PlannedCall:
    """A declared acquisition request before its host binding is resolved."""

    evidence_id: str
    tool: str
    tool_version: str
    evidence_kind: str
    environment: str


@dataclass(frozen=True)
class EvidencePlan:
    """Complete claim dependencies and collection requests in source order."""

    claim: str
    closure: ClaimClosure
    calls: tuple[PlannedCall, ...]

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(call.evidence_id for call in self.calls)

    @property
    def estimated_calls(self) -> int:
        """Maximum collector invocations without host-approved reuse."""
        return len(self.calls)


class EvidencePlanner:
    """Indexed traversal of support, attack and defence dependencies.

    Every alternative derivation is included. Objection premise claims enter
    the same claim worklist, and objections to objections are followed to a
    fixed point. Scope checks match the authored dialectic. The programme
    must already have passed semantic validation before this planner is used.
    """

    def __init__(self, program: Program):
        self.program = program
        by_conclusion: dict[str, list[str]] = {}
        for name, argument in program.arguments.items():
            by_conclusion.setdefault(argument.conclusion, []).append(name)
        self._by_conclusion = by_conclusion
        by_target: dict[tuple[str, str], list[str]] = {}
        for name, objection in program.objections.items():
            by_target.setdefault((objection.target_kind, objection.target), []).append(name)
        self._by_target = by_target
        self._scopes = objection_scopes(program)

    def plan(self, target: str) -> EvidencePlan:
        if target not in self.program.claims:
            raise ValueError(f"Unknown claim {target!r}")

        program = self.program
        claims: set[str] = set()
        arguments: set[str] = set()
        objections: set[str] = set()
        evidence: set[str] = set()
        assumptions: set[str] = set()
        reasoning: set[str] = set()
        pending = deque([("claim", target)])

        def attacks(kind: str, identifier: str, environment: str) -> None:
            for objection_id in self._by_target.get((kind, identifier), ()):
                if self._scopes[objection_id] == {environment}:
                    pending.append(("objection", objection_id))

        while pending:
            kind, name = pending.popleft()
            if kind == "claim":
                if name in claims:
                    continue
                claims.add(name)
                environment = program.claims[name].environment
                pending.extend(("argument", item) for item in self._by_conclusion.get(name, ()))
                attacks("claim", name, environment)
            elif kind == "argument":
                if name in arguments:
                    continue
                arguments.add(name)
                argument = program.arguments[name]
                environment = program.claims[argument.conclusion].environment
                evidence.update(argument.evidence)
                reasoning.add(argument.reasoning)
                evidence.update(program.reasoning[argument.reasoning].backing)
                assumptions.update(argument.assumptions)
                evidence.update(program.assumptions[item].validation for item in argument.assumptions)
                pending.extend(("claim", item) for item in argument.premises)
                attacks("argument", name, environment)
                attacks("reasoning", argument.reasoning, environment)
                for item in argument.assumptions:
                    attacks("assumption", item, environment)
            else:
                if name in objections:
                    continue
                objections.add(name)
                objection = program.objections[name]
                evidence.update(objection.evidence)
                pending.extend(("claim", item) for item in objection.premises)
                attacks("objection", name, next(iter(self._scopes[name])))

        closure = ClaimClosure(*(frozenset(group) for group in
                                 (claims, arguments, objections, evidence, assumptions, reasoning)))
        calls = tuple(PlannedCall(name, program.evidence[name].tool,
                                  program.tools[program.evidence[name].tool].version,
                                  program.evidence[name].kind, program.evidence[name].environment)
                      for name in program.evidence if name in evidence)
        return EvidencePlan(target, closure, calls)
