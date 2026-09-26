"""Optional independent PyArg 2.0.2 check for the common grounded fragment."""
import pytest

from eal.aspic import solve_aspic


@pytest.mark.parametrize("with_undercutter", [False, True])
def test_grounded_undercut_agrees_with_pyarg(with_undercutter):
    pytest.importorskip("py_arg")
    from py_arg.algorithms.semantics.get_grounded_extension import get_grounded_extension
    from py_arg.aspic_classes.argumentation_system import ArgumentationSystem
    from py_arg.aspic_classes.argumentation_theory import ArgumentationTheory
    from py_arg.aspic_classes.defeasible_rule import DefeasibleRule
    from py_arg.aspic_classes.literal import Literal
    from py_arg.aspic_classes.strict_rule import StrictRule

    language = {name: Literal(name) for name in ("p", "q", "r")}
    contrary = {name: [] for name in language}
    rule = DefeasibleRule("d1", {language["p"]}, language["r"])
    applicable = Literal.from_defeasible_rule(rule)
    negated = Literal.from_defeasible_rule_negation(rule)
    language[str(applicable)], language[str(negated)] = applicable, negated
    contrary[str(applicable)], contrary[str(negated)] = [negated], [applicable]
    undercutter = StrictRule("s1", {language["q"]}, negated)
    system = ArgumentationSystem(language, contrary, [undercutter], [rule],
                                 add_defeasible_rule_literals=False)
    facts = ["p", "q"] if with_undercutter else ["p"]
    theory = ArgumentationTheory(system, [], [language[fact] for fact in facts])
    accepted = {str(arg.conclusion) for arg in get_grounded_extension(
        theory.create_abstract_argumentation_framework("reference"))}

    eal = {"premises": [{"atom": fact, "kind": "ordinary", "rank": 5} for fact in facts],
           "rules": [
               {"id": "d1", "kind": "defeasible", "antecedents": ["p"],
                "consequent": "r", "name": "d1", "rank": 5},
               {"id": "s1", "kind": "strict", "antecedents": ["q"], "consequent": "~d1"},
           ],
           "contraries": [{"attacker": "~d1", "target": "d1"}], "goal": "r"}
    outcome = solve_aspic({"theory": eal})
    assert outcome["grounded_accepted"] == ("r" in accepted)
    assert with_undercutter == any(x["kind"] == "undercut" for x in outcome["defeats"])
