"""Bound and validate JSON evidence used by built-in calculations."""
from __future__ import annotations

import re

MAX_ITEMS = 10_000
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")


def _object(value, fields, label):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f"{label} requires exactly these fields: {', '.join(fields)}")
    return value


def _list(value, label, minimum=1, maximum=MAX_ITEMS):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f"{label} must be a list with {minimum}..{maximum} entries")
    return value


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    if not -1e100 <= value <= 1e100:
        raise ValueError(f"{label} must be finite and within [-1e100, 1e100]")
    return value


def _integer(value, label, minimum=0, maximum=1_000_000_000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be an integer in [{minimum}, {maximum}]")
    return value


def _name(value, label):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be an identifier of at most 64 characters")
    return value


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError(f"{label} must contain 1..4096 characters and be nonblank")
    return value


def _probability(value, label):
    value = _number(value, label)
    if not 0 <= value <= 1:
        raise ValueError(f"{label} must be in [0, 1]")
    return value


def _result(ok, reason, **details):
    return {"status": "supported" if ok else "unsupported",
            "reasons": [reason], "details": details}


def _check_json(value):
    """Bound every input before mode-specific traversal, including cycles."""
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if count > 100_000 or depth > 64:
            raise ValueError("Evidence exceeds JSON node or depth limits")
        if item is None or isinstance(item, bool):
            continue
        if isinstance(item, str):
            if len(item) > 4096:
                raise ValueError("Evidence strings are limited to 4096 characters")
            item.encode("utf-8")
        elif isinstance(item, (int, float)):
            _number(item, "Evidence number")
        elif isinstance(item, dict):
            if len(item) > MAX_ITEMS:
                raise ValueError("Evidence object exceeds member limit")
            for key, child in item.items():
                if not isinstance(key, str) or len(key) > 4096:
                    raise ValueError("Evidence object keys must be bounded strings")
                key.encode("utf-8")
                pending.append((child, depth + 1))
        elif isinstance(item, list):
            if len(item) > MAX_ITEMS:
                raise ValueError("Evidence list exceeds entry limit")
            pending.extend((child, depth + 1) for child in item)
        else:
            raise ValueError("Evidence must contain only JSON values")
