"""Identify a run and distinguish provider observations from scripted rehearsal."""
from pathlib import Path
from uuid import uuid4

from experiments.transfer_study.workspace import read_json, write_json
from .provider import OpenAITransport


class RunIdentity:
    """Keep one execution identity across collection and offline reconstruction."""

    @staticmethod
    def record(root: Path, plan: dict, transport: object) -> dict:
        path = root / 'provenance.json'
        value = read_json(path) if path.exists() else {}
        kind = 'live' if type(transport) is OpenAITransport else 'scripted'
        if value.get('execution_kind', kind) != kind:
            raise ValueError('A run cannot mix live and scripted observations')
        value.setdefault('run_id', str(uuid4()))
        if value['run_id'] in plan.get('pilot_run_ids', []):
            raise ValueError('Evaluation cannot reuse an allocation-pilot run identity')
        value.update(execution_kind=kind, study_id=plan.get('study_id'),
                     source_language=plan.get('source_language'),
                     protocol_version=plan.get('protocol_version'),
                     study_role=plan.get('study_role', 'diagnostics'),
                     pilot_run_ids=plan.get('pilot_run_ids', []))
        write_json(path, value)
        return value
