"""Authoritative local coordination state; JSON exports are only views."""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3

from eal.store import utc_now
from .ledger import EffectLedger, canonical_json


class State(EffectLedger):
    def __init__(self, path: Path):
        super().__init__(path)
        with self._transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS run_config(id INTEGER PRIMARY KEY CHECK(id=1), content TEXT NOT NULL, cancelled INTEGER NOT NULL DEFAULT 0)")
            db.execute("CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, at TEXT NOT NULL, kind TEXT NOT NULL, content TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS findings(id TEXT PRIMARY KEY, content TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS calls(seq INTEGER PRIMARY KEY, actor TEXT NOT NULL, category TEXT NOT NULL, operation TEXT NOT NULL, at TEXT NOT NULL)")

    def initialize(self, config):
        with self._transaction() as db:
            if db.execute("SELECT 1 FROM run_config").fetchone():
                raise FileExistsError("A run already exists; resume its frozen configuration")
            db.execute("INSERT INTO run_config(id,content) VALUES(1,?)", (canonical_json(config),))

    def config(self):
        with self._transaction() as db:
            row = db.execute("SELECT content FROM run_config WHERE id=1").fetchone()
            if row is None:
                raise ValueError("No coordination run exists in this directory")
            return json.loads(row[0])

    def event(self, kind, content):
        with self._transaction() as db:
            db.execute("INSERT INTO events(at,kind,content) VALUES(?,?,?)", (utc_now(), kind, canonical_json(content)))

    def events(self):
        with self._transaction() as db:
            return [{"sequence": r[0], "at": r[1], "kind": r[2], "data": json.loads(r[3])}
                    for r in db.execute("SELECT seq,at,kind,content FROM events ORDER BY seq")]

    def effect(self, key):
        with self._transaction() as db:
            row = db.execute("SELECT * FROM effects WHERE effect_key=?", (key,)).fetchone()
            if row is None:
                return None
            value = self._snapshot(db, row)
            value["payload"] = json.loads(row["payload"])
            return value

    def effects(self):
        with self._transaction() as db:
            keys = [r[0] for r in db.execute("SELECT effect_key FROM effects ORDER BY rowid")]
        return [self.effect(key) for key in keys]

    def issue(self, finding):
        encoded = canonical_json(finding)
        with self._transaction() as db:
            prior = db.execute("SELECT content FROM findings WHERE id=?", (finding["finding_id"],)).fetchone()
            if prior and prior[0] != encoded:
                raise ValueError("Finding identity collision")
            db.execute("INSERT OR IGNORE INTO findings(id,content) VALUES(?,?)", (finding["finding_id"], encoded))

    def finding(self, identity):
        with self._transaction() as db:
            row = db.execute("SELECT content FROM findings WHERE id=?", (identity,)).fetchone()
            if row is None:
                raise ValueError("Finding was not issued by this run")
            return json.loads(row[0])

    def reserve_call(self, actor, category, operation, maximum):
        with self._transaction() as db:
            count = db.execute("SELECT count(*) FROM calls WHERE actor=? AND category=?", (actor, category)).fetchone()[0]
            if count >= maximum:
                raise ValueError(f"{category} call budget exhausted for {actor}")
            db.execute("INSERT INTO calls(actor,category,operation,at) VALUES(?,?,?,?)", (actor, category, operation, utc_now()))

    def calls(self):
        with self._transaction() as db:
            return [dict(r) for r in db.execute("SELECT * FROM calls ORDER BY seq")]

    def cancel(self):
        with self._transaction() as db:
            db.execute("UPDATE run_config SET cancelled=1 WHERE id=1")
        self.event("cancelled", {})

    def cancelled(self):
        with self._transaction() as db:
            return bool(db.execute("SELECT cancelled FROM run_config WHERE id=1").fetchone()[0])
