"""Lexical binding and hygienic, identity-preserving argument composition."""
from __future__ import annotations

from dataclasses import dataclass, replace
import re

from .limits import bounded, current_limits
from .model import (Program, Diagnostic, Block, Declaration, Environment, Tool, Evidence, Assumption,
                    Reasoning, Claim, Argument, Objection, Pattern, Application, PatternBinding,
                    ArgumentationDirective, ArgumentOrigin, Context, Module, SourceImport,
                    ArgumentBlock, PatternGuard)

TABLES = {Environment: 'environments', Tool: 'tools', Evidence: 'evidence', Assumption: 'assumptions',
          Reasoning: 'reasoning', Claim: 'claims', Argument: 'arguments', Objection: 'objections',
          Pattern: 'patterns', Application: 'applications'}
KINDS = {cls: name[:-1] if name.endswith('s') else name for cls, name in TABLES.items()}
KINDS[Evidence] = 'evidence'
PARAMETER_KINDS = frozenset({'claim', 'reasoning', 'evidence', 'assumption', 'environment', 'tool'})
_OPERATION = re.compile(r'(head|tail)\(([^()]+)\)\Z')


def qualify(prefix, name):
    return prefix + '.' + name if prefix else name


def candidates(prefix, name):
    while prefix:
        yield qualify(prefix, name)
        prefix = prefix.rpartition('.')[0]
    yield name


def value_references(value):
    """References and their required types; predicate paths are data, not symbols."""
    if isinstance(value, Evidence):
        yield 'tool', value.tool, 'tool', False
        yield 'environment', value.environment, 'environment', False
    elif isinstance(value, (Claim, Assumption)):
        yield 'environment', value.environment, 'environment', False
        if isinstance(value, Assumption):
            yield 'validation', value.validation, 'evidence', False
    elif isinstance(value, Reasoning):
        for ref in value.backing:
            yield 'backing', ref, 'evidence', True
        if value.transfer:
            yield 'transfer', value.transfer.source, 'environment', False
            yield 'transfer', value.transfer.target, 'environment', False
            yield 'transfer', value.transfer.assumption, 'assumption', False
    elif isinstance(value, (Argument, Pattern)):
        yield 'conclusion', value.conclusion, 'claim', False
        yield 'reasoning', value.reasoning, 'reasoning', False
        for attr, kind in (('evidence', 'evidence'), ('assumptions', 'assumption'), ('premises', 'claim')):
            for ref in getattr(value, attr):
                yield attr, ref, kind, True
        if value.binding is not None:
            yield 'binding', value.binding, 'evidence', False
    elif isinstance(value, Objection):
        yield 'target', value.target, value.target_kind, False
        for ref in value.evidence:
            yield 'evidence', ref, 'evidence', True
        for ref in value.premises:
            yield 'premises', ref, 'claim', True


@dataclass
class _Record:
    value: object
    prefix: str
    bindings: dict
    span: object
    pattern: str | None = None
    application: str | None = None
    depth: int = 0
    stack: tuple = ()
    guards: frozenset = frozenset()
    source_file: str | None = None


class _Lowerer:
    def __init__(self, program):
        self.program = program
        self.records = {name: {} for name in TABLES.values()}
        self.symbols = {}
        self.directives = []
        self.namespaces = set()
        self.locations = {}
        self.generated = []
        self.duplicates = []
        self.errors = []
        self.expanded = 0
        self.references = 0
        self.checked_patterns = set()
        self.source_files = {}
        self.calls = []

    def error(self, code, message, owner=None, span=None, expected=None, actual=None):
        self.errors.append(Diagnostic(code, message, owner, span or self.locations.get(owner), expected, actual))

    def register(self, value, prefix, bindings, span, pattern=None, application=None, depth=0, stack=(), guards=frozenset(), source_file=None):
        if len(self.symbols) + len(self.directives) >= current_limits().declarations:
            self.error('resource_limit', 'Declaration budget exceeded', application or getattr(value, 'name', None), span)
            return
        if isinstance(value, ArgumentationDirective):
            self.directives.append(_Record(value, prefix, bindings, span, pattern, application, depth, stack, guards))
            return
        name = qualify(prefix, value.name)
        table = TABLES[type(value)]
        # A compact application and its single generated argument share an ID.
        compact = isinstance(value, Argument) and value.origin is not None and name in self.records['applications']
        if (name in self.symbols and not compact) or name in self.namespaces:
            self.duplicates.append(name)
        self.symbols[name] = KINDS[type(value)] if not compact else 'argument'
        self.records[table][name] = _Record(replace(value, name=name), prefix, bindings, span,
                                           pattern, application, depth, stack, guards, source_file)
        self.locations[name] = span
        if source_file:
            self.source_files[name] = source_file
        if application and not isinstance(value, Application):
            self.generated.append(name)
            for _, ref, _, sequence in value_references(value):
                bound = bindings.get(ref)
                self.references += len(bound) if sequence and type(bound) is tuple else 1
            if self.references > current_limits().expanded_references:
                self.error('resource_limit', 'Expanded reference budget exceeded', application, span)

    def block(self, block, prefix='', bindings=None, pattern=None, application=None, depth=0, stack=(), guards=frozenset()):
        if depth > current_limits().expansion_depth:
            self.error('resource_limit', 'Composition depth budget exceeded', application or prefix)
            return
        bindings = bindings or {}
        for declaration in block.declarations:
            value, span = declaration.value, declaration.span
            if isinstance(value, Context):
                self.block(value.body, prefix, bindings, pattern, application, depth + 1, stack, guards)
            elif isinstance(value, (Module, SourceImport)):
                namespace = qualify(prefix, value.name)
                if namespace in self.namespaces or namespace in self.symbols:
                    self.error('duplicate_symbol', f'Namespace {namespace!r} is declared more than once', namespace, span)
                self.namespaces.add(namespace)
                self.block(value.body, namespace, bindings, pattern, application, depth + 1, stack, guards)
            elif isinstance(value, ArgumentBlock):
                namespace = qualify(prefix, value.name)
                self.block(value.body, namespace, bindings, pattern, application, depth + 1, stack, guards)
                flow = replace(value.conclusion, name=value.name,
                               origin=ArgumentOrigin(pattern, application) if application else None)
                # Its final flow resolves against the block's own lexical scope.
                self.register(flow, prefix, bindings, span, pattern, application, depth, stack, guards, declaration.source_file)
                record = self.records['arguments'].get(namespace)
                if record:
                    record.prefix = namespace
            elif isinstance(value, PatternGuard):
                if pattern is None:
                    self.error('invalid_pattern_guard', 'when is a structural list guard inside a pattern', prefix, span)
                    continue
                values = bindings.get(value.parameter)
                if type(values) is not tuple:
                    self.error('pattern_guard_type', 'when requires a typed list parameter', application, span)
                    continue
                selected = value.body if values else value.otherwise
                if selected:
                    self.block(selected, prefix, bindings, pattern, application, depth + 1, stack,
                               guards | {value.parameter} if values else guards)
            else:
                if application and isinstance(value, Argument):
                    value = replace(value, origin=ArgumentOrigin(pattern, application))
                self.register(value, prefix, bindings, span, pattern, application, depth, stack, guards, declaration.source_file)

    def resolve(self, ref, record, sequence=False):
        operation = _OPERATION.fullmatch(ref)
        if operation:
            name = operation.group(2)
            value = record.bindings.get(name)
            if type(value) is not tuple:
                self.error('pattern_reference_kind', f'{operation.group(1)} requires a list parameter', record.application or record.value.name,
                           record.span)
                return () if sequence else ref
            if operation.group(1) == 'tail':
                value = value[1:]
            elif value:
                value = value[0]
            else:
                self.error('empty_pattern_head', 'head requires a nonempty guarded list', record.application, record.span)
                return () if sequence else ref
        elif ref in record.bindings:
            value = record.bindings[ref]
        else:
            value = next((name for name in candidates(record.prefix, ref) if name in self.symbols), ref)
        if sequence:
            return value if type(value) is tuple else (value,)
        if type(value) is tuple:
            self.error('pattern_reference_kind', 'A scalar reference cannot consume a list', record.application or record.value.name,
                       record.span)
            return ref
        return value

    def resolve_values(self, values, record):
        return tuple(ref for value in values for ref in self.resolve(value, record, True))

    def resolved(self, record):
        value = record.value
        if isinstance(value, Evidence):
            return replace(value, tool=self.resolve(value.tool, record), environment=self.resolve(value.environment, record))
        if isinstance(value, Claim):
            return replace(value, environment=self.resolve(value.environment, record))
        if isinstance(value, Assumption):
            return replace(value, environment=self.resolve(value.environment, record), validation=self.resolve(value.validation, record))
        if isinstance(value, Reasoning):
            transfer = value.transfer
            if transfer:
                transfer = replace(transfer, source=self.resolve(transfer.source, record), target=self.resolve(transfer.target, record),
                                   assumption=self.resolve(transfer.assumption, record))
            return replace(value, backing=self.resolve_values(value.backing, record), transfer=transfer)
        if isinstance(value, Argument):
            return replace(value, conclusion=self.resolve(value.conclusion, record), reasoning=self.resolve(value.reasoning, record),
                           evidence=self.resolve_values(value.evidence, record), assumptions=self.resolve_values(value.assumptions, record),
                           premises=self.resolve_values(value.premises, record),
                           binding=self.resolve(value.binding, record) if value.binding else None)
        if isinstance(value, Objection):
            return replace(value, target=self.resolve(value.target, record), evidence=self.resolve_values(value.evidence, record),
                           premises=self.resolve_values(value.premises, record))
        if isinstance(value, Application):
            bindings = tuple(replace(item, reference=self.resolve_values(item.reference, record) if type(item.reference) is tuple
                                     else self.resolve(item.reference, record, _OPERATION.fullmatch(item.reference) is not None
                                                       and item.reference.startswith('tail('))) for item in value.arguments)
            pattern = next((name for name in candidates(record.prefix, value.pattern) if name in self.records['patterns']), value.pattern)
            return replace(value, pattern=pattern, arguments=bindings)
        if isinstance(value, ArgumentationDirective):
            return replace(value, name=self.resolve(value.name, record), other=self.resolve(value.other, record) if value.other else None)
        return value

    def template_locals(self, block, prefix=''):
        result = {}
        for declaration in block.declarations:
            value = declaration.value
            if isinstance(value, Context):
                result.update(self.template_locals(value.body, prefix))
            elif isinstance(value, (Module, SourceImport, ArgumentBlock)):
                child = qualify(prefix, value.name)
                result.update(self.template_locals(value.body, child))
                if isinstance(value, ArgumentBlock):
                    result[child] = 'argument'
            elif isinstance(value, PatternGuard):
                result.update(self.template_locals(value.body, prefix))
                if value.otherwise:
                    result.update(self.template_locals(value.otherwise, prefix))
            elif isinstance(value, ArgumentationDirective):
                continue
            else:
                result[qualify(prefix, value.name)] = KINDS[type(value)]
        return result

    def check_template(self, record):
        pattern = record.value
        if pattern.name in self.checked_patterns:
            return
        self.checked_patterns.add(pattern.name)
        parameters = {}
        for parameter in pattern.parameters:
            if parameter.name in parameters:
                self.error('duplicate_pattern_parameter', f'Parameter {parameter.name!r} is declared more than once', pattern.name)
            parameters[parameter.name] = parameter.kind
            if parameter.kind.removesuffix('[]') not in PARAMETER_KINDS:
                self.error('invalid_pattern_parameter_kind', f'Unknown parameter kind {parameter.kind!r}', pattern.name)
        if pattern.decreases is not None and not parameters.get(pattern.decreases, '').endswith('[]'):
            self.error('invalid_recursion_measure', 'decreases must name a typed list parameter', pattern.name)
        locals = self.template_locals(pattern.body) if pattern.body else {}
        local_patterns = {}
        def definitions(block, prefix=''):
            for item in block.declarations:
                value = item.value
                if isinstance(value, Pattern):
                    local_patterns[qualify(prefix, value.name)] = value
                elif isinstance(value, (Context, Module, ArgumentBlock)):
                    definitions(value.body, qualify(prefix, value.name) if not isinstance(value, Context) else prefix)
                elif isinstance(value, PatternGuard):
                    definitions(value.body, prefix)
                    if value.otherwise:
                        definitions(value.otherwise, prefix)
        if pattern.body:
            definitions(pattern.body)
            def application_kinds(block, prefix=''):
                for item in block.declarations:
                    value = item.value
                    if isinstance(value, Application):
                        local = next((name for name in candidates(prefix, value.pattern) if name in local_patterns), None)
                        global_name = next((name for name in candidates(record.prefix, value.pattern) if name in self.records['patterns']), None)
                        called = local_patterns[local] if local is not None else self.records['patterns'][global_name].value if global_name else None
                        if called is not None and called.body is None:
                            locals[qualify(prefix, value.name)] = 'argument'
                    elif isinstance(value, (Context, Module, SourceImport, ArgumentBlock, PatternGuard)):
                        child = qualify(prefix, value.name) if isinstance(value, (Module, SourceImport, ArgumentBlock)) else prefix
                        application_kinds(value.body, child)
                        if isinstance(value, PatternGuard) and value.otherwise:
                            application_kinds(value.otherwise, prefix)
            application_kinds(pattern.body)
        for name in locals:
            if name in parameters:
                self.error('generated_symbol_collision', f'Local {name!r} shadows a pattern parameter', pattern.name)

        def reference(ref, kind, sequence, prefix):
            operation = _OPERATION.fullmatch(ref)
            name = operation.group(2) if operation else ref
            actual = parameters.get(name)
            if actual is not None:
                if operation:
                    if not actual.endswith('[]'):
                        self.error('pattern_reference_kind', f'{operation.group(1)} requires a list parameter', pattern.name)
                        return
                    actual = actual if operation.group(1) == 'tail' else actual[:-2]
            else:
                actual = next((locals[name_] for name_ in candidates(prefix, name) if name_ in locals), None)
            if actual is None:
                self.error('unbound_pattern_reference', f'Reference {name!r} must name a typed parameter or local declaration; global capture is forbidden',
                           pattern.name, expected=kind, actual='undeclared parameter')
            elif actual != kind and not (sequence and actual == kind + '[]'):
                self.error('pattern_reference_kind', f'Reference {name!r} has kind {actual!r}; expected {kind!r}', pattern.name,
                           expected=kind, actual=actual)

        def check_value(value, prefix):
            for _, ref, kind, sequence in value_references(value):
                reference(ref, kind, sequence, prefix)

        def walk(block, prefix='', guards=frozenset()):
            for declaration in block.declarations:
                value = declaration.value
                if isinstance(value, Context):
                    walk(value.body, prefix, guards)
                elif isinstance(value, (Module, SourceImport)):
                    walk(value.body, qualify(prefix, value.name), guards)
                elif isinstance(value, ArgumentBlock):
                    child = qualify(prefix, value.name)
                    walk(value.body, child, guards)
                    check_value(value.conclusion, child)
                elif isinstance(value, PatternGuard):
                    if not parameters.get(value.parameter, '').endswith('[]'):
                        self.error('pattern_guard_type', 'when requires a typed list parameter', pattern.name)
                    walk(value.body, prefix, guards | {value.parameter})
                    if value.otherwise:
                        walk(value.otherwise, prefix, guards)
                elif isinstance(value, Pattern):
                    # Nested definitions remain closed in their own parameters.
                    nested = _Record(replace(value, name=qualify(pattern.name, value.name)), record.prefix, {}, declaration.span)
                    self.check_template(nested)
                elif isinstance(value, Application):
                    target = next((name for name in candidates(record.prefix, value.pattern) if name in self.records['patterns']), None)
                    called = self.records['patterns'][target].value if target else None
                    local = next((name for name in candidates(prefix, value.pattern) if name in local_patterns), None)
                    if local is not None:
                        called = replace(local_patterns[local], name=qualify(pattern.name, local))
                    elif value.pattern in (pattern.name, pattern.name.rpartition('.')[2] or pattern.name):
                        called = pattern
                    if called:
                        supplied = {item.name: item.reference for item in value.arguments}
                        kinds = {param.name: param.kind for param in called.parameters}
                        if len(supplied) != len(value.arguments):
                            self.error('duplicate_pattern_argument', 'A parameter is supplied more than once', pattern.name)
                        for item in value.arguments:
                            expected = kinds.get(item.name)
                            if expected is None:
                                self.error('unknown_pattern_argument', f'Unknown parameter {item.name!r}', pattern.name)
                                continue
                            refs = item.reference if type(item.reference) is tuple else (item.reference,)
                            if type(item.reference) is tuple and not expected.endswith('[]'):
                                self.error('pattern_argument_kind', f'Parameter {item.name!r} requires a scalar reference', pattern.name)
                            if type(item.reference) is str and expected.endswith('[]'):
                                op = _OPERATION.fullmatch(item.reference)
                                actual = parameters.get(op.group(2) if op else item.reference, '')
                                if not actual.endswith('[]') or op and op.group(1) == 'head':
                                    self.error('pattern_argument_kind', f'Parameter {item.name!r} requires a list reference or explicit list', pattern.name)
                            for ref in refs:
                                reference(ref, expected.removesuffix('[]'), expected.endswith('[]'), prefix)
                        for missing in kinds.keys() - supplied.keys():
                            self.error('missing_pattern_argument', f'Pattern {called.name!r} requires {missing!r}', pattern.name)
                        self.calls.append((pattern.name, called.name, parameters, supplied, guards))
                        if called.name == pattern.name:
                            measure = pattern.decreases
                            if not measure or measure not in guards or supplied.get(measure) != 'tail(' + measure + ')':
                                self.error('nonterminating_pattern', 'A recursive call must be guarded by the decreasing list and pass its tail', pattern.name)
                    elif value.pattern not in locals:
                        self.error('unknown_pattern', f'Unknown pattern {value.pattern!r}', pattern.name)
                elif not isinstance(value, ArgumentationDirective):
                    check_value(value, prefix)

        if pattern.body:
            walk(pattern.body)
        else:
            if not (pattern.evidence or pattern.assumptions or pattern.premises):
                self.error('empty_pattern', 'An argument pattern requires support', pattern.name)
            check_value(pattern, '')

    def expand(self, record):
        application = self.resolved(record)
        existing = self.records['arguments'].get(application.name)
        if existing is not None and existing.value.origin is None:
            self.error('generated_symbol_collision', 'An application cannot replace an authored argument', application.name)
            return
        self.records['applications'][application.name].value = application
        self.records['applications'][application.name].bindings = {}
        # Its binding references are now fully qualified; prevent resolving twice.
        self.records['applications'][application.name].prefix = ''
        template = self.records['patterns'].get(application.pattern)
        if template is None:
            self.error('unknown_pattern', f'Unknown pattern {application.pattern!r}', application.name)
            return
        pattern = template.value
        self.check_template(template)
        if any(error.declaration == pattern.name for error in self.errors):
            self.error('invalid_pattern', f'Pattern {pattern.name!r} has an invalid definition', application.name)
            return
        self.expanded += 1
        if self.expanded > current_limits().applications:
            self.error('resource_limit', 'Pattern application budget exceeded', application.name)
            return
        parameters = {parameter.name: parameter.kind for parameter in pattern.parameters}
        bindings = {}
        before = len(self.errors)
        for item in application.arguments:
            if item.name in bindings:
                self.error('duplicate_pattern_argument', f'Parameter {item.name!r} is supplied twice', application.name)
            bindings[item.name] = item.reference
            expected = parameters.get(item.name)
            if expected is None:
                self.error('unknown_pattern_argument', f'Unknown parameter {item.name!r}', application.name)
                continue
            many = expected.endswith('[]')
            if many != (type(item.reference) is tuple):
                self.error('pattern_argument_kind', f'Parameter {item.name!r} requires {expected}', application.name)
                continue
            values = item.reference if many else (item.reference,)
            for value in values:
                self.references += 1
                if self.symbols.get(value) != expected.removesuffix('[]'):
                    self.error('pattern_argument_kind', f'Parameter {item.name!r} requires {expected}; {value!r} is {self.symbols.get(value, "unknown reference")}',
                               application.name, expected=expected, actual=self.symbols.get(value, 'unknown reference'))
        for missing in parameters.keys() - bindings.keys():
            self.error('missing_pattern_argument', f'Pattern {pattern.name!r} requires {missing!r}', application.name)
        if self.references > current_limits().expanded_references:
            self.error('resource_limit', 'Expanded reference budget exceeded', application.name)
        if len(self.errors) != before:
            return
        measure = len(bindings[pattern.decreases]) if pattern.decreases else None
        ancestor = next((entry for entry in reversed(record.stack) if entry[0] == pattern.name), None)
        if ancestor and (measure is None or ancestor[1] is None or measure >= ancestor[1]):
            self.error('nonterminating_pattern', 'Recursive composition must strictly decrease its declared finite list', application.name)
            return
        if ancestor and (record.pattern is None or not self.records['patterns'][record.pattern].value.decreases
                         or self.records['patterns'][record.pattern].value.decreases not in record.guards):
            self.error('nonterminating_pattern', 'A recursive call must occur inside its nonempty list guard', application.name)
            return
        depth = record.depth + 1
        stack = record.stack + ((pattern.name, measure),)
        if pattern.body:
            self.block(pattern.body, application.name, bindings, pattern.name, application.name, depth, stack)
        else:
            value = Argument(application.name, pattern.conclusion, pattern.reasoning, pattern.evidence,
                             pattern.assumptions, pattern.premises, pattern.binding,
                             ArgumentOrigin(pattern.name, application.name))
            self.register(value, '', bindings, record.span, pattern.name, application.name, depth, stack, source_file=record.source_file)

    def run(self):
        self.block(self.program.authored)
        for record in list(self.records['patterns'].values()):
            self.check_template(record)
        graph = {}
        for caller, called, *_ in self.calls:
            graph.setdefault(caller, set()).add(called)
        def reaches(start, goal):
            pending, seen = [start], set()
            while pending:
                node = pending.pop()
                if node == goal:
                    return True
                if node not in seen:
                    seen.add(node)
                    pending.extend(graph.get(node, ()))
            return False
        for caller, called, parameters, supplied, guards in self.calls:
            if reaches(called, caller):
                source = self.records['patterns'].get(caller)
                target = self.records['patterns'].get(called)
                if source and target:
                    a, b = source.value.decreases, target.value.decreases
                    if not a or not b or a not in guards or supplied.get(b) != 'tail(' + a + ')':
                        self.error('nonterminating_pattern', 'Every call in a recursive component must pass a guarded decreasing tail', caller)
        done = set()
        if len(self.records['applications']) > current_limits().applications:
            self.error('resource_limit', 'Pattern application budget exceeded')
            done.update(self.records['applications'])
        while True:
            pending = [record for name, record in self.records['applications'].items() if name not in done]
            if not pending:
                break
            for record in pending:
                done.add(record.value.name)
                self.expand(record)
        if any(error.code == 'resource_limit' for error in self.errors):
            # Exhaustion never exposes a seemingly complete partial expansion.
            for records in self.records.values():
                for name in list(records):
                    if records[name].application:
                        del records[name]
            self.generated = []
        tables = {name: {key: self.resolved(record) for key, record in records.items()}
                  for name, records in self.records.items()}
        directives = tuple(self.resolved(record) for record in self.directives)
        def body_count(block):
            count = 0
            for declaration in block.declarations:
                value = declaration.value
                if isinstance(value, Context):
                    count += body_count(value.body)
                else:
                    count += 1
                    if isinstance(value, (Module, SourceImport, ArgumentBlock, PatternGuard, Pattern)) and getattr(value, 'body', None):
                        count += body_count(value.body)
                    if isinstance(value, PatternGuard) and value.otherwise:
                        count += body_count(value.otherwise)
            return count
        definitions = sum(body_count(pattern.body) if pattern.body else 1 for pattern in tables['patterns'].values())
        count = sum(len(table) for table in tables.values()) + definitions + len(directives)
        return replace(self.program, **tables, argumentation_directives=directives, duplicates=tuple(self.duplicates),
                       locations=self.locations, generated=tuple(self.generated), lowering_diagnostics=tuple(self.errors),
                       declaration_count=count, source_files=self.source_files)


@bounded
def lower_program(program):
    if program.authored is None:
        from .abstractions import lower_patterns
        return lower_patterns(program)
    return _Lowerer(program).run()
