"""Equivalent stable-ID delivery over local JSON or the supplied Lab codec."""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
import re
import sqlite3
import time

from .lab_mcp import LabMCPTransport
from .ledger import canonical_json


def envelope(run_id, message):
    return {"message_id": message["message_id"], "run_id": run_id,
            "sender": message["sender"], "recipient": message["recipient"],
            "version": "1", "kind": message["kind"], "payload": message}


class JsonBus:
    """Finite, durable mailbox with idempotent sends and received-before-ACK."""
    def __init__(self, database: Path):
        self.database = database
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS bus_config(id INTEGER PRIMARY KEY CHECK(id=1), content TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS bus_messages(seq INTEGER PRIMARY KEY, id TEXT UNIQUE, content TEXT, received INTEGER DEFAULT 0, acked INTEGER DEFAULT 0)")
            db.execute("CREATE TABLE IF NOT EXISTS bus_calls(id TEXT PRIMARY KEY, actor TEXT, evidence TEXT)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def create(self, run_id, *participants, max_messages=8, max_bytes=65536, max_calls=2):
        value = dict(run_id=run_id, participants=list(participants), max_messages=max_messages, max_bytes=max_bytes, max_calls=max_calls)
        with self.connect() as db:
            prior = db.execute("SELECT content FROM bus_config").fetchone()
            if prior and prior[0] != canonical_json(value):
                raise ValueError("Frozen mailbox configuration differs")
            db.execute("INSERT OR IGNORE INTO bus_config(id,content) VALUES(1,?)", (canonical_json(value),))

    def _config(self, db, run_id, actor=None):
        value = json.loads(db.execute("SELECT content FROM bus_config WHERE id=1").fetchone()[0])
        if value["run_id"] != run_id or (actor and actor not in value["participants"]):
            raise ValueError("Unknown run or actor")
        return value

    def send(self, run_id, payload, *, actor):
        encoded = canonical_json(envelope(run_id, payload))
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cfg = self._config(db, run_id, actor)
            if payload["sender"] != actor or payload["recipient"] not in cfg["participants"]:
                raise ValueError("Message has invalid addressed identities")
            prior = db.execute("SELECT content,seq FROM bus_messages WHERE id=?", (payload["message_id"],)).fetchone()
            if prior:
                if prior[0] != encoded:
                    raise ValueError("Changed content under existing message identity")
                return {"accepted": True, "duplicate": True, "sequence": prior[1]}
            rows = db.execute("SELECT content FROM bus_messages").fetchall()
            if len(rows) >= cfg["max_messages"] or sum(len(r[0].encode()) for r in rows) + len(encoded.encode()) > cfg["max_bytes"]:
                raise ValueError("Communication budget exhausted")
            sequence = db.execute("INSERT INTO bus_messages(id,content) VALUES(?,?)", (payload["message_id"], encoded)).lastrowid
            return {"accepted": True, "duplicate": False, "sequence": sequence}

    def receive(self, run_id, recipient, *, limit=8):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._config(db, run_id, recipient)
            rows = db.execute("SELECT * FROM bus_messages WHERE acked=0 ORDER BY seq").fetchall()
            results = []
            for row in rows:
                message = json.loads(row["content"])
                if message["recipient"] == recipient and len(results) < limit:
                    results.append({"message": message, "sequence": row["seq"], "redelivered": bool(row["received"])})
                    db.execute("UPDATE bus_messages SET received=1 WHERE seq=?", (row["seq"],))
            return results

    def acknowledge(self, run_id, message_id, recipient):
        with self.connect() as db:
            self._config(db, run_id, recipient)
            row = db.execute("SELECT * FROM bus_messages WHERE id=?", (message_id,)).fetchone()
            if not row or json.loads(row["content"])["recipient"] != recipient or not row["received"]:
                raise ValueError("ACK requires the addressed received message")
            db.execute("UPDATE bus_messages SET acked=1 WHERE id=?", (message_id,))
            return {"acknowledged": True, "message_id": message_id}

    def reserve(self, run_id, actor, call_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cfg = self._config(db, run_id, actor)
            if db.execute("SELECT count(*) FROM bus_calls").fetchone()[0] >= cfg["max_calls"]:
                raise ValueError("Worker call budget exhausted")
            db.execute("INSERT INTO bus_calls(id,actor) VALUES(?,?)", (call_id, actor))
        return {"reserved": True, "call_id": call_id}

    def finish(self, run_id, actor, call_id, evidence):
        encoded = canonical_json(evidence)
        with self.connect() as db:
            self._config(db, run_id, actor)
            row = db.execute("SELECT * FROM bus_calls WHERE id=?", (call_id,)).fetchone()
            if not row or row["actor"] != actor or (row["evidence"] is not None and row["evidence"] != encoded):
                raise ValueError("Completion identity or immutable evidence differs")
            db.execute("UPDATE bus_calls SET evidence=? WHERE id=?", (encoded, call_id))
        return {"recorded": True}

    def status(self, run_id):
        with self.connect() as db:
            cfg = self._config(db, run_id)
            messages = [dict(r) for r in db.execute("SELECT * FROM bus_messages ORDER BY seq")]
            calls = [{"id": r["id"], "actor": r["actor"], "state": "recorded" if r["evidence"] is not None else "reserved",
                      "evidence": json.loads(r["evidence"]) if r["evidence"] else None} for r in db.execute("SELECT * FROM bus_calls")]
            return {"run_id": run_id, "config": cfg, "usage": {"messages": len(messages), "bytes": sum(len(r["content"].encode()) for r in messages), "calls": len(calls)},
                    "messages": [{"sequence": r["seq"], "message_id": r["id"], "received": bool(r["received"]), "acked": bool(r["acked"])} for r in messages], "calls": calls}


def open_bus(directory, config):
    transport = config["transport"]
    if transport["kind"] == "lab":
        return LabMCPTransport(transport["runtime"], directory / "mailbox.sqlite")
    if transport == {"kind": "json"}:
        return JsonBus(directory / "mailbox.sqlite")
    raise ValueError("Unknown frozen coordination transport")
