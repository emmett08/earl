"""Parse answer content independently of formatting and optional file effects."""
from __future__ import annotations

import json
import math
from jsonschema import Draft202012Validator

DECISIONS = ['ready', 'not_ready', 'undetermined']
BASES = ['criterion_met', 'criterion_failed', 'measurement_missing', 'assumption_expired',
         'assumption_not_started', 'stale_measurement', 'evidence_unavailable']
ANSWER_SCHEMA = {'type': 'object', 'properties': {
    'decision': {'type': 'string', 'enum': DECISIONS},
    'basis': {'type': 'string', 'enum': BASES},
    'reading': {'type': ['number', 'null']},
    'observed_at': {'type': ['string', 'null']},
    'explanation': {'type': 'string'},
    'files': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'name': {'type': 'string'}, 'content': {'type': 'string'}},
        'required': ['name', 'content'], 'additionalProperties': False}}},
    'required': ['decision', 'basis', 'reading', 'observed_at', 'explanation', 'files'],
    'additionalProperties': False}

OUTPUT = (
    'Return one JSON object: decision (ready, not_ready, undetermined), basis '
    '(' + ', '.join(BASES) + '), reading (the measured number or null), observed_at '
    '(its timestamp or null), explanation (brief text), and files (an array of optional '
    '{name, content} project notes). Cite reading and observed_at for a definite decision. '
    'Use [] when no notes are useful. Notes may use .md/.txt only, at most four project files '
    'totalling 8192 UTF-8 bytes and 8000 characters per file; update existing notes when useful. '
    'Never overwrite specification.txt or source/configuration. '
    'Keep unsupported conclusions qualified. Treat prior notes as dated information: '
    'check applicability to the present task. Return JSON without surrounding prose. '
)


class AnswerParser:
    def parse(self, text: str) -> dict:
        """No answer-dependent repairs or permissive post-hoc extraction."""
        value = json.loads(text, parse_constant=_reject_constant, parse_float=_finite_float,
                           object_pairs_hook=_unique_object)
        if not isinstance(value, dict):
            raise ValueError('An answer must be a JSON object')
        format_valid = not any(Draft202012Validator(ANSWER_SCHEMA).iter_errors(value))
        # File schema/permission failure is a separately measured side effect.
        return {'answer': {key: value.get(key) for key in
                           ('decision', 'basis', 'reading', 'observed_at', 'explanation')},
                'format_valid': format_valid, 'files': value.get('files', [])}


def _reject_constant(value):
    raise ValueError('Non-finite JSON')


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('Non-finite JSON number')
    return number


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field')
        result[key] = value
    return result
