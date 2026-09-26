"""Optional PyArg 2.0.2 differential checks on a precisely shared fragment.

Both systems construct finite acyclic arguments from axioms, ordinary premises,
strict and defeasible rules, and explicit directed contraries. Except for the
preference-independent one-way-contrary case, all fallible ranks are equal.
The generated cases use unique rule shapes because PyArg identifies rules by
antecedents and consequent, whereas EAL retains named rule identity. PyArg's
set-based weakest/last-link preferences also differ from EAL's minimum rank
ordering outside this equal-rank fragment; this test deliberately makes no
claim of general equivalence between those orderings.
"""

from itertools import product

import pytest

from eal.aspic import solve_aspic

pytest.importorskip("py_arg")
from py_arg.algorithms.semantics.get_grounded_extension import get_grounded_extension
from py_arg.aspic_classes.argumentation_system import ArgumentationSystem
from py_arg.aspic_classes.argumentation_theory import ArgumentationTheory
from py_arg.aspic_classes.defeasible_rule import DefeasibleRule
from py_arg.aspic_classes.literal import Literal
from py_arg.aspic_classes.strict_rule import StrictRule


def _key(kind, conclusion, rule_id=None, children=()):
    """Stable derivation tree, independent of solver-generated argument IDs."""
    return kind, conclusion, rule_id, tuple(sorted(children))


def _eal_framework(theory):
    result = solve_aspic({"theory": theory})
    by_id = {argument["id"]: argument for argument in result["arguments"]}
    rules = {rule["id"]: rule for rule in theory["rules"]}
    keys = {}

    def key(argument_id):
        if argument_id in keys:
            return keys[argument_id]
        argument = by_id[argument_id]
        rule_id = argument.get("rule_id")
        if rule_id is None:
            children = ()
        else:
            # The output lists all subarguments, not just the direct ones.
            # Atom acyclicity makes each antecedent identify one direct child
            # among the particular derivation's subarguments.
            children = []
            for atom in rules[rule_id]["antecedents"]:
                matches = [sub_id for sub_id in argument["subarguments"]
                           if by_id[sub_id]["conclusion"] == atom]
                assert len(matches) == 1, (argument, atom, matches)
                children.append(key(matches[0]))
        keys[argument_id] = _key(argument["top"], argument["conclusion"],
                                 rule_id, children)
        return keys[argument_id]

    arguments = {key(argument_id): by_id[argument_id]["label"] for argument_id in by_id}
    assert len(arguments) == len(by_id), "test fragment must have distinct derivations"
    defeats = {(key(defeat["attacker"]), key(defeat["target"]))
               for defeat in result["defeats"]}
    return arguments, defeats, result


def _pyarg_framework(theory):
    atoms = {item["atom"] for item in theory["premises"]}
    for rule in theory["rules"]:
        atoms.update(rule["antecedents"])
        atoms.add(rule["consequent"])
        if rule["kind"] == "defeasible":
            atoms.add(rule["name"])
    for pair in theory["contraries"]:
        atoms.update(pair.values())
    language = {atom: Literal(atom) for atom in atoms}
    strict, defeasible = [], []
    for rule in theory["rules"]:
        cls = StrictRule if rule["kind"] == "strict" else DefeasibleRule
        instance = cls(rule["id"], {language[atom] for atom in rule["antecedents"]},
                       language[rule["consequent"]])
        (strict if rule["kind"] == "strict" else defeasible).append(instance)
        if rule["kind"] == "defeasible":
            assert rule["name"] == rule["id"], "PyArg maps applicability to the rule ID"
            language[rule["name"]] = Literal.from_defeasible_rule(instance)
    contrary = {atom: set() for atom in language}
    for pair in theory["contraries"]:
        contrary[pair["target"]].add(language[pair["attacker"]])
    system = ArgumentationSystem(language, contrary, strict, defeasible,
                                 add_defeasible_rule_literals=False)
    axioms = [language[item["atom"]] for item in theory["premises"]
              if item["kind"] == "axiom"]
    ordinary = [language[item["atom"]] for item in theory["premises"]
                if item["kind"] == "ordinary"]
    reference = ArgumentationTheory(system, axioms, ordinary)
    framework = reference.create_abstract_argumentation_framework("pyarg")
    extension = get_grounded_extension(framework)
    keys = {}

    def key(argument):
        if argument in keys:
            return keys[argument]
        rule = argument.top_rule
        kind = ("axiom" if argument.conclusion in argument.axiom_premises else "ordinary") \
            if rule is None else "strict" if isinstance(rule, StrictRule) else "defeasible"
        keys[argument] = _key(kind, str(argument.conclusion),
                              None if rule is None else rule.id,
                              (key(child) for child in argument.direct_sub_arguments))
        return keys[argument]

    defeats = {(key(defeat.from_argument), key(defeat.to_argument))
               for defeat in framework.defeats}
    accepted = {key(argument) for argument in extension}
    outgoing = {target for attacker, target in defeats if attacker in accepted}
    labels = {key(argument): "in" if key(argument) in accepted else
              "out" if key(argument) in outgoing else "undecided"
              for argument in framework.arguments}
    assert len(labels) == len(framework.arguments), "PyArg coalesced a derivation"
    return labels, defeats


def _assert_same_framework(theory):
    eal_arguments, eal_defeats, result = _eal_framework(theory)
    reference_arguments, reference_defeats = _pyarg_framework(theory)
    assert eal_arguments.keys() == reference_arguments.keys(), theory
    assert eal_defeats == reference_defeats, theory
    assert eal_arguments == reference_arguments, theory
    goal_labels = [label for argument, label in reference_arguments.items()
                   if argument[1] == theory["goal"]]
    status = ("unconstructed" if not goal_labels else
              "accepted" if "in" in goal_labels else
              "rejected" if all(label == "out" for label in goal_labels) else
              "undecided")
    assert result["grounded_status"] == status


def _generated_theory(attack, alternative, downstream, axiom_q):
    """Enumerate bounded acyclic derivations and each of the three attack kinds."""
    rules = [{"id": "d1", "kind": "defeasible", "antecedents": ["p"],
              "consequent": "x", "name": "d1", "rank": 5}]
    if alternative:
        rules.append({"id": "d2", "kind": "defeasible", "antecedents": ["q"],
                      "consequent": "x", "name": "d2", "rank": 5})
    if downstream:
        rules.append({"id": "s_goal", "kind": "strict",
                      "antecedents": ["x"], "consequent": "goal"})
    target = {"undercut": "d1", "undermine": "p", "rebut": "x"}[attack]
    attacker = {"undercut": "~d1", "undermine": "~p", "rebut": "~x"}[attack]
    rules.append({"id": "s_attack", "kind": "strict",
                  "antecedents": ["u"], "consequent": attacker})
    premises = [{"atom": atom, "kind": "ordinary", "rank": 5}
                for atom in ("p", "u")]
    premises.append({"atom": "q", "kind": "axiom"} if axiom_q else
                    {"atom": "q", "kind": "ordinary", "rank": 5})
    return {"premises": premises,
            "rules": rules,
            "contraries": [{"attacker": attacker, "target": target}],
            "goal": "goal" if downstream else "x"}


@pytest.mark.parametrize("attack,alternative,downstream,axiom_q",
                         list(product(("undermine", "rebut", "undercut"),
                                      (False, True), (False, True), (False, True))))
def test_generated_acyclic_framework_agrees_with_pyarg(attack, alternative, downstream, axiom_q):
    _assert_same_framework(_generated_theory(attack, alternative, downstream, axiom_q))


def test_axiom_strict_closure_is_not_undermined():
    theory = {"premises": [{"atom": "p", "kind": "axiom"},
                           {"atom": "q", "kind": "ordinary", "rank": 5}],
              "rules": [{"id": "s_goal", "kind": "strict", "antecedents": ["p"],
                         "consequent": "x"}],
              "contraries": [{"attacker": "q", "target": "p"}], "goal": "x"}
    _assert_same_framework(theory)


def test_binary_downstream_rule_keeps_both_alternative_derivations():
    # Lexical order puts m_goal between d1 and z_alt. A one-shot rule queue
    # would construct only the first downstream argument.
    theory = {"premises": [{"atom": atom, "kind": "ordinary", "rank": 5}
                           for atom in ("p", "q", "u", "v")],
              "rules": [
                  {"id": "d1", "kind": "defeasible", "antecedents": ["p"],
                   "consequent": "x", "name": "d1", "rank": 5},
                  {"id": "m_goal", "kind": "strict", "antecedents": ["x", "v"],
                   "consequent": "goal"},
                  {"id": "z_alt", "kind": "defeasible", "antecedents": ["q"],
                   "consequent": "x", "name": "z_alt", "rank": 5},
                  {"id": "s_attack", "kind": "strict", "antecedents": ["u"],
                   "consequent": "~d1"}],
              "contraries": [{"attacker": "~d1", "target": "d1"}],
              "goal": "goal"}
    _assert_same_framework(theory)


def test_reciprocal_rebuttal_is_undecided_in_both_frameworks():
    theory = {"premises": [{"atom": "p", "kind": "ordinary", "rank": 5},
                           {"atom": "q", "kind": "ordinary", "rank": 5}],
              "rules": [{"id": "d_yes", "kind": "defeasible", "antecedents": ["p"],
                         "consequent": "yes", "name": "d_yes", "rank": 5},
                        {"id": "d_no", "kind": "defeasible", "antecedents": ["q"],
                         "consequent": "~yes", "name": "d_no", "rank": 5}],
              "contraries": [{"attacker": "yes", "target": "~yes"},
                             {"attacker": "~yes", "target": "yes"}], "goal": "yes"}
    _assert_same_framework(theory)


def test_one_way_contrary_ignores_weaker_attacker_preference():
    # This case deliberately includes unequal ranks: ASPIC+ contrary attacks
    # defeat regardless of preference in both systems.
    theory = {"premises": [{"atom": "p", "kind": "ordinary", "rank": 9},
                           {"atom": "q", "kind": "ordinary", "rank": 1}],
              "rules": [],
              "contraries": [{"attacker": "q", "target": "p"}], "goal": "p"}
    _assert_same_framework(theory)


def test_pyarg_collapses_distinct_names_for_identical_rule_shapes():
    # Excluded from the generated comparison: EAL can undercut one named rule
    # while retaining the other, but PyArg Rule equality omits the rule ID.
    p, x = Literal("p"), Literal("x")
    assert DefeasibleRule("d1", {p}, x) == DefeasibleRule("d2", {p}, x)


def test_compiled_eal_routes_and_reviewed_strict_rule_match_reference_fragment():
    """Compare a source generated theory, rather than a manually authored JSON one."""
    from test_aspic_compiler import BASE, compare

    source = BASE + '''
claim run_fails { statement "This synthetic run fails."; environment lab; }
argument failure_route { conclusion run_fails; reasoning authored; evidence gap_data; }
objection challenge { target argument primary_route; evidence gap_data; }
aspic {
  strict argument reporting_route reviewed "review/report-implication";
  contrary claim run_fails to run_passes reviewed "review/one-way-incompatibility";
}
'''
    _, result = compare(source)
    theory = result["theory"]
    # PyArg uses a defeasible rule's identifier as its applicability literal.
    # Alpha rename those compiler-generated atoms while retaining every edge.
    names = {rule["name"]: rule["id"] for rule in theory["rules"]
             if rule["kind"] == "defeasible"}
    normalised = {
        **theory,
        "rules": [{**rule, **({"name": rule["id"]} if rule["kind"] == "defeasible" else {})}
                  for rule in theory["rules"]],
        "contraries": [{"attacker": names.get(pair["attacker"], pair["attacker"]),
                        "target": names.get(pair["target"], pair["target"])}
                       for pair in theory["contraries"]],
    }
    _assert_same_framework(normalised)
