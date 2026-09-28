"""Bind this experiment's readiness task to checked EAL computation.

This is an application adapter, not a general interpreter of claim prose. Its
binding accepts a deliberately small authored argument contract. A changed task
or source must pass correspondence checks before any decision is presented.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from eal.model import Predicate
from eal.parser import parse
from eal.semantics import parse_time


class TaskCorrespondenceError(ValueError):
    """The source cannot be used as the declared experiment task."""


@dataclass(frozen=True)
class TaskContract:
    metric: str
    unit: str
    threshold: float
    direction: str
    assumption_from: str
    assumption_until: str | None
    service: str = 'orders'
    max_age: int = 300
    claim_id: str = 'criterion_evaluated'
    argument_id: str = 'result'
    evidence_id: str = 'report'
    method_id: str = 'experiment/threshold/2'

    @classmethod
    def from_case(cls, case) -> 'TaskContract':
        # Only task metadata enter this binding. Neither current nor expected
        # measurements, reference answers or model answers are read here.
        return cls(case.metric, case.unit, case.threshold, case.direction,
                   case.assumption_from, case.assumption_until)

    @property
    def statement(self) -> str:
        return (f'For {self.service}, the measured {self.metric} in {self.unit} has been compared '
                f'with {self.direction} {self.threshold}; meets establishes ready and fails '
                'establishes not_ready within the declared applicability conditions.')

    def validate(self, source: str):
        """Check parsed declarations against the independent application binding."""
        program = parse(source)
        errors = []
        if (set(program.environments) != {'scope'} or
                program.environments['scope'].predicates != (Predicate('service', '==', self.service),)):
            errors.append('environment scope')
        evidence = program.evidence.get(self.evidence_id)
        expected = (Predicate('reading', '>=', 0), Predicate('threshold', '==', self.threshold),
                    Predicate('direction', '==', self.direction), Predicate('service', '==', self.service),
                    Predicate('metric', '==', self.metric), Predicate('unit', '==', self.unit))
        if (evidence is None or evidence.environment != 'scope' or evidence.tool != 'probe' or
                evidence.kind != 'threshold_measurement' or evidence.max_age != self.max_age or
                set(evidence.predicates) != set(expected) or len(evidence.predicates) != len(expected)):
            errors.append('measurement admission, criterion, scope or units')
        reasoning = program.reasoning.get('threshold')
        if (reasoning is None or reasoning.method != self.method_id or reasoning.backing or
                reasoning.predicates != (Predicate('reading', '>=', 0),)):
            errors.append('method and result requirements')
        claim = program.claims.get(self.claim_id)
        if (claim is None or claim.statement != self.statement or claim.environment != 'scope' or
                claim.proposition is not None):
            errors.append('claim statement or proposition')
        argument = program.arguments.get(self.argument_id)
        expected_assumptions = ('window',) if self.assumption_until else ()
        if (argument is None or argument.conclusion != self.claim_id or argument.reasoning != 'threshold' or
                argument.evidence != (self.evidence_id,) or argument.assumptions != expected_assumptions or
                argument.premises or argument.binding is not None):
            errors.append('argument dependencies')
        if self.assumption_until:
            assumption = program.assumptions.get('window')
            if (assumption is None or assumption.valid_from != self.assumption_from or
                    assumption.valid_until != self.assumption_until or assumption.validation != self.evidence_id or
                    assumption.environment != 'scope' or assumption.statement != 'The operating assumption applies.'):
                errors.append('assumption applicability')
        if (set(program.claims) != {self.claim_id} or set(program.arguments) != {self.argument_id} or
                set(program.evidence) != {self.evidence_id} or set(program.reasoning) != {'threshold'} or
                set(program.assumptions) != set(expected_assumptions) or set(program.tools) != {'probe'} or
                program.tools['probe'].version != '1' or program.objections or program.argumentation_directives or
                program.patterns or program.applications or program.duplicates):
            errors.append('additional or missing argument declarations')
        if errors:
            raise TaskCorrespondenceError('Source/task correspondence failed: ' + '; '.join(errors))
        return program


class TaskContextBuilder:
    """Produce a standalone result from a source-bound, completed assessment.

    The registered method computes the comparison. This adapter maps its checked
    Boolean outputs to the application's answer vocabulary, preserving scope,
    time, unavailable evidence and the limits of authored interpretation.
    """

    def __init__(self, contract: TaskContract, source: str):
        self.contract = contract
        self.program = contract.validate(source)

    def build(self, assessment: dict) -> dict:
        contract = self.contract
        packet = assessment['packet']
        if (assessment.get('source_digest') != self.program.source_digest or
                packet.get('source_digest') != self.program.source_digest or
                assessment.get('claim') != contract.claim_id):
            raise TaskCorrespondenceError('Assessment does not match the source/task binding')
        evidence = packet.get('evidence', {}).get(contract.evidence_id, {})
        assumption = packet.get('assumptions', {}).get('window')
        argument = packet.get('arguments', {}).get(contract.argument_id, {})
        method = argument.get('method_result', {})
        outputs = method.get('outputs', {})
        decision, basis = 'undetermined', 'evidence_unavailable'
        reading = None
        limitations = ['Claim prose and physical measurement interpretation remain authored assertions.']
        if packet.get('summary_complete') is not True:
            limitations.append('The assessment summary omits information required to resolve the task.')
        elif assumption and assumption.get('time_status') in ('expired', 'not_started'):
            basis = 'assumption_' + assumption['time_status']
        elif evidence.get('status') != 'available':
            failures = evidence.get('predicate_failures', [])
            if {'path': 'reading', 'issue': 'missing_field'} in failures:
                basis = 'measurement_missing'
            elif ('stale_observation' in evidence.get('availability_issues', []) or
                  evidence.get('observed_at') and
                  parse_time(evidence['observed_at']) > parse_time(assessment['assessed_at'])):
                basis = 'stale_measurement'
        elif (assessment.get('status') == 'supported' and argument.get('status') == 'supported' and
              method.get('status') == 'supported' and method.get('method') == contract.method_id):
            reading = outputs.get('reading')
            if (type(reading) not in (int, float) or not math.isfinite(reading) or reading < 0 or
                    outputs.get('threshold') != contract.threshold or type(outputs.get('meets')) is not bool or
                    type(outputs.get('fails')) is not bool or outputs['meets'] == outputs['fails']):
                raise TaskCorrespondenceError('Checked method outputs do not satisfy the task binding')
            decision, basis = (('ready', 'criterion_met') if outputs['meets'] else
                               ('not_ready', 'criterion_failed'))
        observed_at = evidence.get('observed_at')
        if observed_at and parse_time(observed_at) > parse_time(assessment['assessed_at']):
            limitations.append('The observation is dated after the assessment time and is unusable.')
        return {
            'schema': 'EAL/readiness-task-context/1', 'service': contract.service,
            'decision': decision, 'basis': basis, 'reading': reading,
            'observed_at': observed_at, 'assessed_at': assessment['assessed_at'],
            'criterion': {'metric': contract.metric, 'unit': contract.unit,
                          'direction': contract.direction, 'threshold': contract.threshold,
                          'max_age_seconds': contract.max_age},
            'assumption': ({key: assumption.get(key) for key in ('status', 'time_status', 'valid_from', 'valid_until')}
                           if assumption is not None else None),
            'claim_statement': self.program.claims[contract.claim_id].statement,
            'prose_verified': False, 'physical_interpretation_verified': False,
            'limitations': limitations,
        }
