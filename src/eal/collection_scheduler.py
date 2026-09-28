"""Bounded collection scheduling under operator-declared independence.

An arbitrary collector can change remote state or depend on another collector.
Only consecutive acquisitions explicitly approved for parallel execution may
overlap. Serial acquisitions form barriers in the requested order.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypeVar


T = TypeVar("T")


class CollectionScheduler:
    """Run independent collections concurrently with a fixed in-flight bound."""

    def __init__(self, max_workers: int = 4):
        if type(max_workers) is not int or not 1 <= max_workers <= 32:
            raise ValueError("max_workers must be an integer from 1 through 32")
        self.max_workers = max_workers

    def run(self, evidence_names: Sequence[str], is_parallel_safe: Callable[[str], bool],
            collect_one: Callable[[str], T]) -> dict[str, T]:
        """Collect each requested ID once and return results in request order.

        The classifier is supplied by the trusted host after resolving the
        current operator binding. It must return false on resolution errors so
        ``collect_one`` can retain the established failed-observation record.
        """
        names = tuple(evidence_names)
        if len(set(names)) != len(names):
            raise ValueError("Evidence identifiers must be unique")
        results: dict[str, T] = {}
        independent: list[str] = []

        def flush() -> None:
            if not independent:
                return
            if len(independent) == 1 or self.max_workers == 1:
                for name in independent:
                    results[name] = collect_one(name)
            else:
                # Submit only max_workers at a time, including queued tasks.
                # The executor is drained before the next serial acquisition.
                with ThreadPoolExecutor(max_workers=min(self.max_workers, len(independent))) as executor:
                    for start in range(0, len(independent), self.max_workers):
                        batch = independent[start:start + self.max_workers]
                        futures = {executor.submit(collect_one, name): name for name in batch}
                        for future in as_completed(futures):
                            results[futures[future]] = future.result()
            independent.clear()

        for name in names:
            if is_parallel_safe(name):
                independent.append(name)
            else:
                flush()
                results[name] = collect_one(name)
        flush()
        return {name: results[name] for name in names}
