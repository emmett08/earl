"""Enforce MCP schemas, admission limits and workspace acquisition exclusion."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
import os
from pathlib import Path
import stat
from typing import Any

import anyio
from filelock import FileLock
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext
from jsonschema import Draft202012Validator

from .operation_contracts import ACQUISITION_OPERATIONS


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


def _lock_path(workspace: Path) -> Path:
    directory = workspace / ".eal"
    directory.mkdir(parents=True, exist_ok=True)
    details = directory.lstat()
    if not stat.S_ISDIR(details.st_mode):
        raise PermissionError("The MCP acquisition directory must be a regular directory")
    if os.name == "posix" and (details.st_uid != os.getuid() or details.st_mode & 0o022):
        raise PermissionError("The MCP acquisition directory must be owned by the process and not writable by others")
    path = directory / "mcp-acquisition.lock"
    if path.is_symlink():
        raise PermissionError("The MCP acquisition lock must not be a symlink")
    return path


def guard_acquisition(name: str, handler: Callable[..., dict[str, Any]],
                      workspace: Path) -> Callable[..., dict[str, Any]]:
    """Serialise complete acquisition operations across local server processes.

    Locking precedes registered-observation reuse, so a waiting assessment can
    reuse the preceding assessment's newly acquired observation. Independent
    collectors inside one operation still use the existing bounded scheduler.
    """
    if name not in ACQUISITION_OPERATIONS:
        return handler
    path = _lock_path(workspace)

    @wraps(handler)
    def guarded(*args, **kwargs):
        # Each worker owns its OS lock until synchronous collection finishes,
        # including when its client disconnects during an acquisition.
        with FileLock(path, timeout=120, mode=0o600):
            return handler(*args, **kwargs)

    return guarded
