"""SQLite storage for immutable collection, observation and reasoning records."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class RunStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS records "
                "(id TEXT PRIMARY KEY, kind TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            connection.execute("CREATE INDEX IF NOT EXISTS records_kind ON records(kind, created_at)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=30)

    def put(self, kind: str, payload: dict[str, Any], *, record_id: str | None = None) -> str:
        record_id = record_id or str(uuid4())
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO records(id, kind, created_at, payload) VALUES (?, ?, ?, ?)",
                (record_id, kind, utc_now(), encoded),
            )
        return record_id

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
