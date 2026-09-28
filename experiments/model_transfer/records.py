"""Checkpoint one sequence at a time and recover the planned experiment rows."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from experiments.transfer_study.workspace import read_json, write_json


class SequenceRecords:
    """Bound checkpoint work by a sequence while retaining every planned unit."""

    def __init__(self, root: Path):
        self.root = root
        self.directory = root / 'sequence-records'
        self.complete = root / 'rows-complete.json'

    def begin(self, rows: list[dict]) -> None:
        if (self.root / 'rows.json').exists():
            raise ValueError('Use a new run directory; sequence records cannot be overwritten')
        write_json(self.root / 'rows.json', rows)
        self.directory.mkdir()

    def record(self, row: dict) -> None:
        key = 'sequence_id' if 'sequence_id' in row else 'block_id'
        identifier = hashlib.sha256(row[key].encode()).hexdigest()
        write_json(self.directory / f'{identifier}.json', row)

    def reopen(self) -> list[dict]:
        rows = self.load()
        self.complete.unlink(missing_ok=True)
        self.directory.mkdir(exist_ok=True)
        return rows

    def finish(self, rows: list[dict]) -> None:
        write_json(self.root / 'rows.json', rows)
        write_json(self.complete, {'materialised': True})

    def text(self) -> str:
        original = (self.root / 'rows.json').read_text(encoding='utf-8')
        if self.complete.exists() or not self.directory.exists():
            return original
        rows = json.loads(original)
        key = 'sequence_id' if rows and 'sequence_id' in rows[0] else 'block_id'
        positions = {row[key]: index for index, row in enumerate(rows)}
        if len(positions) != len(rows):
            raise ValueError('Duplicate planned sequence identity')
        identity_keys = (('case', 'donor', 'receiver', 'native_tools', 'repeat', 'arm', 'pair_id')
                         if key == 'sequence_id' else ('case', 'donor', 'receiver', 'native_tools', 'repeat', 'donor_session_id'))
        for path in sorted(self.directory.glob('*.json')):
            row = read_json(path)
            identifier = row[key]
            if (identifier not in positions or
                    path.stem != hashlib.sha256(identifier.encode()).hexdigest()):
                raise ValueError('Sequence checkpoint does not match a planned identity')
            index = positions[identifier]
            if any(row[key] != rows[index][key] for key in identity_keys):
                raise ValueError('Sequence checkpoint changes its assigned treatment')
            rows[index] = row
        return json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=2) + '\n'

    def load(self) -> list[dict]:
        return json.loads(self.text())
