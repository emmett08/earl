"""Append and reconstruct durable API attempts, including interrupted requests."""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path

from experiments.transfer_study.workspace import write_json


class AttemptJournal:
    def __init__(self, root: Path):
        self.root = root
        self.path = root / 'calls.jsonl'

    def prepare_append(self) -> None:
        """Preserve a torn final write separately before appending new events."""
        if not self.path.exists():
            return
        data = self.path.read_bytes()
        if not data or data.endswith(b'\n'):
            return
        boundary = data.rfind(b'\n') + 1
        tail = data[boundary:]
        try:
            json.loads(tail)
        except (json.JSONDecodeError, UnicodeDecodeError):
            saved = self.root / ('calls-torn-tail-' + hashlib.sha256(tail).hexdigest() + '.bin')
            with saved.open('wb') as stream:
                stream.write(tail)
                stream.flush()
                os.fsync(stream.fileno())
            with self.path.open('r+b') as stream:
                stream.truncate(boundary)
                stream.flush()
                os.fsync(stream.fileno())
        else:
            # A complete JSON event can lose only its trailing newline.
            with self.path.open('ab') as stream:
                stream.write(b'\n')
                stream.flush()
                os.fsync(stream.fileno())

    def append(self, event: dict) -> None:
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

    def finish(self, records: list[dict]) -> None:
        write_json(self.root / 'calls.json', records)

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        records = {}
        lines = self.path.read_bytes().splitlines(keepends=True)
        for index, line in enumerate(lines):
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # A killed write can leave one incomplete final record. Its
                # previously flushed start retains the cost reservation.
                if index == len(lines) - 1 and not line.endswith(b'\n'):
                    break
                raise ValueError('Invalid complete API journal record') from None
            event = dict(event)
            kind, attempt = event.pop('event'), event['attempt']
            if kind == 'started' and type(attempt) is int and attempt == len(records):
                records[attempt] = event
            elif kind == 'finished' and attempt in records and records[attempt]['status'] == 'started':
                if event['session_id'] != records[attempt]['session_id']:
                    raise ValueError('Journal completion changes the session identity')
                records[attempt].update(event)
            else:
                raise ValueError('Duplicate or unmatched API journal event')
        return [records[key] for key in sorted(records)]
