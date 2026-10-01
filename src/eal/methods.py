"""Host-registered versioned methods, typed contracts and bounded execution.

Source selects an installed contract; it cannot import code. Extension functions
are trusted pure host code. A process boundary enforces execution/output limits,
but is not a filesystem or network security sandbox.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
import hashlib
import inspect
import json
import math
import multiprocessing
import os
import re
import signal
from types import CodeType
from typing import Callable

_ID = re.compile(r'[A-Za-z][A-Za-z0-9_.-]*(?:/[A-Za-z][A-Za-z0-9_.-]*)*/[1-9][0-9]*\Z')
_SCHEMA_KEYS = {'type', 'properties', 'required', 'additionalProperties', 'items', 'minItems', 'maxItems',
                'minimum', 'maximum', 'minLength', 'maxLength', 'enum', 'anyOf'}


def is_method_identifier(value):
    """Whether a reference names an exact positive-integer contract version."""
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def schema_errors(value, schema, path='$', *, max_nodes=100_000, max_depth=64):
    """Validate a small documented JSON-schema subset; bool is never a number."""
    errors = []
    budget = [max_nodes]

    def consume(depth):
        budget[0] -= 1
        if budget[0] < 0 or depth > max_depth:
            raise ValueError('Typed schema resource limit exceeded')

    def equal(left, right, depth):
        """Compare JSON recursively without Python's True == 1 coercion."""
        consume(depth)
        if type(left) is not type(right):
            return False
        if type(left) is dict:
            return left.keys() == right.keys() and all(
                equal(value, right[key], depth + 1) for key, value in left.items())
        if type(left) is list:
            return len(left) == len(right) and all(
                equal(a, b, depth + 1) for a, b in zip(left, right))
        return left == right

    def check(item, spec, location, depth):
        consume(depth)
        if 'anyOf' in spec:
            for choice in spec['anyOf']:
                previous = len(errors)
                check(item, choice, location, depth + 1)
                if len(errors) == previous:
                    return
                del errors[previous:]
            errors.append(f'{location}: no declared alternative type matches')
            return
        kind = spec.get('type')
        checks = {'object': lambda: type(item) is dict, 'array': lambda: type(item) is list,
                  'string': lambda: type(item) is str, 'boolean': lambda: type(item) is bool,
                  'number': lambda: type(item) in (int, float) and math.isfinite(item),
                  'integer': lambda: type(item) is int, 'null': lambda: item is None,
                  'json': lambda: item is None or type(item) in (str, bool, int, float, list, dict)}
        if kind not in checks or not checks[kind]():
            errors.append(f'{location}: expected {kind}')
            return
        if isinstance(item, float) and not math.isfinite(item):
            errors.append(f'{location}: numbers must be finite')
            return
        if 'enum' in spec and not any(equal(item, value, depth) for value in spec['enum']):
            errors.append(f'{location}: value is outside the declared enumeration')
        if type(item) in (int, float):
            if 'minimum' in spec and item < spec['minimum'] or 'maximum' in spec and item > spec['maximum']:
                errors.append(f'{location}: number is outside declared bounds')
        elif type(item) is str:
            if not spec.get('minLength', 0) <= len(item) <= spec.get('maxLength', 4096):
                errors.append(f'{location}: string length is outside declared bounds')
        elif type(item) is list:
            if not spec.get('minItems', 0) <= len(item) <= spec.get('maxItems', 10_000):
                errors.append(f'{location}: array length is outside declared bounds')
            for index, child in enumerate(item):
                check(child, spec.get('items', {'type': 'json'}), f'{location}[{index}]', depth + 1)
        elif type(item) is dict:
            if len(item) > 10_000 or any(type(key) is not str for key in item):
                errors.append(f'{location}: object requires at most 10000 string keys')
                return
            properties = spec.get('properties', {})
            for key in spec.get('required', ()):
                if key not in item:
                    errors.append(f'{location}.{key}: required field is missing')
            for key, child in item.items():
                if key in properties:
                    check(child, properties[key], f'{location}.{key}', depth + 1)
                else:
                    additional = spec.get('additionalProperties', {'type': 'json'} if kind == 'json' else False)
                    if additional is False:
                        errors.append(f'{location}.{key}: undeclared field')
                    else:
                        check(child, additional, f'{location}.{key}', depth + 1)

    try:
        check(value, schema, path, 0)
    except (ValueError, OverflowError, RecursionError) as exc:
        errors.append(f'{path}: {exc}')
    return errors[:32]


def _check_schema(schema, depth=0):
    if depth > 32 or not isinstance(schema, dict) or set(schema) - _SCHEMA_KEYS:
        raise ValueError('Invalid or unsupported method schema')
    if 'anyOf' in schema:
        if set(schema) != {'anyOf'} or not isinstance(schema['anyOf'], list) or not 1 <= len(schema['anyOf']) <= 16:
            raise ValueError('anyOf requires 1..16 alternatives')
        for choice in schema['anyOf']:
            _check_schema(choice, depth + 1)
        return
    if schema.get('type') not in ('object', 'array', 'string', 'number', 'integer', 'boolean', 'null', 'json'):
        raise ValueError('Method schema requires a supported explicit type')
    if 'properties' in schema:
        if type(schema['properties']) is not dict or any(type(key) is not str for key in schema['properties']):
            raise ValueError('Schema properties must map names to schemas')
        for child in schema['properties'].values():
            _check_schema(child, depth + 1)
    if 'required' in schema:
        required = schema['required']
        if type(required) is not list or any(type(key) is not str for key in required) or len(set(required)) != len(required) or not set(required) <= set(schema.get('properties', {})):
            raise ValueError('Schema required fields must uniquely name declared properties')
    if 'additionalProperties' in schema and schema['additionalProperties'] is not False:
        _check_schema(schema['additionalProperties'], depth + 1)
    if 'items' in schema:
        _check_schema(schema['items'], depth + 1)
    for key in ('minItems', 'maxItems', 'minLength', 'maxLength'):
        if key in schema and (type(schema[key]) is not int or not 0 <= schema[key] <= 100_000):
            raise ValueError('Schema lengths must be bounded nonnegative integers')
    for key in ('minimum', 'maximum'):
        if key in schema and (type(schema[key]) not in (int, float) or not math.isfinite(schema[key])):
            raise ValueError('Schema numerical bounds must be finite numbers')
    for low, high in (('minItems', 'maxItems'), ('minLength', 'maxLength'), ('minimum', 'maximum')):
        if low in schema and high in schema and schema[low] > schema[high]:
            raise ValueError('Schema lower bound cannot exceed its upper bound')
    if 'enum' in schema and (type(schema['enum']) is not list or not 1 <= len(schema['enum']) <= 128):
        raise ValueError('Schema enum must have 1..128 finite JSON entries')
    _canonical(schema)


def _source_digest(function):
    try:
        source = inspect.getsource(function).encode('utf-8')
    except (OSError, TypeError):
        # The supplied implementation_version remains required for dependencies
        # and dynamically generated callables whose source cannot be recovered.
        source = f'{function.__module__}:{function.__qualname__}'.encode('utf-8')
    return hashlib.sha256(source).hexdigest()


def _code_digest(function):
    """Hash executable code without marshal's mutable object-reference flags.

    CPython may intern constants while executing nested functions. Marshalling a
    code object can then produce different bytes even though its code is
    unchanged. Explicitly serialise the stable executable attributes instead.
    """
    def constant(value):
        kind = type(value)
        if kind is CodeType:
            return ['code', code(value)]
        if kind is slice:
            return ['slice', constant(value.start), constant(value.stop),
                    constant(value.step)]
        if kind in (tuple, frozenset):
            values = [constant(item) for item in value]
            if kind is frozenset:
                values.sort(key=lambda item: json.dumps(item, sort_keys=True))
            return [kind.__name__, values]
        if kind is bytes:
            return ['bytes', value.hex()]
        if kind is float:
            return ['float', value.hex()]
        if kind is complex:
            return ['complex', value.real.hex(), value.imag.hex()]
        if value is Ellipsis:
            return ['ellipsis']
        if value is None or kind in (str, bool, int):
            return [kind.__name__, value]
        raise ValueError(f'Unsupported method code constant {kind.__name__}')

    def code(value):
        attributes = ('co_argcount', 'co_posonlyargcount', 'co_kwonlyargcount',
                      'co_nlocals', 'co_stacksize', 'co_flags', 'co_names',
                      'co_varnames', 'co_freevars', 'co_cellvars')
        return {**{key: getattr(value, key) for key in attributes},
                'co_code': value.co_code.hex(),
                'co_exceptiontable': value.co_exceptiontable.hex(),
                'co_consts': [constant(item) for item in value.co_consts]}

    encoded = json.dumps(code(function.__code__), sort_keys=True,
                         separators=(',', ':'), ensure_ascii=True).encode('ascii')
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class MethodContract:
    identifier: str
    evidence_kind: str | None
    input_schema: dict
    query_schema: dict
    output_schema: dict
    outputs: dict[str, str]
    quantities: tuple[str, ...]
    exact_unit: bool
    implementation: Callable[[dict], dict] = field(repr=False, compare=False)
    implementation_version: str
    timeout_seconds: float = 1.0
    max_input_bytes: int = 1024 * 1024
    max_output_bytes: int = 1024 * 1024
    max_memory_bytes: int = 256 * 1024 * 1024
    builtin_mode: str | None = field(default=None, repr=False)
    _source_identity: str | None = field(default=None, init=False, repr=False)
    _code_identity: str | None = field(default=None, init=False, repr=False)

    @property
    def query_fields(self):
        return tuple(self.query_schema.get('properties', {}))

    def describe(self):
        return {'identifier': self.identifier, 'evidence_kind': self.evidence_kind,
                'input_schema': deepcopy(self.input_schema), 'query_schema': deepcopy(self.query_schema),
                'output_schema': deepcopy(self.output_schema), 'outputs': dict(self.outputs),
                'quantities': list(self.quantities), 'exact_unit': self.exact_unit,
                'quantity_interpretation': 'input measurement basis; each output separately declares its unit interpretation',
                'implementation_version': self.implementation_version,
                'implementation_source_digest': self._source_identity or _source_digest(self.implementation),
                'implementation_code_digest': self._code_identity or _code_digest(self.implementation),
                'limits': {'timeout_seconds': self.timeout_seconds, 'max_input_bytes': self.max_input_bytes,
                           'max_output_bytes': self.max_output_bytes, 'max_memory_bytes': self.max_memory_bytes,
                           'startup_timeout_seconds': 5.0},
                'execution': 'bounded_builtin' if self.builtin_mode else 'bounded_process'}

    def output_type(self, path):
        if path in self.outputs:
            return self.outputs[path]
        parent, _, child = path.rpartition('.')
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', child):
            return self.outputs.get(parent + '.*')
        return None


class MethodRegistry:
    """Copy-on-extension host registry; identifiers cannot replace existing code."""
    def __init__(self, contracts=()):
        self._contracts = {}
        for contract in contracts:
            self._add(contract)

    def _add(self, contract):
        from .propositions import QUANTITIES
        if not isinstance(contract, MethodContract) or not is_method_identifier(contract.identifier):
            raise ValueError('Method identifier requires a name and positive integer version')
        if contract.identifier in self._contracts:
            raise ValueError(f'Method {contract.identifier!r} is already registered')
        if not inspect.isfunction(contract.implementation) or not isinstance(contract.implementation_version, str) or not contract.implementation_version.strip():
            raise ValueError('Method requires a Python function and explicit implementation version')
        if '<locals>' in contract.implementation.__qualname__ or '<lambda>' in contract.implementation.__qualname__ or contract.implementation.__module__ == '__main__':
            raise ValueError('Method implementation must be an importable module-level function')
        if contract.builtin_mode is not None:
            from .builtin_methods import BUILTIN_SPECS
            from .reasoning import BUILTIN_STRATEGIES
            spec = BUILTIN_SPECS.get(contract.builtin_mode)
            strategy = BUILTIN_STRATEGIES.get(contract.builtin_mode)
            expected = strategy.compute if strategy is not None else None
            if spec is None or contract.identifier != spec.identifier or contract.implementation is not expected:
                raise ValueError('Built-in method identities are reserved')
        elif contract.evidence_kind is None:
            raise ValueError('Custom methods require a computational evidence kind')
        if contract.evidence_kind is not None and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', contract.evidence_kind):
            raise ValueError('Method evidence kind must be an identifier')
        for schema in (contract.input_schema, contract.query_schema, contract.output_schema):
            _check_schema(schema)
            if schema.get('type') != 'object':
                raise ValueError('Input, query and output contracts require object schemas')
        query = contract.query_schema
        if query.get('additionalProperties') is not False or set(query.get('required', ())) != set(query.get('properties', {})):
            raise ValueError('Every query property must be required and additional query properties forbidden')
        if not set(query.get('properties', {})) <= set(contract.input_schema.get('properties', {})):
            raise ValueError('Each query field must be a declared input field')
        for key, schema in query.get('properties', {}).items():
            if key not in contract.input_schema.get('required', ()):
                raise ValueError(f'Each query field must be required by the input contract: {key!r}')
            if _canonical(schema) != _canonical(contract.input_schema['properties'][key]):
                raise ValueError(f'Each query field must use the identical input schema: {key!r}')
        if type(contract.exact_unit) is not bool or not set(contract.quantities) <= set(QUANTITIES):
            raise ValueError('Method requires known quantities and an explicit exact_unit flag')
        if type(contract.timeout_seconds) not in (int, float) or not 0 < contract.timeout_seconds <= 60:
            raise ValueError('Method timeout must be in (0, 60] seconds')
        if any(type(value) is not int or not 1024 <= value <= 16 * 1024 * 1024 for value in (contract.max_input_bytes, contract.max_output_bytes)):
            raise ValueError('Method input/output limits must be 1 KiB..16 MiB')
        if type(contract.max_memory_bytes) is not int or not 64 * 1024 * 1024 <= contract.max_memory_bytes <= 4 * 1024**3:
            raise ValueError('Method memory limit must be 64 MiB..4 GiB')
        for path, kind in contract.outputs.items():
            if kind not in ('boolean', 'basis', 'dimensionless'):
                raise ValueError('Typed outputs require boolean, basis or dimensionless interpretation')
            current = contract.output_schema
            for part in path.split('.'):
                current = (current.get('additionalProperties', {}) if part == '*' else current.get('properties', {}).get(part, {}))
                if not isinstance(current, dict):
                    current = {}
            if current.get('type') not in (('boolean',) if kind == 'boolean' else ('number', 'integer')):
                raise ValueError(f'Typed output {path!r} does not match its output schema')
        copied = deepcopy(contract)
        if copied._source_identity is None:
            object.__setattr__(copied, '_source_identity', _source_digest(copied.implementation))
        if copied._code_identity is None:
            object.__setattr__(copied, '_code_identity', _code_digest(copied.implementation))
        self._contracts[contract.identifier] = copied

    def with_method(self, contract):
        if not isinstance(contract, MethodContract):
            raise ValueError('Extensions require a MethodContract')
        if contract.builtin_mode is not None:
            raise ValueError('Extensions cannot define built-in execution profiles')
        return MethodRegistry([*self._contracts.values(), contract])

    def get(self, identifier):
        """Resolve an exact versioned identifier; no aliases or version inference."""
        value = self._contracts.get(identifier) if isinstance(identifier, str) else None
        return deepcopy(value) if value is not None else None

    def describe(self):
        return {key: self._contracts[key].describe() for key in sorted(self._contracts)}

    @property
    def fingerprint(self):
        return hashlib.sha256(_canonical(self.describe())).hexdigest()


def check_implementation_identity(contract):
    """Reject entry-point code changed after the registry captured its identity."""
    if (contract._code_identity is not None and
            _code_digest(contract.implementation) != contract._code_identity):
        raise ValueError('Loaded method implementation differs from its registered code identity')


def _worker(payload, connection, contract, limits):
    try:
        os.setsid()
        import resource
        # RLIMIT_CPU is cumulative from process birth. Spawn reimports the
        # launcher before reaching this function, so charge only subsequent
        # CPU against the callback allowance. The parent separately bounds
        # startup and execution wall time.
        usage = resource.getrusage(resource.RUSAGE_SELF)
        cpu_limit = math.ceil(usage.ru_utime + usage.ru_stime + contract.timeout_seconds)
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
        resource.setrlimit(resource.RLIMIT_AS, (contract.max_memory_bytes, contract.max_memory_bytes))
        # Pure callbacks receive a detached JSON object and return only their
        # typed outputs. Child stdout/stderr cannot corrupt the MCP transport.
        with open(os.devnull, 'wb') as sink:
            os.dup2(sink.fileno(), 1)
            os.dup2(sink.fileno(), 2)
        check_implementation_identity(contract)
        connection.send_bytes(b'{"ready":true}')
        from .limits import using_limits
        with using_limits(limits):
            output = contract.implementation(payload)
        encoded = _canonical({'ok': True, 'output': output})
        if len(encoded) > contract.max_output_bytes:
            raise ValueError('Method output exceeds byte limit')
        connection.send_bytes(encoded)
    except BaseException as exc:
        try:
            from .limits import BudgetExceeded
            connection.send_bytes(_canonical({'ok': False, 'incomplete': isinstance(exc, (BudgetExceeded, MemoryError)),
                                              'error': f'{type(exc).__name__}: {str(exc)[:512]}'}))
        except BaseException:
            pass
    finally:
        connection.close()


def execute_extension(contract, payload):
    """Run one custom pure callback in a fresh, bounded POSIX worker."""
    from .limits import current_limits, BudgetExceeded
    try:
        encoded = _canonical(payload)
        if len(encoded) > contract.max_input_bytes:
            raise ValueError('Method input exceeds byte limit')
        errors = schema_errors(payload, contract.input_schema)
        if errors:
            raise ValueError('; '.join(errors))
        if os.name != 'posix':
            raise ValueError('Bounded custom methods require POSIX resource limits')
        context = multiprocessing.get_context('spawn')
        reader, writer = context.Pipe(duplex=False)
        worker = context.Process(target=_worker, args=(json.loads(encoded), writer, contract, current_limits()), daemon=True)
        worker.start()
        writer.close()
        try:
            if not reader.poll(5.0):
                raise BudgetExceeded('Method worker startup exceeded its timeout')
            startup = json.loads(reader.recv_bytes(contract.max_output_bytes))
            if startup != {'ready': True}:
                raise ValueError(f"Method worker startup failed: {startup.get('error', 'invalid startup message')}")
            if not reader.poll(contract.timeout_seconds):
                raise BudgetExceeded('Method execution exceeded its timeout')
            response = json.loads(reader.recv_bytes(contract.max_output_bytes))
            if not response['ok']:
                if response.get('incomplete'):
                    raise BudgetExceeded(response['error'])
                raise ValueError(f"Method execution failed: {response['error']}")
            output = response['output']
            errors = schema_errors(output, contract.output_schema)
            if errors:
                raise ValueError('Method output contract violation: ' + '; '.join(errors))
            return {'status': 'supported', 'reasons': [f'Computed registered method {contract.identifier}'],
                    'details': output, 'method_contract': contract.describe()}
        finally:
            reader.close()
            if worker.is_alive():
                try:
                    os.killpg(worker.pid, signal.SIGKILL)
                except ProcessLookupError:
                    worker.kill()
            worker.join(timeout=1)
            if worker.is_alive():
                worker.kill()
                worker.join(timeout=1)
    except (ValueError, TypeError, OverflowError, RecursionError, OSError, EOFError, KeyError) as exc:
        return {'status': 'incomplete' if isinstance(exc, BudgetExceeded) else 'unsupported',
                'reasons': [str(exc) or f'Method worker failed ({type(exc).__name__})'], 'details': {}, 'method_contract': contract.describe()}


@lru_cache(maxsize=1)
def default_registry():
    """Built-in methods use the same exact versioned references as extensions."""
    from .builtin_methods import BUILTIN_SPECS
    from .reasoning import BUILTIN_STRATEGIES
    from .propositions import QUANTITIES
    if set(BUILTIN_STRATEGIES) != set(BUILTIN_SPECS):
        raise ValueError('Each built-in strategy requires one versioned specification')
    contracts = []
    for mode, strategy in BUILTIN_STRATEGIES.items():
        spec = BUILTIN_SPECS[mode]
        query_schema, output_schema = spec.contract_schemas()
        quantities = (spec.quantities if spec.quantities is not None else
                      tuple(q for q in QUANTITIES if q != 'proposition'))
        contracts.append(MethodContract(spec.identifier, spec.evidence_kind, spec.input_schema,
                         query_schema, output_schema, spec.outputs, quantities,
                         spec.exact_unit, strategy.compute, spec.implementation_version,
                         builtin_mode=mode))
    return MethodRegistry(contracts)
