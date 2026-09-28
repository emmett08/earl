"""Strategies for ordinary sessions, EAL reuse and forced-collection diagnostics."""
from typing import Protocol
import time

from eal.knowledge import EALKnowledgeBase, ModelContextAdapter
from .threshold_method import registry


class ContextStrategy(Protocol):
    requires_source: bool

    def prepare(self, project, question: str) -> list[dict]: ...


class OrdinaryContext:
    requires_source = False

    def prepare(self, project, question: str) -> list[dict]:
        return []


class EALContext:
    requires_source = True

    def __init__(self, reuse: str = 'compatible'):
        self.reuse = reuse

    def prepare(self, project, question: str) -> list[dict]:
        # Reopen host state; no Python-held assessment crosses a session boundary.
        knowledge = EALKnowledgeBase(project.workspace, project.workspace / 'tools.toml',
                                     method_registry=registry())
        event = {'session': project.session, 'kind': 'eal_assess', 'assessment': None}
        project.events.append(event)
        start = time.monotonic()
        try:
            result = ModelContextAdapter(knowledge).prepare(
                question, 'orders', 'criterion_evaluated', now=project.case.time(project.session),
                reuse=self.reuse)
            event['assessment'] = result['assessment']
        finally:
            event['elapsed_seconds'] = time.monotonic() - start
        return result['messages'][:-1]


CONDITIONS: dict[str, ContextStrategy] = {
    'ordinary': OrdinaryContext(), 'eal': EALContext(), 'eal_fresh': EALContext('fresh'),
}
