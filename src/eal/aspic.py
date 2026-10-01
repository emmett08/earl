"""A finite, explicitly delimited ASPIC+ instantiation for EAL/3.

The host installs this method. EAL binds the exact theory to a scoped typed
proposition and an observation; this module only constructs arguments and
computes grounded defeat within the supplied formal theory.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
from .limits import current_limits, BudgetExceeded
from itertools import product
import hashlib
import json
import re

from .methods import MethodContract, default_registry

METHOD = "argumentation/aspic/2"
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
          "antecedents": {"type": "array", "items": _ATOM_SCHEMA, "minItems": 1},
          "consequent": _ATOM_SCHEMA}),
    _obj({"id": _ATOM_SCHEMA, "kind": {"type": "string", "enum": ["defeasible"]},
          "antecedents": {"type": "array", "items": _ATOM_SCHEMA, "minItems": 1},
          "consequent": _ATOM_SCHEMA, "name": _ATOM_SCHEMA, "rank": _RANK}),
]}
THEORY_SCHEMA = _obj({
    "premises": {"type": "array", "items": _PREMISE, "minItems": 1},
    "rules": {"type": "array", "items": _RULE},
    "contraries": {"type": "array", "items": _obj({
        "attacker": _ATOM_SCHEMA, "target": _ATOM_SCHEMA})},
    "goal": _ATOM_SCHEMA,
    "options": _obj({
        "semantics": {"type": "string", "enum": ["grounded", "preferred", "stable"]},
        "query_mode": {"type": "string", "enum": ["credulous", "sceptical"]},
        "preference": {"type": "string", "enum": ["minimum_rank", "last_link_rank", "last_link_partial"]},
    }, required=[]),
    "priorities": {"type": "array", "items": _obj({
        "kind": {"type": "string", "enum": ["premise", "rule"]}, "higher": _ATOM_SCHEMA, "lower": _ATOM_SCHEMA,
    })},
}, required=["premises", "rules", "contraries", "goal"])
INPUT_SCHEMA = _obj({"theory": THEORY_SCHEMA})
OUTPUT_SCHEMA = _obj({
    "semantics": {"type": "string", "enum": ["grounded", "preferred", "stable"]},
    "query_mode": {"type": "string", "enum": ["credulous", "sceptical"]},
    "preference": {"type": "string", "enum": ["minimum_rank", "last_link_rank", "last_link_partial"]},
    "query_status": {"type": "string", "enum": ["accepted", "rejected", "undecided", "unconstructed", "no_extension"]},
    "query_accepted": {"type": "boolean"},
    "query_rejected": {"type": "boolean"},
    "extensions": {"type": "array", "items": {"type": "array", "items": _ATOM_SCHEMA}},
    "grounded_accepted": {"type": "boolean"},
    "grounded_rejected": {"type": "boolean"},
    "grounded_status": {"type": "string", "enum": ["accepted", "rejected", "undecided", "unconstructed"]},
    "argument_count": {"type": "integer", "minimum": 1},
    "defeat_count": {"type": "integer", "minimum": 0},
    "theory_sha256": {"type": "string", "minLength": 64, "maxLength": 64},
    "arguments": {"type": "array", "items": _obj({
        "id": _ATOM_SCHEMA, "conclusion": _ATOM_SCHEMA, "top": _ATOM_SCHEMA,
        "subarguments": {"type": "array", "items": _ATOM_SCHEMA},
        "direct_subarguments": {"type": "array", "items": _ATOM_SCHEMA},
        "strength": {"type": "integer", "minimum": 0, "maximum": 1001},
        "label": {"type": "string", "enum": ["in", "out", "undecided"]},
        "rule_id": _ATOM_SCHEMA, "rule_name": _ATOM_SCHEMA,
        "rank": _RANK,
    }, required=["id", "conclusion", "top", "subarguments", "direct_subarguments",
                 "strength", "label"]),
        "minItems": 1},
    "defeats": {"type": "array", "items": _obj({
        "attacker": _ATOM_SCHEMA, "target": _ATOM_SCHEMA, "subargument": _ATOM_SCHEMA,
        "kind": {"type": "string", "enum": ["undermine", "rebut", "undercut"]},
    })},
})


@dataclass(frozen=True)
class _Argument:
    id: str
    conclusion: str
    top: str
    subarguments: tuple[str, ...]
    direct_subarguments: tuple[str, ...]
    strength: int
    rule_id: str | None = None
    rule_name: str | None = None
    rank: int | None = None
    ordinary: tuple[str, ...] = ()
    defeasible: tuple[str, ...] = ()
    last: tuple[str, ...] = ()


def _validate(theory):
    from .methods import schema_errors
    errors = schema_errors(theory, THEORY_SCHEMA)
    if errors:
        raise ValueError("; ".join(errors))
    limits = current_limits()
    for field, limit in (("premises", limits.formal_premises), ("rules", limits.formal_rules),
                         ("contraries", limits.formal_contraries)):
        if len(theory[field]) > limit:
            raise BudgetExceeded(f"Theory exceeds the {field} budget of {limit}")
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
        if len(item["antecedents"]) > limits.formal_antecedents:
            raise BudgetExceeded('Rule exceeds the antecedent budget')
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
    if len(atoms) > limits.formal_atoms:
        raise BudgetExceeded('Theory exceeds the atom budget')
    _priority_order(theory)
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
    # A cyclic rule graph is allowed. Construction then enumerates only finite
    # premise-founded arguments without repeating a conclusion along a branch.
    return contrary_pairs, ordered if len(ordered) == len(atoms) else None



def _priority_order(theory):
    priorities = theory.get('priorities', [])
    if priorities and theory.get('options', {}).get('preference') != 'last_link_partial':
        raise ValueError('Partial priorities require last_link_partial preference')
    kinds = {'premise': {p['atom'] for p in theory['premises'] if p['kind'] == 'ordinary'},
             'rule': {r['id'] for r in theory['rules'] if r['kind'] == 'defeasible'}}
    order = set()
    for item in priorities:
        kind, low, high = item['kind'], item['lower'], item['higher']
        if low not in kinds[kind] or high not in kinds[kind] or low == high or (kind, low, high) in order:
            raise ValueError('Priorities require distinct declared fallible elements of the same kind')
        order.add((kind, low, high))
    while True:
        extra = {(kind, low, high) for kind, low, middle in order
                 for other_kind, other_middle, high in order
                 if kind == other_kind and middle == other_middle} - order
        if not extra:
            break
        if len(order) + len(extra) > current_limits().formal_defeats:
            raise BudgetExceeded('Priority-closure budget exceeded')
        order.update(extra)
        if any(low == high for _, low, high in order):
            raise ValueError('Strict priorities must be acyclic')
    return order


def _extensions(identifiers, edges, grounded, rejected, semantics):
    """Exact bounded enumeration of maximal admissible or stable extensions."""
    indices = {name: index for index, name in enumerate(identifiers)}
    incoming = [0] * len(identifiers)
    outgoing = [0] * len(identifiers)
    for attacker, target in edges:
        a, b = indices[attacker], indices[target]
        outgoing[a] |= 1 << b
        incoming[b] |= 1 << a
    fixed = sum(1 << indices[item] for item in grounded)
    undecided = [indices[item] for item in identifiers if item not in grounded | rejected]
    universe = (1 << len(identifiers)) - 1
    candidates = []
    steps = 0
    pending = [(0, fixed)]
    while pending:
        cursor, selected = pending.pop()
        steps += 1
        if steps > current_limits().extension_search:
            raise BudgetExceeded('Extension enumeration budget exceeded')
        attacked = 0
        attackers = 0
        for index in range(len(identifiers)):
            if selected & (1 << index):
                attacked |= outgoing[index]
                attackers |= incoming[index]
        if attacked & selected:
            continue
        if cursor < len(undecided):
            bit = 1 << undecided[cursor]
            pending.append((cursor + 1, selected))
            pending.append((cursor + 1, selected | bit))
            continue
        if attackers & ~attacked:
            continue
        if semantics == 'stable':
            if selected | attacked == universe:
                candidates.append(selected)
        else:
            candidates.append(selected)
    if semantics == 'preferred':
        maximal = []
        for candidate in sorted(candidates, key=int.bit_count, reverse=True):
            for larger in maximal:
                steps += 1
                if steps > current_limits().extension_search:
                    raise BudgetExceeded('Maximal-extension search budget exceeded')
                if candidate & larger == candidate:
                    break
            else:
                maximal.append(candidate)
        candidates = maximal
    return [{name for name, index in indices.items() if candidate & (1 << index)}
            for candidate in sorted(candidates)]

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

    construction_steps = 0
    seen_derivations = set()

    def add(atom, top, children=(), rank=1001, rule_id=None, name=None):
        if len(arguments) >= current_limits().formal_arguments:
            raise BudgetExceeded('Theory exceeds the constructed-argument budget')
        subs = tuple(dict.fromkeys(sub for child in children
                                   for sub in (*child.subarguments, child.id)))
        ordinary = tuple(dict.fromkeys(([atom] if top == 'ordinary' else []) +
                                      [p for child in children for p in child.ordinary]))
        defeasible = tuple(dict.fromkeys(([rule_id] if top == 'defeasible' else []) +
                                        [r for child in children for r in child.defeasible]))
        last = (rule_id,) if top == 'defeasible' else tuple(dict.fromkeys(r for child in children for r in child.last))
        arg = _Argument(f"A{len(arguments)}", atom, top, subs,
                        tuple(child.id for child in children),
                        min(rank, *(child.strength for child in children)) if children else rank,
                        rule_id, name, rank if rank != 1001 else None,
                        ordinary, defeasible, last)
        arguments.append(arg)
        by_atom.setdefault(atom, []).append(arg)

    for premise in theory["premises"]:
        add(premise["atom"], premise["kind"], rank=premise.get("rank", 1001))

    def construct(rule, finite=False):
        nonlocal construction_steps
        if not all(antecedent in by_atom for antecedent in rule["antecedents"]):
            return
        choices = [tuple(by_atom[atom]) for atom in rule['antecedents']]
        for children in product(*choices):
            construction_steps += 1
            if construction_steps > current_limits().formal_construction:
                raise BudgetExceeded('Argument-construction search budget exceeded')
            identity = rule['id'], tuple(child.id for child in children)
            if identity in seen_derivations:
                continue
            seen_derivations.add(identity)
            if finite:
                by_id = {argument.id: argument for argument in arguments}
                if any(rule['consequent'] == by_id[identifier].conclusion
                       for child in children for identifier in (*child.subarguments, child.id)):
                    continue
            add(rule["consequent"], rule["kind"], children,
                rule.get("rank", 1001), rule["id"], rule.get("name"))

    if atom_order is not None:
        for atom in atom_order:
            for rule in sorted((item for item in theory['rules'] if item['consequent'] == atom), key=lambda item: item['id']):
                construct(rule)
    else:
        while True:
            before = len(arguments)
            for rule in sorted(theory['rules'], key=lambda item: item['id']):
                construct(rule, finite=True)
            if len(arguments) == before:
                break

    preference = theory.get('options', {}).get('preference', 'minimum_rank')
    order = _priority_order(theory)
    premise_ranks = {item['atom']: item.get('rank', 1001) for item in theory['premises']}
    rule_ranks = {item['id']: item.get('rank', 1001) for item in theory['rules']}

    def weaker(a, b):
        if preference == 'minimum_rank':
            return a.strength < b.strength
        if a.last or b.last:
            left, right, kind, ranks = a.last, b.last, 'rule', rule_ranks
        else:
            left, right, kind, ranks = a.ordinary, b.ordinary, 'premise', premise_ranks
        if preference == 'last_link_rank':
            return min((ranks[item] for item in left), default=1001) < min((ranks[item] for item in right), default=1001)
        # Strict elitist lifting: an empty uncertain set is strongest, while
        # genuinely incomparable sets do not suppress contradictory attacks.
        return bool(left) and any(all((kind, item, other) in order for other in right) for item in left)

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
                        and weaker(attacker, sub)):
                    continue
                edges.add((attacker.id, target.id))
                if len(defeats) >= current_limits().formal_defeats:
                    raise BudgetExceeded('Theory exceeds the defeat-witness budget')
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
    # Strict conclusions can also rest on fallible premises. Without further
    # logical conditions (such as suitable contraposition rules), the attack
    # definitions alone can leave declared contrary conclusions both in.
    # Keep those definitions intact and reject this outcome from our bounded
    # engineering profile rather than presenting inconsistent support.
    accepted_conclusions = {by_id[identifier].conclusion for identifier in accepted}
    conflicts = sorted((attacker, target) for attacker, target in contraries
                       if attacker in accepted_conclusions and target in accepted_conclusions)
    if conflicts:
        attacker, target = conflicts[0]
        raise ValueError("Accepted conclusions contain a declared contrary pair "
                         f"{attacker!r} -> {target!r}; outside the bounded ASPIC profile")
    semantics = theory.get('options', {}).get('semantics', 'grounded')
    query_mode = theory.get('options', {}).get('query_mode', 'sceptical')
    extensions = ([accepted] if semantics == 'grounded' else
                  _extensions(tuple(by_id), edges, accepted, rejected, semantics))
    goal_ids = {argument.id for argument in goals}
    if not extensions:
        query_status = 'no_extension'
    elif not goals:
        query_status = 'unconstructed'
    else:
        acceptance = [bool(extension & goal_ids) for extension in extensions]
        accepted_query = any(acceptance) if query_mode == 'credulous' else all(acceptance)
        all_rejected = all(goal_ids <= {target for attacker, target in edges if attacker in extension}
                           for extension in extensions)
        query_status = 'accepted' if accepted_query else 'rejected' if all_rejected else 'undecided'
    # Every returned extension must satisfy the same explicit consistency guard.
    for extension in extensions:
        conclusions = {by_id[identifier].conclusion for identifier in extension}
        if any(a in conclusions and b in conclusions for a, b in contraries):
            raise ValueError('An extension contains contrary conclusions; outside this profile')
    encoded = json.dumps(theory, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return {
        "semantics": semantics, "query_mode": query_mode, "preference": preference,
        "query_status": query_status, "query_accepted": query_status == 'accepted',
        "query_rejected": query_status == 'rejected',
        "extensions": [sorted(extension, key=lambda item: int(item[1:])) for extension in extensions],
        "grounded_accepted": status == "accepted",
        "grounded_rejected": status == "rejected",
        "grounded_status": status,
        "argument_count": len(arguments), "defeat_count": len(edges),
        "theory_sha256": hashlib.sha256(encoded).hexdigest(),
        "arguments": [{"id": a.id, "conclusion": a.conclusion, "top": a.top,
                       "subarguments": list(a.subarguments), "strength": a.strength,
                       "direct_subarguments": list(a.direct_subarguments),
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
    outputs={"grounded_accepted": "boolean", "grounded_rejected": "boolean",
             "query_accepted": "boolean", "query_rejected": "boolean"},
    quantities=("proposition",), exact_unit=True,
    implementation=solve_aspic, implementation_version="eal-aspic-finite-5",
    timeout_seconds=5.0, max_input_bytes=256 * 1024, max_output_bytes=1024 * 1024,
)


def aspic_registry():
    """Operator-installed factory: --methods eal.aspic:aspic_registry."""
    return default_registry().with_method(ASPIC_CONTRACT)
