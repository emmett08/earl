"""Append and reconstruct durable API attempts, including interrupted requests."""
from __future__ import annotations

import json
import os
from pathlib import Path

from experiments.transfer_study.workspace import write_json


class AttemptJournal:
    def __init__(self, root: Path):
        self.root = root
        self.path = root / 'calls.jsonl'

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
        lines = self.path.read_text().splitlines(keepends=True)
        for index, line in enumerate(lines):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                # A killed write can leave one incomplete final record. Its
                # previously flushed start retains the cost reservation.
                if index == len(lines) - 1 and not line.endswith('\n'):
                    break
                raise ValueError('Invalid complete API journal record') from None
            event = dict(event)
            kind, attempt = event.pop('event'), event['attempt']
            if kind == 'started' and attempt not in records:
                records[attempt] = event
            elif kind == 'finished' and attempt in records and records[attempt]['status'] == 'started':
                if event['session_id'] != records[attempt]['session_id']:
                    raise ValueError('Journal completion changes the session identity')
                records[attempt].update(event)
            else:
                raise ValueError('Duplicate or unmatched API journal event')
        return [records[key] for key in sorted(records)]
