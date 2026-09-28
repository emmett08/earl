"""Lock a run identity and preserve its budget across resumable segments."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import time
import sys
import importlib.metadata

from experiments.transfer_study.workspace import read_json, write_json, utc_now


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def implementation_digest() -> str:
    root = Path(__file__).resolve().parents[2]
    files = sorted((root / 'experiments').rglob('*.py')) + sorted((root / 'src/eal').rglob('*.py'))
    files += [p for p in (root / 'experiments').rglob('*.json')
              if not set(p.relative_to(root / 'experiments').parts) & {'runs', 'results', 'validation', 'verification'}]
    files += sorted((root / 'grammar').glob('*.g4'))
    files.append(Path(__file__).with_name('requirements.lock'))
    return digest({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files})


class RunState:
    def __init__(self, root: Path, plan: dict, *, resume: bool = False):
        self.root, self.plan, self.resume = root, plan, resume

    @contextmanager
    def locked(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / '.execution.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError('Another process owns this run') from exc
            try:
                self._validate()
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _validate(self):
        path = self.root / 'execution-contract.json'
        expected = {'schema': 'EAL/execution-contract/1', 'plan_sha256': digest(self.plan),
                    'implementation_sha256': implementation_digest(), 'root': str(self.root.resolve()),
                    'python': sys.version, 'executable': sys.executable,
                    'dependencies': {line.split('==')[0]: importlib.metadata.version(line.split('==')[0])
                        for line in Path(__file__).with_name('requirements.lock').read_text().splitlines()
                        if line and not line.startswith('#')}}
        if self.resume:
            if not path.exists():
                raise ValueError('This historical run has no resumable execution contract; analyse its retained data separately')
            if read_json(path) != expected:
                raise ValueError('Resume requires the same plan, implementation, Python/dependencies and absolute run directory')
        else:
            if path.exists() or (self.root / 'rows.json').exists():
                raise ValueError('Use a new run directory or --resume; records cannot be overwritten')
            write_json(path, expected)

    @contextmanager
    def segment(self, seconds: int | None):
        ledger_path = self.root / 'segments.json'
        segments = read_json(ledger_path) if ledger_path.exists() else []
        # A hard-killed segment consumes its full lease, not an invented zero.
        used = sum(s.get('elapsed_seconds', s['allowance_seconds']) for s in segments)
        available = self.plan.get('time_limit_seconds', 7200) - used
        allowance = min(seconds if seconds is not None else available, available)
        if allowance <= 0:
            raise ValueError('The run elapsed-time allowance is exhausted; retain this result without increasing its budget')
        index = len(segments)
        archive = self.root / 'segments' / f'{index:04d}'
        archive.mkdir(parents=True, exist_ok=True)
        for name in ('report.json', 'progress.json'):
            if (self.root / name).exists():
                shutil.copy2(self.root / name, archive / name)
        # More collection invalidates the immutable row digest of derived coding.
        # Retain those outputs in the prior segment rather than auto-selecting
        # stale labels or a previous allocation on the next offline workflow.
        if self.resume:
            derived = [self.root / name for name in ('annotation-bundle', 'annotated-rows.json',
                        'information-report.json', 'evaluation-plan.json')]
            derived += list(self.root.glob('analysis*.json'))
            for derived_path in derived:
                if derived_path.exists():
                    shutil.move(derived_path, archive / derived_path.name)
        entry = {'segment': index, 'started_at': utc_now().isoformat(), 'allowance_seconds': allowance,
                 'status': 'running'}
        segments.append(entry)
        write_json(ledger_path, segments)
        start = time.monotonic()
        try:
            yield allowance
        finally:
            entry.update(status='finished', elapsed_seconds=time.monotonic() - start, finished_at=utc_now().isoformat())
            write_json(ledger_path, segments)
