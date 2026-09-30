"""Opt-in, bounded EAL/3-to-ASPIC+ translation at a checked observation snapshot.

This is a derived profile, not the default EAL evaluator.  It translates
authored argument routes and targeted objections, never prose, into rules of
``argumentation/aspic/1``.  EAL performs the observation and local
method checks first.  The returned source map preserves the checked origins of
every generated premise, rule and attack, including unavailable observations.

Strictness, directed claim contraries and ranks require explicit reviewed EAL
argumentation directives; none is inferred from English statements. Unannotated
fallible premises and rules receive the same rank.
The current ASPIC method bounds the theory to 64 rules/premises, eight
antecedents per rule and 128 constructed arguments; exceedance is an error.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass, field
import hashlib
from pathlib import Path

from . import aspic as aspic_module
from .aspic import ASPIC_CONTRACT, METHOD, _validate
from .evaluator import canonical_digest, evaluate
from .model import Program
from .parser import parse
from .semantics import objection_scopes

PROFILE = "EAL/3-compiled-aspic/4"
RANK = 500


class CompilationError(ValueError):
    """This snapshot cannot be represented by the bounded compiled profile."""


def _symbol(kind: str, name: str) -> str:
    # Stable under insertion/reordering of unrelated declarations.  The type
    # prefix keeps same-spelled EAL declarations in separate formal namespaces.
    return kind + hashlib.sha256(name.encode("utf-8")).hexdigest()[:20]


def _location(program: Program, name: str):
    span = program.locations.get(name)
    return asdict(span) if span is not None else None


def _backend_identity() -> dict:
    return {"method": ASPIC_CONTRACT.identifier,
            "contract_digest": canonical_digest(ASPIC_CONTRACT.describe()),
            "module_digest": hashlib.sha256(Path(aspic_module.__file__).read_bytes()).hexdigest()}


def _snapshot_digest(mapping: dict) -> str:
    return canonical_digest({
        **{key: mapping[key] for key in (
            "source_digest", "assessed_at", "context_fingerprint",
            "method_registry_fingerprint", "backend", "assessment_digest", "theory_digest")},
        "evidence_record_digests": {name: mapping["evidence"][name]["record_digest"]
                                    for name in sorted(mapping["evidence"])},
    })


@dataclass(frozen=True)
class CompiledTheory:
    """An independently solvable theory and its source-to-formal correspondence."""

    theory: dict
    source_map: dict
    assessment: dict
    _integrity: tuple[str, str, str] = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        # frozen=True protects attributes, not the dictionaries they contain.
        # Bind all provenance, including fields outside the snapshot digest,
        # so later caller edits cannot acquire the original source identity.
        object.__setattr__(self, "_integrity", tuple(canonical_digest(value)
                           for value in (self.theory, self.source_map, self.assessment)))

    def _checked_snapshot(self) -> tuple[dict, dict, dict]:
        try:
            theory, mapping, assessment = deepcopy((self.theory, self.source_map, self.assessment))
            digests = tuple(canonical_digest(value) for value in (theory, mapping, assessment))
            if digests != self._integrity:
                raise ValueError("compiled theory, assessment or source map was modified")
            if (mapping["profile"] != PROFILE or mapping["theory_digest"] != digests[0]
                    or mapping["assessment_digest"] != digests[2]
                    or mapping["snapshot_digest"] != _snapshot_digest(mapping)
                    or mapping["backend"] != _backend_identity()
                    or mapping["goal"]["atom"] != theory["goal"]
                    or mapping["claims"][mapping["goal"]["claim"]]["atom"] != theory["goal"]
                    or mapping["goal"]["claim"] not in assessment["claims"]
                    or any(mapping[key] != assessment[key] for key in (
                        "source_digest", "assessed_at", "context_fingerprint",
                        "method_registry_fingerprint"))):
                raise ValueError("compiled theory and provenance identities disagree")
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError, UnicodeError) as exc:
            raise CompilationError(f"Compiled snapshot integrity check failed: {exc}") from exc
        return theory, mapping, assessment

    def solve(self) -> dict:
        """Solve the compiled goal and project formal routes to EAL identities."""
        return self._solve_snapshot(*self._checked_snapshot())

    @staticmethod
    def _solve_snapshot(theory: dict, mapping: dict, assessment: dict) -> dict:
        from .methods import execute_extension

        # Use the same isolated POSIX worker, input/output schemas, memory
        # ceiling and execution timeout as the installed ASPIC method.
        computation = execute_extension(ASPIC_CONTRACT, {"theory": theory})
        if computation["status"] != "supported":
            raise CompilationError("Bounded ASPIC execution failed: " +
                                   "; ".join(computation["reasons"]))
        formal = computation["details"]
        by_rule: dict[str, list[str]] = {}
        for argument in formal["arguments"]:
            rule = argument.get("rule_id")
            if rule is not None:
                by_rule.setdefault(rule, []).append(argument["label"])
        routes = {}
        for name, origin in mapping["arguments"].items():
            labels = by_rule.get(origin["rule_id"], [])
            routes[name] = {"labels": labels,
                            "status": ("accepted" if "in" in labels else
                                       "undecided" if "undecided" in labels else
                                       "rejected" if labels else "unconstructed"),
                            "rule_id": origin["rule_id"],
                            "emitted": origin["emitted"]}
        status = formal["grounded_status"]
        scoped_status = assessment["claims"][mapping["goal"]["claim"]]["status"]
        return {"profile": PROFILE, "formal": formal, "routes": routes,
                "claim": mapping["goal"]["claim"],
                "claim_status": ("out_of_scope" if scoped_status == "out_of_scope" else
                                 "supported" if status == "accepted" else
                                 "contested" if status in ("rejected", "undecided") else
                                 "unsupported"),
                "source_map": mapping}

    def to_dict(self) -> dict:
        """Return the complete JSON-serialisable, opt-in compilation result."""
        theory, mapping, assessment = self._checked_snapshot()
        projected = self._solve_snapshot(theory, mapping, assessment)
        return {"profile": PROFILE, "theory": theory,
                "source_map": mapping,
                "diagnostics": [],
                "formal": projected["formal"],
                "routes": projected["routes"],
                "claim": projected["claim"],
                "claim_status": projected["claim_status"],
                "authored_claim_status": assessment["claims"][projected["claim"]]["status"],
                "source_digest": mapping["source_digest"],
                "snapshot_digest": mapping["snapshot_digest"]}


def compile_eal_aspic(source: str, records: Mapping[str, Mapping], *,
                      goal: str, now, context: Mapping,
                      registry=None,
                      binding_digests: Mapping[str, str | None] | None = None) -> CompiledTheory:
    """Parse and compile exact EAL/3 source bytes at one checked snapshot.

    The named goal is an EAL claim.  No records are collected here.  Method
    checks are taken from EAL's local assessment, while the EAL-composed graph
    remains available as ``assessment`` for differential inspection.  Method
    ``argumentation/aspic/1`` is deliberately excluded from this profile: a
    pre-authored formal theory cannot be silently reinterpreted as EAL routes.
    """
    # A Program's declaration maps are mutable while its source_digest is
    # fixed.  Accept text only, so source spans and the published source hash
    # always correspond to the declarations actually assessed and compiled.
    if not isinstance(source, str):
        raise TypeError("source must be EAL/3 text")
    program = parse(source)
    # These conservative declaration limits run before any local method
    # execution.  The final theory schema checks actual emitted cardinality.
    if len(program.evidence) > 64 or (len(program.arguments) +
                                      len(program.assumptions) +
                                      len(program.objections)) > 64:
        raise CompilationError("Compiled profile permits at most 64 evidence declarations "
                               "and 64 combined argument, assumption and objection rules")
    assessment = evaluate(program, records, now=now, context=context,
                          registry=registry, binding_digests=binding_digests)
    if not assessment["valid"]:
        raise CompilationError(f"EAL programme is invalid: {assessment['diagnostics']!r}")
    if goal not in program.claims:
        raise CompilationError(f"Unknown EAL goal claim {goal!r}")
    if any(program.reasoning[a.reasoning].method == METHOD for a in program.arguments.values()):
        raise CompilationError("Compile authored EAL routes, not an argumentation/aspic/1 theory")

    annotations = {(item.kind, item.name): item for item in program.argumentation_directives
                   if item.kind != "contrary"}
    target_kinds = {name: kind for kind, table in (
        ("evidence", program.evidence), ("assumption", program.assumptions),
        ("argument", program.arguments), ("objection", program.objections),
        ("claim", program.claims)) for name in table}

    def rank(name: str) -> int:
        item = annotations.get(("rank", name))
        return item.rank if item is not None else RANK

    def argumentation_directive(item):
        return {**asdict(item), "target_kind": target_kinds[item.name]}

    def annotated(kind: str, name: str):
        item = annotations.get((kind, name))
        return argumentation_directive(item) if item is not None else None

    claims = {name: _symbol("c", name) for name in program.claims}
    evidence = {name: _symbol("e", name) for name in program.evidence}
    assumptions = {name: _symbol("s", name) for name in program.assumptions}
    objections = {name: _symbol("o", name) for name in program.objections}
    premises: list[dict] = []
    rules: list[dict] = []
    contraries: list[dict] = []
    mapping = {"profile": PROFILE, "source_digest": program.source_digest,
               "assessed_at": assessment["assessed_at"],
               "context_fingerprint": assessment["context_fingerprint"],
               "method_registry_fingerprint": assessment["method_registry_fingerprint"],
               "backend": _backend_identity(),
               "goal": {"claim": goal, "atom": claims[goal]},
               "claims": {}, "evidence": {}, "assumptions": {},
               "arguments": {}, "objections": {}, "contraries": [],
               "formal_directives": [argumentation_directive(item) for item in program.argumentation_directives]}
    for name in sorted(claims):
        mapping["claims"][name] = {"atom": claims[name],
                                    "statement": program.claims[name].statement,
                                    "environment": program.claims[name].environment,
                                    "span": _location(program, name)}
    for name in sorted(evidence):
        verdict = assessment["evidence"][name]
        available = verdict["status"] == "available"
        supplied = records.get(name)
        try:
            record_digest = canonical_digest(supplied) if supplied is not None else None
        except (ValueError, TypeError, OverflowError, RecursionError, UnicodeError) as exc:
            raise CompilationError(f"Evidence {name!r} cannot be fingerprinted: {exc}") from exc
        record = records.get(name) if available else None
        if record is not None and not isinstance(record.get("tool_binding_digest"), str):
            raise CompilationError(f"Available evidence {name!r} lacks a binding digest")
        identity = ({"run_id": record["run_id"], "data_digest": record["data_digest"],
                     "request_digest": record["request_digest"],
                     "collected_at": record["collected_at"],
                     "tool_binding_digest": record["tool_binding_digest"]}
                    if record is not None else None)
        mapping["evidence"][name] = {"atom": evidence[name], "available": available,
                                      "identity": identity, "record_digest": record_digest,
                                      "reasons": verdict["reasons"],
                                      "availability_issues": verdict["availability_issues"],
                                      "rank": rank(name),
                                      "rank_annotation": annotated("rank", name),
                                      "span": _location(program, name)}
        if available:
            premises.append({"atom": evidence[name], "kind": "ordinary",
                             "rank": rank(name)})
    for name in sorted(assumptions):
        assumption = program.assumptions[name]
        # EAL marks a locally valid assumption ``contested`` only after the
        # composed objection pass.  Construct its provisional rule so ASPIC
        # can resolve that very objection, rather than erasing its target.
        supported = assessment["assumptions"][name]["status"] in ("supported", "contested")
        rule_id = _symbol("v", name)
        mapping["assumptions"][name] = {"atom": assumptions[name], "rule_id": rule_id,
                                         "applicability_atom": _symbol("x", rule_id),
                                         "validation": assumption.validation,
                                         "rank": rank(name),
                                         "rank_annotation": annotated("rank", name),
                                         "emitted": supported,
                                         "span": _location(program, name)}
        if supported:
            rules.append({"id": rule_id, "kind": "defeasible",
                          "antecedents": [evidence[assumption.validation]],
                          "consequent": assumptions[name],
                          "name": mapping["assumptions"][name]["applicability_atom"],
                          "rank": rank(name)})

    # EAL permits an objection supported by no evidence or premise.  A marked
    # structural axiom lets a defeasible authored objection use a rule with a
    # nonempty antecedent.  It is never presented as a measured observation.
    structural = _symbol("b", "compiler_basis")
    basis_needed = False
    for name in sorted(program.arguments):
        argument = program.arguments[name]
        method = program.reasoning[argument.reasoning]
        backing = tuple(method.backing)
        antecedents = list(dict.fromkeys(
            [*(evidence[e] for e in argument.evidence),
             *(evidence[e] for e in backing),
             *(assumptions[a] for a in argument.assumptions),
             *(claims[p] for p in argument.premises)]))
        eligible = assessment["arguments"][name]["locally_usable"]
        strict = ("strict", name) in annotations
        rule_id = _symbol("r", name)
        applicability = _symbol("x", rule_id)
        mapping["arguments"][name] = {"rule_id": rule_id,
                                        "applicability_atom": None if strict else applicability,
                                        "conclusion_atom": claims[argument.conclusion],
                                        "conclusion": argument.conclusion,
                                        "antecedents": antecedents,
                                        "emitted": eligible,
                                        "reasoning": argument.reasoning,
                                        "rationale": method.rationale,
                                        "rule_kind": "strict" if strict else "defeasible",
                                        "strict_annotation": annotated("strict", name),
                                        "rank": None if strict else rank(name),
                                        "rank_annotation": annotated("rank", name),
                                        "origin": asdict(argument.origin) if argument.origin else None,
                                        "span": _location(program, name)}
        if eligible:
            if not antecedents:
                antecedents = [structural]
                basis_needed = True
            rule = {"id": rule_id, "kind": "strict" if strict else "defeasible",
                    "antecedents": antecedents,
                    "consequent": claims[argument.conclusion]}
            if not strict:
                rule.update({"name": applicability, "rank": rank(name)})
            rules.append(rule)

    scopes = objection_scopes(program)
    for name in sorted(program.objections):
        objection = program.objections[name]
        scope = next(iter(scopes[name]))
        antecedents = list(dict.fromkeys(
            [*(evidence[e] for e in objection.evidence),
             *(claims[p] for p in objection.premises)]))
        eligible = (assessment["environments"][scope]["status"] == "matched"
                    and all(mapping["evidence"][e]["available"] for e in objection.evidence))
        rule_id = _symbol("j", name)
        applicability = _symbol("x", rule_id)
        targets: list[tuple[str, str]] = []
        if objection.target_kind == "objection":
            targets.append(("objection", objection.target))
        elif objection.target_kind == "assumption":
            targets.append(("assumption", objection.target))
        else:
            for route, argument in sorted(program.arguments.items()):
                if program.claims[argument.conclusion].environment != scope:
                    continue
                if ((objection.target_kind == "claim" and argument.conclusion == objection.target)
                    or (objection.target_kind == "argument" and route == objection.target)
                    or (objection.target_kind == "reasoning" and argument.reasoning == objection.target)):
                    targets.append(("argument", route))
        mapping["objections"][name] = {"atom": objections[name], "rule_id": rule_id,
                                       "applicability_atom": applicability,
                                       "target_kind": objection.target_kind,
                                       "target": objection.target,
                                       "targets": [{"kind": kind, "name": target}
                                                   for kind, target in targets],
                                       "antecedents": antecedents,
                                       "rank": rank(name),
                                       "rank_annotation": annotated("rank", name),
                                       "emitted": eligible,
                                       "span": _location(program, name)}
        if eligible:
            if not antecedents:
                antecedents = [structural]
                basis_needed = True
            rules.append({"id": rule_id, "kind": "defeasible",
                          "antecedents": antecedents,
                          "consequent": objections[name],
                          "name": applicability, "rank": rank(name)})
        for kind, target in targets:
            owner = {"argument": mapping["arguments"],
                     "assumption": mapping["assumptions"],
                     "objection": mapping["objections"]}[kind]
            if kind == "argument" and owner[target]["rule_kind"] == "strict":
                raise CompilationError(
                    f"Objection {name!r} targets strict route {target!r}; a strict rule cannot be undercut")
            # Forward objection references are possible: resolve their stable
            # applicability atoms independently of declaration order.
            target_rule = (owner[target]["rule_id"] if target in owner else
                           _symbol("j", target))
            pair = {"attacker": objections[name],
                    "target": _symbol("x", target_rule)}
            contraries.append(pair)
            mapping["contraries"].append({**pair, "objection": name,
                                           "target_kind": kind,
                                           "target_name": target})

    for item in program.argumentation_directives:
        if item.kind == "contrary":
            pair = {"attacker": claims[item.name], "target": claims[item.other]}
            contraries.append(pair)
            mapping["contraries"].append({**pair, "target_kind": "claim",
                                           "attacker_name": item.name,
                                           "target_name": item.other,
                                           "annotation": argumentation_directive(item)})

    if basis_needed or not premises:
        premises.append({"atom": structural, "kind": "axiom"})
        mapping["structural_basis"] = {"atom": structural,
                                        "meaning": "Authored ungrounded relation or empty snapshot; no observation"}
    theory = {"premises": premises, "rules": rules, "contraries": contraries,
              "goal": claims[goal]}
    try:
        _validate(theory)
    except ValueError as exc:
        raise CompilationError(f"Compiled theory exceeds its bounded profile: {exc}") from exc
    # Two runs can use the same observations yet produce different local
    # method outputs.  Bind the actual checked decisions and emitted theory,
    # including present observations that were unusable at this instant.
    mapping["assessment_digest"] = canonical_digest(assessment)
    mapping["theory_digest"] = canonical_digest(theory)
    mapping["snapshot_digest"] = _snapshot_digest(mapping)
    return CompiledTheory(theory=theory, source_map=mapping, assessment=assessment)
