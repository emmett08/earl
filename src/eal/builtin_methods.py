"""Versioned specifications for the built-in reasoning methods.

The algorithms live in ``modes``. This module owns their declared evidence,
input, query, output and quantity contracts; public discovery is generated
from these same specifications by ``methods.default_registry``.
"""
from __future__ import annotations

from dataclasses import dataclass


def _object(properties, required=None, additional=False):
    return {'type': 'object', 'properties': properties,
            'required': list(properties) if required is None else required,
            'additionalProperties': additional}


@dataclass(frozen=True)
class BuiltinMethodSpec:
    identifier: str
    evidence_kind: str | None
    input_schema: dict
    query_fields: tuple[str, ...]
    outputs: dict[str, str]
    quantities: tuple[str, ...] | None
    exact_unit: bool = False
    implementation_version: str = 'eal-builtin-2.1.0'
    output_schema: dict | None = None

    @property
    def mode(self):
        return self.identifier.rpartition('/')[0]

    def contract_schemas(self):
        """Produce detached, typed query/output schemas from the declared fields."""
        number = {'type': 'number', 'minimum': -1e100, 'maximum': 1e100}
        boolean = {'type': 'boolean'}
        query = _object({key: self.input_schema['properties'][key] for key in self.query_fields})
        if self.output_schema is not None:
            return query, self.output_schema
        properties = {}
        for path, kind in self.outputs.items():
            if path.endswith('.*'):
                properties[path[:-2]] = {'type': 'object', 'additionalProperties': number}
            else:
                properties[path] = boolean if kind == 'boolean' else number
        return query, _object(properties, additional={'type': 'json'})


number = {'type': 'number', 'minimum': -1e100, 'maximum': 1e100}
integer = {'type': 'integer', 'minimum': 0, 'maximum': 1_000_000_000}
text = {'type': 'string', 'minLength': 1, 'maxLength': 4096}
anything = {'type': 'json'}


def array(item=number, low=1, high=10_000):
    return {'type': 'array', 'items': item, 'minItems': low, 'maxItems': high}


# ``quantities=None`` means all declared non-proposition quantities; the
# quantity vocabulary remains defined by propositions rather than duplicated.
BUILTIN_SPECS = {
    spec.mode: spec for spec in (
        BuiltinMethodSpec('structured/1', None, _object({}), (), {}, (),
                          output_schema=_object({'authored': {'type': 'boolean'},
                                                 'mechanically_proved': {'type': 'boolean'}})),
        BuiltinMethodSpec('deductive/1', 'logical_case',
                          _object({'premises': array(anything, 0, 128), 'conclusion': anything}),
                          ('premises', 'conclusion'),
                          {'entailed': 'boolean', 'consistent_premises': 'boolean'}, ('proposition',)),
        BuiltinMethodSpec('inductive/1', 'sample',
                          _object({'successes': integer, 'trials': {**integer, 'minimum': 1},
                                   'confidence': {'type': 'number', 'minimum': .001, 'maximum': .999999}}),
                          ('confidence',),
                          {'estimate': 'dimensionless', 'lower': 'dimensionless', 'upper': 'dimensionless'},
                          ('probability',)),
        BuiltinMethodSpec('abductive/1', 'hypotheses',
                          _object({'observed': text, 'candidates': array(_object({
                              'name': text, 'prior': number, 'likelihood': number}), 2, 128)}),
                          ('observed', 'candidates'),
                          {'best_posterior': 'dimensionless', 'posterior.*': 'dimensionless'},
                          ('probability',)),
        BuiltinMethodSpec('causal/1', 'experiment',
                          _object({'assignment': {'type': 'string', 'enum': ['randomised']},
                                   'treatment': array(number, 2), 'control': array(number, 2)}),
                          ('assignment',),
                          {'estimate': 'basis', 'standard_error': 'basis',
                           'treatment_mean': 'basis', 'control_mean': 'basis'}, None),
        BuiltinMethodSpec('counterfactual/1', 'causal_model',
                          _object({'variables': {'type': 'object', 'additionalProperties': _object({
                              'intercept': number, 'coefficients': {'type': 'object', 'additionalProperties': number},
                              'noise': number})},
                                   'intervention': _object({'variable': text, 'value': number}),
                                   'outcome': text}),
                          ('variables', 'intervention', 'outcome'),
                          {'factual': 'basis', 'counterfactual': 'basis', 'difference': 'basis'},
                          None, exact_unit=True),
        BuiltinMethodSpec('analogical/1', 'analogy',
                          _object({'relevant_features': array(text, 1, 256),
                                   'source': {'type': 'object', 'additionalProperties': anything},
                                   'target': {'type': 'object', 'additionalProperties': anything}}),
                          ('relevant_features', 'source', 'target'),
                          {'match_fraction': 'dimensionless', 'complete': 'boolean'},
                          ('dimensionless',)),
        BuiltinMethodSpec('temporal/1', 'trace',
                          _object({'start': number, 'end': number, 'max_gap': number,
                                   'events': array(_object({'time': number, 'value': number})),
                                   'property': _object({'operator': {'type': 'string', 'enum': [
                                       'lt', 'le', 'eq', 'ne', 'ge', 'gt']}, 'value': number}),
                                   'semantics': {'type': 'string', 'enum': ['sampled']}}),
                          ('start', 'end', 'max_gap', 'property', 'semantics'),
                          {'holds': 'boolean', 'coverage': 'boolean'},
                          None, exact_unit=True),
    )
}
