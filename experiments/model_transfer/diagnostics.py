"""Run controlled component comparisons from independently cloned donor state.

These diagnostics are separate from the ordinary-workflow comparison. Each block
has one actual donor and recipient variants that change one declared component.
"""
from __future__ import annotations

from pathlib import Path

from experiments.transfer_study.workspace import read_json, write_json
from .task_manifest import cases_for_plan
from .cases import CASES
from .diagnostic_design import BASELINE, DiagnosticSchedule, load_diagnostic_plan
from .diagnostic_measurement import ProjectSnapshot
from .diagnostic_preparation import PreparationTimer
from .diagnostic_reporting import DiagnosticReportBuilder
from .project import Project
from .provider import BudgetedClient, ExecutionStopped, Transport
from .scoring import ReferenceScorer
from .session import SessionRunner


class DiagnosticPilot:
    def __init__(self, plan: dict, root: Path, transport: Transport, *, session_runner_factory=SessionRunner):
        self.plan, self.root = plan, root
        self.client = BudgetedClient(root, plan, transport)
        self.sessions = session_runner_factory(self.client, plan)
        self.scorer = ReferenceScorer()

    def run(self) -> dict:
        rows = [{**assignment, 'status': 'not_run',
                 'preparation': {'donor_setup': PreparationTimer.pending(),
                                 'shared_state': PreparationTimer.pending()}}
                for assignment in DiagnosticSchedule(self.plan).allocations()]
        for row in rows:
            for variant in row['variants']:
                variant['preparation'] = PreparationTimer.pending()
        write_json(self.root / 'assignments.json', rows)
        write_json(self.root / 'rows.json', rows)
        preparation = PreparationTimer(lambda: write_json(self.root / 'rows.json', rows))
        stop = None
        try:
            for row in rows:
                if stop:
                    row['reason'] = stop
                    continue
                row['status'] = 'started'
                try:
                    self._run_block(row, rows, preparation)
                    row['status'] = 'complete'
                except Exception as exc:
                    stop = f'{type(exc).__name__}: {exc}'
                    row.update(status='stopped', reason=stop)
                write_json(self.root / 'rows.json', rows)
        finally:
            write_json(self.root / 'rows.json', rows)
            self.client.finish()
        report = DiagnosticReportBuilder(self.plan).build(rows, self.client.records, stop)
        write_json(self.root / 'report.json', report)
        return report

    def _run_block(self, row: dict, rows: list[dict], preparation: PreparationTimer) -> None:
        case = next(case for case in cases_for_plan(self.plan) if case.identifier == row['case'])
        root = self.root / 'blocks' / row['block_id']
        with preparation.measure(row['preparation']['donor_setup']):
            donor = Project(root / 'donor', case, 'eal')
        result = self.sessions.run(donor, self.plan['models'][row['donor']], True,
                                   row['donor_session_id'], **BASELINE)
        result['score'] = self.scorer.score(case, 0, result)
        row['donor_result'] = result
        write_json(self.root / 'rows.json', rows)
        if result.get('stop_reason'):
            raise ExecutionStopped(result['stop_reason'])
        with preparation.measure(row['preparation']['shared_state']):
            if any(variant['factor'] == 'notes' for variant in row['variants']):
                reference = self.scorer.reference(case, 0)
                content = (f'Diagnostic dated note: at {case.time(0)} the service was '
                           f'{reference["decision"]}; {case.metric} reading '
                           f'{reference["reading"]} {case.unit}. This note describes that earlier assessment.\n')
                # Deliberate note exposure is a component intervention. The main
                # comparison never receives this investigator-authored note.
                (donor.workspace / 'diagnostic-prior-note.md').write_text(content)
                row['note_intervention'] = {'origin': 'predeclared diagnostic fixture',
                    'initial_reference': reference, 'content': content,
                    'file': 'diagnostic-prior-note.md'}
            donor.set_session(1)
        row['donor_snapshot'] = ProjectSnapshot.capture(donor)
        write_json(root / 'initial-state.json', row['donor_snapshot'])
        write_json(root / 'current-evidence.json', read_json(donor.state))
        for variant in row['variants']:
            with preparation.measure(variant['preparation']):
                project = donor.fork(root / f'{variant["factor"]}-{variant["level_index"]}', session=1)
            variant['native_tools'] = row['native_tools']
            variant['input_snapshot'] = ProjectSnapshot.capture(project)
            write_json(project.root / 'initial-state.json', variant['input_snapshot'])
            if variant['input_snapshot'] != row['donor_snapshot']:
                variant['status'] = 'invalid_initial_state'
                continue
            result = self.sessions.run(project, self.plan['models'][row['receiver']], row['native_tools'],
                                       variant['session_id'], **variant['options'])
            result['score'] = self.scorer.score(case, 1, result)
            variant['result'], variant['status'] = result, 'observed'
            variant['shared_state_unchanged'] = ProjectSnapshot.capture(donor) == row['donor_snapshot']
            write_json(self.root / 'rows.json', rows)
            if not variant['shared_state_unchanged']:
                raise ExecutionStopped('A recipient changed the shared diagnostic starting state')
            if result.get('stop_reason'):
                raise ExecutionStopped(result['stop_reason'])
