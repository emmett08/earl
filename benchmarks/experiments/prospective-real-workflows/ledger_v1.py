"""Append-only, hash-linked assignment ledger for the version 1 runner.

Each assignment has one durable start and one final outcome. A missing outcome
is an interrupted attempt, never permission to reuse the assignment ID.
The chain detects accidental edits; it is not an external signature or review.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from gateway_v1 import canonical


SCHEMA = "eal2-real-workflow-ledger/1"
ZERO = "0" * 64


class LedgerError(ValueError):
    pass


class AttemptLedger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.is_symlink():
            raise LedgerError("Ledger path cannot be a symlink")

    @staticmethod
    def _read(data: bytes) -> tuple[list[dict], dict[str, str]]:
        previous = ZERO
        attempts: dict[str, str] = {}
        events = []
        if data and not data.endswith(b"\n"):
            raise LedgerError("Partial ledger line; recover from the last verified external copy")
        for line in data.splitlines():
            try:
                item = json.loads(line)
                if set(item) != {"schema", "sequence", "previous_sha256", "event", "sha256"}:
                    raise LedgerError("Malformed ledger event")
                body = {key: item[key] for key in item if key != "sha256"}
                if (item["schema"] != SCHEMA or item["sequence"] != len(events)
                        or item["previous_sha256"] != previous
                        or hashlib.sha256(canonical(body)).hexdigest() != item["sha256"]):
                    raise LedgerError("Ledger chain or sequence failed verification")
                event = item["event"]
                attempt_id = event["attempt_id"]
                if not isinstance(attempt_id, str) or not attempt_id:
                    raise LedgerError("Missing assignment identity")
                if event["kind"] == "start":
                    if attempt_id in attempts:
                        raise LedgerError("Repeated assignment identity")
                    attempts[attempt_id] = "started"
                elif event["kind"] == "outcome":
                    if attempts.get(attempt_id) != "started":
                        raise LedgerError("Outcome lacks one unmatched start")
                    attempts[attempt_id] = "finished"
                else:
                    raise LedgerError("Unknown ledger event kind")
            except (KeyError, TypeError, ValueError, UnicodeError) as exc:
                raise LedgerError(f"Invalid ledger line {len(events) + 1}: {exc}") from exc
            events.append(item)
            previous = item["sha256"]
        return events, attempts

    def verify(self, *, require_complete: bool = False) -> dict:
        if not self.path.exists():
            return {"events": 0, "assigned": 0, "completed": 0,
                    "interrupted": [], "head_sha256": ZERO}
        events, attempts = self._read(self.path.read_bytes())
        incomplete = sorted(key for key, state in attempts.items() if state == "started")
        if require_complete and incomplete:
            raise LedgerError("Unfinished assignments must remain in the analysis denominator")
        return {"events": len(events), "assigned": len(attempts),
                "completed": len(attempts) - len(incomplete), "interrupted": incomplete,
                "head_sha256": events[-1]["sha256"] if events else ZERO}

    def append(self, event: dict[str, Any]) -> str:
        return self.append_many([event])[-1]

    def reserve_block(self, starts: list[dict[str, Any]]) -> list[str]:
        """Reserve one four-arm assignment block without partial logical starts."""
        if len(starts) != 4 or any(item.get("kind") != "start" for item in starts):
            raise LedgerError("A block must contain exactly four start events")
        return self.append_many(starts)

    def append_many(self, incoming: list[dict[str, Any]]) -> list[str]:
        if not incoming or any(item.get("kind") not in {"start", "outcome"} for item in incoming):
            raise LedgerError("Only nonempty start/outcome batches are permitted")
        flags = os.O_RDWR | os.O_APPEND | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.path, flags, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            if os.fstat(descriptor).st_mode & 0o077:
                raise LedgerError("Ledger file must be private (mode 0600)")
            with os.fdopen(os.dup(descriptor), "rb") as stream:
                events, attempts = self._read(stream.read())
            previous = events[-1]["sha256"] if events else ZERO
            chunks, digests = [], []
            for index, event in enumerate(incoming):
                attempt_id = event.get("attempt_id")
                if not isinstance(attempt_id, str) or not attempt_id:
                    raise LedgerError("Assignment identity must be nonempty")
                if event["kind"] == "start":
                    if attempt_id in attempts:
                        raise LedgerError("Duplicate assignment identity")
                    attempts[attempt_id] = "started"
                elif attempts.get(attempt_id) != "started":
                    raise LedgerError("Outcome lacks one unmatched start")
                else:
                    attempts[attempt_id] = "finished"
                body = {"schema": SCHEMA, "sequence": len(events) + index,
                        "previous_sha256": previous, "event": event}
                previous = hashlib.sha256(canonical(body)).hexdigest()
                chunks.append(canonical({**body, "sha256": previous}) + b"\n")
                digests.append(previous)
            encoded = b"".join(chunks)
            written = 0
            while written < len(encoded):
                written += os.write(descriptor, encoded[written:])
            os.fsync(descriptor)
            return digests
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
