"""Closed pure expressions with strict scalar types and explicit unknown values."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
import math
import json
import operator
import re

from .limits import current_limits, BudgetExceeded
from .model import Expression, Predicate

COMPARATORS = {'==', '!=', '<', '<=', '>', '>='}
FUNCTIONS = {'field': (1, 1), 'literal': (1, 1), 'count': (1, 1), 'sum': (1, 1),
             'min': (1, None), 'max': (1, None), 'abs': (1, 1), 'all': (1, 1),
             'any': (1, 1), 'quantity': (2, 2)}
UNKNOWN = object()


@dataclass(frozen=True)
class Quantity:
    amount: Fraction
    dimensions: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class ExpressionResult:
    value: object = UNKNOWN
    reason: str = ''
    issue: str | None = None

    @property
    def known(self):
        return self.value is not UNKNOWN


def numeric(value):
    return type(value) in (int, float, Fraction) and (type(value) is not float or math.isfinite(value))


def predicate_expression(predicate):
    return predicate.expression or Expression('binary', predicate.operator, (
        Expression('field', predicate.path), Expression('literal', predicate.expected)))


def make_predicate(expression):
    # A directly quoted left key keeps its established field-path denotation.
    if expression.kind == 'binary' and expression.value in COMPARATORS:
        left, right = expression.arguments
        if left.kind == 'literal' and type(left.value) is str:
            left = Expression('field', left.value)
            expression = Expression('binary', expression.value, (left, right))
        if left.kind == 'field' and right.kind == 'literal' and re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*(\.[A-Za-z_][A-Za-z_0-9]*)*', left.value):
            return Predicate(left.value, expression.value, right.value)
    return Predicate('', 'expression', None, expression)


def nodes(expression):
    pending = [(expression, 1)]
    visited = 0
    while pending:
        node, depth = pending.pop()
        visited += 1
        if visited > current_limits().expression_nodes:
            raise BudgetExceeded('Expression node budget exceeded')
        if depth > current_limits().expression_depth:
            raise BudgetExceeded('Expression depth budget exceeded')
        yield node
        pending.extend((child, depth + 1) for child in reversed(node.arguments))


def predicate_paths(predicate):
    return tuple(dict.fromkeys(node.value for node in nodes(predicate_expression(predicate))
                               if node.kind == 'field'))


def schema_at(schema, path):
    if schema is None or schema.get('type') == 'json':
        return None
    if 'anyOf' in schema:
        choices = [schema_at(choice, path) for choice in schema['anyOf']]
        return None if None in choices else {'anyOf': choices}
    if not path:
        return schema
    if schema.get('type') != 'object':
        return {}
    first, *rest = path
    child = schema.get('properties', {}).get(first, schema.get('additionalProperties', False))
    return schema_at(child, rest) if isinstance(child, dict) else {}


def expression_errors(expression, schema=None):
    errors = []
    try:
        list(nodes(expression))
    except (BudgetExceeded, AttributeError, TypeError) as exc:
        return [str(exc)]

    def types(node):
        kind, value, args = node.kind, node.value, node.arguments
        if kind == 'literal':
            if args:
                errors.append('A literal cannot have operands')
            from .semantics import _check_json_resources
            try:
                _check_json_resources(value)
            except (ValueError, TypeError, UnicodeError):
                errors.append('An expression literal requires finite JSON')
            return {bool: {'boolean'}, int: {'number'}, float: {'number'}, str: {'string'},
                    type(None): {'null'}, list: {'array'}, dict: {'object'}}.get(type(value), set())
        if kind == 'field':
            if args or type(value) is not str or not value or any(not part for part in value.split('.')):
                errors.append('A field requires a nonempty literal property path')
            spec = schema_at(schema, value.split('.')) if type(value) is str else {}
            if spec is None:
                return None
            if 'anyOf' in spec:
                result = {choice.get('type') for choice in spec['anyOf']}
            else:
                result = {spec['type']} if spec.get('type') else set()
            result = {'number' if item == 'integer' else item for item in result}
            if not result:
                errors.append(f'No declared output exists at {value!r}')
            return result
        if kind == 'unary':
            if value not in ('not', '+', '-') or len(args) != 1:
                errors.append('Unknown unary operator or operand count')
                return set()
            actual = types(args[0])
            allowed = {'boolean'} if value == 'not' else {'number', 'quantity'}
            if actual is not None and not actual <= allowed:
                errors.append(f'Operator {value!r} requires {" or ".join(sorted(allowed))}')
            return {'boolean'} if value == 'not' else actual
        if kind == 'binary':
            if value not in COMPARATORS | {'and', 'or', '+', '-', '*', '/', '%'} or len(args) != 2:
                errors.append('Unknown binary operator or operand count')
                return set()
            left, right = map(types, args)
            if value in ('and', 'or'):
                if any(actual is not None and actual != {'boolean'} for actual in (left, right)):
                    errors.append(f'Operator {value!r} requires Boolean operands')
                return {'boolean'}
            if value in COMPARATORS:
                if left is not None and right is not None and not left & right:
                    errors.append('Comparison operands have incompatible types')
                allowed = {'number', 'string', 'boolean', 'null', 'quantity'} if value in ('==', '!=') else {'number', 'string', 'quantity'}
                if any(actual is not None and not actual <= allowed for actual in (left, right)):
                    errors.append('Comparison requires compatible scalar operands')
                return {'boolean'}
            if any(actual is not None and not actual <= {'number', 'quantity'} for actual in (left, right)):
                errors.append('Arithmetic requires finite numbers or quantities')
            return {'quantity'} if left == {'quantity'} or right == {'quantity'} else {'number'}
        if kind == 'call':
            if value == 'field':
                errors.append('A field lookup must use the canonical field expression node')
                return set()
            if value not in FUNCTIONS:
                errors.append(f'Unknown pure expression function {value!r}')
                return set()
            low, high = FUNCTIONS[value]
            if len(args) < low or high is not None and len(args) > high:
                errors.append(f'Function {value!r} has an invalid argument count')
                return set()
            actual = [types(arg) for arg in args]
            if value == 'quantity':
                if actual[0] is not None and actual[0] != {'number'}:
                    errors.append('quantity requires a finite number')
                if args[1].kind != 'literal' or type(args[1].value) is not str:
                    errors.append('quantity requires a literal unit')
                else:
                    from .propositions import UNITS
                    if args[1].value not in UNITS:
                        errors.append(f'Unknown unit {args[1].value!r}')
                return {'quantity'}
            if value in ('count', 'sum', 'all', 'any') and actual[0] is not None and actual[0] != {'array'}:
                errors.append(f'{value} requires an array')
            if value in ('all', 'any'):
                return {'boolean'}
            if value in ('count', 'sum'):
                return {'number'}
            if value in ('min', 'max', 'abs'):
                if any(t is not None and not t <= {'number', 'quantity', 'array'} for t in actual):
                    errors.append(f'{value} requires numeric operands')
                return None if None in actual else {'quantity'} if {'quantity'} in actual else {'number'}
            return actual[0]
        errors.append(f'Unknown expression node {kind!r}')
        return set()

    try:
        result = types(expression)
    except RecursionError:
        return ['Expression exceeds the implementation recursion bound']
    if result is not None and result != {'boolean'}:
        errors.append('A required condition must produce a Boolean')
    # Unit literals establish dimensions even when their numerical inputs are
    # dynamic. Unknown JSON fields remain unknown until runtime typing.
    def dimensions(node):
        if node.kind == 'literal':
            return () if numeric(node.value) else None
        if node.kind == 'field':
            spec = schema_at(schema, node.value.split('.'))
            return () if spec and spec.get('type') in ('number', 'integer') else None
        if node.kind == 'call' and node.value == 'quantity':
            return _quantity(1, node.arguments[1].value).dimensions
        child = [dimensions(arg) for arg in node.arguments]
        if node.kind == 'unary' and node.value in ('+', '-'):
            return child[0]
        if node.kind == 'call' and node.value in ('abs', 'literal'):
            return child[0]
        if node.kind == 'call' and node.value in ('count', 'sum'):
            return ()
        if node.kind == 'call' and node.value in ('min', 'max'):
            known = [dim for dim in child if dim is not None]
            if known and any(dim != known[0] for dim in known):
                errors.append('Quantity dimensions are incompatible')
            return known[0] if known else None
        if node.kind == 'binary' and node.value in COMPARATORS | {'+', '-', '*', '/', '%'}:
            left, right = child
            if left is None or right is None:
                return None
            if node.value in COMPARATORS | {'+', '-', '%'}:
                if left != right:
                    errors.append('Quantity dimensions are incompatible')
                return left if node.value not in COMPARATORS else None
            combined = dict(left)
            for name, power in right:
                combined[name] = combined.get(name, 0) + power * (1 if node.value == '*' else -1)
            return tuple(sorted((name, power) for name, power in combined.items() if power))
        return None
    if not errors:
        try:
            dimensions(expression)
        except RecursionError:
            errors.append('Expression exceeds the implementation recursion bound')
    # Fully constant expressions also receive numerical and dimensional checks.
    if not any(node.kind == 'field' for node in nodes(expression)) and not errors:
        checked = evaluate_expression(expression, {})
        if not checked.known:
            errors.append(checked.reason)
    return errors


def _quantity(value, unit):
    from .propositions import UNITS
    if not numeric(value) or unit not in UNITS:
        raise ValueError('quantity requires a finite number and a registered unit')
    dimension, scale = UNITS[unit]
    dimensions = {'dimensionless': (), 'velocity': (('length', 1), ('time', -1)),
                  'volumetric_flow': (('length', 3), ('time', -1)),
                  'pressure': (('length', -1), ('mass', 1), ('time', -2))}
    return Quantity(Fraction(str(value)) * Fraction(scale), dimensions.get(dimension, ((dimension, 1),)))


def _arithmetic(symbol, left, right):
    if not isinstance(left, Quantity) and not isinstance(right, Quantity):
        if not numeric(left) or not numeric(right):
            raise ValueError('Arithmetic requires finite numbers')
        result = {'+': operator.add, '-': operator.sub, '*': operator.mul,
                  '/': operator.truediv, '%': operator.mod}[symbol](left, right)
        if not numeric(result):
            raise ValueError('Arithmetic result is not finite')
        return result
    left = left if isinstance(left, Quantity) else Quantity(Fraction(str(left)), ()) if numeric(left) else None
    right = right if isinstance(right, Quantity) else Quantity(Fraction(str(right)), ()) if numeric(right) else None
    if left is None or right is None:
        raise ValueError('Quantity arithmetic requires numerical operands')
    if symbol in ('+', '-', '%'):
        if left.dimensions != right.dimensions:
            raise ValueError('Quantity dimensions are incompatible')
        return Quantity({'+': operator.add, '-': operator.sub, '%': operator.mod}[symbol](left.amount, right.amount), left.dimensions)
    dimensions = dict(left.dimensions)
    for name, power in right.dimensions:
        dimensions[name] = dimensions.get(name, 0) + power * (1 if symbol == '*' else -1)
    return Quantity(operator.mul(left.amount, right.amount) if symbol == '*' else left.amount / right.amount,
                    tuple(sorted((name, power) for name, power in dimensions.items() if power)))


def _compare(symbol, left, right):
    if isinstance(left, Quantity) or isinstance(right, Quantity):
        if not isinstance(left, Quantity) or not isinstance(right, Quantity) or left.dimensions != right.dimensions:
            raise ValueError('Compared quantities have incompatible dimensions')
        left, right = left.amount, right.amount
    elif type(left) is not type(right) and not (numeric(left) and numeric(right)):
        raise ValueError('Compared values have incompatible types')
    if type(left) in (dict, list) or type(right) in (dict, list):
        raise ValueError('Comparison requires scalar values')
    if symbol not in ('==', '!=') and not (numeric(left) and numeric(right) or type(left) is str and type(right) is str):
        raise ValueError('Ordered comparison requires finite numbers, strings or quantities')
    if type(left) is float and not math.isfinite(left) or type(right) is float and not math.isfinite(right):
        raise ValueError('Compared numbers must be finite')
    return {'==': operator.eq, '!=': operator.ne, '<': operator.lt, '<=': operator.le,
            '>': operator.gt, '>=': operator.ge}[symbol](left, right)


def evaluate_expression(expression, value):
    visited = [0]

    def run(node, depth=1):
        visited[0] += 1
        if visited[0] > current_limits().expression_nodes:
            raise BudgetExceeded('Expression evaluation budget exceeded')
        if depth > current_limits().expression_depth:
            raise BudgetExceeded('Expression depth budget exceeded')
        if node.kind == 'literal':
            return ExpressionResult(node.value)
        if node.kind == 'field':
            actual = value
            for field in node.value.split('.'):
                if not isinstance(actual, Mapping) or field not in actual:
                    return ExpressionResult(reason=f'Field {node.value!r} is missing', issue='missing_field')
                actual = actual[field]
            return ExpressionResult(actual)
        args = [run(child, depth + 1) for child in node.arguments]
        invalid = next((arg for arg in args if not arg.known and arg.issue != 'missing_field'), None)
        if invalid:
            return invalid
        if node.kind == 'binary' and node.value in ('and', 'or'):
            if any(arg.known and type(arg.value) is not bool for arg in args):
                raise ValueError('Boolean composition requires Boolean operands')
            decisive = False if node.value == 'and' else True
            if any(arg.known and arg.value is decisive for arg in args):
                return ExpressionResult(decisive)
            unknown = next((arg for arg in args if not arg.known), None)
            return unknown or ExpressionResult(not decisive)
        unknown = next((arg for arg in args if not arg.known), None)
        if unknown:
            return unknown
        values = [arg.value for arg in args]
        if node.kind == 'unary':
            actual = values[0]
            if node.value == 'not':
                if type(actual) is not bool:
                    raise ValueError('Negation requires a Boolean')
                return ExpressionResult(not actual)
            if isinstance(actual, Quantity):
                return ExpressionResult(Quantity(actual.amount * (-1 if node.value == '-' else 1), actual.dimensions))
            if not numeric(actual):
                raise ValueError('Unary arithmetic requires a finite number')
            return ExpressionResult(-actual if node.value == '-' else actual)
        if node.kind == 'binary':
            return ExpressionResult(_compare(node.value, *values) if node.value in COMPARATORS else _arithmetic(node.value, *values))
        if node.kind == 'call':
            name = node.value
            if name == 'quantity':
                result = _quantity(*values)
            elif name == 'literal':
                result = values[0]
            elif name in ('count', 'sum', 'all', 'any'):
                items = values[0]
                if type(items) is not list:
                    raise ValueError(f'{name} requires an array')
                if name in ('all', 'any'):
                    if any(type(item) is not bool for item in items):
                        raise ValueError(f'{name} requires Boolean elements')
                    result = all(items) if name == 'all' else any(items)
                elif name == 'count':
                    result = len(items)
                else:
                    if any(not numeric(item) for item in items):
                        raise ValueError('sum requires finite numerical elements')
                    result = sum(items)
            elif name in ('min', 'max'):
                items = values[0] if len(values) == 1 and type(values[0]) is list else values
                if items and all(isinstance(item, Quantity) for item in items):
                    if any(item.dimensions != items[0].dimensions for item in items):
                        raise ValueError('Quantity dimensions are incompatible')
                    result = (min if name == 'min' else max)(items, key=lambda item: item.amount)
                elif not items or any(not numeric(item) for item in items):
                    raise ValueError(f'{name} requires nonempty finite numerical operands')
                else:
                    result = min(items) if name == 'min' else max(items)
            elif name == 'abs':
                actual = values[0]
                if not numeric(actual) and not isinstance(actual, Quantity):
                    raise ValueError('abs requires a number or quantity')
                result = Quantity(abs(actual.amount), actual.dimensions) if isinstance(actual, Quantity) else abs(actual)
            else:
                raise ValueError(f'Unknown pure function {name!r}')
            if type(result) is float and not math.isfinite(result):
                raise ValueError('Function result is not finite')
            return ExpressionResult(result)
        raise ValueError('Unknown expression node')

    try:
        return run(expression)
    except (ValueError, TypeError, ArithmeticError, RecursionError) as exc:
        return ExpressionResult(reason=str(exc), issue='invalid_expression')


def format_expression(expression, encode=None):
    encode = encode or (lambda value: json.dumps(value, ensure_ascii=False, allow_nan=False))
    if expression.kind == 'literal':
        return encode(expression.value)
    if expression.kind == 'field':
        from .semantics import _RESERVED_NAMES
        return expression.value if all(re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', p) and p not in _RESERVED_NAMES for p in expression.value.split('.')) else 'field(' + encode(expression.value) + ')'
    args = [format_expression(arg, encode) for arg in expression.arguments]
    if expression.kind == 'call':
        return expression.value + '(' + ', '.join(args) + ')'
    if expression.kind == 'unary':
        return '(' + expression.value + (' ' if expression.value == 'not' else '') + args[0] + ')'
    return '(' + args[0] + ' ' + expression.value + ' ' + args[1] + ')'
