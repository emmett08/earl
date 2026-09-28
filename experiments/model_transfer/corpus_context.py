"""Bind an authored task to checked runtime output, without access to answer keys."""
from __future__ import annotations

from dataclasses import dataclass, fields

from eal.model import Program
from eal.parser import parse
from .corpus_logic import rule_digest


@dataclass(frozen=True)
class CorpusTaskContract:
    expected_source: str
    rule_identity: str
    target_identity: str
    task_id: str

    @classmethod
    def from_case(cls, case):
        return cls(case.source(), rule_digest(case.rule), rule_digest(case.target_identity()), case.identifier)

    def validate(self, source: str):
        from .task_context import TaskCorrespondenceError
        expected, actual = parse(self.expected_source), parse(source)
        excluded = {'source_digest', 'locations'}
        changes = [field.name for field in fields(Program)
                   if field.name not in excluded and getattr(expected, field.name) != getattr(actual, field.name)]
        if changes:
            raise TaskCorrespondenceError('Source/task correspondence failed: ' + ', '.join(changes))
        return actual

    def build(self, assessment: dict, program: Program, explain=None) -> dict:
        from .task_context import TaskCorrespondenceError
        from .corpus_cases import dated
        from eal.semantics import parse_time
        packet = assessment['packet']
        if (assessment.get('source_digest') != program.source_digest or
                packet.get('source_digest') != program.source_digest or assessment.get('claim') != 'criterion_evaluated'):
            raise TaskCorrespondenceError('Assessment does not match the source/task binding')
        evidence = packet.get('evidence', {}).get('report', {})
        argument = packet.get('arguments', {}).get('result', {})
        method = argument.get('method_result', {})
        decision, basis, states, scope = 'undetermined', 'evidence_unavailable', {}, None
        if (packet.get('summary_complete') is True and assessment.get('status') == 'supported' and
                evidence.get('status') == 'available' and argument.get('status') == 'supported' and
                method.get('status') == 'supported' and method.get('method') == 'experiment/task-rules/1'):
            if explain is None:
                raise TaskCorrespondenceError('The checked structured method result requires the public explanation')
            trace = explain(assessment['assessment_id'])
            if any(trace.get(key) != assessment.get(key) for key in
                   ('assessment_id', 'source_digest', 'collection_id', 'assessed_at', 'context_fingerprint')):
                raise TaskCorrespondenceError('Explanation does not match the assessed task')
            checked = trace.get('arguments', {}).get('result', {}).get('reasoning_result', {})
            if any(checked.get(key) != method.get(key) for key in ('status', 'method', 'evidence_id', 'input_digest')):
                raise TaskCorrespondenceError('Explanation method does not match the bounded packet')
            output = checked.get('details', {})
            pairs = {'ready': 'criterion_met', 'not_ready': 'criterion_failed', 'undetermined': 'evidence_unavailable'}
            if (output.get('rule_digest') != self.rule_identity or output.get('decision') not in pairs or
                    output.get('target_identity_digest') != self.target_identity or
                    output.get('basis') != pairs[output['decision']]):
                raise TaskCorrespondenceError('Checked method output differs from the declared task rule')
            if parse_time(dated(output['snapshot_minute'])) != parse_time(evidence['observed_at']):
                raise TaskCorrespondenceError('Snapshot computation time differs from the acquired observation time')
            decision, basis, states = output['decision'], output['basis'], output['states']
            scope = output['scope']
        return {'schema': 'EAL/rule-task-context/1', 'task_id': self.task_id, 'scope': scope,
                'decision': decision, 'basis': basis,
                'reading': None, 'observed_at': evidence.get('observed_at'), 'assessed_at': assessment['assessed_at'],
                'criterion': {'method': 'experiment/task-rules/1', 'rule_digest': self.rule_identity,
                              'max_age_seconds': 60}, 'requirement_states': states,
                'claim_statement': program.claims['criterion_evaluated'].statement,
                'prose_verified': False, 'physical_interpretation_verified': False,
                'limitations': ['Task semantics and snapshot continuity are authored assumptions.',
                                'Facts are acquired as one snapshot; selective individual-fact collection is not measured.']}
