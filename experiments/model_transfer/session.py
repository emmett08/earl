"""Execute a fresh model session while preserving raw answers and measurement status."""
from __future__ import annotations

import copy
import json
import time

from experiments.transfer_study.workspace import write_json
from .answers import response_format
from .prompts import SessionPromptBuilder
from .provider import BudgetedClient, ExecutionStopped, ProviderResponseError
from .project import Project

TOOL = {'type': 'function', 'name': 'probe', 'description': 'Read the current service measurement report.',
        'strict': True, 'parameters': {'type': 'object', 'properties': {}, 'required': [],
                                        'additionalProperties': False}}


class SessionRunner:
    def __init__(self, client: BudgetedClient, plan: dict):
        self.client, self.plan = client, plan
        self.prompts = SessionPromptBuilder()

    def run(self, project: Project, model: dict, native_tools: bool, session_id: str, *,
            response_mode: str | None = None, context_style: str = 'compact',
            include_notes: bool | None = None, reuse: str = 'compatible') -> dict:
        start = time.monotonic()
        mode = response_mode or self.plan['response_mode']
        formatter = response_format(mode)
        notes = not project.strategy.requires_source if include_notes is None else include_notes
        question = f'Assess the service readiness now at {project.case.time(project.session)}. '
        result = {'session_id': session_id, 'session': project.session, 'model': model['version'],
                  'reasoning_effort': model['reasoning_effort'], 'native_tools': native_tools,
                  'response_mode': mode, 'context_style': context_style, 'include_notes': notes,
                  'reuse': reuse, 'task_context': None, 'status': 'no_answer', 'answer': None,
                  'format_valid': None, 'annotation': {'status': 'empty', 'reason': 'No response'},
                  'file_result': {'status': 'not_requested', 'written': []}}
        try:
            prepared = self.prompts.prepare(project, question, response_mode=mode,
                                             context_style=context_style, include_notes=notes, reuse=reuse)
            messages = prepared.messages
            result.update(context_seconds=prepared.context_seconds, task_context=prepared.task_context,
                          initial_messages=copy.deepcopy(messages),
                          initial_message_bytes=len(json.dumps(messages, ensure_ascii=False).encode('utf-8')))
            write_json(project.root / f'input-files-{project.session}.json', prepared.visible_files)
            for _ in range(self.plan['max_calls_per_session']):
                response = self.client.request(model, messages, [TOOL] if native_tools else [], session_id,
                                               response_mode=mode)
                result['provider_status'] = response['status']
                output = response['output']
                messages.extend(output)
                calls = [item for item in output if item.get('type') == 'function_call']
                if calls:
                    if not native_tools:
                        raise ValueError('Model requested an unavailable tool')
                    for call in calls:
                        if call.get('name') != 'probe' or json.loads(call['arguments']) != {}:
                            tool_output = {'error': 'Only probe with empty arguments is available'}
                        else:
                            tool_output = project.probe()
                        messages.append({'type': 'function_call_output', 'call_id': call['call_id'],
                                         'output': json.dumps(tool_output)})
                    continue
                text = self._response_text(response)
                result['raw_answer'] = text
                parsed = formatter.parse(text)
                result.update(status='submitted', **{k: parsed[k] for k in ('answer', 'format_valid', 'annotation')})
                result['file_result'] = project.persist(parsed['files']) if mode != 'prose' else result['file_result']
                result['handoff'] = project.remember_answer(text)
                break
            if result['status'] == 'no_answer':
                result['error'] = {'type': 'CallLimit', 'message': 'No answer within the call limit'}
        except Exception as exc:
            result.update(status='failed', error={'type': type(exc).__name__, 'message': str(exc)[:1000]})
            if isinstance(exc, ProviderResponseError):
                # Available task text is a measurement even when the provider
                # did not finish. It cannot trigger actions or become a complete
                # project handoff, and its meaning requires independent coding.
                text = self._response_text(exc.response)
                result.update(status=exc.attempt_status, provider_status=exc.response.get('status'),
                              raw_answer=text, answer=None, format_valid=None,
                              annotation={'status': 'pending' if text.strip() else 'empty',
                                          'reason': 'Response completion or validation failed; code any retained text independently',
                                          'method': 'unfinished-response/1'},
                              handoff={'status': 'not_retained', 'reason': 'Response was not complete and validated'})
            if isinstance(exc, ExecutionStopped):
                result['stop_reason'] = str(exc)
        finally:
            result['elapsed_seconds'] = time.monotonic() - start
            result['events'] = [e for e in project.events if e['session'] == project.session]
            write_json(project.root / f'session-{project.session}.json', result)
        return result

    @staticmethod
    def _response_text(response: dict) -> str:
        """Read only available text fragments, including a partly malformed response."""
        output = response.get('output')
        if not isinstance(output, list):
            return ''
        fragments = []
        for item in output:
            if not isinstance(item, dict) or item.get('type') != 'message':
                continue
            content = item.get('content')
            if not isinstance(content, list):
                continue
            fragments.extend(part['text'] for part in content
                             if isinstance(part, dict) and part.get('type') == 'output_text'
                             and isinstance(part.get('text'), str))
        return ''.join(fragments)
