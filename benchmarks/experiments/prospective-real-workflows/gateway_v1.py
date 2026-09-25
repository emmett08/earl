"""Version 1 read-only study gateway; authority comes from operator-owned grants.

The Git adapter executes local object reads. The HTTPS adapter executes GETs
against an exact operator-pinned endpoint. Neither is an operating-system
sandbox: operators must provide isolated replicas/read-only credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Any, Mapping, Protocol
from urllib.parse import urlsplit

import httpx
from eal.runtime import strict_json


TRACE_SCHEMA = "eal2-real-tool-trace/1"
_SHA = re.compile(r"[0-9a-f]{40}")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Time must be an ISO-8601 string with offset")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid ISO-8601 time") from exc
    if result.utcoffset() is None:
        raise ValueError("Time must have an offset")
    return result.astimezone(timezone.utc)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Grant:
    id: str
    adapter: str
    version: str
    mode: str
    principal: str
    allowed_arguments: Mapping[str, tuple[str, ...]]
    # Operator-owned configuration; never copied into prompts or the ledger.
    config: Mapping[str, Any]
    case_ids: tuple[str, ...]
    max_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        if (not self.id or not self.version or not self.principal
                or self.adapter not in {"git_object", "https_json_get"}
                or self.mode not in {"deterministic", "nondeterministic"}
                or not self.case_ids or any(not isinstance(item, str) or not item for item in self.case_ids)
                or type(self.max_bytes) is not int or not 1 <= self.max_bytes <= 4_000_000):
            raise ValueError("Invalid read-only grant")
        if (not isinstance(self.allowed_arguments, Mapping)
                or any(not isinstance(k, str) or not isinstance(v, tuple)
                       or not v or any(not isinstance(s, str) for s in v)
                       for k, v in self.allowed_arguments.items())):
            raise ValueError("Grant requires exact finite argument allowlists")
        keys = set(self.config)
        if self.adapter == "git_object" and keys != {"repository", "commit"}:
            raise ValueError("Pinned Git grant needs only repository and commit")
        if self.adapter == "https_json_get" and not ({"endpoint", "token_env"} <= keys <=
                                                    {"endpoint", "token_env", "snapshot_id"}):
            raise ValueError("HTTPS grant has missing or unknown configuration fields")

    def public(self) -> dict:
        return {"id": self.id, "adapter": self.adapter, "version": self.version,
                "mode": self.mode, "arguments": {k: list(v) for k, v in self.allowed_arguments.items()}}

    def signed_spec(self) -> dict:
        return {**self.public(), "principal": self.principal, "config": dict(self.config),
                "case_ids": list(self.case_ids), "max_bytes": self.max_bytes}


class Reader(Protocol):
    def read(self, grant: Grant, arguments: Mapping[str, str], decision_cut: datetime,
             stage: str) -> tuple[Any, str, dict]: ...


class GitObjectReader:
    """Read a pinned blob from a reviewed local repository, without Git config/env."""

    @staticmethod
    def _git(repo: Path, *arguments: str, timeout: float = 10) -> bytes:
        # Git is still a local executable. Its isolation and repository trust
        # belong in the separately reviewed tool-allowlist receipt.
        process = subprocess.run(
            ["git", "--no-pager", "--no-optional-locks", "-C", str(repo),
             "-c", "core.hooksPath=/dev/null", *arguments],
            input=b"", capture_output=True, timeout=timeout, check=False,
            env={"PATH": os.defpath, "HOME": "/nonexistent", "GIT_CONFIG_NOSYSTEM": "1",
                 "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_NO_LAZY_FETCH": "1",
                 "GIT_NO_REPLACE_OBJECTS": "1"},
        )
        if process.returncode:
            raise ValueError(f"Pinned Git read failed with exit status {process.returncode}")
        if len(process.stderr) > 1024:
            raise ValueError("Git diagnostic exceeded the bounded limit")
        return process.stdout

    def read(self, grant: Grant, arguments: Mapping[str, str], decision_cut: datetime,
             stage: str) -> tuple[Any, str, dict]:
        config = grant.config
        repo = Path(config["repository"]).resolve(strict=True)
        if not repo.is_dir():
            raise ValueError("Repository must be a directory")
        commit = config["commit"]
        if not isinstance(commit, str) or not _SHA.fullmatch(commit):
            raise ValueError("Git object grant requires a full pinned commit")
        path = arguments["path"]
        if (not path or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts
                or path.startswith("-") or ":" in path):
            raise ValueError("Invalid bounded repository path")
        commit_time = timestamp(self._git(repo, "show", "-s", "--format=%cI", commit).decode().strip())
        if commit_time > decision_cut:
            raise ValueError("Pinned commit postdates the decision cut")
        oid = self._git(repo, "rev-parse", "--verify", f"{commit}:{path}").decode().strip()
        if not _SHA.fullmatch(oid):
            raise ValueError("Resolved Git blob identity is invalid")
        size = int(self._git(repo, "cat-file", "-s", oid).decode().strip())
        if size > grant.max_bytes:
            raise ValueError("Pinned Git blob exceeds grant byte limit")
        raw = self._git(repo, "cat-file", "blob", oid)
        if len(raw) != size or len(raw) > grant.max_bytes:
            raise ValueError("Pinned Git object changed or exceeded the limit")
        return {"text": raw.decode("utf-8")}, commit_time.isoformat(), {
            "source_revision": commit, "blob_oid": oid, "raw_sha256": digest(raw),
            "source": f"git:{repo.name}:{commit}:{path}",
        }


class HTTPSJSONReader:
    """GET an exact HTTPS URL with pinned finite query values and no redirects/proxy."""

    def read(self, grant: Grant, arguments: Mapping[str, str], decision_cut: datetime,
             stage: str) -> tuple[Any, str, dict]:
        config = grant.config
        endpoint = config["endpoint"]
        parsed = urlsplit(endpoint)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.fragment or parsed.query
                or parsed.port not in (None, 443)):
            raise ValueError("Grant endpoint must be an exact HTTPS URL without credentials/query")
        token_name = config.get("token_env")
        if not isinstance(token_name, str) or not token_name.startswith("EAL_STUDY_TOKEN_"):
            raise ValueError("HTTPS grant requires an operator-controlled token variable")
        token = os.environ.get(token_name)
        if not token:
            raise ValueError("Read-only credential is unavailable")
        snapshot = config.get("snapshot_id")
        if stage == "retrospective_execution" and (not isinstance(snapshot, str) or not snapshot):
            raise ValueError("Retrospective HTTP reads require an immutable snapshot ID")
        with httpx.Client(follow_redirects=False, trust_env=False, timeout=10) as client:
            with client.stream("GET", endpoint, params=dict(arguments),
                               headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}) as response:
                if response.status_code != 200:
                    raise ValueError(f"Read-only endpoint returned HTTP {response.status_code}")
                total = bytearray()
                for chunk in response.iter_bytes():
                    total.extend(chunk)
                    if len(total) > grant.max_bytes:
                        raise ValueError("Endpoint response exceeded grant byte limit")
        try:
            envelope = strict_json(total.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise ValueError("Endpoint returned invalid JSON") from exc
        if (not isinstance(envelope, dict) or set(envelope) != {"snapshot_id", "observed_at", "value"}
                or not isinstance(envelope["value"], dict)):
            raise ValueError("Endpoint must return snapshot_id, observed_at and structured value")
        observed = timestamp(envelope["observed_at"])
        if observed > decision_cut:
            raise ValueError("Endpoint observation postdates the decision cut")
        if snapshot is not None and envelope["snapshot_id"] != snapshot:
            raise ValueError("Endpoint snapshot identity differs from pinned grant")
        canonical(envelope)
        return envelope["value"], observed.isoformat(), {
            "source_revision": envelope["snapshot_id"],
            "raw_sha256": digest(bytes(total)), "source": endpoint,
        }


class ReadOnlyGateway:
    def __init__(self, grants: Mapping[str, Grant], *, readers: Mapping[str, Reader] | None = None):
        self.grants = dict(grants)
        if any(name != grant.id for name, grant in self.grants.items()):
            raise ValueError("Grant keys must match grant IDs")
        self.readers = dict(readers or {"git_object": GitObjectReader(),
                                        "https_json_get": HTTPSJSONReader()})

    def catalogue(self, principal: str, case_id: str) -> list[dict]:
        return [grant.public() for grant in self.grants.values()
                if grant.principal == principal and case_id in grant.case_ids]

    def signed_spec(self) -> dict:
        return {"schema": "eal2-real-tool-allowlist/1",
                "grants": [self.grants[key].signed_spec() for key in sorted(self.grants)]}

    def capture(self, *, case_id: str, family_id: str, principal: str, decision_cut: str,
                stage: str, tool_id: str, arguments: Mapping[str, str]) -> dict:
        started = now()
        trace: dict[str, Any] = {"schema": TRACE_SCHEMA, "case_id": case_id,
                                 "case_family_id": family_id, "decision_cut": decision_cut,
                                 "principal": principal, "tool_id": tool_id,
                                 "arguments": dict(arguments) if isinstance(arguments, Mapping) else arguments,
                                 "started_at": started, "status": "error", "value": None,
                                 "observed_at": None, "metadata": {}, "error": None}
        try:
            cut = timestamp(decision_cut)
            grant = self.grants[tool_id]
            trace["tool_version"] = grant.version
            trace["mode"] = grant.mode
            trace["adapter"] = grant.adapter
            if principal != grant.principal:
                raise ValueError("Caller principal lacks this grant")
            if case_id not in grant.case_ids:
                raise ValueError("Tool grant is outside this case")
            if (not isinstance(arguments, Mapping) or set(arguments) != set(grant.allowed_arguments)
                    or any(type(value) is not str or value not in grant.allowed_arguments[key]
                           for key, value in arguments.items())):
                raise ValueError("Tool arguments exceed the case-specific grant")
            reader = self.readers[grant.adapter]
            value, observed, metadata = reader.read(grant, arguments, cut, stage)
            if timestamp(observed) > cut:
                raise ValueError("Observation postdates the decision cut")
            encoded = canonical(value)
            if len(encoded) > grant.max_bytes:
                raise ValueError("Observation exceeds grant byte limit")
            trace.update(status="ok", value=value, observed_at=observed,
                         value_sha256=digest(encoded), metadata=metadata)
        except (ValueError, KeyError, OSError, TimeoutError, TypeError, UnicodeError,
                httpx.HTTPError, subprocess.SubprocessError) as exc:
            # Error strings from network clients can include URLs. Keep only
            # stable error classes or our own fixed, credential-free messages.
            trace["error"] = {"type": type(exc).__name__,
                              "message": str(exc) if type(exc) is ValueError else "Tool execution failed"}
        trace["finished_at"] = now()
        return trace
