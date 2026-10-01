"""Host-owned resource budgets, independent of source-language expressiveness."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, fields
from functools import wraps
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class ExecutionLimits:
    source_bytes: int = 1024 * 1024
    source_tokens: int = 100_000
    structural_values: int = 100_000
    declarations: int = 4096
    premise_depth: int = 128
    expansion_depth: int = 128
    applications: int = 1000
    expanded_references: int = 100_000
    expression_nodes: int = 10_000
    expression_depth: int = 128
    json_depth: int = 64
    json_nodes: int = 100_000
    record_bytes: int = 4 * 1024 * 1024
    collection_evidence: int = 128
    composed_edges: int = 131_072
    abstract_attacks: int = 65_536
    formal_premises: int = 64
    formal_rules: int = 64
    formal_antecedents: int = 8
    formal_atoms: int = 128
    formal_contraries: int = 128
    formal_arguments: int = 128
    formal_defeats: int = 4096
    formal_construction: int = 100_000
    extension_search: int = 100_000

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int or value < 1:
                raise ValueError(f"Budget {field.name} must be a positive integer")

    def describe(self):
        return asdict(self)

    @classmethod
    def load(cls, path: str | Path):
        with Path(path).open("rb") as source:
            supplied = tomllib.load(source)
        if set(supplied) != {"limits"} or type(supplied["limits"]) is not dict:
            raise ValueError("Budget file must contain exactly a [limits] table")
        return cls(**supplied["limits"])


_ACTIVE = ContextVar("eal_execution_limits", default=ExecutionLimits())


def current_limits() -> ExecutionLimits:
    return _ACTIVE.get()


@contextmanager
def using_limits(limits: ExecutionLimits):
    if type(limits) is not ExecutionLimits:
        raise TypeError("Host budgets require ExecutionLimits")
    token = _ACTIVE.set(limits)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def bounded(function):
    """Carry a parsed programme's captured host budget across pure passes."""
    @wraps(function)
    def run(program, *args, **kwargs):
        limits = kwargs.get('limits') or next((getattr(value, "limits", None) for value in (program, *args)
                       if type(getattr(value, "limits", None)) is ExecutionLimits), None)
        with using_limits(limits if type(limits) is ExecutionLimits else current_limits()):
            return function(program, *args, **kwargs)
    return run


class BudgetExceeded(ValueError):
    """An operation is incomplete; exhaustion supplies no logical conclusion."""
