"""Transport-independent effect reservations and a durable reply outbox.

The caller receives an inbound message, reserves its stable identity, and runs
the external effect only for a ``new`` reservation. Execution happens outside
SQLite. The caller then commits the raw response and admission decision in
``result``, together with the reply messages, before publishing or acknowledging
the inbound message. Both durable JSON and Lab transports can use this ledger.

A repeated reservation whose result was never committed reports
``effect_outcome_unknown``. It may represent an effect that ran before a crash;
the ledger never reruns it or claims exactly-once external execution. A trusted
caller can reconcile an independently retained result with ``complete_effect``.

Send and ACK callbacks must raise if confirmation is unavailable. Sends can be
repeated after a crash between delivery and marking: the transport must dedupe
identical stable message IDs and reject changed content. ACK must also tolerate
repetition. The ledger does not provide these guarantees for an arbitrary
callback, launch models, validate domain answers, or impose inference budgets.
"""

from __future__ import annotations

from contextlib import closing, contextmanager
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Any, Callable


class LedgerError(ValueError):
    """A missing reservation, changed identity, or non-JSON record."""


def canonical_json(value: Any) -> str:
    """Encode finite JSON without silently coercing keys or Python containers."""
    def check(item):
        if item is None or type(item) in (bool, int, str):
            return
        if type(item) is float:
            if math.isfinite(item):
                return
            raise LedgerError("Ledger values must be finite JSON")
        if type(item) is list:
            for child in item:
                check(child)
            return
        if type(item) is dict:
            if any(type(key) is not str for key in item):
                raise LedgerError("Ledger object keys must be strings")
            for child in item.values():
                check(child)
            return
        raise LedgerError("Ledger values must use JSON types")

    try:
        check(value)
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False)
        encoded.encode("utf-8")
        return encoded
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, LedgerError):
            raise
        raise LedgerError("Ledger values must be finite UTF-8 JSON") from exc


def _identity(value: Any) -> str:
    if type(value) is not str or not value.strip():
        raise LedgerError("A nonempty stable identity is required")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise LedgerError("Identities must be valid UTF-8") from exc
    return value


class EffectLedger:
    """Reserve once, commit immutable results, and resume delivery independently.

    Keys must include the caller's full inbound identity, such as run, recipient
    and message ID; a message ID alone need not be unique across runs. Outgoing
    message IDs must be unique within an effect, and stable within the transport's
    identity scope. No lease expiry automatically reopens a reservation.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS effects (
                effect_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                payload_digest TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('reserved', 'committed')),
                result TEXT,
                acknowledged INTEGER NOT NULL DEFAULT 0 CHECK(acknowledged IN (0, 1)),
                CHECK(state = 'reserved' OR result IS NOT NULL)
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS effect_outbox (
                effect_key TEXT NOT NULL REFERENCES effects(effect_key),
                position INTEGER NOT NULL,
                message_id TEXT NOT NULL,
                message TEXT NOT NULL,
                sent INTEGER NOT NULL DEFAULT 0 CHECK(sent IN (0, 1)),
                PRIMARY KEY(effect_key, position),
                UNIQUE(effect_key, message_id)
            )""")

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA synchronous = FULL")
        return db

    @contextmanager
    def _transaction(self):
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _snapshot(db, row, *, new: bool = False):
        committed = row["state"] == "committed"
        messages = db.execute(
            "SELECT message FROM effect_outbox WHERE effect_key = ? ORDER BY position",
            (row["effect_key"],),
        ).fetchall()
        return {
            "status": "new" if new else "committed" if committed else "unknown",
            "key": row["effect_key"],
            "payload_digest": row["payload_digest"],
            "result": json.loads(row["result"]) if committed else None,
            "outbox": [json.loads(message["message"]) for message in messages],
            "acknowledged": bool(row["acknowledged"]),
            "diagnosis": None if new or committed else "effect_outcome_unknown",
        }

    def reserve_effect(self, key: str, payload: Any) -> dict[str, Any]:
        """Return ``new``, stored ``committed``, or conservatively ``unknown``.

        Only ``new`` authorizes the caller to begin the external effect. A repeat
        with changed canonical payload is an identity collision, even if the old
        effect is still reserved. Equivalent object key order does not collide.
        """
        key = _identity(key)
        encoded = canonical_json(payload)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        with self._transaction() as db:
            row = db.execute("SELECT * FROM effects WHERE effect_key = ?", (key,)).fetchone()
            if row is not None:
                if row["payload_digest"] != digest or row["payload"] != encoded:
                    raise LedgerError("Inbound identity collision: canonical payload changed")
                return self._snapshot(db, row)
            db.execute(
                "INSERT INTO effects(effect_key, payload, payload_digest, state) VALUES (?, ?, ?, 'reserved')",
                (key, encoded, digest),
            )
            row = db.execute("SELECT * FROM effects WHERE effect_key = ?", (key,)).fetchone()
            return self._snapshot(db, row, new=True)

    def complete_effect(self, key: str, result: Any, outbox: list[dict]) -> dict[str, Any]:
        """Atomically persist result/admission and ordered immutable reply messages.

        Repeating the same completion is harmless; changing a committed result
        or outbox is rejected. Publication and inbound ACK are separate operations
        performed only by ``drain_outbox`` after this transaction commits.
        """
        key = _identity(key)
        encoded_result = canonical_json(result)
        if type(outbox) is not list:
            raise LedgerError("Outbox must be a list of message objects")
        messages = []
        ids = set()
        for message in outbox:
            if type(message) is not dict:
                raise LedgerError("Outbox entries must be message objects")
            message_id = _identity(message.get("message_id"))
            if message_id in ids:
                raise LedgerError("Outbox message identities must be unique within an effect")
            ids.add(message_id)
            messages.append((message_id, canonical_json(message)))
        with self._transaction() as db:
            row = db.execute("SELECT * FROM effects WHERE effect_key = ?", (key,)).fetchone()
            if row is None:
                raise LedgerError("Complete requires an existing effect reservation")
            if row["state"] == "committed":
                stored = db.execute(
                    "SELECT message_id, message FROM effect_outbox WHERE effect_key = ? ORDER BY position",
                    (key,),
                ).fetchall()
                if row["result"] != encoded_result or [(x["message_id"], x["message"]) for x in stored] != messages:
                    raise LedgerError("Committed effect result or outbox cannot change")
                return self._snapshot(db, row)
            db.execute("UPDATE effects SET state = 'committed', result = ? WHERE effect_key = ?",
                       (encoded_result, key))
            db.executemany(
                "INSERT INTO effect_outbox(effect_key, position, message_id, message) VALUES (?, ?, ?, ?)",
                [(key, index, message_id, message) for index, (message_id, message) in enumerate(messages)],
            )
            row = db.execute("SELECT * FROM effects WHERE effect_key = ?", (key,)).fetchone()
            return self._snapshot(db, row)

    def drain_outbox(self, send: Callable[[dict], Any], ack: Callable[[str], Any]) -> dict[str, Any]:
        """Deliver committed replies, then acknowledge their inbound effects.

        Callbacks run outside database transactions. A normal callback return is
        confirmation; callbacks must raise on failed or uncertain delivery. The
        report counts confirmations during this drain, not unique remote sends.
        Unknown reservations are left untouched and are never acknowledged.
        """
        with closing(self._connect()) as db:
            effects = db.execute(
                "SELECT effect_key FROM effects WHERE state = 'committed' AND acknowledged = 0 ORDER BY rowid",
            ).fetchall()
        confirmed = []
        acknowledged = []
        for effect in effects:
            key = effect["effect_key"]
            with closing(self._connect()) as db:
                messages = db.execute(
                    "SELECT position, message_id, message FROM effect_outbox WHERE effect_key = ? AND sent = 0 ORDER BY position",
                    (key,),
                ).fetchall()
            for message in messages:
                send(json.loads(message["message"]))
                with self._transaction() as db:
                    db.execute("UPDATE effect_outbox SET sent = 1 WHERE effect_key = ? AND position = ?",
                               (key, message["position"]))
                confirmed.append({"key": key, "message_id": message["message_id"]})
            with closing(self._connect()) as db:
                unsent = db.execute("SELECT 1 FROM effect_outbox WHERE effect_key = ? AND sent = 0 LIMIT 1",
                                    (key,)).fetchone()
            if unsent is None:
                ack(key)
                with self._transaction() as db:
                    db.execute("UPDATE effects SET acknowledged = 1 WHERE effect_key = ? AND state = 'committed'",
                               (key,))
                acknowledged.append(key)
        return {"confirmed_sends": confirmed, "acknowledged_effects": acknowledged}
