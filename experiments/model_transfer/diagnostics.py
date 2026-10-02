"""Run controlled component comparisons from independently cloned donor state.

These diagnostics are separate from the ordinary-workflow comparison. Each block
has one actual donor and recipient variants that change one declared component.
"""
from __future__ import annotations

from pathlib import Path
import time

from experiments.transfer_study.workspace import read_json, write_json
from .task_manifest import cases_for_plan
from .cases import CASES
from .diagnostic_design import BASELINE, DiagnosticSchedule, load_diagnostic_plan, recipient_positions
from .diagnostic_measurement import ProjectSnapshot
from .diagnostic_preparation import PreparationTimer
from .diagnostic_reporting import DiagnosticReportBuilder
from .project import Project
from .provider import BudgetedClient, ExecutionStopped, Transport
from .scoring import ReferenceScorer
from .session import SessionRunner


class DiagnosticPilot:
    def __init__(self, plan: dict, root: Path, transport: Transport, *, session_runner_factory=SessionRunner,
                 resume: bool = False, segment_seconds: int | None = None, clock=time.monotonic):
        self.plan, self.root, self.transport = plan, root, transport
        self.factory, self.resume, self.segment_seconds, self.clock = session_runner_factory, resume, segment_seconds, clock
        self.scorer = ReferenceScorer()

    def run(self) -> dict:
        from .run_state import RunState
        from .execution import ExecutionControl
        from .records import SequenceRecords
        from .provenance import RunIdentity
        state = RunState(self.root, self.plan, resume=self.resume)
        with state.locked(), state.segment(self.segment_seconds) as seconds:
            self.control = ExecutionControl(seconds, clock=self.clock)
            RunIdentity.record(self.root, self.plan, self.transport)
            write_json(self.root / 'plan.json', self.plan)
            self.client = BudgetedClient(self.root, self.plan, self.transport, control=self.control)
            self.sessions = self.factory(self.client, self.plan)
            self.records = SequenceRecords(self.root)
            if self.resume:
                rows = self.records.reopen()
                # Validate retained assignments before any network request.
                DiagnosticReportBuilder(self.plan).build(rows, self.client.records)
            else:
                rows = [{**assignment, 'status': 'not_run',
                         'preparation': {'donor_setup': PreparationTimer.pending(),
                                         'shared_state': PreparationTimer.pending()}}
                        for assignment in DiagnosticSchedule(self.plan).allocations()]
                for row in rows:
                    for variant in row['variants']:
                        variant['preparation'] = PreparationTimer.pending()
                write_json(self.root / 'assignments.json', rows)
                self.records.begin(rows)
            from .progress import Progress
            progress = Progress(self.root, rows, self.client, sum(1 + len(r['variants']) for r in rows))
            try:
                self.control.batches(rows, self._execute_block, self.plan.get('workers', 1), progress)
            finally:
                self.records.finish(rows)
                self.client.finish()
                progress()
            report = DiagnosticReportBuilder(self.plan).build(rows, self.client.records, self.control.reason)
            write_json(self.root / 'report.json', report)
            return report

    def _execute_block(self, row):
        if row['status'] == 'complete':
            return
        try:
            self.control.remaining()
            row.update(status='started')
            row.pop('reason', None)
            preparation = PreparationTimer(lambda: self.records.record(row))
            self._run_block(row, preparation)
            row['status'] = 'complete'
            print(f"{row['block_id']}: donor and {len(row['variants'])} recipients retained", flush=True)
        except Exception as exc:
            self.control.stop(f'{type(exc).__name__}: {exc}')
            row.update(status='stopped', reason=self.control.reason)
        finally:
            self.records.record(row)

    def _run_block(self, row: dict, preparation: PreparationTimer) -> None:
        case = next(case for case in cases_for_plan(self.plan) if case.identifier == row['case'])
        root = self.root / 'blocks' / row['block_id']
        from .session_recovery import retained_session
        if (root / 'donor').exists():
            donor = Project.attach(root / 'donor', case, 'eal')
        else:
            with preparation.measure(row['preparation']['donor_setup']):
                donor = Project(root / 'donor', case, 'eal')
        if row.get('donor_result') is None:
            donor.set_session(0)
            result = retained_session(donor, self.client, row['donor_session_id']) if self.resume else None
            if result is None:
                result = self.sessions.run(donor, self.plan['models'][row['donor']], self.plan.get('donor_native_tools', True),
                                           row['donor_session_id'], **BASELINE)
                stopped = result.get('stop_reason')
            else:
                stopped = None
            result['score'] = self.scorer.score(case, 0, result)
            row['donor_result'] = result
            self.records.record(row)
            if stopped:
                raise ExecutionStopped(stopped)
        if 'donor_snapshot' not in row:
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
                donor.set_session(recipient_positions(self.plan)[0])
            row['donor_snapshot'] = ProjectSnapshot.capture(donor)
            if 'recipient_positions' in self.plan:
                row['donor_snapshots'] = {}
                for position in recipient_positions(self.plan):
                    donor.set_session(position)
                    row['donor_snapshots'][str(position)] = ProjectSnapshot.capture(donor)
                donor.set_session(recipient_positions(self.plan)[0])
            write_json(root / 'initial-state.json', row['donor_snapshot'])
            write_json(root / 'current-evidence.json', read_json(donor.state))
        for variant in row['variants']:
            if variant.get('result') is not None:
                continue
            self.control.remaining()
            position = variant.get('recipient_session', 1)
            donor.set_session(position)
            snapshot = row.get('donor_snapshots', {}).get(str(position), row['donor_snapshot'])
            suffix = f'-session-{position}' if 'recipient_positions' in self.plan else ''
            clone_root = root / f'{variant["factor"]}-{variant["level_index"]}{suffix}'
            if clone_root.exists():
                project = Project.attach(clone_root, case, 'eal')
                project.state, project.session = donor.state, position
            else:
                with preparation.measure(variant['preparation']):
                    project = donor.fork(clone_root, session=position)
            variant['native_tools'] = row['native_tools']
            variant.setdefault('input_snapshot', ProjectSnapshot.capture(project))
            write_json(project.root / 'initial-state.json', variant['input_snapshot'])
            if variant['input_snapshot'] != snapshot:
                variant['status'] = 'invalid_initial_state'
                continue
            result = retained_session(project, self.client, variant['session_id']) if self.resume else None
            if result is None:
                result = self.sessions.run(project, self.plan['models'][row['receiver']], row['native_tools'],
                                           variant['session_id'], **variant['options'])
                stopped = result.get('stop_reason')
            else:
                stopped = None
            result['score'] = self.scorer.score(case, position, result)
            variant['result'], variant['status'] = result, 'observed'
            variant['shared_state_unchanged'] = ProjectSnapshot.capture(donor) == snapshot
            self.records.record(row)
            if not variant['shared_state_unchanged']:
                raise ExecutionStopped('A recipient changed the shared diagnostic starting state')
            if stopped:
                raise ExecutionStopped(stopped)
