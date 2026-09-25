"""A strict JSON spelling of the EAL/2 typed declarations used in this study.

Both front ends run through the same EAL formatter, static semantics and MCP
server. This version deliberately excludes patterns/applications; admitting a
new EAL construct requires a separately versioned front end and parity review.
"""

from __future__ import annotations

from dataclasses import asdict, fields, is_dataclass
import json
from types import UnionType
from typing import Any, get_args, get_origin, get_type_hints

from eal.formatter import format_program, semantic_ir
from eal.model import (Argument, Assumption, Claim, Environment, Evidence,
                       Objection, Program, Reasoning, Tool)
from eal.parser import parse


SCHEMA = "eal2-ci-json-frontend/1"
GROUPS = {"environments": Environment, "tools": Tool, "evidence": Evidence,
          "assumptions": Assumption, "reasoning": Reasoning, "claims": Claim,
          "arguments": Argument, "objections": Objection}


class FrontendError(ValueError):
    pass


def _typed(value: Any, expected: Any, location: str) -> Any:
    if expected is Any:
        return value
    origin = get_origin(expected)
    if origin is UnionType:
        options = get_args(expected)
        for option in options:
            try:
                return _typed(value, option, location)
            except FrontendError:
                pass
        raise FrontendError(f"{location}: wrong union type")
    if origin is tuple:
        if type(value) is not list:
            raise FrontendError(f"{location}: expected JSON array")
        item_type = get_args(expected)[0]
        return tuple(_typed(item, item_type, f"{location}[{index}]")
                       for index, item in enumerate(value))
    if origin is dict:
        if type(value) is not dict:
            raise FrontendError(f"{location}: expected object")
        key_type, item_type = get_args(expected)
        return {_typed(key, key_type, f"{location} key"):
                _typed(item, item_type, f"{location}[{key!r}]")
                for key, item in value.items()}
    if isinstance(expected, type) and is_dataclass(expected):
        if type(value) is not dict:
            raise FrontendError(f"{location}: expected declaration object")
        required = {field.name for field in fields(expected)}
        if set(value) != required:
            raise FrontendError(f"{location}: fields must be {sorted(required)}")
        hints = get_type_hints(expected)
        return expected(**{name: _typed(value[name], hints[name], f"{location}.{name}")
                           for name in required})
    if expected is float and type(value) in (int, float):
        return float(value)
    if type(value) is not expected:
        raise FrontendError(f"{location}: expected {expected}")
    return value


def compile_json(document: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return EAL text and its canonical typed meaning; reject silent lowering.

    The model authors typed declarations, not an embedded EAL source string.
    `format_program` and `parse` must agree on the semantic IR before a tool
    can be acquired. A model-authored digest or generated declaration is never
    accepted as a substitute for the host's identity.
    """
    if type(document) is not dict or set(document) != {"schema", "language", "declarations"}:
        raise FrontendError("JSON front end requires schema, language and declarations")
    if document["schema"] != SCHEMA or document["language"] != "EAL/2":
        raise FrontendError("Unsupported JSON front end or language version")
    data = document["declarations"]
    if type(data) is not dict or set(data) != set(GROUPS):
        raise FrontendError("JSON declarations require the exact supported groups")
    groups = {}
    names = set()
    for kind, cls in GROUPS.items():
        entries = data[kind]
        if type(entries) is not dict:
            raise FrontendError(f"{kind}: expected named declarations")
        groups[kind] = {}
        for name, value in entries.items():
            if type(name) is not str or name in names:
                raise FrontendError("Declaration names must be unique strings")
            names.add(name)
            declaration = _typed(value, cls, f"{kind}.{name}")
            if declaration.name != name:
                raise FrontendError(f"{kind}.{name}: dictionary key differs from declaration name")
            groups[kind][name] = declaration
    authored = Program("EAL/2", "0" * 64, **groups,
                       declaration_count=len(names))
    source = format_program(authored)
    canonical = parse(source)
    if semantic_ir(canonical) != semantic_ir(authored):
        raise FrontendError("JSON-to-EAL semantic round trip changed the typed program")
    return source, semantic_ir(canonical)


def from_source(source: str) -> dict[str, Any]:
    """Study fixture helper; never give a generated answer to a model arm."""
    program = parse(source)
    if program.patterns or program.applications or program.duplicates:
        raise FrontendError("This version supports direct declarations only")
    document = {"schema": SCHEMA, "language": program.language,
                "declarations": {kind: {name: json.loads(json.dumps(asdict(value)))
                                        for name, value in getattr(program, kind).items()}
                                 for kind in GROUPS}}
    compile_json(document)
    return document


def frontend_contract() -> dict[str, Any]:
    """Bounded, versioned schema plus a source-independent worked JSON shape."""
    from eal.discovery import EXAMPLE
    return {"schema": SCHEMA, "language": "EAL/2",
            "top_level": ["schema", "language", "declarations"],
            "declaration_groups": {
                kind: {field.name: str(get_type_hints(cls)[field.name])
                       for field in fields(cls)}
                for kind, cls in GROUPS.items()},
            "example": from_source(EXAMPLE),
            "restriction": "Direct declarations only; patterns/applications are not in this version"}
