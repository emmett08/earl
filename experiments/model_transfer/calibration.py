"""Check task/source/result correspondence before transmitting model requests."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from eal.knowledge import EALKnowledgeBase
from experiments.transfer_study.workspace import read_json, write_json
from .task_manifest import cases_for_plan
from .cases import CASES, Case, FIRST, EARLY, LATE
from .project import Project
from .task_context import TaskContextBuilder, TaskContract, TaskCorrespondenceError
from .threshold_method import registry


# Independently authored expected outcomes. This table is deliberately not
# computed by the scorer, the method, the case generator or the task adapter.
# Entries give initial and recipient (decision, basis, reading, observed_at).
EXPECTED = {
    'fresh_positive': (('ready', 'criterion_met', 180, FIRST), ('ready', 'criterion_met', 180, FIRST)),
    'fresh_negative': (('not_ready', 'criterion_failed', 240, FIRST), ('not_ready', 'criterion_failed', 240, FIRST)),
    'refresh_positive': (('not_ready', 'criterion_failed', 240, FIRST), ('ready', 'criterion_met', 180, LATE)),
    'refresh_negative': (('ready', 'criterion_met', 180, FIRST), ('not_ready', 'criterion_failed', 240, LATE)),
    'missing_measurement': (('ready', 'criterion_met', 180, FIRST), ('undetermined', 'measurement_missing', None, LATE)),
    'expired_assumption': (('ready', 'criterion_met', 180, FIRST), ('undetermined', 'assumption_expired', None, FIRST)),
    'capacity_boundary': (('ready', 'criterion_met', 20, FIRST), ('ready', 'criterion_met', 20, FIRST)),
    'capacity_drop': (('ready', 'criterion_met', 25, FIRST), ('not_ready', 'criterion_failed', 15, LATE)),
}


def assess_project(project: Project, *, now: str, source: str | None = None,
                   report: dict | None = None) -> dict:
    """Run the real registered collector/evaluator path, with no model calls."""
    if source is not None:
        (project.workspace / 'argument.eal').write_text(source)
    if report is not None:
        write_json(project.state, report)
    knowledge = EALKnowledgeBase(project.workspace, project.workspace / 'tools.toml', method_registry=registry())
    knowledge.register('argument.eal', entry_id='orders', context=project.case.context(),
                       claims=['criterion_evaluated'])
    return knowledge.assess('orders', 'criterion_evaluated', now=now, context=project.registration_context())


class ContractCalibration:
    """Separate application correspondence from model behaviour and scoring."""

    def check(self, plan: dict) -> dict:
        checks = []
        with TemporaryDirectory(prefix='eal-calibration-') as temporary:
            root = Path(temporary)
            for case in cases_for_plan(plan):
                if case.identifier not in plan['cases']:
                    continue
                try:
                    project = Project(root / case.identifier, case, 'eal')
                    binding = TaskContextBuilder(TaskContract.from_case(case), case.source(), explain=project.explain)
                    positions = plan.get('recipient_positions')
                    sessions = [0, *positions] if positions is not None else range(1 + plan['recipient_sessions'])
                    for session in sessions:
                        project.set_session(session)
                        assessment = assess_project(project, now=case.time(session))
                        context = binding.build(assessment)
                        if getattr(case, 'task_kind', 'threshold') == 'task_rules':
                            from .corpus_reference import CorpusReference
                            authored = case.expected_decisions[session]
                            oracle = CorpusReference().reference(case, session)['decision']
                            actual = context['decision']
                            checks.append({'kind': 'task_outcome', 'case': case.identifier,
                                           'session': session, 'passed': actual == authored == oracle and
                                           assessment['packet']['summary_complete'] is True,
                                           'expected': authored, 'reference': oracle, 'actual': actual})
                            continue
                        expected = self._threshold_expected(case, session)
                        criterion = ({'metric': 'free storage', 'unit': 'GB', 'direction': 'at_least', 'threshold': 20}
                                     if case.identifier.startswith('capacity_') else
                                     {'metric': 'latency', 'unit': 'ms', 'direction': 'at_most', 'threshold': 200})
                        actual = tuple(context[key] for key in ('decision', 'basis', 'reading', 'observed_at'))
                        passed = (actual == expected and context['prose_verified'] is False and
                                  all(context['criterion'][key] == value for key, value in criterion.items()) and
                                  assessment['packet']['summary_complete'] is True)
                        checks.append({'kind': 'task_outcome', 'case': case.identifier,
                                       'session': session, 'passed': passed,
                                       'expected': list(expected), 'actual': list(actual)})
                except Exception as exc:
                    checks.append(self._failure(case.identifier, exc))
            checks.extend(self._adversarial(root / 'adversarial'))
        return {'status': 'passed' if checks and all(c['passed'] for c in checks) else 'failed',
                'checks': checks,
                'scope': 'Software, authored task/source correspondence and result preservation; not model performance.'}

    @staticmethod
    def _threshold_expected(case: Case, session: int) -> tuple:
        expected = EXPECTED[case.identifier][int(session > 0)]
        now = datetime.fromisoformat(case.time(session).replace('Z', '+00:00'))
        observed = datetime.fromisoformat(expected[3].replace('Z', '+00:00'))
        if expected[1] != 'assumption_expired' and (now - observed).total_seconds() > 300:
            return ('undetermined', 'stale_measurement', None, expected[3])
        return expected

    @staticmethod
    def _failure(name: str, error: Exception) -> dict:
        return {'case': name, 'session': None, 'passed': False,
                'error': {'type': type(error).__name__, 'message': str(error)[:1000]}}

    def _adversarial(self, root: Path) -> list[dict]:
        """Attempt semantic changes and boundary conditions with fixed expectations."""
        checks = []
        base = Case('calibration', 200, 200, EARLY)
        mutations = {
            'reversed_criterion': lambda source: source.replace('"direction" == "at_most"', '"direction" == "at_least"'),
            'changed_threshold': lambda source: source.replace('require "threshold" == 200', 'require "threshold" == 201', 1),
            'missing_admission_predicate': lambda source: source.replace('require "reading" >= 0', '', 1),
            'changed_claim_statement': lambda source: source.replace('meets establishes ready', 'meets establishes not_ready'),
            'changed_source_scope': lambda source: source.replace('require "service" == "orders"', 'require "service" == "payments"', 1),
            'changed_source_unit': lambda source: source.replace('require "unit" == "ms"', 'require "unit" == "s"'),
            'changed_assumption_interval': lambda source: source.replace('valid_until "2026-09-28T10:01:00Z"', 'valid_until "2026-09-28T11:00:00Z"'),
        }
        for name, mutate in mutations.items():
            try:
                case = replace(base, assumption_until=EARLY) if name == 'changed_assumption_interval' else base
                project = Project(root / name, case, 'eal')
                source = mutate(case.source())
                assessment = assess_project(project, now=FIRST, source=source)
                try:
                    TaskContextBuilder(TaskContract.from_case(case), source).build(assessment)
                    rejected = False
                except TaskCorrespondenceError:
                    rejected = True
                checks.append({'kind': 'source_mutation', 'case': name, 'passed': rejected,
                               'eal_status': assessment['status'], 'correspondence_rejected': rejected})
            except Exception as exc:
                checks.append(self._failure(name, exc))
        boundaries = (
            ('fresh_299_seconds', '2026-09-28T10:04:59Z', {}, None, 'ready', 'criterion_met'),
            ('fresh_300_seconds', '2026-09-28T10:05:00Z', {}, None, 'ready', 'criterion_met'),
            ('stale_301_seconds', '2026-09-28T10:05:01Z', {}, None, 'undetermined', 'stale_measurement'),
            ('future_observation', FIRST, {'observed_at': EARLY}, None, 'undetermined', 'stale_measurement'),
            ('wrong_measurement_scope', FIRST, {'service': 'payments'}, None, 'undetermined', 'evidence_unavailable'),
            ('wrong_measurement_units', FIRST, {'unit': 's'}, None, 'undetermined', 'evidence_unavailable'),
            ('missing_reading', FIRST, {'reading': None}, None, 'undetermined', 'measurement_missing'),
            ('assumption_before_start', FIRST, {}, (EARLY, LATE), 'undetermined', 'assumption_not_started'),
            ('assumption_at_start', FIRST, {}, (FIRST, EARLY), 'ready', 'criterion_met'),
            ('assumption_at_end', EARLY, {}, (FIRST, EARLY), 'undetermined', 'assumption_expired'),
        )
        for name, now, changes, interval, decision, basis in boundaries:
            try:
                case = replace(base, assumption_from=interval[0], assumption_until=interval[1]) if interval else base
                project = Project(root / name, case, 'eal')
                report = read_json(project.state)
                for key, value in changes.items():
                    if key == 'observed_at':
                        report[key] = value
                    elif value is None:
                        report['value'].pop(key, None)
                    else:
                        report['value'][key] = value
                assessment = assess_project(project, now=now, report=report)
                context = TaskContextBuilder(TaskContract.from_case(case), case.source()).build(assessment)
                actual = (context['decision'], context['basis'])
                checks.append({'kind': 'boundary', 'case': name, 'passed': actual == (decision, basis),
                               'expected': [decision, basis], 'actual': list(actual)})
            except Exception as exc:
                checks.append(self._failure(name, exc))
        return checks
