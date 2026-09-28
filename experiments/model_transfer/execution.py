"""Bound concurrent blocks by one cancellable elapsed-time allowance."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import signal
import threading
import time


class ExecutionStopped(RuntimeError):
    """No further provider requests may start in this execution segment."""


def validate_execution(plan: dict) -> None:
    for key, default, maximum in (('workers', 1, 8), ('time_limit_seconds', 7200, 21600)):
        value = plan.get(key, default)
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError(f'{key} must be an integer in [1, {maximum}]')


class ExecutionControl:
    def __init__(self, seconds: float, *, clock=time.monotonic):
        self.clock = clock
        self.started = clock()
        self.deadline = self.started + seconds
        self.reason: str | None = None
        self._lock = threading.RLock()

    def stop(self, reason: str) -> None:
        with self._lock:
            if self.reason is None:
                self.reason = reason

    def remaining(self) -> float:
        if self.reason:
            raise ExecutionStopped(self.reason)
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            self.stop('Experiment elapsed-time limit reached; resume the retained run')
            raise ExecutionStopped(self.reason)
        return remaining

    @contextmanager
    def signals(self):
        """Drain bounded in-flight calls on SIGINT/SIGTERM, then finalise records."""
        if threading.current_thread() is not threading.main_thread():
            yield
            return
        previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
        for sig in previous:
            signal.signal(sig, lambda number, frame: self.stop(f'Cancellation signal {number}; resume retained run'))
        try:
            yield
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)

    def batches(self, blocks: list, function, workers: int, on_batch=None) -> None:
        """Keep paired arms ordered; launch bounded, ordered batches of blocks."""
        with self.signals(), ThreadPoolExecutor(max_workers=workers) as pool:
            for start in range(0, len(blocks), workers):
                if self.reason:
                    break
                futures = [pool.submit(function, block) for block in blocks[start:start + workers]]
                # Consume every worker exception and wait for all started work.
                for future in futures:
                    try:
                        future.result()
                    except Exception as exc:
                        self.stop(f'{type(exc).__name__}: {exc}')
                if on_batch is not None:
                    on_batch()
