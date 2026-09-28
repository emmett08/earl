"""SQLite storage for immutable collection, observation and reasoning records."""

from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _private_binding_key(database_path: Path) -> bytes:
    """Atomically establish a private store-local identity key outside SQLite."""
    parent = database_path.parent
    if os.name == "posix":
        directory = parent.stat()
        if (not stat.S_ISDIR(directory.st_mode) or directory.st_uid != os.getuid()
                or directory.st_mode & 0o022):
            raise PermissionError("The run-store directory must be owned by the process and not writable by others")
    key_path = database_path.with_name(database_path.name + ".binding-key")
    temporary = key_path.with_name(key_path.name + "." + secrets.token_hex(16) + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        candidate = secrets.token_bytes(32)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(candidate)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, key_path, follow_symlinks=False)
        except FileExistsError:
            pass
    finally:
        temporary.unlink(missing_ok=True)
    descriptor = os.open(key_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise PermissionError("The run-store binding key must be a private regular file")
        if os.name == "posix" and info.st_uid != os.getuid():
            raise PermissionError("The run-store binding key must be owned by the process")
        key = stream.read(33)
    if len(key) != 32:
        raise ValueError("The run-store binding key must contain exactly 32 bytes")
    return key


def _check_private_sqlite_files(database_path: Path, *, create_database: bool = False) -> None:
    """Refuse readable or replaceable SQLite files before opening the store."""
    if create_database:
        try:
            descriptor = os.open(
                database_path, os.O_RDWR | os.O_CREAT | os.O_EXCL |
                getattr(os, "O_NOFOLLOW", 0), 0o600,
            )
        except FileExistsError:
            pass
        else:
            os.close(descriptor)
    for path in (database_path, database_path.with_name(database_path.name + "-wal"),
                 database_path.with_name(database_path.name + "-shm")):
        try:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        except FileNotFoundError:
            if path == database_path:
                raise
            continue
        with os.fdopen(descriptor, "rb") as stream:
            details = os.fstat(stream.fileno())
        if (not stat.S_ISREG(details.st_mode) or stat.S_IMODE(details.st_mode) != 0o600
                or (os.name == "posix" and details.st_uid != os.getuid())):
            raise PermissionError(f"SQLite store file must be a private regular 0600 file: {path.name}")


class RunStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._binding_key = _private_binding_key(self.path)
        _check_private_sqlite_files(self.path, create_database=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS records "
                "(id TEXT PRIMARY KEY, kind TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            connection.execute("CREATE INDEX IF NOT EXISTS records_kind ON records(kind, created_at)")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS observation_index "
                "(sequence INTEGER PRIMARY KEY, record_id TEXT NOT NULL UNIQUE, "
                "evidence_id TEXT NOT NULL, environment TEXT NOT NULL, "
                "request_digest TEXT NOT NULL, tool_binding_digest TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS observation_identity ON observation_index "
                "(evidence_id, environment, request_digest, tool_binding_digest, sequence DESC)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS store_metadata "
                "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS reuse_invalidations "
                "(id TEXT PRIMARY KEY, kind TEXT NOT NULL, reason TEXT NOT NULL, "
                "origin_run_id TEXT, tool_binding_digest TEXT, acquisition_request_digest TEXT, "
                "cutoff_sequence INTEGER NOT NULL, created_at TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS reuse_invalidations_origin "
                "ON reuse_invalidations(origin_run_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS reuse_invalidations_scope "
                "ON reuse_invalidations(tool_binding_digest, acquisition_request_digest)"
            )
            indexed = connection.execute(
                "SELECT value FROM store_metadata WHERE key = 'observation-index-version'"
            ).fetchone()
            if indexed is None:
                # Existing stores predate the index. Scan once, including failed
                # attempts which deliberately get no reusable index entry.
                for record_id, encoded in connection.execute(
                    "SELECT id, payload FROM records WHERE kind = 'observation' ORDER BY rowid"
                ):
                    self._index_observation(connection, record_id, json.loads(encoded))
                connection.execute(
                    "INSERT INTO store_metadata(key, value) VALUES ('observation-index-version', '1')"
                )
            elif indexed[0] != "1":
                raise ValueError("Unsupported observation index version")
        _check_private_sqlite_files(self.path)

    def _connect(self) -> sqlite3.Connection:
        _check_private_sqlite_files(self.path)
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            _check_private_sqlite_files(self.path)
        except BaseException:
            connection.close()
            raise
        return connection

    def put(self, kind: str, payload: dict[str, Any], *, record_id: str | None = None) -> str:
        record_id = record_id or str(uuid4())
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO records(id, kind, created_at, payload) VALUES (?, ?, ?, ?)",
                (record_id, kind, utc_now(), encoded),
            )
            if kind == "observation":
                self._index_observation(connection, record_id, payload)
        return record_id

    @staticmethod
    def _index_observation(connection: sqlite3.Connection, record_id: str, payload: dict[str, Any]) -> None:
        if payload.get("status") != "ok":
            return
        keys = (payload.get("evidence_id"), payload.get("environment"),
                payload.get("request_digest"), payload.get("tool_binding_digest"))
        if any(not isinstance(key, str) or not key for key in keys):
            return
        connection.execute(
            "INSERT INTO observation_index(record_id, evidence_id, environment, request_digest, "
            "tool_binding_digest) VALUES (?, ?, ?, ?, ?)", (record_id, *keys)
        )

    def put_batch(self, entries: list[tuple[str, dict[str, Any], str | None]]) -> list[str]:
        """Commit a collection and its observations as one transaction."""
        if not entries:
            raise ValueError("entries must not be empty")
        ids = [record_id or str(uuid4()) for _, _, record_id in entries]
        encoded = [json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
                   for _, payload, _ in entries]
        with self._connect() as connection:
            for (kind, payload, _), record_id, value in zip(entries, ids, encoded):
                connection.execute(
                    "INSERT INTO records(id, kind, created_at, payload) VALUES (?, ?, ?, ?)",
                    (record_id, kind, utc_now(), value),
                )
                if kind == "observation":
                    self._index_observation(connection, record_id, payload)
        return ids

    def put_rebound_batch(self, entries: list[tuple[str, dict[str, Any], str | None]],
                          *, source_run_ids: list[str]) -> list[str]:
        """Atomically check source reuse eligibility and commit derived records.

        An invalidation racing with rebinding must either precede the check or
        follow the commit. In the latter case it also covers the new records.
        """
        if not entries or not source_run_ids:
            raise ValueError("Rebinding requires records and their source run IDs")
        ids = [record_id or str(uuid4()) for _, _, record_id in entries]
        encoded = [json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
                   for _, payload, _ in entries]
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for run_id in source_run_ids:
                row = connection.execute(
                    "SELECT payload FROM records WHERE id = ? AND kind = 'observation'", (run_id,)
                ).fetchone()
                if row is None or self._reuse_invalidated(connection, json.loads(row[0])):
                    raise ValueError(f"Observation {run_id!r} is unavailable for reuse")
            for (kind, payload, _), record_id, value in zip(entries, ids, encoded):
                connection.execute(
                    "INSERT INTO records(id, kind, created_at, payload) VALUES (?, ?, ?, ?)",
                    (record_id, kind, utc_now(), value),
                )
                if kind == "observation":
                    self._index_observation(connection, record_id, payload)
        return ids

    def invalidate_reuse(self, *, kind: str, reason: str,
                         origin_run_id: str | None = None,
                         tool_binding_digest: str | None = None,
                         acquisition_request_digest: str | None = None) -> dict[str, Any]:
        """Persist an operator event or reconnect gap that blocks later reuse.

        A scoped invalidation covers measurements already indexed and
        acquisitions that began or observed their value before the event. A new
        authoritative collection begun and observed afterwards is eligible.
        Historical collection and assessment records are never changed.
        """
        if not isinstance(kind, str) or kind not in {"event", "gap"}:
            raise ValueError("Invalidation kind must be event or gap")
        try:
            reason_bytes = reason.encode("utf-8") if isinstance(reason, str) else b""
        except UnicodeError:
            reason_bytes = b""
        if not 1 <= len(reason_bytes) <= 1024 or not reason.strip():
            raise ValueError("Invalidation reason must contain one to 1024 UTF-8 bytes")
        if origin_run_id is not None and (not isinstance(origin_run_id, str)
                                          or not 1 <= len(origin_run_id) <= 128):
            raise ValueError("origin_run_id must be a stored observation identifier")
        for label, digest in (("tool_binding_digest", tool_binding_digest),
                              ("acquisition_request_digest", acquisition_request_digest)):
            if digest is not None and (not isinstance(digest, str)
                                       or re.fullmatch(r"[0-9a-f]{64}", digest) is None):
                raise ValueError(f"{label} must be a lowercase SHA-256 digest")
        if acquisition_request_digest is not None and tool_binding_digest is None:
            raise ValueError("Request-scope invalidation requires a tool binding digest")
        if origin_run_id is not None and (kind != "event" or tool_binding_digest is not None):
            raise ValueError("An origin event cannot combine with a binding or gap scope")
        if kind == "event" and origin_run_id is None and tool_binding_digest is None:
            raise ValueError("An event requires an origin or tool binding scope")
        if kind == "gap" and (origin_run_id is not None or acquisition_request_digest is not None):
            raise ValueError("A reconnect gap may scope only to a binding or all bindings")
        identifier = str(uuid4())
        created_at = utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if origin_run_id is not None:
                row = connection.execute(
                    "SELECT payload FROM records WHERE id = ? AND kind = 'observation'", (origin_run_id,)
                ).fetchone()
                if row is None:
                    raise ValueError("Origin observation does not exist")
                record = json.loads(row[0])
                if record.get("origin_run_id", record.get("run_id")) != origin_run_id:
                    raise ValueError("Specify the origin run ID, not a derived observation")
            cutoff = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) FROM observation_index"
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO reuse_invalidations "
                "(id, kind, reason, origin_run_id, tool_binding_digest, "
                "acquisition_request_digest, cutoff_sequence, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (identifier, kind, reason, origin_run_id, tool_binding_digest,
                 acquisition_request_digest, cutoff, created_at),
            )
        return {"invalidation_id": identifier, "kind": kind, "reason": reason,
                "origin_run_id": origin_run_id, "tool_binding_digest": tool_binding_digest,
                "acquisition_request_digest": acquisition_request_digest,
                "cutoff_sequence": cutoff, "created_at": created_at}

    @staticmethod
    def _at_or_before(value: Any, cutoff: str) -> bool:
        """Treat an absent or invalid acquisition time as unsafe for reuse."""
        if not isinstance(value, str):
            return True
        try:
            instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
            boundary = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
            return instant <= boundary
        except (TypeError, ValueError):
            return True

    @classmethod
    def _reuse_invalidated(cls, connection: sqlite3.Connection, record: dict[str, Any]) -> bool:
        run_id = record.get("run_id")
        indexed = connection.execute(
            "SELECT sequence FROM observation_index WHERE record_id = ?", (run_id,)
        ).fetchone()
        if indexed is None:
            return True
        sequence = indexed[0]
        origin = record.get("origin_run_id", run_id)
        binding = record.get("tool_binding_digest")
        request = record.get("acquisition_request_digest")
        for row in connection.execute(
            "SELECT origin_run_id, tool_binding_digest, acquisition_request_digest, "
            "cutoff_sequence, created_at FROM reuse_invalidations "
            "WHERE origin_run_id = ? OR "
            "(origin_run_id IS NULL AND "
            "(tool_binding_digest IS NULL OR tool_binding_digest = ?) AND "
            "(acquisition_request_digest IS NULL OR acquisition_request_digest = ?))",
            (origin, binding, request),
        ):
            invalid_origin, _, _, cutoff_sequence, created_at = row
            if invalid_origin is not None or sequence <= cutoff_sequence:
                return True
            if (cls._at_or_before(record.get("started_at"), created_at)
                    or cls._at_or_before(record.get("collected_at"), created_at)):
                return True
        return False

    def reuse_invalidated(self, record: dict[str, Any]) -> bool:
        """Check a stored observation against persistent reuse invalidations."""
        if not isinstance(record, dict) or not isinstance(record.get("run_id"), str):
            raise ValueError("Reuse requires a stored observation with a run_id")
        with self._connect() as connection:
            return self._reuse_invalidated(connection, record)

    def find_observations(self, *, evidence_id: str, environment: str,
                          request_digest: str, tool_binding_digest: str,
                          limit: int = 100) -> list[dict[str, Any]]:
        """Return exact-identity candidates, newest first, for explicit reuse."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        compatible = []
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT records.payload FROM observation_index "
                "JOIN records ON records.id = observation_index.record_id "
                "WHERE evidence_id = ? AND environment = ? AND request_digest = ? "
                "AND tool_binding_digest = ? ORDER BY sequence DESC",
                (evidence_id, environment, request_digest, tool_binding_digest),
            )
            for row in rows:
                record = json.loads(row[0])
                if not self._reuse_invalidated(connection, record):
                    compatible.append(record)
                    if len(compatible) == limit:
                        break
        return compatible

    def get(self, record_id: str, *, kind: str | None = None) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT kind, payload FROM records WHERE id = ?", (record_id,)).fetchone()
        if row is None or (kind is not None and row[0] != kind):
            raise KeyError(f"No {kind or 'stored'} record with ID {record_id!r}")
        return json.loads(row[1])

    def list(self, *, kind: str | None = None, limit: int = 100) -> list[dict[str, str]]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._connect() as connection:
            if kind is None:
                rows = connection.execute(
                    "SELECT id, kind, created_at FROM records ORDER BY rowid DESC LIMIT ?", (limit,)
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT id, kind, created_at FROM records WHERE kind = ? ORDER BY rowid DESC LIMIT ?",
                    (kind, limit),
                ).fetchall()
        return [dict(zip(("id", "kind", "created_at"), row)) for row in rows]
