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
        record.update(status='started', elapsed_seconds=None)
        self.persist()
        start = self.clock()
        try:
            yield
        except BaseException:
            record.update(status='failed', elapsed_seconds=self.clock() - start)
            raise
        else:
            record.update(status='complete', elapsed_seconds=self.clock() - start)
        finally:
            self.persist()
