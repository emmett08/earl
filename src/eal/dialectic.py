"""Finite abstract argumentation with Dung's least-fixed-point grounded semantics.

Argument identifiers and attacks are supplied explicitly by the caller. This
module does not infer attacks from natural language or interpret EAL declarations.
"""
from __future__ import annotations

MAX_ARGUMENTS = 4096
MAX_ATTACKS = 65536
MAX_IDENTIFIER_LENGTH = 256
MAX_COMPOSED_NODES = 4096
MAX_COMPOSED_CLAIMS = 4096
MAX_COMPOSED_EDGES = 131072


class ArgumentationError(ValueError):
    """An abstract argumentation graph violates the input contract."""


def _identifier(value: object, location: str) -> str:
    if not isinstance(value, str):
        raise ArgumentationError(f"{location} must be a string")
    if not value or value != value.strip() or not value.isprintable():
        raise ArgumentationError(
            f"{location} must be nonempty and printable without surrounding whitespace"
        )
    if len(value) > MAX_IDENTIFIER_LENGTH:
        raise ArgumentationError(
            f"{location} exceeds {MAX_IDENTIFIER_LENGTH} characters"
        )
    return value


def solve_grounded(arguments: list[str], attacks: list[list[str]]) -> dict:
    """Return the grounded labelling and deterministic, replayable defence trace.

    ``[source, target]`` means source attacks target. The accepted arguments form
    the least fixed point of the defence function F, starting with the empty set.
    Rejected arguments are attacked by an accepted argument; the rest remain
    undecided. These are graph-relative argument statuses, not truth values.

    Input lists must contain distinct identifiers and distinct directed edges.
    Cycles and self-attacks are valid. All result identifiers use Python's sorted
    string order, independent of input order. No caller-owned value is modified.
    Propagation visits each node and edge a bounded number of times. Deterministic
    sorting gives O((V + E) log(V + E)) worst-case time; space is O(V + E), including
    the trace. No recursion, network, clock or tool execution is used.
    """
    if not isinstance(arguments, list):
        raise ArgumentationError("arguments must be a list")
    if not isinstance(attacks, list):
        raise ArgumentationError("attacks must be a list")
    if len(arguments) > MAX_ARGUMENTS:
        raise ArgumentationError(f"arguments exceeds the limit of {MAX_ARGUMENTS}")
    if len(attacks) > MAX_ATTACKS:
        raise ArgumentationError(f"attacks exceeds the limit of {MAX_ATTACKS}")

    nodes: set[str] = set()
    for index, value in enumerate(arguments):
        argument = _identifier(value, f"arguments[{index}]")
        if argument in nodes:
            raise ArgumentationError(f"duplicate argument: {argument!r}")
        nodes.add(argument)

    edges: set[tuple[str, str]] = set()
    for index, edge in enumerate(attacks):
        if not isinstance(edge, list) or len(edge) != 2:
            raise ArgumentationError(f"attacks[{index}] must be a two-element list")
        source = _identifier(edge[0], f"attacks[{index}][0]")
        target = _identifier(edge[1], f"attacks[{index}][1]")
        if source not in nodes or target not in nodes:
            raise ArgumentationError(f"attack contains an undeclared argument: {edge!r}")
        pair = (source, target)
        if pair in edges:
            raise ArgumentationError(f"duplicate attack: {edge!r}")
        edges.add(pair)

    ordered = sorted(nodes)
    incoming: dict[str, list[str]] = {node: [] for node in ordered}
    outgoing: dict[str, list[str]] = {node: [] for node in ordered}
    for source, target in sorted(edges):
        incoming[target].append(source)
        outgoing[source].append(target)

    # An argument is defended once all its attackers have been rejected. The
    # remaining count is reduced once per rejected attacker, never per defender.
    remaining = {node: len(incoming[node]) for node in ordered}
    accepted: set[str] = set()
    rejected: set[str] = set()
    rejected_by: dict[str, str] = {}
    wave = [node for node in ordered if remaining[node] == 0]
    trace: list[dict] = []
    round_number = 0

    while wave:
        round_number += 1
        # Certificates only refer to defenders accepted in an earlier round.
        accepted_trace = [
            {
                "argument": node,
                "defence": [
                    {"attacker": attacker, "defender": rejected_by[attacker]}
                    for attacker in incoming[node]
                ],
            }
            for node in wave
        ]
        accepted.update(wave)
        defeated: dict[str, list[str]] = {}
        for defender in wave:
            for target in outgoing[defender]:
                if target not in rejected:
                    defeated.setdefault(target, []).append(defender)
        rejected.update(defeated)
        for target, defenders in defeated.items():
            rejected_by[target] = defenders[0]

        trace.append(
            {
                "round": round_number,
                "accepted": accepted_trace,
                "rejected": [
                    {"argument": target, "attacked_by": defeated[target]}
                    for target in sorted(defeated)
                ],
            }
        )
        next_wave: set[str] = set()
        for target in defeated:
            for dependent in outgoing[target]:
                remaining[dependent] -= 1
                if (
                    remaining[dependent] == 0
                    and dependent not in accepted
                    and dependent not in rejected
                ):
                    next_wave.add(dependent)
        wave = sorted(next_wave)

    undecided = sorted(nodes - accepted - rejected)
    return {
        "semantics": "grounded",
        "accepted": sorted(accepted),
        "rejected": sorted(rejected),
        "undecided": undecided,
        "trace": trace,
        "unresolved_attackers": {
            node: [attacker for attacker in incoming[node] if attacker not in rejected]
            for node in undecided
        },
    }


def solve_composed(nodes: dict[str, dict], claims: dict[str, list[str]],
                   attacks: list[list[str]]) -> dict:
    """Solve the explicit AND/OR support extension by least information.

    A node has exactly ``usable: bool`` and ``premises: list[claim_id]``. It is
    accepted when locally usable, all premise claims are accepted and all its
    attackers are rejected. It is rejected when locally unusable, a premise is
    rejected or an attacker is accepted. A claim is accepted if any of its listed
    nodes is accepted, and rejected if all are rejected (including an empty list).

    Starting with every label undecided, apply these rules until no label changes.
    This is an explicit support extension, not full ASPIC+. The attack-only
    fragment, with all nodes usable, is Dung grounded labelling. Dependencies can
    be cyclic: an unresolved cycle does not generate acceptance.

    Node and claim identifiers occupy separate namespaces. Each node can support
    zero, one or several claims. Local usability must already reflect the caller's
    evidence and computational checks, before attack/support status is applied.
    Invalid input raises ArgumentationError. Nothing is executed or mutated.
    """
    if not isinstance(nodes, dict) or not isinstance(claims, dict):
        raise ArgumentationError("nodes and claims must be dictionaries")
    if not isinstance(attacks, list):
        raise ArgumentationError("attacks must be a list")
    if len(nodes) > MAX_COMPOSED_NODES:
        raise ArgumentationError(f"nodes exceeds the limit of {MAX_COMPOSED_NODES}")
    if len(claims) > MAX_COMPOSED_CLAIMS:
        raise ArgumentationError(f"claims exceeds the limit of {MAX_COMPOSED_CLAIMS}")
    if len(attacks) > MAX_COMPOSED_EDGES:
        raise ArgumentationError(f"relationships exceeds the limit of {MAX_COMPOSED_EDGES}")
    for node in nodes:
        _identifier(node, "node identifier")
    for claim in claims:
        _identifier(claim, "claim identifier")
    node_ids, claim_ids = sorted(nodes), sorted(claims)
    edge_count = len(attacks)

    def references(value, declared, location):
        nonlocal edge_count
        if not isinstance(value, list):
            raise ArgumentationError(f"{location} must be a list")
        edge_count += len(value)
        if edge_count > MAX_COMPOSED_EDGES:
            raise ArgumentationError(f"relationships exceeds the limit of {MAX_COMPOSED_EDGES}")
        found = set()
        for item in value:
            _identifier(item, location)
            if item not in declared:
                raise ArgumentationError(f"{location} contains an undeclared identifier: {item!r}")
            if item in found:
                raise ArgumentationError(f"{location} contains a duplicate identifier: {item!r}")
            found.add(item)
        return sorted(found)

    premises = {}
    for node in node_ids:
        declaration = nodes[node]
        if not isinstance(declaration, dict) or set(declaration) != {"usable", "premises"}:
            raise ArgumentationError(f"Node {node!r} requires exactly usable and premises")
        if type(declaration["usable"]) is not bool:
            raise ArgumentationError(f"Node {node!r} usable must be a boolean")
        premises[node] = references(declaration["premises"], claims, f"Node {node!r} premises")
    derivations = {
        claim: references(claims[claim], nodes, f"Claim {claim!r} derivations")
        for claim in claim_ids
    }
    edge_set = set()
    for index, edge in enumerate(attacks):
        if not isinstance(edge, list) or len(edge) != 2:
            raise ArgumentationError(f"attacks[{index}] must be a two-element list")
        source = _identifier(edge[0], f"attacks[{index}][0]")
        target = _identifier(edge[1], f"attacks[{index}][1]")
        if source not in nodes or target not in nodes:
            raise ArgumentationError(f"attack contains an undeclared node: {edge!r}")
        pair = (source, target)
        if pair in edge_set:
            raise ArgumentationError(f"duplicate attack: {edge!r}")
        edge_set.add(pair)

    attackers = {node: [] for node in node_ids}
    attacked_nodes = {node: [] for node in node_ids}
    for source, target in sorted(edge_set):
        attackers[target].append(source)
        attacked_nodes[source].append(target)
    premise_dependants = {claim: [] for claim in claim_ids}
    derived_claims = {node: [] for node in node_ids}
    for node in node_ids:
        for claim in premises[node]:
            premise_dependants[claim].append(node)
    for claim in claim_ids:
        for node in derivations[claim]:
            derived_claims[node].append(claim)

    node_labels = {node: "undecided" for node in node_ids}
    claim_labels = {claim: "undecided" for claim in claim_ids}
    premises_in = dict.fromkeys(node_ids, 0)
    premises_out = dict.fromkeys(node_ids, 0)
    attackers_in = dict.fromkeys(node_ids, 0)
    attackers_out = dict.fromkeys(node_ids, 0)
    derivations_in = dict.fromkeys(claim_ids, 0)
    derivations_out = dict.fromkeys(claim_ids, 0)
    pending_nodes, pending_claims = set(node_ids), set(claim_ids)
    trace = []

    while pending_nodes or pending_claims:
        new_nodes, new_claims = {}, {}
        # Each batch reads only labels determined in earlier batches. Counts
        # prevent rescanning all undecided dependencies on every iteration.
        for node in sorted(pending_nodes):
            if node_labels[node] != "undecided":
                continue
            if not nodes[node]["usable"] or premises_out[node] or attackers_in[node]:
                new_nodes[node] = "rejected"
            elif (premises_in[node] == len(premises[node])
                  and attackers_out[node] == len(attackers[node])):
                new_nodes[node] = "accepted"
        for claim in sorted(pending_claims):
            if claim_labels[claim] != "undecided":
                continue
            if derivations_in[claim]:
                new_claims[claim] = "accepted"
            elif derivations_out[claim] == len(derivations[claim]):
                new_claims[claim] = "rejected"
        if not new_nodes and not new_claims:
            break

        node_trace, claim_trace = [], []
        for node, label in new_nodes.items():
            if label == "accepted":
                reasons = [{"kind": "local", "usable": True}]
                reasons.extend({"kind": "premise", "id": claim, "status": "accepted"}
                               for claim in premises[node])
                reasons.extend({"kind": "attacker", "id": attacker, "status": "rejected"}
                               for attacker in attackers[node])
            else:
                reasons = ([{"kind": "local", "usable": False}]
                           if not nodes[node]["usable"] else [])
                reasons.extend({"kind": "premise", "id": claim, "status": "rejected"}
                               for claim in premises[node] if claim_labels[claim] == "rejected")
                reasons.extend({"kind": "attacker", "id": attacker, "status": "accepted"}
                               for attacker in attackers[node] if node_labels[attacker] == "accepted")
            node_trace.append({"id": node, "status": label, "reasons": reasons})
        for claim, label in new_claims.items():
            reasons = [
                {"kind": "derivation", "id": node, "status": label}
                for node in derivations[claim] if node_labels[node] == label
            ] or [{"kind": "no_derivation"}]
            claim_trace.append({"id": claim, "status": label, "reasons": reasons})
        trace.append({"round": len(trace) + 1, "nodes": node_trace, "claims": claim_trace})

        node_labels.update(new_nodes)
        claim_labels.update(new_claims)
        pending_nodes, pending_claims = set(), set()
        for node, label in new_nodes.items():
            for target in attacked_nodes[node]:
                (attackers_in if label == "accepted" else attackers_out)[target] += 1
                pending_nodes.add(target)
            for claim in derived_claims[node]:
                (derivations_in if label == "accepted" else derivations_out)[claim] += 1
                pending_claims.add(claim)
        for claim, label in new_claims.items():
            for node in premise_dependants[claim]:
                (premises_in if label == "accepted" else premises_out)[node] += 1
                pending_nodes.add(node)

    return {"semantics": "grounded_with_support", "nodes": node_labels,
            "claims": claim_labels, "trace": trace}
