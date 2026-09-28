"""Own one sequence's persistent project files and external fixture collector."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

from eal.knowledge import EALKnowledgeBase
from experiments.transfer_study.workspace import read_json, write_json
from .cases import Case
from .conditions import CONDITIONS
from .threshold_method import registry


class Project:
    def __init__(self, root: Path, case: Case, arm: str):
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
                '\ntimeout_seconds=10\nmax_output_bytes=4096\ninherit_env=[]\n')
            knowledge = EALKnowledgeBase(self.workspace, self.workspace / 'tools.toml',
                                         method_registry=registry())
            knowledge.register('argument.eal', entry_id='orders', context={'service': 'orders'},
                               claims=['criterion_evaluated'])

    def set_session(self, session: int) -> None:
        self.session = session
        write_json(self.state, self.case.measurement(session))

    def probe(self) -> dict:
        start = time.monotonic()
        result = read_json(self.state)
        self.events.append({'session': self.session, 'kind': 'native_probe', 'output': result,
                            'elapsed_seconds': time.monotonic() - start})
        return result

    def context(self, question: str) -> list[dict]:
        return self.strategy.prepare(self, question)

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
        prospective = {name: value for name, value in self.files().items() if name != 'specification.txt'}
        for item in files:
            if not isinstance(item, dict) or set(item) != {'name', 'content'}:
                return {'status': 'rejected', 'reason': 'Each file needs name and content', 'written': []}
            name, content = item['name'], item['content']
            if (not isinstance(name, str) or name != Path(name).name or name in names or
                    not name.endswith(('.md', '.txt')) or name == 'specification.txt' or
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
