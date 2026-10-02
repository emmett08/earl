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

TOOL = {'type': 'function', 'name': 'probe', 'description': 'Read the current task evidence snapshot.',
        'strict': True, 'parameters': {'type': 'object', 'properties': {}, 'required': [],
                                        'additionalProperties': False}}


class SessionRunner:
    def __init__(self, client: BudgetedClient, plan: dict):
        self.client, self.plan = client, plan
        self.prompts = SessionPromptBuilder()

    def run(self, project: Project, model: dict, native_tools: bool, session_id: str, *,
            response_mode: str | None = None, context_style: str = 'compact',
            include_notes: bool | None = None, reuse: str = 'compatible', reasoner: str = 'workflow') -> dict:
        start = time.monotonic()
        first_record = len(self.client.records)
        mode = response_mode or self.plan['response_mode']
        formatter = response_format(mode)
        notes = not project.strategy.requires_source if include_notes is None else include_notes
        question = f'Assess task readiness now at {project.case.time(project.session)}. '
        revision = project.registration_context().get('evidence_revision')
        if revision is not None:
            question += f'Public evidence revision: {revision}. Earlier revisions have been invalidated. '
        result = {'session_id': session_id, 'session': project.session, 'model': model['version'],
                  'reasoning_effort': model['reasoning_effort'], 'native_tools': native_tools,
                  'response_mode': mode, 'context_style': context_style, 'include_notes': notes,
                  'reuse': reuse, 'reasoner': reasoner, 'task_context': None, 'status': 'no_answer', 'answer': None,
                  'response_texts': [],
                  'format_valid': None, 'annotation': {'status': 'empty', 'reason': 'No response'},
                  'file_result': {'status': 'not_requested', 'written': []}}
        if self.plan.get('evidence_restoration'):
            result.update(whole_answer_consistency_required=True, canonical_decision=None)
        progress_path = project.root / f'session-{project.session}-progress.json'
        def checkpoint():
            result['events'] = [e for e in project.events if e['session'] == project.session]
            result['elapsed_seconds'] = time.monotonic() - start
            write_json(progress_path, result)

        try:
            prepared = self.prompts.prepare(project, question, response_mode=mode,
                                             context_style=context_style, include_notes=notes, reuse=reuse, reasoner=reasoner)
            messages = prepared.messages
            result.update(context_seconds=prepared.context_seconds, task_context=prepared.task_context,
                          initial_messages=copy.deepcopy(messages),
                          initial_message_bytes=len(json.dumps(messages, ensure_ascii=False).encode('utf-8')))
            write_json(project.root / f'input-files-{project.session}.json', prepared.visible_files)
            checkpoint()
            for _ in range(self.plan['max_calls_per_session']):
                response = self.client.request(model, messages, [TOOL] if native_tools else [], session_id,
                                               response_mode=mode)
                result['provider_status'] = response['status']
                output = response['output']
                messages.extend(output)
                # A response can contain both task text and function calls. Keep
                # its text before any tool fails or the call limit ends the run.
                text = self._response_text(response)
                if text:
                    result['response_texts'].append(text)
                calls = [item for item in output if item.get('type') == 'function_call']
                if calls:
                    self._execute_tools(project, calls, native_tools, messages)
                    checkpoint()
                    continue
                if not text.strip() and any(part.strip() for part in result['response_texts']):
                    result.update(status='incomplete', error={
                        'type': 'MissingFinalAnswer', 'message': 'No final text followed the tool response'})
                    break
                result['raw_answer'] = text
                parsed = formatter.parse(text)
                result.update(status='submitted', **{k: parsed[k] for k in ('answer', 'format_valid', 'annotation')})
                if self.plan.get('evidence_restoration'):
                    result['canonical_decision'] = parsed.get('canonical_decision')
                result['file_result'] = project.persist(parsed['files']) if mode != 'prose' else result['file_result']
                result['handoff'] = project.remember_answer(text)
                break
            if result['status'] == 'no_answer':
                result['error'] = {'type': 'CallLimit', 'message': 'No answer within the call limit'}
                if any(part.strip() for part in result['response_texts']):
                    result['status'] = 'incomplete'
        except Exception as exc:
            result.update(status='failed', error={'type': type(exc).__name__, 'message': str(exc)[:1000]})
            if isinstance(exc, ProviderResponseError):
                text = self._response_text(exc.response)
                if text:
                    result['response_texts'].append(text)
                result.update(status=exc.attempt_status, provider_status=exc.response.get('status'))
                self._retain_unfinished_text(result)
            if (isinstance(exc, ExecutionStopped) or
                    isinstance(exc, ProviderResponseError) and exc.stop_collection):
                result['stop_reason'] = str(exc)
        finally:
            if result['status'] != 'submitted' and result['response_texts']:
                self._retain_unfinished_text(result)
            # This per-invocation list distinguishes an absent ledger from a
            # confirmed pre-request failure, even if a session ID was reused.
            result['api_attempt_ids'] = self.client.receipts(session_id, first_record)
            result['elapsed_seconds'] = time.monotonic() - start
            result['events'] = [e for e in project.events if e['session'] == project.session]
            write_json(project.root / f'session-{project.session}.json', result)
        return result

    @staticmethod
    def _execute_tools(project: Project, calls: list[dict], native_tools: bool,
                       messages: list[dict]) -> None:
        if not native_tools:
            raise ValueError('Model requested an unavailable tool')
        for call in calls:
            if call.get('name') != 'probe' or json.loads(call['arguments']) != {}:
                tool_output = {'error': 'Only probe with empty arguments is available'}
            else:
                tool_output = project.probe()
            messages.append({'type': 'function_call_output', 'call_id': call['call_id'],
                             'output': json.dumps(tool_output)})

    @staticmethod
    def _retain_unfinished_text(result: dict) -> None:
        """Expose unfinished text to measurement without file or handoff effects."""
        text = '\n\n'.join(result['response_texts'])
        result.update(raw_answer=text, answer=None, format_valid=None,
                      annotation={'status': 'pending' if text.strip() else 'empty',
                                  'reason': 'Session did not finish; code retained response text independently',
                                  'method': 'unfinished-response/1'},
                      handoff={'status': 'not_retained', 'reason': 'Response was not complete and validated'})

    @staticmethod
    def _response_text(response: dict) -> str:
        """Read only available text fragments, including a partly malformed response."""
        if not isinstance(response, dict):
            return ''
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
