"""Trusted host settings for the configurable MCP server.

Precedence is CLI > ``EAL_MCP_*`` environment > TOML file > defaults. A config
file is selected by ``--config`` or ``EAL_MCP_CONFIG``. File paths are relative
to that file's parent; CLI and environment paths are relative to the current
directory. ``EAL_MCP_KNOWN_ENTRIES`` is a JSON array of registered identifiers.
An explicit exposure must agree with the selected entries. Otherwise non-empty
entries select registered exposure and an empty selection selects operator
exposure. Registered exposure always requires at least one entry.

Settings contain the token environment variable's name, never its value. Only
the application composition root reads credentials. This module imports no
server framework and creates no service, database, collector or network socket.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import ipaddress
import json
import os
from pathlib import Path
import re
import tomllib
from typing import Any, Literal


_SERVICE_KEYS = frozenset({"workspace", "registry", "database", "methods", "limits", "known_entries"})
_SERVER_KEYS = frozenset({"transport", "exposure", "max_in_flight", "http"})
_HTTP_KEYS = frozenset({"host", "port", "path", "token_env"})
_PATH_KEYS = frozenset({"workspace", "registry", "database", "limits"})
_ENV_KEYS = _SERVICE_KEYS | (_SERVER_KEYS - {"http"}) | _HTTP_KEYS
_METHOD_FACTORY = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*", re.ASCII)
_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_HOST_NAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*\.?", re.ASCII)


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty string without surrounding whitespace")
    return value


def _loopback_host(host: str) -> bool:
    if host.lower().rstrip(".") == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class ServerSettings:
    """Validated immutable service and transport configuration."""

    workspace: Path = field(default_factory=Path.cwd)
    registry: Path | None = None
    database: Path | None = None
    methods: str | None = None
    limits: Path | None = None
    known_entries: tuple[str, ...] = ()
    exposure: Literal["operator", "registered"] = "operator"
    transport: Literal["stdio", "http"] = "stdio"
    host: str = "127.0.0.1"
    port: int = 8000
    path: str = "/mcp"
    max_in_flight: int = 1
    token_env: str | None = None

    def __post_init__(self) -> None:
        for name in _PATH_KEYS:
            value = getattr(self, name)
            if value is None and name != "workspace":
                continue
            if not isinstance(value, Path):
                raise ValueError(f"{name} must be a filesystem path")
            object.__setattr__(self, name, value.expanduser().resolve())
        if self.methods is not None and not _METHOD_FACTORY.fullmatch(_text(self.methods, "methods")):
            raise ValueError("methods must have the form package.module:function")
        if _text(self.transport, "transport") not in {"stdio", "http"}:
            raise ValueError("transport must be stdio or http")
        if _text(self.exposure, "exposure") not in {"operator", "registered"}:
            raise ValueError("exposure must be operator or registered")
        if (not isinstance(self.known_entries, tuple)
                or len(self.known_entries) > 128
                or any(not isinstance(item, str) or not item or item != item.strip()
                       for item in self.known_entries)
                or len(set(self.known_entries)) != len(self.known_entries)):
            raise ValueError("known_entries must contain up to 128 unique non-empty registered IDs")
        if self.exposure == "registered" and not self.known_entries:
            raise ValueError("registered exposure requires at least one known entry")
        if self.exposure == "operator" and self.known_entries:
            raise ValueError("operator exposure conflicts with known entries")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("port must be an integer from 1 through 65535")
        if type(self.max_in_flight) is not int or not 1 <= self.max_in_flight <= 1024:
            raise ValueError("max_in_flight must be an integer from 1 through 1024")
        host = _text(self.host, "host")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not _HOST_NAME.fullmatch(host):
                raise ValueError("host must be an IP address or hostname without a URL or port")
        path = _text(self.path, "path")
        if (not path.startswith("/") or path.startswith("//")
                or any(character.isspace() or ord(character) < 32 for character in path)
                or any(character in path for character in "?#\\")
                or any(part in {".", ".."} for part in path.split("/"))):
            raise ValueError("path must be an absolute HTTP path without query, fragment or traversal")
        if self.token_env is not None and not _ENV_NAME.fullmatch(_text(self.token_env, "token_env")):
            raise ValueError("token_env must name an environment variable")
        if self.transport == "http" and not _loopback_host(host) and self.token_env is None:
            raise ValueError("HTTP on a non-loopback host requires token_env authentication")


def _table(value: Any, name: str, permitted: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a TOML table")
    unknown = set(value) - permitted
    if unknown:
        raise ValueError(f"Unknown {name} settings: {', '.join(sorted(unknown))}")
    return value


def _read_config(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            document = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"Cannot read server configuration {path}: {exc}") from exc
    document = _table(document, "root", frozenset({"service", "server"}))
    service = _table(document.get("service", {}), "service", _SERVICE_KEYS)
    server = _table(document.get("server", {}), "server", _SERVER_KEYS)
    http = _table(server.get("http", {}), "server.http", _HTTP_KEYS)
    return {**service, **{name: value for name, value in server.items() if name != "http"}, **http}


def _parse_env(environ: Mapping[str, str], overridden: set[str]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key in _ENV_KEYS:
        name = "EAL_MCP_" + key.upper()
        if name not in environ or key in overridden:
            continue
        raw = environ[name]
        if key == "known_entries":
            if not isinstance(raw, str):
                raise ValueError("EAL_MCP_KNOWN_ENTRIES must be a JSON array of registered IDs")
            try:
                values[key] = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError("EAL_MCP_KNOWN_ENTRIES must be a JSON array of registered IDs") from exc
            continue
        raw = _text(raw, name)
        if key in {"port", "max_in_flight"}:
            if not re.fullmatch(r"[+-]?[0-9]+", raw):
                raise ValueError(f"{name} must be an integer")
            values[key] = int(raw)
        else:
            values[key] = raw
    return values


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EAL MCP server with stdio or Streamable HTTP transport",
                                     argument_default=argparse.SUPPRESS)
    parser.add_argument("--config", help="Trusted server TOML configuration")
    for name in ("workspace", "registry", "database", "limits"):
        parser.add_argument("--" + name)
    parser.add_argument("--methods", help="Trusted method-registry factory: package.module:function")
    parser.add_argument("--known-entry", dest="known_entries", action="append", metavar="ENTRY_ID",
                        help="Expose a registered source; repeat for each permitted entry")
    parser.add_argument("--transport", choices=("stdio", "http"))
    parser.add_argument("--exposure", choices=("operator", "registered"))
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--path")
    parser.add_argument("--max-in-flight", type=int)
    parser.add_argument("--token-env", help="Environment variable containing the HTTP bearer token")
    return parser


def parse_server_settings(argv: Sequence[str] | None = None,
                          environ: Mapping[str, str] | None = None) -> ServerSettings:
    """Resolve trusted settings without loading service code or reading tokens.

    CLI errors follow argparse's standard behaviour; invalid file, environment
    or resolved settings raise ``ValueError``. Known entries are replaced as a
    collection at each precedence level. Relative paths retain their source's
    base directory even when other values are overridden.
    """
    environ = os.environ if environ is None else environ
    cli = vars(_parser().parse_args(argv))
    config_name = cli.pop("config", environ.get("EAL_MCP_CONFIG"))
    cwd = Path.cwd()
    config_path = (cwd / Path(_text(config_name, "config")).expanduser()).resolve() if config_name is not None else None
    file_values = _read_config(config_path) if config_path is not None else {}
    env_values = _parse_env(environ, set(cli))
    values = {**file_values, **env_values, **cli}
    for name in _PATH_KEYS & values.keys():
        raw = _text(values[name], name)
        base = config_path.parent if name in file_values and name not in env_values and name not in cli else cwd
        values[name] = (base / Path(raw).expanduser()).resolve()
    if "known_entries" in values:
        selected = values["known_entries"]
        if not isinstance(selected, list):
            raise ValueError("known_entries must be an array of registered IDs")
        values["known_entries"] = tuple(selected)
    if "exposure" not in values:
        values["exposure"] = "registered" if values.get("known_entries") else "operator"
    return ServerSettings(**values)
