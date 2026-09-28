"""Typed host method for bounded, three-valued task rules over dated facts.

Acquisition is a single snapshot. Fact selection and rule evaluation are distinct
strategies; unavailable facts remain unknown rather than becoming false.
"""
from __future__ import annotations

import hashlib
import json
import operator
from typing import Protocol

from eal.methods import MethodContract


def rule_digest(rule: dict) -> str:
    return hashlib.sha256(json.dumps(rule, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class RuleStrategy(Protocol):
    def evaluate(self, rule: dict, states: dict[str, bool | None]) -> bool | None: ...


class Conjunction:
    def evaluate(self, rule: dict, states: dict[str, bool | None]) -> bool | None:
        values = list(states.values())
        return False if False in values else None if None in values else True


class Alternatives:
    def evaluate(self, rule: dict, states: dict[str, bool | None]) -> bool | None:
        conjunction = Conjunction()
        routes = [conjunction.evaluate(rule, {name: states[name] for name in route['requirement_ids']})
                  for route in rule['alternatives']]
        return True if True in routes else None if None in routes else False


STRATEGIES: dict[str, RuleStrategy] = {
    # Version applicability belongs to FactSelector; its composition is the
    # same conjunction algorithm rather than a nominal third implementation.
    'all_of': Conjunction(), 'any_of': Alternatives(), 'versioned_all_of': Conjunction(),
}
COMPARISONS = {'eq': operator.eq, 'lte': operator.le, 'gte': operator.ge}


def scalar_equal(left, right) -> bool:
    """JSON numbers share a kind; booleans do not share that numeric kind."""
    compatible = type(left) is type(right) or type(left) in (int, float) and type(right) in (int, float)
    return compatible and left == right


class FactSelector:
    def state(self, requirement: dict, report: dict) -> bool | None:
        eligible = [fact for fact in report['facts']
                    if fact['key'] == requirement['fact_key'] and fact['status'] == 'active'
                    and all(scalar_equal(fact['scope'].get(key), report['scope'].get(key))
                            and key in fact['scope'] and key in report['scope']
                            for key in requirement['scope_keys'])
                    and 0 <= report['now_minute'] - fact['observed_at_minute'] <= requirement['max_age_minutes']]
        if not eligible:
            return None
        newest_time = max(fact['observed_at_minute'] for fact in eligible)
        newest = [fact for fact in eligible if fact['observed_at_minute'] == newest_time]
        if len(newest) != 1:
            raise ValueError('A requirement must have a unique newest eligible fact')
        value, expected = newest[0]['value'], requirement['expected_value']
        if requirement['operator'] != 'eq' and (type(value) not in (int, float) or type(expected) not in (int, float)):
            raise ValueError('Ordered comparisons require numeric fact values')
        if requirement['operator'] == 'eq':
            return scalar_equal(value, expected)
        return COMPARISONS[requirement['operator']](value, expected)


class CorpusComputation:
    def __call__(self, report: dict) -> dict:
        rule = report['rule']
        if rule_digest(rule) != report['rule_digest']:
            raise ValueError('Observed rule differs from the source-bound rule digest')
        if (rule_digest(report['target_identity']) != report['target_identity_digest'] or
                any(not scalar_equal(report['scope'].get(key), value) for key, value in report['target_identity'].items())):
            raise ValueError('Observed target differs from the source-bound task identity')
        identifiers = [item['id'] for item in rule['requirements']]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError('Requirement identities must be unique')
        states = {item['id']: FactSelector().state(item, report) for item in rule['requirements']}
        value = STRATEGIES[rule['type']].evaluate(rule, states)
        decision, basis = {True: ('ready', 'criterion_met'), False: ('not_ready', 'criterion_failed'),
                           None: ('undetermined', 'evidence_unavailable')}[value]
        return {'decision': decision, 'basis': basis, 'rule_digest': report['rule_digest'],
                'states': states, 'snapshot_minute': report['now_minute'], 'scope': report['scope'],
                'target_identity_digest': report['target_identity_digest']}


def evaluate_snapshot(report: dict) -> dict:
    """Importable method entry point; composition remains in strategy objects."""
    return CorpusComputation()(report)


TEXT = {'type': 'string', 'minLength': 1, 'maxLength': 128}
SCALAR = {'anyOf': [{'type': 'string', 'maxLength': 128}, {'type': 'number'}, {'type': 'boolean'}]}
SCOPE = {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': SCALAR}


def object_schema(properties: dict, *, required: list[str] | None = None) -> dict:
    return {'type': 'object', 'properties': properties,
            'required': list(properties) if required is None else required, 'additionalProperties': False}


REQUIREMENT = object_schema({
    'id': TEXT, 'fact_key': TEXT, 'operator': {'type': 'string', 'enum': list(COMPARISONS)},
    'expected_value': SCALAR, 'max_age_minutes': {'type': 'number', 'minimum': 0, 'maximum': 10000},
    'scope_keys': {'type': 'array', 'items': TEXT, 'minItems': 1, 'maxItems': 12},
})
RULE = object_schema({
    'type': {'type': 'string', 'enum': list(STRATEGIES)},
    'requirements': {'type': 'array', 'items': REQUIREMENT, 'minItems': 1, 'maxItems': 32},
    'alternatives': {'type': 'array', 'minItems': 1, 'maxItems': 16,
                     'items': object_schema({'id': TEXT, 'requirement_ids': {
                         'type': 'array', 'items': TEXT, 'minItems': 1, 'maxItems': 32}})},
}, required=['type', 'requirements'])
FACT = object_schema({
    'id': TEXT, 'key': TEXT, 'value': SCALAR,
    'observed_at_minute': {'type': 'number', 'minimum': -10000, 'maximum': 10000},
    'scope': SCOPE, 'status': {'type': 'string', 'enum': ['active', 'invalidated']},
})
CONTRACT = MethodContract(
    identifier='experiment/task-rules/1', evidence_kind='task_snapshot',
    input_schema=object_schema({
        'task_id': TEXT, 'rule_digest': {'type': 'string', 'minLength': 64, 'maxLength': 64},
        'target_identity': SCOPE, 'target_identity_digest': {'type': 'string', 'minLength': 64, 'maxLength': 64},
        'rule': RULE, 'now_minute': {'type': 'number', 'minimum': 0, 'maximum': 10000},
        'scope': SCOPE, 'facts': {'type': 'array', 'items': FACT, 'maxItems': 128},
    }),
    query_schema=object_schema({}),
    output_schema=object_schema({
        'decision': {'type': 'string', 'enum': ['ready', 'not_ready', 'undetermined']},
        'basis': {'type': 'string', 'enum': ['criterion_met', 'criterion_failed', 'evidence_unavailable']},
        'rule_digest': {'type': 'string', 'minLength': 64, 'maxLength': 64},
        'states': {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': {'anyOf': [{'type': 'boolean'}, {'type': 'null'}]}},
        'snapshot_minute': {'type': 'number', 'minimum': 0, 'maximum': 10000},
        'scope': SCOPE, 'target_identity_digest': {'type': 'string', 'minLength': 64, 'maxLength': 64},
    }),
    outputs={'snapshot_minute': 'basis'}, quantities=(), exact_unit=False,
    implementation=evaluate_snapshot, implementation_version='model-transfer-task-rules-1',
    max_input_bytes=65536, max_output_bytes=16384,
)
