"""Independent checks of conjunction, alternatives and grounded attack support."""
from copy import deepcopy
from itertools import product
import random

import pytest

from eal.dialectic import (
    ArgumentationError,
    MAX_COMPOSED_CLAIMS,
    MAX_COMPOSED_EDGES,
    MAX_COMPOSED_NODES,
    solve_composed,
    solve_grounded,
)


def node(*premises, usable=True):
    return {"usable": usable, "premises": list(premises)}


def compiled_grounded_reference(nodes, claims, attacks):
    """Compile support into an ordinary attack graph, independently of counters.

    A complement for each claim is attacked by every derivation, and attacks the
    claim and every node requiring that claim. An unattacked blocker rejects each
    locally unusable node. This construction uses neither the production support
    equations nor its iteration order. The ordinary solver has separate exhaustive
    tests against complete-extension enumeration.
    """
    original = {name: f"node_{i}" for i, name in enumerate(sorted(nodes))}
    claim_nodes = {name: f"claim_{i}" for i, name in enumerate(sorted(claims))}
    complements = {name: f"complement_{i}" for i, name in enumerate(sorted(claims))}
    arguments = [*original.values(), *claim_nodes.values(), *complements.values()]
    edges = [[original[source], original[target]] for source, target in attacks]
    for claim, derivations in claims.items():
        edges.append([complements[claim], claim_nodes[claim]])
        edges.extend([original[supporter], complements[claim]] for supporter in derivations)
    for name, declaration in nodes.items():
        edges.extend([complements[claim], original[name]] for claim in declaration["premises"])
        if not declaration["usable"]:
            blocker = f"unusable_{original[name]}"
            arguments.append(blocker)
            edges.append([blocker, original[name]])
    grounded = solve_grounded(arguments, edges)
    labels = {name: label for label in ("accepted", "rejected", "undecided")
              for name in grounded[label]}
    return ({name: labels[identifier] for name, identifier in original.items()},
            {name: labels[identifier] for name, identifier in claim_nodes.items()})


def assert_trace(result, nodes, claims, attacks):
    """Every step must be justified entirely by the previous information state."""
    node_labels = dict.fromkeys(nodes, "undecided")
    claim_labels = dict.fromkeys(claims, "undecided")
    attackers = {name: [source for source, target in attacks if target == name] for name in nodes}
    for index, step in enumerate(result["trace"], start=1):
        assert step["round"] == index
        expected_nodes, expected_claims = {}, {}
        for name, declaration in nodes.items():
            if node_labels[name] != "undecided":
                continue
            requirements = [claim_labels[claim] for claim in declaration["premises"]]
            opposition = [node_labels[source] for source in attackers[name]]
            if not declaration["usable"] or "rejected" in requirements or "accepted" in opposition:
                expected_nodes[name] = "rejected"
            elif all(label == "accepted" for label in requirements) and all(label == "rejected" for label in opposition):
                expected_nodes[name] = "accepted"
        for name, derivations in claims.items():
            if claim_labels[name] != "undecided":
                continue
            current = [node_labels[derivation] for derivation in derivations]
            if "accepted" in current:
                expected_claims[name] = "accepted"
            elif all(label == "rejected" for label in current):
                expected_claims[name] = "rejected"
        assert {item["id"]: item["status"] for item in step["nodes"]} == expected_nodes
        assert {item["id"]: item["status"] for item in step["claims"]} == expected_claims
        for entry in step["nodes"]:
            assert entry["reasons"]
            for reason in entry["reasons"]:
                if reason["kind"] == "local":
                    assert reason["usable"] == nodes[entry["id"]]["usable"]
                elif reason["kind"] == "premise":
                    assert reason["id"] in nodes[entry["id"]]["premises"]
                    assert reason["status"] == claim_labels[reason["id"]]
                else:
                    assert reason["id"] in attackers[entry["id"]]
                    assert reason["status"] == node_labels[reason["id"]]
        for entry in step["claims"]:
            assert entry["reasons"]
            for reason in entry["reasons"]:
                if reason["kind"] == "no_derivation":
                    assert not claims[entry["id"]]
                else:
                    assert reason["id"] in claims[entry["id"]]
                    assert reason["status"] == node_labels[reason["id"]]
        node_labels.update(expected_nodes)
        claim_labels.update(expected_claims)
    assert node_labels == result["nodes"]
    assert claim_labels == result["claims"]


def assert_reference(nodes, claims, attacks):
    result = solve_composed(nodes, claims, attacks)
    assert (result["nodes"], result["claims"]) == compiled_grounded_reference(nodes, claims, attacks)
    assert_trace(result, nodes, claims, attacks)
    return result


def test_empty_graph_and_claim_without_a_derivation():
    assert solve_composed({}, {}, []) == {
        "semantics": "grounded_with_support", "nodes": {}, "claims": {}, "trace": []
    }
    result = assert_reference({}, {"missing": []}, [])
    assert result["claims"] == {"missing": "rejected"}


def test_and_support_requires_every_premise_and_or_support_preserves_alternatives():
    nodes = {"a": node(), "b": node(usable=False), "dependent": node("first", "second")}
    claims = {"first": ["a"], "second": ["b"], "result": ["dependent"]}
    result = assert_reference(nodes, claims, [])
    assert result["nodes"]["dependent"] == "rejected"
    nodes["alternative"] = node()
    claims["second"].append("alternative")
    result = assert_reference(nodes, claims, [])
    assert result["nodes"]["dependent"] == "accepted"
    assert result["claims"]["result"] == "accepted"


@pytest.mark.parametrize("usable,derivations", [(False, []), (True, [])])
def test_unavailable_or_unsupported_attacker_has_no_force(usable, derivations):
    nodes = {"base": node(), "objection": node("objection_basis", usable=usable)}
    claims = {"conclusion": ["base"], "objection_basis": derivations}
    result = assert_reference(nodes, claims, [["objection", "base"]])
    assert result["nodes"]["objection"] == "rejected"
    assert result["claims"]["conclusion"] == "accepted"


def test_unavailable_attacker_cannot_block_even_with_undecided_support():
    nodes = {"base": node(), "cycle": node("basis"), "objection": node("basis", usable=False)}
    result = assert_reference(nodes, {"conclusion": ["base"], "basis": ["cycle"]}, [["objection", "base"]])
    assert result["nodes"]["cycle"] == "undecided"
    assert result["nodes"]["objection"] == "rejected"
    assert result["claims"]["conclusion"] == "accepted"


def test_argument_local_attack_preserves_independent_route_and_downstream_claim():
    nodes = {"first": node(), "alternative": node(), "objection": node(), "downstream": node("claim")}
    claims = {"claim": ["first", "alternative"], "consequence": ["downstream"]}
    result = assert_reference(nodes, claims, [["objection", "first"]])
    assert result["nodes"]["first"] == "rejected"
    assert result["nodes"]["alternative"] == "accepted"
    assert result["claims"] == {"claim": "accepted", "consequence": "accepted"}
    result = assert_reference(nodes, claims, [["objection", "first"], ["objection", "alternative"]])
    assert result["claims"] == {"claim": "rejected", "consequence": "rejected"}


def test_defence_then_rebuttal_of_defence_changes_the_accepted_conclusion():
    nodes = {"base": node(), "objection": node(), "defence": node()}
    attacks = [["objection", "base"], ["defence", "objection"]]
    claims = {"conclusion": ["base"]}
    result = assert_reference(nodes, claims, attacks)
    assert result["claims"]["conclusion"] == "accepted"
    nodes["rebuttal"] = node()
    attacks.append(["rebuttal", "defence"])
    result = assert_reference(nodes, claims, attacks)
    assert result["nodes"]["defence"] == "rejected"
    assert result["nodes"]["objection"] == "accepted"
    assert result["claims"]["conclusion"] == "rejected"


def test_positive_support_cycle_never_justifies_itself():
    result = assert_reference({"a": node("c")}, {"c": ["a"]}, [])
    assert result["nodes"] == {"a": "undecided"}
    assert result["claims"] == {"c": "undecided"}
    assert result["trace"] == []


def test_objection_supported_by_the_claim_it_attacks_is_undecided():
    nodes = {"base": node(), "objection": node("conclusion")}
    result = assert_reference(nodes, {"conclusion": ["base"]}, [["objection", "base"]])
    assert result["nodes"] == {"base": "undecided", "objection": "undecided"}
    assert result["claims"]["conclusion"] == "undecided"


def test_mutual_objections_and_downstream_claim_remain_undecided():
    nodes = {"base": node(), "o1": node(), "o2": node()}
    result = assert_reference(nodes, {"claim": ["base"]}, [["o1", "o2"], ["o2", "o1"], ["o1", "base"]])
    assert set(result["nodes"].values()) == {"undecided"}
    assert result["claims"]["claim"] == "undecided"


def test_an_independent_route_can_supply_the_basis_for_an_objection():
    nodes = {"base": node(), "alternative": node(), "objection": node("claim")}
    result = assert_reference(nodes, {"claim": ["base", "alternative"]}, [["objection", "base"]])
    assert result["nodes"] == {"alternative": "accepted", "base": "rejected", "objection": "accepted"}
    assert result["claims"]["claim"] == "accepted"


def test_all_two_node_one_claim_compositions_against_dung_compilation():
    # 2 usability flags, 2 premise links, 2 derivation links, 4 attack links.
    for flags in product((False, True), repeat=10):
        nodes = {name: node(*(["c"] if flags[2 + i] else []), usable=flags[i])
                 for i, name in enumerate(("a", "b"))}
        claims = {"c": [name for i, name in enumerate(("a", "b")) if flags[4 + i]]}
        attacks = [list(edge) for edge, present in zip(product(("a", "b"), repeat=2), flags[6:]) if present]
        assert_reference(nodes, claims, attacks)


def test_larger_seeded_compositions_against_dung_compilation():
    rng = random.Random(76003)
    for _ in range(200):
        names = ["a", "b", "c", "d", "e"]
        claim_names = ["first", "second", "third"]
        nodes = {name: node(*(claim for claim in claim_names if rng.random() < .2),
                            usable=rng.random() < .85) for name in names}
        claims = {claim: [name for name in names if rng.random() < .35] for claim in claim_names}
        attacks = [[source, target] for source, target in product(names, repeat=2) if rng.random() < .15]
        assert_reference(nodes, claims, attacks)


def test_attack_only_fragment_matches_grounded():
    names = ["a", "b", "c"]
    for flags in product((False, True), repeat=9):
        attacks = [list(edge) for edge, present in zip(product(names, repeat=2), flags) if present]
        ordinary = solve_grounded(names, attacks)
        composed = solve_composed({name: node() for name in names}, {}, attacks)
        assert composed["nodes"] == {name: label for label in ("accepted", "rejected", "undecided")
                                     for name in ordinary[label]}


def test_order_independence_distinct_namespaces_and_input_preservation():
    nodes = {"same": node(), "second": node("same"), "objector": node(usable=False)}
    claims = {"same": ["same"], "conclusion": ["second", "same"]}
    attacks = [["objector", "same"], ["objector", "second"]]
    original = deepcopy((nodes, claims, attacks))
    result = solve_composed(nodes, claims, attacks)
    reordered = solve_composed(dict(reversed(list(nodes.items()))),
                               {name: list(reversed(items)) for name, items in reversed(list(claims.items()))},
                               list(reversed(attacks)))
    assert result == reordered
    assert (nodes, claims, attacks) == original


def test_maximum_support_chain_uses_no_recursion():
    nodes = {f"node{i}": node(*([f"claim{i - 1}"] if i else [])) for i in range(MAX_COMPOSED_NODES)}
    claims = {f"claim{i}": [f"node{i}"] for i in range(MAX_COMPOSED_NODES)}
    result = solve_composed(nodes, claims, [])
    assert set(result["nodes"].values()) == {"accepted"}
    assert set(result["claims"].values()) == {"accepted"}
    assert len(result["trace"]) == 2 * MAX_COMPOSED_NODES


@pytest.mark.parametrize("nodes,claims,attacks,match", [
    ([], {}, [], "dictionaries"),
    ({}, [], [], "dictionaries"),
    ({}, {}, {}, "attacks must be a list"),
    ({"a": {}}, {}, [], "exactly usable and premises"),
    ({"a": {"usable": 1, "premises": []}}, {}, [], "boolean"),
    ({"a": {"usable": True, "premises": ()}}, {}, [], "premises must be a list"),
    ({"a": node("missing")}, {}, [], "undeclared identifier"),
    ({"a": node("c", "c")}, {"c": []}, [], "duplicate identifier"),
    ({"a": node()}, {"c": ["missing"]}, [], "undeclared identifier"),
    ({"a": node()}, {"c": ["a", "a"]}, [], "duplicate identifier"),
    ({"a": node()}, {"c": "a"}, [], "derivations must be a list"),
    ({"a": node()}, {}, [["a"]], "two-element list"),
    ({"a": node()}, {}, [["a", "missing"]], "undeclared node"),
    ({"a": node()}, {}, [["a", "a"], ["a", "a"]], "duplicate attack"),
    ({True: node()}, {}, [], "must be a string"),
    ({}, {" ": []}, [], "nonempty"),
    ({f"a{i}": node() for i in range(MAX_COMPOSED_NODES + 1)}, {}, [], "nodes exceeds"),
    ({}, {f"c{i}": [] for i in range(MAX_COMPOSED_CLAIMS + 1)}, [], "claims exceeds"),
    ({"a": node()}, {}, [["a", "a"]] * (MAX_COMPOSED_EDGES + 1), "relationships exceeds"),
    ({"a": node(*(["c"] * (MAX_COMPOSED_EDGES + 1)))}, {"c": []}, [], "relationships exceeds"),
])
def test_invalid_composed_input_is_rejected(nodes, claims, attacks, match):
    with pytest.raises(ArgumentationError, match=match):
        solve_composed(nodes, claims, attacks)
