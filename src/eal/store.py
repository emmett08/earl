"""SQLite storage for immutable collection, observation and reasoning records."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import json
import os
import secrets
import sqlite3
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from filelock import FileLock


def _check_private_directory(directory: Path) -> None:
    details = directory.lstat()
    if not stat.S_ISDIR(details.st_mode):
        raise PermissionError("The run-store directory must be a regular directory")
    if os.name == "posix" and (details.st_uid != os.getuid() or details.st_mode & 0o022):
        raise PermissionError("The run-store directory must be owned by the process and not writable by others")


@contextmanager
def _store_initialisation_lock(database_path: Path, *, timeout: float = 30) -> Iterator[None]:
    """Coordinate store setup before SQLite or its private identity is opened.

    Keep the lock file in place after release: unlinking it could let another
    process acquire a different inode while a contender still holds this one.
    The private parent excludes replacement by other operating-system users.
    """
    _check_private_directory(database_path.parent)
    path = database_path.with_name(database_path.name + ".initialisation.lock")
    flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        # Check before opening an existing object: opening a FIFO or device
        # can block or have effects before descriptor validation is possible.
        details = path.lstat()
        if not stat.S_ISREG(details.st_mode):
            raise PermissionError("The run-store initialisation lock must be a private regular 0600 file")
        descriptor = os.open(path, flags)
    try:
        details = os.fstat(descriptor)
        named = path.lstat()
        if (not stat.S_ISREG(details.st_mode) or not stat.S_ISREG(named.st_mode)
                or (details.st_dev, details.st_ino) != (named.st_dev, named.st_ino)
                or stat.S_IMODE(details.st_mode) != 0o600
                or (os.name == "posix" and details.st_uid != os.getuid())):
            raise PermissionError("The run-store initialisation lock must be a private regular 0600 file")
    finally:
        os.close(descriptor)
    with FileLock(path, timeout=timeout, mode=0o600):
        # FileLock owns a separate descriptor. Check the pathname once more
        # before touching storage; participating processes retain the file.
        details = path.lstat()
        if (not stat.S_ISREG(details.st_mode) or stat.S_IMODE(details.st_mode) != 0o600
                or (os.name == "posix" and details.st_uid != os.getuid())):
            raise PermissionError("The run-store initialisation lock must be a private regular 0600 file")
        yield


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _private_binding_key(database_path: Path) -> bytes:
    """Atomically establish a private store-local identity key outside SQLite."""
    parent = database_path.parent
    _check_private_directory(parent)
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
        with _store_initialisation_lock(self.path):
            self._binding_key = _private_binding_key(self.path)
            _check_private_sqlite_files(self.path, create_database=True)
            self._initialise_schema()
            _check_private_sqlite_files(self.path)

    def _initialise_schema(self) -> None:
        """Establish the current schema and backfill its index atomically."""
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("BEGIN IMMEDIATE")
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

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Commit or roll back one operation and close its owned connection."""
        _check_private_sqlite_files(self.path)
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            _check_private_sqlite_files(self.path)
            with connection:
                yield connection
        finally:
            connection.close()

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

    def find_observations(self, *, evidence_id: str, environment: str,
                          request_digest: str, tool_binding_digest: str,
                          limit: int = 100) -> list[dict[str, Any]]:
        """Return exact-acquisition candidates, newest first, for reuse."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT records.payload FROM observation_index "
                "JOIN records ON records.id = observation_index.record_id "
                "WHERE evidence_id = ? AND environment = ? AND request_digest = ? "
                "AND tool_binding_digest = ? ORDER BY sequence DESC LIMIT ?",
                (evidence_id, environment, request_digest, tool_binding_digest, limit),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

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
