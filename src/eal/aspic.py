"""A finite, explicitly delimited ASPIC+ instantiation for EAL/2.

The host installs this method. EAL binds the exact theory to a scoped typed
proposition and an observation; this module only constructs arguments and
computes grounded defeat within the supplied formal theory.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
from itertools import product
import hashlib
import json
import re

from .methods import MethodContract, default_registry

METHOD = "argumentation/aspic/1"
MAX_ARGUMENTS = 128
MAX_DEFEATS = 4096
_ATOM = re.compile(r"~?[A-Za-z][A-Za-z0-9_]{0,63}\Z")
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\Z")
_RANK = {"type": "integer", "minimum": 0, "maximum": 1000}
_ATOM_SCHEMA = {"type": "string", "minLength": 1, "maxLength": 65}


def _obj(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required,
            "additionalProperties": False}


_PREMISE = {"anyOf": [
    _obj({"atom": _ATOM_SCHEMA, "kind": {"type": "string", "enum": ["axiom"]}}),
    _obj({"atom": _ATOM_SCHEMA, "kind": {"type": "string", "enum": ["ordinary"]}, "rank": _RANK}),
]}
_RULE = {"anyOf": [
    _obj({"id": _ATOM_SCHEMA, "kind": {"type": "string", "enum": ["strict"]},
          "antecedents": {"type": "array", "items": _ATOM_SCHEMA, "minItems": 1, "maxItems": 8},
          "consequent": _ATOM_SCHEMA}),
    _obj({"id": _ATOM_SCHEMA, "kind": {"type": "string", "enum": ["defeasible"]},
          "antecedents": {"type": "array", "items": _ATOM_SCHEMA, "minItems": 1, "maxItems": 8},
          "consequent": _ATOM_SCHEMA, "name": _ATOM_SCHEMA, "rank": _RANK}),
]}
THEORY_SCHEMA = _obj({
    "premises": {"type": "array", "items": _PREMISE, "minItems": 1, "maxItems": 64},
    "rules": {"type": "array", "items": _RULE, "maxItems": 64},
    "contraries": {"type": "array", "items": _obj({
        "attacker": _ATOM_SCHEMA, "target": _ATOM_SCHEMA}), "maxItems": 128},
    "goal": _ATOM_SCHEMA,
})
INPUT_SCHEMA = _obj({"theory": THEORY_SCHEMA})
OUTPUT_SCHEMA = _obj({
    "grounded_accepted": {"type": "boolean"},
    "grounded_rejected": {"type": "boolean"},
    "grounded_status": {"type": "string", "enum": ["accepted", "rejected", "undecided", "unconstructed"]},
    "argument_count": {"type": "integer", "minimum": 1, "maximum": MAX_ARGUMENTS},
    "defeat_count": {"type": "integer", "minimum": 0, "maximum": MAX_DEFEATS},
    "theory_sha256": {"type": "string", "minLength": 64, "maxLength": 64},
    "arguments": {"type": "array", "items": _obj({
        "id": _ATOM_SCHEMA, "conclusion": _ATOM_SCHEMA, "top": _ATOM_SCHEMA,
        "subarguments": {"type": "array", "items": _ATOM_SCHEMA, "maxItems": MAX_ARGUMENTS},
        "strength": {"type": "integer", "minimum": 0, "maximum": 1001},
        "label": {"type": "string", "enum": ["in", "out", "undecided"]},
        "rule_id": _ATOM_SCHEMA, "rule_name": _ATOM_SCHEMA,
        "rank": _RANK,
    }, required=["id", "conclusion", "top", "subarguments", "strength", "label"]),
        "minItems": 1, "maxItems": MAX_ARGUMENTS},
    "defeats": {"type": "array", "items": _obj({
        "attacker": _ATOM_SCHEMA, "target": _ATOM_SCHEMA, "subargument": _ATOM_SCHEMA,
        "kind": {"type": "string", "enum": ["undermine", "rebut", "undercut"]},
    }), "maxItems": MAX_DEFEATS},
})


@dataclass(frozen=True)
class _Argument:
    id: str
    conclusion: str
    top: str
    subarguments: tuple[str, ...]
    strength: int
    rule_id: str | None = None
    rule_name: str | None = None
    rank: int | None = None


def _validate(theory):
    from .methods import schema_errors
    errors = schema_errors(theory, THEORY_SCHEMA)
    if errors:
        raise ValueError("; ".join(errors))
    atoms = set()
    premises = set()
    rules = set()
    names = set()
    for item in theory["premises"]:
        atom = item["atom"]
        if not _ATOM.fullmatch(atom) or atom in premises:
            raise ValueError("Premise atoms must be distinct bounded literals")
        premises.add(atom)
        atoms.add(atom)
    for item in theory["rules"]:
        if not _NAME.fullmatch(item["id"]) or item["id"] in rules:
            raise ValueError("Rule identifiers must be distinct bounded identifiers")
        rules.add(item["id"])
        if len(set(item["antecedents"])) != len(item["antecedents"]):
            raise ValueError("A rule cannot repeat an antecedent")
        for atom in [*item["antecedents"], item["consequent"]]:
            if not _ATOM.fullmatch(atom):
                raise ValueError("Rules require bounded literal atoms")
            atoms.add(atom)
        if item["kind"] == "defeasible":
            if not _NAME.fullmatch(item["name"]) or item["name"] in names:
                raise ValueError("Defeasible rule names must be unique positive atoms")
            names.add(item["name"])
            atoms.add(item["name"])
    if not _ATOM.fullmatch(theory["goal"]):
        raise ValueError("Goal must be a bounded literal atom")
    atoms.add(theory["goal"])
    contrary_pairs = set()
    for pair in theory["contraries"]:
        a, b = pair["attacker"], pair["target"]
        if not _ATOM.fullmatch(a) or not _ATOM.fullmatch(b) or a == b or (a, b) in contrary_pairs:
            raise ValueError("Contrariness requires unique, distinct bounded literal pairs")
        contrary_pairs.add((a, b))
        atoms.update((a, b))
    if len(atoms) > 128:
        raise ValueError("Theory exceeds 128 distinct atoms")
    # Reject cyclic dependency even if no premise currently activates the cycle.
    graph = {atom: set() for atom in atoms}
    for rule in theory["rules"]:
        for antecedent in rule["antecedents"]:
            graph[antecedent].add(rule["consequent"])
    indegree = {atom: 0 for atom in atoms}
    for children in graph.values():
        for child in children:
            indegree[child] += 1
    ready = [atom for atom, count in indegree.items() if count == 0]
    heapq.heapify(ready)
    ordered = []
    while ready:
        atom = heapq.heappop(ready)
        ordered.append(atom)
        for child in sorted(graph[atom]):
            indegree[child] -= 1
            if indegree[child] == 0:
                heapq.heappush(ready, child)
    if len(ordered) != len(atoms):
        raise ValueError("Rule dependencies contain an atom cycle")
    return contrary_pairs, ordered


def solve_aspic(payload):
    """Construct bounded arguments, defeats and grounded labels.

    A one-way contrary or an undercutter defeats regardless of preference.
    A reciprocal contradiction defeats when the attacker is not strictly
    weaker than the attacked subargument. Strength is the
    minimum global rank of fallible premises and defeasible rules; an argument
    containing only axioms and strict rules has strength 1001.
    """
    if type(payload) is not dict or set(payload) != {"theory"}:
        raise ValueError("ASPIC input requires exactly one theory")
    theory = payload["theory"]
    contraries, atom_order = _validate(theory)
    arguments: list[_Argument] = []
    by_atom: dict[str, list[_Argument]] = {}

    def add(atom, top, children=(), rank=1001, rule_id=None, name=None):
        if len(arguments) >= MAX_ARGUMENTS:
            raise ValueError("Theory exceeds 128 constructed arguments")
        subs = tuple(dict.fromkeys(sub for child in children
                                   for sub in (*child.subarguments, child.id)))
        arg = _Argument(f"A{len(arguments)}", atom, top, subs,
                        min(rank, *(child.strength for child in children)) if children else rank,
                        rule_id, name, rank if rank != 1001 else None)
        arguments.append(arg)
        by_atom.setdefault(atom, []).append(arg)

    for premise in theory["premises"]:
        add(premise["atom"], premise["kind"], rank=premise.get("rank", 1001))
    rules_by_consequent = {atom: [] for atom in atom_order}
    for rule in theory["rules"]:
        rules_by_consequent[rule["consequent"]].append(rule)
    # Atom dependencies are acyclic, so all derivations of each antecedent
    # exist before a rule using it is visited. No rule is consumed early.
    for atom in atom_order:
        for rule in sorted(rules_by_consequent[atom], key=lambda item: item["id"]):
            if not all(antecedent in by_atom for antecedent in rule["antecedents"]):
                continue
            for children in product(*(by_atom[atom] for atom in rule["antecedents"])):
                add(rule["consequent"], rule["kind"], children,
                    rule.get("rank", 1001), rule["id"], rule.get("name"))

    by_id = {arg.id: arg for arg in arguments}
    defeats = []
    edges = set()
    for attacker in arguments:
        for target in arguments:
            for sub_id in (*target.subarguments, target.id):
                sub = by_id[sub_id]
                kind = None
                if sub.top == "ordinary" and (attacker.conclusion, sub.conclusion) in contraries:
                    kind = "undermine"
                elif sub.top == "defeasible" and (attacker.conclusion, sub.rule_name) in contraries:
                    kind = "undercut"
                elif sub.top == "defeasible" and (attacker.conclusion, sub.conclusion) in contraries:
                    kind = "rebut"
                if kind is None:
                    continue
                # A declared pair is a one-way contrary unless its reverse
                # is declared as well. Only contradictory attacks compare
                # preferences; undercutting always succeeds.
                if (kind != "undercut"
                        and (sub.conclusion, attacker.conclusion) in contraries
                        and attacker.strength < sub.strength):
                    continue
                edges.add((attacker.id, target.id))
                if len(defeats) >= MAX_DEFEATS:
                    raise ValueError("Theory exceeds 4096 defeat witnesses")
                defeats.append({"attacker": attacker.id, "target": target.id,
                                "subargument": sub_id, "kind": kind})

    # The usual least grounded labelling of the constructed Dung defeat graph.
    incoming = {arg.id: set() for arg in arguments}
    for attacker, target in edges:
        incoming[target].add(attacker)
    accepted, rejected = set(), set()
    while True:
        new_in = {arg.id for arg in arguments if arg.id not in accepted | rejected
                  and incoming[arg.id] <= rejected}
        new_out = {target for attacker, target in edges if attacker in accepted | new_in}
        new_out -= rejected
        if not new_in and not new_out:
            break
        accepted.update(new_in)
        rejected.update(new_out)
    goals = by_atom.get(theory["goal"], [])
    status = ("unconstructed" if not goals else "accepted" if any(a.id in accepted for a in goals)
              else "rejected" if all(a.id in rejected for a in goals) else "undecided")
    # Inconsistent strict/axiom closure is outside this profile.
    indefeasible = [a for a in arguments if a.strength == 1001]
    if any((a.conclusion, b.conclusion) in contraries
           for a in indefeasible for b in indefeasible):
        raise ValueError("Axiom and strict-rule closure contains contrary conclusions")
    encoded = json.dumps(theory, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return {
        "grounded_accepted": status == "accepted",
        "grounded_rejected": status == "rejected",
        "grounded_status": status,
        "argument_count": len(arguments), "defeat_count": len(edges),
        "theory_sha256": hashlib.sha256(encoded).hexdigest(),
        "arguments": [{"id": a.id, "conclusion": a.conclusion, "top": a.top,
                       "subarguments": list(a.subarguments), "strength": a.strength,
                       "label": "in" if a.id in accepted else "out" if a.id in rejected else "undecided",
                       **({"rule_id": a.rule_id} if a.rule_id is not None else {}),
                       **({"rule_name": a.rule_name} if a.rule_name is not None else {}),
                       **({"rank": a.rank} if a.rank is not None else {})}
                      for a in arguments],
        "defeats": defeats,
    }


ASPIC_CONTRACT = MethodContract(
    identifier=METHOD, evidence_kind="aspic_theory",
    input_schema=INPUT_SCHEMA,
    query_schema=_obj({"theory": THEORY_SCHEMA}),
    output_schema=OUTPUT_SCHEMA,
    outputs={"grounded_accepted": "boolean", "grounded_rejected": "boolean"},
    quantities=("proposition",), exact_unit=True,
    implementation=solve_aspic, implementation_version="eal-aspic-grounded-2",
    timeout_seconds=5.0, max_input_bytes=256 * 1024, max_output_bytes=1024 * 1024,
)


def aspic_registry():
    """Operator-installed factory: --methods eal.aspic:aspic_registry."""
    return default_registry().with_method(ASPIC_CONTRACT)
