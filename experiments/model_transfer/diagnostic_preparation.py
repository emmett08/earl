"""Durably time one preparation operation without counting persistence overhead."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import time


class PreparationTimer:
    def __init__(self, persist: Callable[[], None], *, clock: Callable[[], float] = time.monotonic):
        self.persist, self.clock = persist, clock

    @staticmethod
    def pending() -> dict:
        return {'status': 'not_run', 'elapsed_seconds': None}

    @contextmanager
    def measure(self, record: dict) -> Iterator[None]:
        """Persist the start so an interrupted operation retains an unknown duration."""
        retry = record.get('status', 'not_run') != 'not_run'
        previous = record.get('elapsed_seconds') if retry else 0
        if retry:
            record.setdefault('previous_attempts', []).append({
                'status': record.get('status'), 'elapsed_seconds': previous})
        record.update(status='started', elapsed_seconds=None)
        self.persist()
        start = self.clock()
        try:
            yield
        except BaseException:
            record['status'] = 'failed'
            raise
        else:
            record['status'] = 'complete'
        finally:
            elapsed = self.clock() - start
            record['elapsed_seconds'] = previous + elapsed if previous is not None else None
            if retry:
                record['last_attempt_seconds'] = elapsed
            self.persist()
