"""Independent semantic checks for the finite grounded argumentation operation."""
from __future__ import annotations

from itertools import product
import random

import pytest

from eal.dialectic import (
    MAX_ARGUMENTS,
    MAX_ATTACKS,
    MAX_IDENTIFIER_LENGTH,
    ArgumentationError,
    solve_grounded,
)


def enumerated_grounded(arguments, attacks):
    """Find the least complete extension by enumerating every candidate subset.

    Deliberately independent of production propagation, counters and traces.
    """
    edges = {tuple(edge) for edge in attacks}
    complete = []
    for flags in product((False, True), repeat=len(arguments)):
        candidate = {node for node, present in zip(arguments, flags) if present}
        conflict_free = all(
            not (source in candidate and target in candidate) for source, target in edges
        )
        defended = {
            node for node in arguments
            if all(
                any((defender, attacker) in edges for defender in candidate)
                for attacker in arguments if (attacker, node) in edges
            )
        }
        if conflict_free and candidate == defended:
            complete.append(candidate)
    least = [candidate for candidate in complete if all(candidate <= other for other in complete)]
    assert len(least) == 1
    accepted = least[0]
    rejected = {target for source, target in edges if source in accepted}
    return sorted(accepted), sorted(rejected), sorted(set(arguments) - accepted - rejected)


def assert_trace(result, arguments, attacks):
    """Replay every defence using only earlier accepted rounds."""
    incoming = {
        node: {source for source, target in attacks if target == node}
        for node in arguments
    }
    edges = {tuple(edge) for edge in attacks}
    accepted, rejected = set(), set()
    for round_number, step in enumerate(result["trace"], start=1):
        assert step["round"] == round_number
        new_accepted = {entry["argument"] for entry in step["accepted"]}
        # The complete next F iteration must be represented, not just sound members.
        defended = {node for node in arguments if incoming[node] <= rejected}
        assert new_accepted == defended - accepted
        for entry in step["accepted"]:
            node = entry["argument"]
            assert {item["attacker"] for item in entry["defence"]} == incoming[node]
            for item in entry["defence"]:
                assert item["defender"] in accepted
                assert (item["defender"], item["attacker"]) in edges
        new_rejected = {entry["argument"] for entry in step["rejected"]}
        assert new_rejected == {
            target for source, target in edges if source in new_accepted
        } - rejected
        for entry in step["rejected"]:
            assert set(entry["attacked_by"]) == incoming[entry["argument"]] & new_accepted
        accepted.update(new_accepted)
        rejected.update(new_rejected)
    assert sorted(accepted) == result["accepted"]
    assert sorted(rejected) == result["rejected"]
    assert accepted.isdisjoint(rejected)
    assert {node for node in arguments if incoming[node] <= rejected} == accepted
    for node in result["undecided"]:
        assert result["unresolved_attackers"][node] == sorted(incoming[node] - rejected)
        assert result["unresolved_attackers"][node]


@pytest.mark.parametrize(
    ("arguments", "attacks", "accepted", "rejected", "undecided"),
    [
        ([], [], [], [], []),
        (["a", "b"], [], ["a", "b"], [], []),
        (["a"], [["a", "a"]], [], [], ["a"]),
        (["a", "b"], [["a", "b"], ["b", "a"]], [], [], ["a", "b"]),
        (
            ["a", "b", "c"], [["a", "b"], ["b", "c"]],
            ["a", "c"], ["b"], [],
        ),
        (
            ["a", "b", "c"], [["a", "b"], ["b", "a"], ["c", "b"]],
            ["a", "c"], ["b"], [],
        ),
        (
            ["a", "b", "c"], [["a", "b"], ["b", "c"], ["c", "a"]],
            [], [], ["a", "b", "c"],
        ),
        (
            ["a", "b", "c", "d"],
            [["a", "b"], ["b", "c"], ["c", "d"], ["d", "a"]],
            [], [], ["a", "b", "c", "d"],
        ),
        (
            ["a", "b", "c", "d"],
            [["a", "a"], ["b", "a"], ["a", "c"], ["c", "d"]],
            ["b", "c"], ["a", "d"], [],
        ),
    ],
)
def test_known_frameworks(arguments, attacks, accepted, rejected, undecided):
    result = solve_grounded(arguments, attacks)
    assert (result["accepted"], result["rejected"], result["undecided"]) == (
        accepted, rejected, undecided
    )
    assert_trace(result, arguments, attacks)


def test_all_graphs_through_three_arguments_against_complete_extension_enumeration():
    for size in range(4):
        arguments = list("abc"[:size])
        possible = list(product(arguments, repeat=2))
        for flags in product((False, True), repeat=len(possible)):
            attacks = [list(edge) for edge, present in zip(possible, flags) if present]
            result = solve_grounded(arguments, attacks)
            assert (result["accepted"], result["rejected"], result["undecided"]) == (
                enumerated_grounded(arguments, attacks)
            )
            assert_trace(result, arguments, attacks)


def test_larger_graphs_against_complete_extension_enumeration():
    rng = random.Random(781241)
    for size in range(4, 7):
        arguments = list("abcdef"[:size])
        for _ in range(25):
            attacks = [
                [source, target] for source, target in product(arguments, repeat=2)
                if rng.random() < 0.22
            ]
            result = solve_grounded(arguments, attacks)
            assert (result["accepted"], result["rejected"], result["undecided"]) == (
                enumerated_grounded(arguments, attacks)
            )
            assert_trace(result, arguments, attacks)


def test_multiple_attackers_need_all_to_be_defeated():
    arguments = ["a", "b", "c", "d", "e"]
    attacks = [["a", "b"], ["b", "e"], ["c", "d"], ["d", "c"], ["d", "e"]]
    result = solve_grounded(arguments, attacks)
    assert result["accepted"] == ["a"]
    assert result["rejected"] == ["b"]
    assert result["undecided"] == ["c", "d", "e"]
    assert result["unresolved_attackers"]["e"] == ["d"]


def test_defenders_are_from_an_earlier_round_and_reinstatement_is_explicit():
    result = solve_grounded(["c", "b", "a"], [["b", "a"], ["a", "b"], ["c", "b"]])
    assert result["trace"] == [
        {
            "round": 1,
            "accepted": [{"argument": "c", "defence": []}],
            "rejected": [{"argument": "b", "attacked_by": ["c"]}],
        },
        {
            "round": 2,
            "accepted": [{"argument": "a", "defence": [{"attacker": "b", "defender": "c"}]}],
            "rejected": [],
        },
    ]


def test_order_independence_and_no_input_mutation():
    arguments = ["z", "a", "b", "c", "d", "u", "v"]
    attacks = [["z", "b"], ["a", "b"], ["b", "c"], ["c", "d"], ["u", "v"], ["v", "u"]]
    original_arguments = arguments.copy()
    original_attacks = [edge.copy() for edge in attacks]
    expected = solve_grounded(arguments, attacks)
    rng = random.Random(9835)
    for _ in range(20):
        shuffled_arguments = rng.sample(arguments, len(arguments))
        shuffled_attacks = rng.sample(attacks, len(attacks))
        assert solve_grounded(shuffled_arguments, shuffled_attacks) == expected
    assert arguments == original_arguments
    assert attacks == original_attacks


def test_full_size_chain_is_iterative():
    arguments = [f"a{index:04}" for index in range(MAX_ARGUMENTS)]
    attacks = [[arguments[index], arguments[index + 1]] for index in range(len(arguments) - 1)]
    result = solve_grounded(arguments, attacks)
    assert result["accepted"] == arguments[::2]
    assert result["rejected"] == arguments[1::2]
    assert result["undecided"] == []
    assert len(result["trace"]) == (MAX_ARGUMENTS + 1) // 2


@pytest.mark.parametrize(
    ("arguments", "attacks", "message"),
    [
        (None, [], "arguments must be a list"),
        (("a",), [], "arguments must be a list"),
        ([], {}, "attacks must be a list"),
        (["a", "a"], [], "duplicate argument"),
        (["a", 1], [], "must be a string"),
        ([True], [], "must be a string"),
        ([""], [], "nonempty"),
        ([" "], [], "nonempty"),
        ([" a"], [], "surrounding whitespace"),
        (["a\nb"], [], "printable"),
        (["a\x00"], [], "printable"),
        (["a" * (MAX_IDENTIFIER_LENGTH + 1)], [], "characters"),
        (["a"], [["a"]], "two-element list"),
        (["a"], [["a", "a", "a"]], "two-element list"),
        (["a"], [("a", "a")], "two-element list"),
        (["a"], ["aa"], "two-element list"),
        (["a"], [["a", None]], "must be a string"),
        (["a"], [["a", "b"]], "undeclared argument"),
        (["a"], [["a", "a"], ["a", "a"]], "duplicate attack"),
        ([f"a{i}" for i in range(MAX_ARGUMENTS + 1)], [], "arguments exceeds"),
        (["a"], [["a", "a"]] * (MAX_ATTACKS + 1), "attacks exceeds"),
    ],
)
def test_invalid_graph_is_rejected(arguments, attacks, message):
    with pytest.raises(ArgumentationError, match=message):
        solve_grounded(arguments, attacks)


def test_opaque_printable_identifiers_and_maximum_length_are_supported():
    arguments = ["sensor reading", "α", "a" * MAX_IDENTIFIER_LENGTH]
    assert solve_grounded(arguments, [])["accepted"] == sorted(arguments)
