"""Canonical human-readable source translation from the checked typed IR."""
from __future__ import annotations

from dataclasses import asdict
from collections import Counter
import json
import re

from .model import Program
from .parser import parse
from .semantics import validate, _RESERVED_NAMES


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(', ', ': '))


def semantic_ir(program: Program):
    """Source-independent interchange view used for semantic round trips.

    Source byte identity deliberately remains separate: formatted source requires
    newly bound observation records even when this representation is unchanged.
    """
    result = asdict(program)
    # Keep the structured interchange key independent of Python model names.
    result['formal'] = result.pop('argumentation_directives')
    for key in ('source_digest', 'locations'):
        result.pop(key, None)
    for argument in result['arguments'].values():
        argument.pop('origin', None)
    for diagnostic in result['lowering_diagnostics']:
        diagnostic.pop('span', None)
    for directive in result['formal']:
        directive.pop('span', None)
    return result


def format_program(program: Program, *, registry=None) -> str:
    diagnostics = validate(program, registry=registry)
    if diagnostics:
        raise ValueError('; '.join(f'{d.code}: {d.message}' for d in diagnostics))
    blocks = [f'language {_json(program.language)}']
    defaults = {}
    for key, values in (
        ('environment', [value.environment for table in (program.evidence, program.assumptions, program.claims)
                         for value in table.values()]),
        ('tool', [value.tool for value in program.evidence.values()]),
        ('max_age', [value.max_age for value in program.evidence.values()]),
    ):
        if values:
            value, count = Counter(values).most_common(1)[0]
            if count > 1:
                defaults[key] = value

    def emit(kind, name, lines):
        blocks.append(f'{kind} {name} {{\n' + '\n'.join(f'  {line}' for line in lines) + '\n}')

    def predicates(values):
        return [f'require {key(p.path)} {p.operator} {_json(p.expected)}' for p in values]

    def key(path):
        parts = path.split('.')
        return path if all(re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', part)
                           and part not in _RESERVED_NAMES for part in parts) else _json(path)

    def support(value, kinds):
        return '[' + ', '.join(f'{name} {", ".join(getattr(value, name))}'
                               for name in kinds if getattr(value, name)) + ']'

    def argument_flow(value):
        line = (support(value, ('evidence', 'assumptions', 'premises'))
                + f' via {value.reasoning} => {value.conclusion}')
        if value.binding is not None:
            line += f' binding {value.binding}'
        return line

    def metadata(value, keys):
        return [f'{name} {_json(getattr(value, name)) if name == "max_age" else getattr(value, name)}'
                for name in keys if getattr(value, name) != defaults.get(name)]

    for name, value in program.environments.items():
        emit('environment', name, predicates(value.predicates))
    for name, value in program.tools.items():
        emit('tool', name, [f'version {_json(value.version)}'])
    definitions_end = len(blocks)
    for name, value in program.evidence.items():
        emit('evidence', name, [*metadata(value, ('tool',)), f'kind {value.kind}',
             *metadata(value, ('environment', 'max_age')),
             f'input {_json(value.input)}', *predicates(value.predicates)])
    for name, value in program.assumptions.items():
        lines = [f'statement {_json(value.statement)}', *metadata(value, ('environment',)),
                 f'validate {value.validation}']
        for name_ in ('valid_from', 'valid_until'):
            if getattr(value, name_) is not None:
                lines.append(f'{name_} {_json(getattr(value, name_))}')
        emit('assumption', name, lines)
    for name, value in program.reasoning.items():
        lines = [f'method {_json(value.method)}', f'rationale {_json(value.rationale)}']
        if value.backing:
            lines.append(f'backing [{", ".join(value.backing)}]')
        emit('reasoning', name, [*lines, *predicates(value.predicates)])
    for name, value in program.claims.items():
        lines = [f'statement {_json(value.statement)}', *metadata(value, ('environment',))]
        if value.proposition is not None:
            proposition = value.proposition
            lines.append('proposition {')
            for name_ in ('subject', 'quantity', 'unit', 'scope', 'valid_from', 'valid_until'):
                lines.append(f'  {name_} {_json(getattr(proposition, name_))}')
            lines.append(f'  query {_json(proposition.query)}')
            p = proposition.result
            lines.append(f'  result {key(p.path)} {p.operator} {_json(p.expected)}')
            lines.append('}')
        emit('claim', name, lines)
    for name, value in program.arguments.items():
        if value.origin is None:
            blocks.append(f'argument {name} = {argument_flow(value)}')
    for name, value in program.patterns.items():
        parameters = ', '.join(f'{parameter.name}: {parameter.kind}' for parameter in value.parameters)
        blocks.append(f'pattern {name}({parameters}) = {argument_flow(value)}')
    for name, value in program.applications.items():
        bindings = ', '.join(f'{binding.name}={binding.reference}' for binding in value.arguments)
        blocks.append(f'apply {name} = {value.pattern}({bindings})')
    for name, value in program.objections.items():
        blocks.append(f'objection {name} = {support(value, ("evidence", "premises"))}'
                      + f' -x> {value.target_kind} {value.target}')
    for directive in program.argumentation_directives:
        if directive.kind == 'strict':
            line = f'strict {directive.name}'
        elif directive.kind == 'rank':
            line = f'rank {directive.name} {directive.rank}'
        else:
            line = f'contrary {directive.name} to {directive.other}'
        blocks.append(f'{line} reviewed {_json(directive.review)}')
    if defaults and len(blocks) > definitions_end:
        attributes = ', '.join(f'{name} {_json(value) if name == "max_age" else value}'
                               for name, value in defaults.items())
        body = '\n\n'.join(blocks[definitions_end:])
        blocks[definitions_end:] = ['context ' + attributes + ' {\n'
                                   + '\n'.join('  ' + line if line else '' for line in body.splitlines()) + '\n}']
    return '\n\n'.join(blocks) + '\n'


def format_source(source: str, *, registry=None) -> str:
    """Parse, validate and print source; invalid input is never repaired silently."""
    return format_program(parse(source), registry=registry)
