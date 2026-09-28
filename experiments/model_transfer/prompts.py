"""Assemble sufficient fresh-session prompts without redundant EAL project text."""
from dataclasses import dataclass
import json
import time

from .answers import response_format
from .project import Project


@dataclass
class PreparedPrompt:
    messages: list[dict]
    visible_files: dict[str, str]
    task_context: dict | None
    context_seconds: float


class SessionPromptBuilder:
    def prepare(self, project: Project, question: str, *, response_mode: str,
                context_style: str, include_notes: bool, reuse: str, reasoner: str = 'workflow') -> PreparedPrompt:
        started = time.monotonic()
        messages = [{'role': 'system', 'content':
                     'Complete the engineering task using the supplied project information and available tools.'}]
        messages.extend(project.context(question, style=context_style, reuse=reuse, reasoner=reasoner))
        context_seconds = time.monotonic() - started
        task_context = next((event['task_context'] for event in reversed(project.events)
                             if event['session'] == project.session and 'task_context' in event), None)
        files = project.files()
        visible = {}
        if not project.strategy.requires_source:
            visible['specification.txt'] = files['specification.txt']
        if include_notes:
            visible.update({name: text for name, text in files.items() if name != 'specification.txt'})
        content = question + response_format(response_mode).instructions
        if visible:
            content += '\nProject files:\n' + json.dumps(visible, ensure_ascii=False)
        messages.append({'role': 'user', 'content': content})
        return PreparedPrompt(messages, visible, task_context, context_seconds)
