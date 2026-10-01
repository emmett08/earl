"""Compose and launch the EAL FastMCP 4 adapter over stdio or HTTP."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.auth import AuthProvider

from . import __version__
from .limits import ExecutionLimits
from .mcp_guard import OperationGuard, guard_acquisition
from .operations import create_operations
from .runtime import ReasoningService, load_method_registry
from .server_auth import configured_auth
from .server_settings import ServerSettings, parse_server_settings


def create_server(service: ReasoningService, *,
                  known_entries: Collection[str] | None = None,
                  exposure: str | None = None, max_in_flight: int = 1,
                  auth: AuthProvider | None = None) -> FastMCP:
    """Register one application catalogue with equivalent transport contracts."""
    operations = create_operations(service, known_entries=known_entries, exposure=exposure)
    server = FastMCP(
        "EAL engineering reasoning", version=__version__, auth=auth,
        instructions="Validate explicit engineering arguments, collect configured observations, reason over their declared scope, and explain results. Support is relative to declared inference rationales, not a proof of prose truth.",
        strict_input_validation=True,
    )
    schemas: dict[str, dict[str, Any]] = {}
    for name, handler in operations.items():
        registered = server.add_tool(guard_acquisition(name, handler, service.workspace))
        schemas[name] = registered.parameters
    server.add_middleware(OperationGuard(schemas, max_in_flight=max_in_flight))
    return server


def build_server(settings: ServerSettings, *,
                 environ: Mapping[str, str] | None = None) -> FastMCP:
    """Resolve trusted dependencies once; reject missing auth before creating state."""
    auth = configured_auth(settings, environ=environ)
    service = ReasoningService(
        settings.workspace, settings.registry, settings.database,
        method_registry=load_method_registry(settings.methods),
        limits=ExecutionLimits.load(settings.limits) if settings.limits else ExecutionLimits(),
    )
    return create_server(service, known_entries=settings.known_entries,
                         exposure=settings.exposure, max_in_flight=settings.max_in_flight,
                         auth=auth)


def _run_stdio(server: FastMCP, settings: ServerSettings) -> None:
    server.run(transport="stdio", show_banner=False)


def _run_http(server: FastMCP, settings: ServerSettings) -> None:
    server.run(transport="http", host=settings.host, port=settings.port,
               path=settings.path, stateless_http=True, show_banner=False,
               log_level="warning")


_RUNNERS = {"stdio": _run_stdio, "http": _run_http}


def run_server(server: FastMCP, settings: ServerSettings) -> None:
    """Select a transport without branching inside any EAL operation."""
    _RUNNERS[settings.transport](server, settings)


def main() -> None:
    settings = parse_server_settings()
    run_server(build_server(settings), settings)


if __name__ == "__main__":
    main()
