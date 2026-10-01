"""Enforce MCP schemas, admission limits and workspace acquisition exclusion."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

import anyio
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext
from jsonschema import Draft202012Validator

from .operation_contracts import ACQUISITION_OPERATIONS
from .acquisition_coordination import WorkspaceAcquisition


class OperationGuard(Middleware):
    """Bound active calls and validate schemas before framework coercion."""

    def __init__(self, schemas: dict[str, dict[str, Any]], *, max_in_flight: int = 1):
        if type(max_in_flight) is not int or not 1 <= max_in_flight <= 1024:
            raise ValueError("max_in_flight must be an integer from 1 through 1024")
        self._validators = {name: Draft202012Validator(schema) for name, schema in schemas.items()}
        self._slots = anyio.Semaphore(max_in_flight)

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        validator = self._validators.get(context.message.name)
        if validator is not None:
            errors = validator.iter_errors(context.message.arguments or {})
            error = next(errors, None)
            if error is not None:
                raise ToolError("Tool input schema rejected request: " + error.message)
        async with self._slots:
            return await call_next(context)


def guard_acquisition(name: str, handler: Callable[..., dict[str, Any]],
                      workspace: Path) -> Callable[..., dict[str, Any]]:
    """Serialise complete acquisition operations across local server processes.

    Locking precedes registered-observation reuse, so a waiting assessment can
    reuse the preceding assessment's newly acquired observation. Independent
    collectors inside one operation still use the existing bounded scheduler.
    """
    if name not in ACQUISITION_OPERATIONS:
        return handler
    coordinator = WorkspaceAcquisition(workspace)

    @wraps(handler)
    def guarded(*args, **kwargs):
        with coordinator.hold():
            return handler(*args, **kwargs)

    return guarded
