"""Load independently authored synthetic tasks without loading answer keys into prompts."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from .corpus_logic import rule_digest

EPOCH = datetime(2026, 9, 28, 10, tzinfo=timezone.utc)
SNAPSHOT_MAX_AGE_SECONDS = 60


def dated(minute: float) -> str:
    return (EPOCH + timedelta(minutes=minute)).isoformat().replace('+00:00', 'Z')


@dataclass(frozen=True)
class CorpusCase:
    identifier: str
    family: str
    task_specification: dict
    rule: dict
    timeline: tuple[dict, ...]
    expected_decisions: tuple[str, ...]
    cohort: str = 'separate_ai_authored'
    task_kind: str = 'task_rules'

    def context(self) -> dict:
        return {'task_id': self.identifier}

    def context_at(self, session: int) -> dict:
        context = self.context()
        revision = self.timeline[session].get('evidence_revision')
        if revision is not None:
            context['evidence_revision'] = revision
        return context

    def target_identity(self) -> dict:
        return {key: self.task_specification['scope'][key]
                for key in self.task_specification['identity_scope_keys']}

    def time(self, session: int) -> str:
        return dated(self.timeline[session]['now_minute'])

    def measurement(self, session: int) -> dict:
        snapshot = self.timeline[session]
        return {'observed_at': self.time(session), 'value': {
            'task_id': self.identifier, 'rule_digest': rule_digest(self.rule), 'rule': deepcopy(self.rule),
            'target_identity': self.target_identity(), 'target_identity_digest': rule_digest(self.target_identity()),
            'now_minute': snapshot['now_minute'], 'scope': deepcopy(snapshot['scope']),
            'facts': deepcopy(snapshot['facts']),
        }}

    def specification(self) -> str:
        return (self.task_specification['scope_description'] + '\n' +
                self.task_specification['natural_language_rule'] + '\n'
                'Answer ready, not_ready or undetermined for the current service task. '
                'The probe supplies a dated snapshot; reuse it for at most 60 seconds inclusive. '
                'Select active facts matching each requirement\'s scope keys, whose age at the snapshot '
                'time lies between zero and the requirement maximum inclusive. Use the uniquely newest '
                'eligible fact. Missing or ineligible facts are unknown. A false conjunct makes its '
                'conjunction false; otherwise an unknown conjunct makes it unknown. A true route makes '
                'an alternative true; otherwise an unknown route makes it unknown. True means ready, '
                'false means not_ready and unknown means undetermined. '
                'These rules assess the snapshot; validity for 60 seconds is an explicit task assumption. '
                'Snapshot times and fact times use minutes after 2026-09-28T10:00:00Z.\n'
                'Target identity: ' + json.dumps(self.target_identity(), sort_keys=True) + '\n'
                'Current version and configuration scope comes from the probe snapshot.\n'
                'Task rule: ' + json.dumps(self.rule, sort_keys=True))

    def source(self) -> str:
        statement = json.dumps(self.task_specification['natural_language_rule'])
        digest = rule_digest(self.rule)
        target_digest = rule_digest(self.target_identity())
        return f'''language "EAL/2"

environment scope {{
  require "task_id" == "{self.identifier}"
}}
tool probe {{
  version "1"
}}
evidence report {{
  tool probe
  kind task_snapshot
  environment scope
  max_age {SNAPSHOT_MAX_AGE_SECONDS}
  require "task_id" == "{self.identifier}"
  require "rule_digest" == "{digest}"
  require "target_identity_digest" == "{target_digest}"
}}
reasoning task_rules {{
  method "experiment/task-rules/1"
  rationale "Evaluate eligible dated facts using the source-bound three-valued task rule; negative and unknown outcomes are completed calculations."
  require "snapshot_minute" >= 0
}}
claim criterion_evaluated {{
  statement {statement}
  environment scope
}}
argument result = [evidence report] via task_rules => criterion_evaluated
'''


def load_cases(path: Path | None = None) -> tuple[CorpusCase, ...]:
    payload = json.loads((path or Path(__file__).with_name('task_corpus.json')).read_text())
    if payload['schema'] != 'EAL/model-transfer-task-corpus/1':
        raise ValueError('Unsupported task corpus schema')
    cases = []
    for record in payload['cases']:
        timeline = tuple({key: deepcopy(value) for key, value in item.items() if key != 'expected'}
                         for item in record['timeline'])
        if [item['session'] for item in timeline] != list(range(11)):
            raise ValueError('The task corpus requires exactly initial plus ten recipient sessions')
        if [item['now_minute'] for item in timeline] != list(range(11)):
            raise ValueError('The snapshot-reuse corpus requires one-minute session intervals')
        for session in range(1, 11, 2):
            for key in ('scope', 'facts'):
                previous = json.dumps(timeline[session - 1][key], sort_keys=True)
                current = json.dumps(timeline[session][key], sort_keys=True)
                if previous != current:
                    raise ValueError('Snapshot continuity requires unchanged facts and scope in intervening sessions')
        cases.append(CorpusCase(record['identifier'], record['family'], record['specification'],
                                record['rule'], timeline,
                                tuple(item['expected'] for item in record['timeline'])))
    if len({case.identifier for case in cases}) != len(cases):
        raise ValueError('Task corpus identifiers must be unique')
    return tuple(cases)
