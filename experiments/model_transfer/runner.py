"""Run and retain a bounded prospective model-session comparison."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import time

from experiments.transfer_study.workspace import read_json, utc_now, write_json
from .calibration import ContractCalibration
from .task_manifest import cases_for_plan
from .cases import CASES
from .design import AssignmentSchedule, load_plan
from .project import Project
from .provider import BudgetedClient, ExecutionStopped, OpenAITransport, Transport
from .reporting import ReportBuilder
from .scoring import ReferenceScorer
from .session import SessionRunner
from .provenance import RunIdentity
from .records import SequenceRecords
from .run_state import digest


class Pilot:
    """Execute independent paired blocks concurrently, retaining within-arm order."""
    def __init__(self, plan: dict, root: Path, transport: Transport, *, clock=time.monotonic,
                 resume: bool = False, segment_seconds: int | None = None):
        self.plan, self.root, self.transport = plan, root, transport
        self.clock, self.resume, self.segment_seconds = clock, resume, segment_seconds
        self.scorer = ReferenceScorer()

    def run(self) -> dict:
        from .run_state import RunState
        from .execution import ExecutionControl
        state = RunState(self.root, self.plan, resume=self.resume)
        with state.locked(), state.segment(self.segment_seconds) as seconds:
            self.control = ExecutionControl(seconds, clock=self.clock)
            self.provenance = RunIdentity.record(self.root, self.plan, self.transport)
            self.client = BudgetedClient(self.root, self.plan, self.transport, control=self.control)
            self.sessions = SessionRunner(self.client, self.plan)
            write_json(self.root / 'plan.json', self.plan)
            assignments = AssignmentSchedule(self.plan).allocations()
            cases = {c.identifier: c for c in cases_for_plan(self.plan)}
            self.records = SequenceRecords(self.root)
            if self.resume:
                rows = self.records.reopen()
                expected = {a['sequence_id']: a for a in assignments}
                if len(rows) != len(expected) or any(any(r.get(k) != v for k, v in expected[r['sequence_id']].items()) for r in rows):
                    raise ValueError('Retained allocation differs from the frozen plan')
            else:
                write_json(self.root / 'assignments.json', assignments)
                rows = [{**a, 'cohort': cases[a['case']].cohort, 'status': 'not_run', 'sessions': []} for a in assignments]
                self.records.begin(rows)
            blocks = [rows[i:i + 2] for i in range(0, len(rows), 2)]
            from .progress import Progress
            progress = Progress(self.root, rows, self.client, len(rows) * (1 + self.plan['recipient_sessions']))
            try:
                self.control.batches(blocks, lambda block: self._block(block, cases), self.plan.get('workers', 1), progress)
            finally:
                self.records.finish(rows)
                self.client.finish()
                progress()
            report = ReportBuilder(self.plan).build(rows, self.client.records, self.control.reason, provenance=self.provenance)
            report['created_at'] = utc_now().isoformat()
            write_json(self.root / 'report.json', report)
            return report

    def _block(self, block, cases):
        from .session_recovery import retained_session
        for row in block:
            if row['status'] == 'complete':
                continue
            try:
                self.control.remaining()
                row.update(status='started')
                row.pop('reason', None)
                case = cases[row['case']]
                root = self.root / 'sequences' / row['sequence_id']
                if root.exists():
                    project = Project.attach(root, case, row['arm'])
                else:
                    start = time.monotonic()
                    project = Project(root, case, row['arm'])
                    row['setup_seconds'] = time.monotonic() - start
                for session in range(len(row['sessions']), 1 + self.plan['recipient_sessions']):
                    self.control.remaining()
                    project.set_session(session)
                    sid = f"{row['sequence_id']}.session-{session}"
                    result = retained_session(project, self.client, sid) if self.resume else None
                    if result is None:
                        model = self.plan['models'][row['donor'] if session == 0 else row['receiver']]
                        result = self.sessions.run(project, model, True if session == 0 else row['native_tools'], sid)
                        stopped = result.get('stop_reason')
                    else:
                        stopped = None  # The retained failed attempt is never retried.
                    result['score'] = self.scorer.score(case, session, result)
                    row['sessions'].append(result)
                    self.records.record(row)
                    if stopped:
                        raise ExecutionStopped(stopped)
                row['status'] = 'complete'
                print(f"{row['sequence_id']}: {len(row['sessions'])} sessions retained", flush=True)
            except Exception as exc:
                self.control.stop(f'{type(exc).__name__}: {exc}')
                row.update(status='stopped', reason=self.control.reason)
            finally:
                self.records.record(row)
            if self.control.reason:
                return


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--plan', type=Path)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--calibrate-only', action='store_true')
    cli.add_argument('--workers', type=int, choices=range(1, 9), help='Independent paired blocks; frozen for this run')
    cli.add_argument('--resume', action='store_true', help='Continue the same frozen run without retrying recorded sessions')
    cli.add_argument('--segment-seconds', type=int, default=6000, help='Stop and retain progress before the outer job deadline')
    args = cli.parse_args()
    if not 1 <= args.segment_seconds <= 18000:
        cli.error('--segment-seconds must be between 1 and 18000')
    args.plan = args.plan or (args.output / 'plan.json' if args.resume else Path(__file__).with_name('plan.json'))
    diagnostic = read_json(args.plan).get('schema') == 'EAL/model-transfer-diagnostic-plan/2'
    if diagnostic:
        from .diagnostics import DiagnosticPilot, load_diagnostic_plan
        plan = load_diagnostic_plan(args.plan)
    else:
        plan = load_plan(args.plan)
    if args.workers is not None:
        if args.resume:
            cli.error('Resume uses the frozen worker count; do not override it')
        if plan.get('study_role') == 'evaluation' and args.workers != plan.get('workers', 1):
            cli.error('Evaluation must retain the worker count used for prospective allocation')
        plan = {**plan, 'workers': args.workers}
    if args.resume and args.calibrate_only:
        cli.error('Calibration does not resume a live run')
    if args.resume:
        if not args.output.is_dir():
            cli.error('Resume requires a retained run directory')
        from .run_state import RunState
        with RunState(args.output, plan, resume=True).locked():
            pass
        implementation = DiagnosticPilot if diagnostic else Pilot
        result = implementation(plan, args.output, OpenAITransport(), resume=True, segment_seconds=args.segment_seconds).run()
        print(json.dumps({'status': result['status'], 'execution_status': result['execution_status']}))
        return
    if args.output.exists():
        raise ValueError('Use a new run directory; attempts must never be overwritten')
    args.output.mkdir(parents=True)
    write_json(args.output / 'plan.json', plan)
    write_json(args.output / 'cases.json', [asdict(c) for c in cases_for_plan(plan) if c.identifier in plan['cases']])
    protocol = read_json(Path(__file__).with_name('protocol.json'))
    write_json(args.output / 'protocol.json', protocol)
    try:
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        revision, dirty = None, None
    write_json(args.output / 'provenance.json', {
        'revision': revision, 'working_tree_dirty': dirty, 'started_at': utc_now().isoformat(),
        'protocol_version': protocol['version'],
        'plan_file_sha256': hashlib.sha256(args.plan.read_bytes()).hexdigest(),
        'plan_sha256': digest(plan),
        'implementation_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in Path(__file__).parent.glob('*.py')}})
    calibration = ContractCalibration().check(plan)
    write_json(args.output / 'calibration.json', calibration)
    if args.calibrate_only or calibration['status'] != 'passed':
        write_json(args.output / 'report.json', {'status': 'calibration_only' if calibration['status'] == 'passed'
                   else 'invalid_measurement', 'api_attempts': 0, 'calibration': calibration['status']})
        if calibration['status'] != 'passed':
            raise SystemExit(1)
        return
    try:
        implementation = DiagnosticPilot if diagnostic else Pilot
        transport = OpenAITransport()
        RunIdentity.record(args.output, plan, transport)
        result = implementation(plan, args.output, transport, segment_seconds=args.segment_seconds).run()
    except ExecutionStopped as exc:
        write_json(args.output / 'report.json', {'status': 'blocked', 'reason': str(exc), 'api_attempts': 0})
        raise SystemExit(str(exc)) from exc
    print(json.dumps({k: result[k] for k in ('status', 'planned_sequences', 'planned_sessions',
                                           'api_attempts', 'estimated_cost_usd') if k in result}))
    # A retained partial run is an expected resumable outcome, not lost data.
    if result['execution_status'] != 'complete':
        print('Partial run retained. Inspect report.json and resume the same run when its limits permit.')


if __name__ == '__main__':
    main()
