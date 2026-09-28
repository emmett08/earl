"""Select ordinary information or a checked EAL task-context projection."""
from typing import Protocol
import json
import time

from eal.knowledge import EALKnowledgeBase, ModelContextAdapter
from .threshold_method import registry
from .task_context import TaskContextBuilder, TaskContract


class ContextStrategy(Protocol):
    requires_source: bool

    def prepare(self, project, question: str, *, style: str, reuse: str) -> list[dict]: ...


class OrdinaryContext:
    requires_source = False

    def prepare(self, project, question: str, *, style: str = 'full', reuse: str = 'compatible') -> list[dict]:
        return []


class EALContext:
    requires_source = True

    def prepare(self, project, question: str, *, style: str = 'full', reuse: str = 'compatible') -> list[dict]:
        if style not in ('compact', 'full'):
            raise ValueError('Unknown EAL context style')
        knowledge = EALKnowledgeBase(project.workspace, project.workspace / 'tools.toml',
                                     method_registry=registry())
        event = {'session': project.session, 'kind': 'eal_assess', 'assessment': None}
        project.events.append(event)
        start = time.monotonic()
        try:
            result = ModelContextAdapter(knowledge).prepare(
                question, 'orders', 'criterion_evaluated', now=project.case.time(project.session), reuse=reuse)
            event['assessment'] = result['assessment']
            task = TaskContextBuilder(TaskContract.from_case(project.case),
                                      (project.workspace / 'argument.eal').read_text()).build(result['assessment'])
            event['task_context'] = task
            messages = [{'role': 'system', 'content':
                         'Current host-computed task result and its applicability:\n' +
                         json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}]
            if style == 'full':
                messages.extend(result['messages'][:-1])
            return messages
        finally:
            event['elapsed_seconds'] = time.monotonic() - start


CONDITIONS: dict[str, ContextStrategy] = {'ordinary': OrdinaryContext(), 'eal': EALContext()}
