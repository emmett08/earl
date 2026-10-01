"""Hand-calculated finite argumentation, preferences and execution budgets."""
from copy import deepcopy
import pytest
from eal.aspic import solve_aspic, ASPIC_CONTRACT
from eal.limits import ExecutionLimits, using_limits, BudgetExceeded
from eal.methods import execute_extension
from eal.aspic_export import export_aspic_view


def pair():
    return {'premises': [{'atom': 'p', 'kind': 'ordinary', 'rank': 500},
                         {'atom': 'q', 'kind': 'ordinary', 'rank': 500}],
            'rules': [], 'contraries': [{'attacker': 'p', 'target': 'q'},
                                        {'attacker': 'q', 'target': 'p'}], 'goal': 'p'}


def test_preferred_extensions_and_conclusion_quantifiers_have_distinct_results():
    theory = pair()
    theory['options'] = {'semantics': 'preferred', 'query_mode': 'credulous'}
    result = solve_aspic({'theory': theory})
    assert result['extensions'] == [['A0'], ['A1']]
    assert result['grounded_status'] == 'undecided'
    assert result['query_status'] == 'accepted'
    theory['options']['query_mode'] = 'sceptical'
    assert solve_aspic({'theory': theory})['query_status'] == 'undecided'


def test_stable_absence_is_explicit_and_never_vacuously_accepts_the_goal():
    theory = pair()
    theory['premises'].append({'atom': 'r', 'kind': 'ordinary', 'rank': 500})
    theory['contraries'] = [{'attacker': a, 'target': b} for a, b in [('p','q'),('q','r'),('r','p')]]
    theory['options'] = {'semantics': 'stable'}
    result = solve_aspic({'theory': theory})
    assert result['extensions'] == []
    assert result['query_status'] == 'no_extension'
    assert result['query_accepted'] is False and result['query_rejected'] is False
    theory['options']['semantics'] = 'preferred'
    result = solve_aspic({'theory': theory})
    assert result['extensions'] == [[]] and result['query_status'] == 'undecided'


def two_routes():
    return {'premises': [{'atom': 'a', 'kind': 'ordinary', 'rank': 100},
                         {'atom': 'b', 'kind': 'ordinary', 'rank': 500}],
            'rules': [{'id': 'r_x', 'kind': 'defeasible', 'antecedents': ['a'], 'consequent': 'x', 'name': 'use_x', 'rank': 800},
                      {'id': 'r_y', 'kind': 'defeasible', 'antecedents': ['b'], 'consequent': 'y', 'name': 'use_y', 'rank': 700}],
            'contraries': [{'attacker': 'x', 'target': 'y'}, {'attacker': 'y', 'target': 'x'}], 'goal': 'x'}


def test_last_link_and_minimum_rank_make_the_expected_different_defeats():
    theory = two_routes()
    assert solve_aspic({'theory': theory})['query_status'] == 'rejected'
    theory['options'] = {'preference': 'last_link_rank'}
    result = solve_aspic({'theory': theory})
    assert result['query_status'] == 'accepted'
    # Strength retains its display meaning; it is not the last-link ordering.
    assert next(a for a in result['arguments'] if a['conclusion'] == 'x')['strength'] == 100


def test_partial_last_link_respects_explicit_priority_and_incomparability():
    theory = two_routes()
    theory['options'] = {'preference': 'last_link_partial'}
    assert solve_aspic({'theory': theory})['query_status'] == 'undecided'
    theory['priorities'] = [{'kind': 'rule', 'higher': 'r_x', 'lower': 'r_y'}]
    assert solve_aspic({'theory': theory})['query_status'] == 'accepted'
    theory['priorities'].append({'kind': 'rule', 'higher': 'r_y', 'lower': 'r_x'})
    with pytest.raises(ValueError, match='acyclic'):
        solve_aspic({'theory': theory})


def test_atom_cycle_has_finite_premise_founded_routes_and_never_self_supports():
    theory = {'premises': [{'atom': 'p', 'kind': 'ordinary', 'rank': 500}],
              'rules': [{'id':'r_q','kind':'strict','antecedents':['p'],'consequent':'q'},
                        {'id':'r_p','kind':'strict','antecedents':['q'],'consequent':'p'},
                        {'id':'r_y','kind':'strict','antecedents':['x'],'consequent':'y'},
                        {'id':'r_x','kind':'strict','antecedents':['y'],'consequent':'x'}],
              'contraries': [], 'goal': 'x'}
    result = solve_aspic({'theory': theory})
    assert result['argument_count'] == 2
    assert result['query_status'] == 'unconstructed'
    assert [a['conclusion'] for a in result['arguments']] == ['p','q']


def test_host_budgets_allow_more_than_the_previous_128_arguments_in_the_worker():
    theory = {'premises': [{'atom': f'p{i}', 'kind':'ordinary','rank':500} for i in range(129)],
              'rules': [], 'contraries': [], 'goal':'p128'}
    with pytest.raises(BudgetExceeded):
        solve_aspic({'theory': theory})
    limits = ExecutionLimits(formal_premises=200, formal_arguments=200, formal_atoms=200)
    with using_limits(limits):
        computation = execute_extension(ASPIC_CONTRACT, {'theory':theory})
        assert computation['status'] == 'supported', computation['reasons']
        assert computation['details']['argument_count'] == 129
        view = export_aspic_view({'theory':theory,'formal':computation['details']})
        assert len(view['arguments']) == 129


def test_extension_budget_exhaustion_returns_incomplete_without_partial_extensions():
    theory = pair()
    theory['options'] = {'semantics': 'preferred'}
    with using_limits(ExecutionLimits(extension_search=1)):
        result = execute_extension(ASPIC_CONTRACT, {'theory':theory})
    assert result['status'] == 'incomplete'
    assert result['details'] == {}
