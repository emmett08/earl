"""Recover retained session results without replaying a paid or uncertain request."""
from __future__ import annotations

from experiments.transfer_study.workspace import read_json, write_json


def retained_session(project, client, session_id: str) -> dict | None:
    path = project.root / f'session-{project.session}.json'
    if path.exists():
        result = read_json(path)
        if result['session_id'] != session_id:
            raise ValueError('Retained session identity differs from its allocation')
        return result
    progress = project.root / f'session-{project.session}-progress.json'
    calls = [c for c in client.records if c['session_id'] == session_id]
    if not calls and not progress.exists():
        return None
    result = read_json(progress) if progress.exists() else {
        'session_id': session_id, 'session': project.session, 'events': [], 'context_seconds': 0,
        'elapsed_seconds': 0, 'initial_messages': [], 'task_context': None}
    if result['session_id'] != session_id:
        raise ValueError('Interrupted session identity differs from its allocation')
    from .session import SessionRunner
    texts = [SessionRunner._response_text(c.get('response', {})) for c in calls]
    text = '\n\n'.join(t for t in texts if t.strip())
    result.update(status='interrupted', raw_answer=text, response_texts=texts, answer=None,
        api_attempt_ids=[c['attempt'] for c in calls], format_valid=None,
        annotation={'status': 'pending' if text else 'unobserved', 'method': 'interrupted-session/1',
                    'reason': 'Hard interruption; retained responses require independent coding'},
        handoff={'status': 'unverified', 'reason': 'Process stopped before terminal checkpoint'},
        file_result={'status': 'unverified', 'written': []}, timing_complete=False,
        recovery={'replayed_requests': 0, 'uncertain_attempts': [c['attempt'] for c in calls if c['status'] == 'started'],
                  'reason': 'Keep the interrupted attempt; continue only later planned sessions'})
    write_json(path, result)
    return result
