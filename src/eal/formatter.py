"""Canonical human-readable source translation from the checked typed IR."""
from __future__ import annotations

from dataclasses import asdict
import json

from .model import Program
from .parser import parse
from .semantics import validate


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(', ', ': '))


def semantic_ir(program: Program):
    """Source-independent interchange view used for semantic round trips.

    Source byte identity deliberately remains separate: formatted source requires
    newly bound observation records even when this representation is unchanged.
    """
    return {key: value for key, value in asdict(program).items() if key != 'source_digest'}


def format_program(program: Program, *, registry=None) -> str:
    diagnostics = validate(program, registry=registry)
    if diagnostics:
        raise ValueError('; '.join(f'{d.code}: {d.message}' for d in diagnostics))
    blocks = [f'language {_json(program.language)};']

    def emit(kind, name, lines):
        blocks.append(f'{kind} {name} {{\n' + '\n'.join(f'  {line}' for line in lines) + '\n}')

    def predicates(values):
        return [f'require {_json(p.path)} {p.operator} {_json(p.expected)};' for p in values]

    for name, value in program.environments.items():
        emit('environment', name, predicates(value.predicates))
    for name, value in program.tools.items():
        emit('tool', name, [f'version {_json(value.version)};', f'mode {value.mode};'])
    for name, value in program.evidence.items():
        emit('evidence', name, [f'tool {value.tool};', f'kind {value.kind};',
             f'environment {value.environment};', f'max_age {_json(value.max_age)};',
             f'input {_json(value.input)};', *predicates(value.predicates)])
    for name, value in program.assumptions.items():
        lines = [f'statement {_json(value.statement)};', f'environment {value.environment};',
                 f'validate {value.validation};']
        for key in ('valid_from', 'valid_until'):
            if getattr(value, key) is not None:
                lines.append(f'{key} {_json(getattr(value, key))};')
        emit('assumption', name, lines)
    for name, value in program.reasoning.items():
        selector = f'method {_json(value.method)};' if value.method is not None else f'mode {value.mode};'
        lines = [selector, f'rationale {_json(value.rationale)};']
        if value.backing:
            lines.append(f'backing {", ".join(value.backing)};')
        emit('reasoning', name, [*lines, *predicates(value.predicates)])
    for name, value in program.claims.items():
        lines = [f'statement {_json(value.statement)};', f'environment {value.environment};']
        if value.proposition is not None:
            proposition = value.proposition
            lines.append('proposition {')
            for key in ('subject', 'quantity', 'unit', 'scope', 'valid_from', 'valid_until'):
                lines.append(f'  {key} {_json(getattr(proposition, key))};')
            lines.append(f'  query {_json(proposition.query)};')
            p = proposition.result
            lines.append(f'  result {_json(p.path)} {p.operator} {_json(p.expected)};')
            lines.append('}')
        emit('claim', name, lines)
    for name, value in program.arguments.items():
        lines = [f'conclusion {value.conclusion};', f'reasoning {value.reasoning};']
        for key in ('evidence', 'assumptions', 'premises'):
            if getattr(value, key):
                lines.append(f'{key} {", ".join(getattr(value, key))};')
        if value.binding is not None:
            lines.append(f'binding {value.binding};')
        emit('argument', name, lines)
    for name, value in program.objections.items():
        lines = [f'target {value.target_kind} {value.target};']
        for key in ('evidence', 'premises'):
            if getattr(value, key):
                lines.append(f'{key} {", ".join(getattr(value, key))};')
        emit('objection', name, lines)
    return '\n\n'.join(blocks) + '\n'


def format_source(source: str, *, registry=None) -> str:
    """Parse, validate and print source; invalid input is never repaired silently."""
    return format_program(parse(source), registry=registry)
