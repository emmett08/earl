"""Parse answer content independently of formatting and optional file effects."""
from __future__ import annotations

import json
import math
import re
from typing import Protocol
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

PROSE_OUTPUT = 'Give your assessment and a brief explanation in ordinary prose. '


class AnswerParser:
    def parse(self, text: str) -> dict:
        """No answer-dependent repairs or permissive post-hoc extraction."""
        value = json.loads(text, parse_constant=_reject_constant, parse_float=_finite_float,
                           object_pairs_hook=_unique_object)
        if not isinstance(value, dict):
            raise ValueError('An answer must be a JSON object')
        format_valid = not any(Draft202012Validator(ANSWER_SCHEMA).iter_errors(value))
        # File schema/permission failure is a separately measured side effect.
        decision = value.get('decision')
        known = isinstance(decision, str) and decision in DECISIONS
        return {'answer': {key: value.get(key) for key in
                           ('decision', 'basis', 'reading', 'observed_at', 'explanation')},
                'format_valid': format_valid, 'files': value.get('files', []),
                'annotation': {'status': 'automatic' if known else 'pending',
                               'reason': 'Explicit JSON decision' if known else 'Decision requires independent coding',
                               'method': 'json-decision/1'}}


class ResponseFormat(Protocol):
    """Response presentation is an intervention, independent of model capabilities."""

    instructions: str
    provider_format: dict | None

    def parse(self, text: str) -> dict: ...


class ProseFormat:
    instructions = PROSE_OUTPUT
    provider_format = None

    def parse(self, text: str) -> dict:
        """Code only a complete, unambiguous explicit decision; retain other answers."""
        if not text.strip():
            return _uncoded('empty', 'No text answer was returned', format_valid=None)
        # JSON volunteered in an unconstrained condition can be coded without
        # making that format a task requirement or scoring a missing field wrong.
        try:
            parsed = AnswerParser().parse(text)
        except (ValueError, TypeError):
            parsed = None
        if parsed and parsed['annotation']['status'] == 'automatic':
            parsed['format_valid'] = None
            parsed['files'] = []
            parsed['annotation']['method'] = 'volunteered-json-decision/1'
            return parsed

        normal = re.sub(r'[*`]', '', text).strip()
        # Conditional, interrogative, quoted, historical and retracted statements
        # are not reliably coded by phrase matching. An independent assessor
        # handles them, including correct answers outside this narrow grammar.
        guards = (r'\b(if|unless|would|could|might|previously|earlier|yesterday|was|were|then|however|but|'
                  r'cannot|unlikely|uncertain|unsure|perhaps|probably|possibly|actually|instead|false|incorrect|'
                  r'no|retract|withdraw|disregard|correction)\b'
                  r"|\b(?:isn|aren|can|doesn)['’]t\b")
        candidates = set()
        if not re.search(guards, normal, re.IGNORECASE) and not re.search(r'["“”>?]', normal):
            for sentence in re.split(r'[.!?\n]+', normal):
                sentence = sentence.strip()
                match = re.fullmatch(
                    r'(?:(?:assessment|decision|conclusion)\s*:\s*)?'
                    r'(?:(?:the\s+)?service\s+is\s+(?:currently\s+)?)?'
                    r'(not[ _-]ready|ready|undetermined)(?:\s*[:;—–-]\s*[^.!?]+)?',
                    sentence, re.IGNORECASE)
                if match:
                    candidates.add(re.sub(r'[ -]', '_', match.group(1).lower()))
            # Do not choose one explicit result while overlooking a contrary
            # conclusion embedded in explanatory prose.
            labels = set(re.findall(r'\b(?:not[ _-]ready|ready|undetermined)\b', normal.lower()))
            labels = {re.sub(r'[ -]', '_', item) for item in labels}
            if len(labels) > 1:
                candidates.clear()
        if len(candidates) != 1:
            return _uncoded('pending', 'Natural-language decision requires independent coding', format_valid=None)
        decision = candidates.pop()
        return {'answer': {'decision': decision, 'basis': None, 'reading': None,
                           'observed_at': None, 'explanation': text},
                'format_valid': None, 'files': [],
                'annotation': {'status': 'automatic', 'reason': 'Unambiguous explicit decision',
                               'method': 'explicit-prose-decision/1'}}


class JSONPromptedFormat:
    instructions = OUTPUT
    provider_format = None

    def parse(self, text: str) -> dict:
        if not text.strip():
            return _uncoded('empty', 'No text answer was returned', format_valid=False)
        try:
            return AnswerParser().parse(text)
        except (ValueError, TypeError):
            # Formatting failure is observed; substantive success remains
            # unassessed until the retained answer is independently coded.
            return _uncoded('pending', 'Invalid JSON; substantive answer requires independent coding',
                            format_valid=False)


class JSONSchemaFormat(JSONPromptedFormat):
    provider_format = {'type': 'json_schema', 'name': 'readiness_answer',
                       'strict': True, 'schema': ANSWER_SCHEMA}


def response_format(mode: str) -> ResponseFormat:
    formats = {'prose': ProseFormat, 'json_prompted': JSONPromptedFormat,
               'json_schema': JSONSchemaFormat}
    if mode not in formats:
        raise ValueError(f'Unknown response mode: {mode}')
    return formats[mode]()


def _uncoded(status: str, reason: str, *, format_valid: bool | None) -> dict:
    return {'answer': None, 'format_valid': format_valid, 'files': [],
            'annotation': {'status': status, 'reason': reason}}


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
