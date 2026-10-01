"""Conditional scope transfer with explicit review and a validated assumption.

Correspondence checks do not establish that the asserted transfer relation is
physically justified. That responsibility remains with its reviewed assumption.
"""
from dataclasses import asdict
import json
from .semantics import parse_time


def transfer_errors(program, argument):
    method = program.reasoning[argument.reasoning]
    relation = method.transfer
    if relation is None:
        return []
    errors = []
    if method.method != 'structured/1':
        errors.append('Scope transfer requires structured/1 and an explicit conditional relation')
    if relation.source == relation.target:
        errors.append('Scope transfer must name distinct environments')
    if relation.assumption not in argument.assumptions:
        errors.append('The transfer assumption must be an explicit argument dependency')
    assumption = program.assumptions.get(relation.assumption)
    if assumption is None or assumption.environment != relation.target:
        errors.append('The transfer assumption must be declared in the target environment')
    if argument.binding is not None:
        errors.append('Scope transfer binds the source proposition through its premise, not an evidence result')
    target = program.claims.get(argument.conclusion)
    if target is None or target.environment != relation.target or target.proposition is None:
        errors.append('Scope transfer requires a typed target claim in the declared target environment')
    source = program.claims.get(argument.premises[0]) if len(argument.premises) == 1 else None
    if source is None or source.environment != relation.source or source.proposition is None:
        errors.append('Scope transfer requires exactly one typed premise in the declared source environment')
    if source is not None and source.proposition is not None and target is not None and target.proposition is not None:
        a, b = source.proposition, target.proposition
        for key in ('subject', 'quantity', 'unit', 'query', 'result'):
            left, right = getattr(a, key), getattr(b, key)
            if key == 'result':
                left, right = asdict(left), asdict(right)
            if json.dumps(left, sort_keys=True, allow_nan=False) != json.dumps(right, sort_keys=True, allow_nan=False):
                errors.append(f'Scope transfer must preserve proposition {key}')
        try:
            if parse_time(b.valid_from) < parse_time(a.valid_from) or parse_time(b.valid_until) > parse_time(a.valid_until):
                errors.append('The target interval must be contained in the source interval')
        except ValueError:
            errors.append('Scope transfer requires checked proposition intervals')
    return errors


def computation(program, argument):
    relation = program.reasoning[argument.reasoning].transfer
    return {'status': 'supported', 'method': 'structured/1',
            'reasons': ['The source proposition is conditionally transported under the explicit reviewed assumption'],
            'details': {'authored': True, 'mechanically_proved': False},
            'binding': {'status': 'supported', 'kind': 'scope_transfer',
                        'reasons': ['Exact proposition correspondence and the contained interval are checked'],
                        'relation': asdict(relation), 'source_claim': argument.premises[0],
                        'target_claim': argument.conclusion, 'correspondence_checked': True,
                        'transport_justification_verified': False, 'prose_verified': False}}
