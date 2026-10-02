"""Own one sequence's persistent project files and external fixture collector."""
from __future__ import annotations

import json
from contextlib import closing
import shutil
import sqlite3
from pathlib import Path
import sys
import time

from eal.knowledge import EALKnowledgeBase
from experiments.transfer_study.workspace import read_json, write_json
from .task_case import TaskCase
from .conditions import CONDITIONS
from .threshold_method import registry


class Project:
    def __init__(self, root: Path, case: TaskCase, arm: str):
        self.root, self.case, self.arm = root, case, arm
        self.strategy = CONDITIONS[arm]
        self.workspace = root / 'project'
        self.workspace.mkdir(parents=True)
        self.state = root / 'collector-state.json'
        self.events: list[dict] = []
        self.set_session(0)
        (self.workspace / 'specification.txt').write_text(case.specification())
        if self.strategy.requires_source:
            (self.workspace / 'argument.eal').write_text(case.source())
            collector = Path(__file__).with_name('collector.py').resolve()
            (self.workspace / 'tools.toml').write_text(
                '[tools.probe]\nkind="command"\nversion="1"\n' +
                'argv=' + json.dumps([sys.executable, str(collector), str(self.state.resolve())]) +
                '\ntimeout_seconds=10\nmax_output_bytes=65536\ninherit_env=[]\n')
            knowledge = EALKnowledgeBase(self.workspace, self.workspace / 'tools.toml',
                                         method_registry=registry())
            knowledge.register('argument.eal', entry_id='orders', context=case.context(),
                               claims=['criterion_evaluated'])

    @classmethod
    def attach(cls, root: Path, case: TaskCase, arm: str):
        """Open the same persistent project; never reinitialise its observations."""
        project = object.__new__(cls)
        project.root, project.case, project.arm = root, case, arm
        project.strategy = CONDITIONS[arm]
        project.workspace = root / 'project'
        project.state = root / 'collector-state.json'
        project.events, project.session = [], 0
        if not project.workspace.is_dir() or not project.state.is_file():
            raise ValueError('Retained project is incomplete')
        return project

    def explain(self, assessment_id: str) -> dict:
        knowledge = EALKnowledgeBase(self.workspace, self.workspace / 'tools.toml', method_registry=registry())
        return knowledge.explain(assessment_id)

    def set_session(self, session: int) -> None:
        self.session = session
        write_json(self.state, self.case.measurement(session))

    def registration_context(self) -> dict:
        return self.case.context_at(self.session) if hasattr(self.case, 'context_at') else self.case.context()

    def probe(self, *, host_snapshot: bool = False) -> dict:
        start = time.monotonic()
        event = {'session': self.session,
                 'kind': 'host_raw_snapshot_read' if host_snapshot else 'native_probe', 'status': 'started'}
        self.events.append(event)
        try:
            result = read_json(self.state)
            event.update(status='completed', output=result)
            return result
        except Exception as exc:
            event.update(status='failed', error={'type': type(exc).__name__, 'message': str(exc)[:1000]})
            raise
        finally:
            event['elapsed_seconds'] = time.monotonic() - start

    def context(self, question: str, *, style: str = 'full', reuse: str = 'compatible', reasoner: str = 'workflow') -> list[dict]:
        if reasoner != 'workflow':
            from .reasoning_context import prepare_reasoning_context
            return prepare_reasoning_context(self, question, reasoner=reasoner, reuse=reuse)
        return self.strategy.prepare(self, question, style=style, reuse=reuse)

    def fork(self, root: Path, session: int) -> Project:
        """Clone donor artefacts while keeping the frozen collector binding identical."""
        shutil.copytree(self.root, root, ignore=shutil.ignore_patterns('*-wal', '*-shm'))
        for source in self.workspace.rglob('*.sqlite3'):
            destination = root / source.relative_to(self.root)
            with closing(sqlite3.connect(source)) as origin, closing(sqlite3.connect(destination)) as target:
                origin.backup(target)
        clone = object.__new__(Project)
        clone.root, clone.case, clone.arm = root, self.case, self.arm
        clone.strategy = self.strategy
        clone.workspace = root / 'project'
        clone.state, clone.session, clone.events = self.state, session, []
        return clone

    def remember_answer(self, text: str) -> dict:
        """Retain the latest complete answer verbatim as an ordinary project note."""
        if not text.strip():
            return {'status': 'not_retained', 'reason': 'No answer text'}
        if len(text.encode('utf-8')) > 8192:
            return {'status': 'not_retained', 'reason': 'Complete answer exceeds the note byte limit'}
        path = self.workspace / 'latest-answer.md'
        path.write_text(text)
        return {'status': 'retained', 'name': path.name, 'bytes': len(text.encode('utf-8'))}

    def files(self) -> dict[str, str]:
        # The host interprets EAL source. Models see the specification and natural
        # notes, not executable collector state, configuration or redundant source.
        return {p.name: p.read_text() for p in sorted(self.workspace.iterdir())
                if p.is_file() and p.suffix in ('.txt', '.md')}

    def persist(self, files: object) -> dict:
        """Reject invalid side effects without discarding the submitted answer."""
        if not isinstance(files, list) or len(files) > 4:
            return {'status': 'rejected', 'reason': 'Use at most four file objects', 'written': []}
        names = set()
        prospective = {name: value for name, value in self.files().items()
                       if name not in ('specification.txt', 'latest-answer.md')}
        for item in files:
            if not isinstance(item, dict) or set(item) != {'name', 'content'}:
                return {'status': 'rejected', 'reason': 'Each file needs name and content', 'written': []}
            name, content = item['name'], item['content']
            if (not isinstance(name, str) or name != Path(name).name or name in names or
                    not name.endswith(('.md', '.txt')) or name in ('specification.txt', 'latest-answer.md') or
                    not isinstance(content, str) or len(content) > 8000 or
                    (self.workspace / name).is_symlink()):
                return {'status': 'rejected', 'reason': 'Invalid or protected project note', 'written': []}
            names.add(name)
            prospective[name] = content
        if len(prospective) > 4 or sum(len(value.encode('utf-8')) for value in prospective.values()) > 8192:
            return {'status': 'rejected', 'reason': 'Project notes exceed four files or 8192 UTF-8 bytes', 'written': []}
        for item in files:
            (self.workspace / item['name']).write_text(item['content'])
        return {'status': 'accepted', 'written': sorted(names)}
