"""Canonical printing of retained lexical structure without flattening templates."""
from __future__ import annotations

import json
from .model import (Environment, Tool, Evidence, Assumption, Reasoning, Claim, Argument,
                    Pattern, Application, Objection, ArgumentationDirective, Context,
                    Module, SourceImport, ArgumentBlock, PatternGuard)
from .expressions import format_expression, predicate_expression
from .parser import DEFAULT_FIELDS


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(', ', ': '))


def expression(predicate):
    return format_expression(predicate_expression(predicate), encode)


def support(value, kinds=('evidence', 'assumptions', 'premises')):
    return '[' + ', '.join(kind + ' ' + ', '.join(getattr(value, kind))
                           for kind in kinds if getattr(value, kind)) + ']'


def flow(value):
    return support(value) + f' via {value.reasoning} => {value.conclusion}' + (
        f' binding {value.binding}' if value.binding is not None else '')


def wrap(header, lines):
    return header + ' {\n' + '\n'.join('  ' + line if line else '' for line in lines) + '\n}'


def block(value, defaults=None):
    return '\n\n'.join(declaration(item.value, defaults or {}) for item in value.declarations)


def declaration(value, defaults):
    if isinstance(value, Context):
        ref_keys = {'environment', 'tool', 'kind', 'validate'}
        attributes = ', '.join(key + ' ' + (item if key in ref_keys else encode(item))
                               for key, item in value.defaults.items())
        return wrap('context ' + attributes, block(value.body, defaults | value.defaults).splitlines())
    if isinstance(value, Module):
        return wrap('module ' + value.name, block(value.body, defaults).splitlines())
    if isinstance(value, SourceImport):
        return 'import ' + encode(value.path) + ' as ' + value.name
    if isinstance(value, ArgumentBlock):
        lines = block(value.body, defaults).splitlines()
        if lines:
            lines.append('')
        return wrap('argument ' + value.name, lines + [flow(value.conclusion)])
    if isinstance(value, PatternGuard):
        text = wrap('when ' + value.parameter, block(value.body, defaults).splitlines())
        if value.otherwise is not None:
            text += ' ' + wrap('else', block(value.otherwise, defaults).splitlines())
        return text
    if isinstance(value, Pattern):
        parameters = ', '.join(f'{item.name}: {item.kind}' for item in value.parameters)
        header = 'pattern ' + value.name + '(' + parameters + ')'
        if value.decreases:
            header += ' decreases ' + value.decreases
        return wrap(header, block(value.body, defaults).splitlines()) if value.body else header + ' = ' + flow(value)
    if isinstance(value, Application):
        bindings = ', '.join(item.name + '=' + ('[' + ', '.join(item.reference) + ']'
                                               if type(item.reference) is tuple else item.reference)
                             for item in value.arguments)
        return f'apply {value.name} = {value.pattern}({bindings})'
    if isinstance(value, Argument):
        return 'argument ' + value.name + ' = ' + flow(value)
    if isinstance(value, Objection):
        return 'objection ' + value.name + ' = ' + support(value, ('evidence', 'premises')) + f' -x> {value.target_kind} {value.target}'
    if isinstance(value, ArgumentationDirective):
        text = value.kind + ' ' + value.name
        if value.kind == 'rank':
            text += ' ' + str(value.rank)
        elif value.kind == 'contrary':
            text += ' to ' + value.other
        elif value.kind == 'prefer':
            text += ' over ' + value.other
        return text + ' reviewed ' + encode(value.review)

    kind = {Environment: 'environment', Tool: 'tool', Evidence: 'evidence',
            Assumption: 'assumption', Reasoning: 'reasoning', Claim: 'claim'}[type(value)]
    lines = []

    def field(name, item, quoted=False):
        if name in DEFAULT_FIELDS.get(kind, ()) and name in defaults and encode(item) == encode(defaults[name]):
            return
        lines.append(name + ' ' + (encode(item) if quoted else str(item)))

    if isinstance(value, Tool):
        field('version', value.version, True)
    if isinstance(value, Evidence):
        field('tool', value.tool)
        field('kind', value.kind)
        field('environment', value.environment)
        field('max_age', value.max_age, True)
        field('input', value.input, True)
    if isinstance(value, (Claim, Assumption)):
        field('statement', value.statement, True)
        field('environment', value.environment)
    if isinstance(value, Assumption):
        field('validate', value.validation)
        for name in ('valid_from', 'valid_until'):
            if getattr(value, name) is not None:
                field(name, getattr(value, name), True)
    if isinstance(value, Reasoning):
        field('method', value.method, True)
        field('rationale', value.rationale, True)
        if value.backing:
            lines.append('backing [' + ', '.join(value.backing) + ']')
        if value.transfer:
            relation = value.transfer
            lines.append(f'transfer from {relation.source} to {relation.target} assuming {relation.assumption} reviewed ' + encode(relation.review))
    if isinstance(value, (Environment, Evidence, Reasoning)):
        lines.extend('require ' + expression(predicate) for predicate in value.predicates)
    if isinstance(value, Claim) and value.proposition:
        proposition = value.proposition
        properties = [name + ' ' + encode(getattr(proposition, name))
                      for name in ('subject', 'quantity', 'unit', 'scope', 'valid_from', 'valid_until', 'query')
                      if name not in defaults or encode(getattr(proposition, name)) != encode(defaults[name])]
        properties.append('result ' + expression(proposition.result))
        lines.extend(wrap('proposition', properties).splitlines())
    return wrap(kind + ' ' + value.name, lines)


def print_program(program):
    return 'language ' + encode(program.language) + '\n\n' + block(program.authored) + '\n'
