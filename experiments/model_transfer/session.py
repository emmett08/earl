"""Execute one fresh model session, retaining answer and side-effect outcomes."""
from __future__ import annotations

import copy
import json
import time

from experiments.transfer_study.workspace import write_json
from .answers import AnswerParser, OUTPUT
from .provider import BudgetedClient, ExecutionStopped
from .project import Project

TOOL = {'type': 'function', 'name': 'probe', 'description': 'Read the current service measurement report.',
        'strict': True, 'parameters': {'type': 'object', 'properties': {}, 'required': [],
                                        'additionalProperties': False}}


class SessionRunner:
    def __init__(self, client: BudgetedClient, plan: dict):
        self.client, self.plan = client, plan
        self.parser = AnswerParser()

    def run(self, project: Project, model: dict, native_tools: bool, session_id: str) -> dict:
        start = time.monotonic()
        question = f'Assess the service now at {project.case.time(project.session)}. '
        messages = [{'role': 'system', 'content': 'Complete the engineering task using the supplied project and available tools.'}]
        result = {'session_id': session_id, 'session': project.session, 'model': model['version'],
                  'reasoning_effort': model['reasoning_effort'], 'native_tools': native_tools,
                  'status': 'no_answer', 'answer': None, 'format_valid': False,
                  'file_result': {'status': 'not_requested', 'written': []}}
        try:
            context_start = time.monotonic()
            messages.extend(project.context(question))
            result['context_seconds'] = time.monotonic() - context_start
            visible_files = project.files()
            write_json(project.root / f'input-files-{project.session}.json', visible_files)
            messages.append({'role': 'user', 'content': question + OUTPUT + '\nProject files:\n' +
                             json.dumps(visible_files)})
            result['initial_messages'] = copy.deepcopy(messages)
            for _ in range(self.plan['max_calls_per_session']):
                response = self.client.request(model, messages, [TOOL] if native_tools else [], session_id)
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
                text = ''.join(part['text'] for item in output if item.get('type') == 'message'
                               for part in item.get('content', []) if part.get('type') == 'output_text')
                result['raw_answer'] = text
                parsed = self.parser.parse(text)
                result.update(status='submitted', answer=parsed['answer'], format_valid=parsed['format_valid'])
                result['file_result'] = project.persist(parsed['files'])
                break
            if result['status'] == 'no_answer':
                result['error'] = {'type': 'CallLimit', 'message': 'No answer within the call limit'}
        except Exception as exc:
            result.update(status='failed', error={'type': type(exc).__name__, 'message': str(exc)[:1000]})
            if isinstance(exc, ExecutionStopped):
                result['stop_reason'] = str(exc)
        finally:
            result['elapsed_seconds'] = time.monotonic() - start
            result['events'] = [e for e in project.events if e['session'] == project.session]
            write_json(project.root / f'session-{project.session}.json', result)
        return result
