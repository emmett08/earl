"""Check bounded propositional entailment and retain counterexamples."""
from __future__ import annotations

import itertools

MAX_ATOMS = 12
MAX_FORMULA_NODES = 512

from .strategy import BuiltinStrategy
from .validation import _list, _name, _object, _result


def _deductive(value):
    _object(value, ("premises", "conclusion"), "logical_case")
    premises = _list(value["premises"], "Logical premises", minimum=0, maximum=128)
    atoms, budget = set(), [MAX_FORMULA_NODES]

    def check(formula, depth=0):
        budget[0] -= 1
        if budget[0] < 0 or depth > 32:
            raise ValueError("Logical formulas exceed 512 total nodes or depth 32")
        if isinstance(formula, str):
            atoms.add(_name(formula, "Propositional atom"))
            return
        if not isinstance(formula, dict) or len(formula) != 1:
            raise ValueError("A formula is an atom or one not/and/or/implies object")
        op, operand = next(iter(formula.items()))
        if op == "not":
            check(operand, depth + 1)
        elif op in ("and", "or", "implies"):
            _list(operand, f"{op} operands", minimum=2, maximum=2 if op == "implies" else 128)
            for child in operand:
                check(child, depth + 1)
        else:
            raise ValueError(f"Unsupported logical operator {op!r}")

    for formula in [*premises, value["conclusion"]]:
        check(formula)
    if len(atoms) > MAX_ATOMS:
        raise ValueError("Finite deduction supports at most 12 distinct atoms")

    def truth(formula, assignment):
        if isinstance(formula, str):
            return assignment[formula]
        op, operand = next(iter(formula.items()))
        if op == "not":
            return not truth(operand, assignment)
        if op == "and":
            return all(truth(item, assignment) for item in operand)
        if op == "or":
            return any(truth(item, assignment) for item in operand)
        return not truth(operand[0], assignment) or truth(operand[1], assignment)

    atoms = sorted(atoms)
    satisfying = 0
    counterexample = None
    for values in itertools.product((False, True), repeat=len(atoms)):
        assignment = dict(zip(atoms, values))
        if all(truth(formula, assignment) for formula in premises):
            satisfying += 1
            if counterexample is None and not truth(value["conclusion"], assignment):
                counterexample = assignment
    consistent = satisfying > 0
    entailed = counterexample is None
    return _result(consistent,
                   "Finite entailment established with satisfiable premises" if consistent and entailed
                   else "Premises are inconsistent" if not consistent else "A counterexample refutes entailment",
                   entailed=entailed, consistent_premises=consistent, counterexample=counterexample,
                   atoms=atoms, valuations=2 ** len(atoms), satisfying_premise_valuations=satisfying)


STRATEGY = BuiltinStrategy("deductive", _deductive)
