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


class Pilot:
    def __init__(self, plan: dict, root: Path, transport: Transport, *, clock=time.monotonic):
        self.plan, self.root = plan, root
        self.clock = clock
        self.provenance = RunIdentity.record(root, plan, transport)
        self.client = BudgetedClient(root, plan, transport)
        self.sessions = SessionRunner(self.client, plan)
        self.scorer = ReferenceScorer()

    def run(self) -> dict:
        write_json(self.root / 'plan.json', self.plan)
        assignments = AssignmentSchedule(self.plan).allocations()
        write_json(self.root / 'assignments.json', assignments)
        cases = {c.identifier: c for c in cases_for_plan(self.plan)}
        rows = [{**a, 'cohort': cases[a['case']].cohort, 'status': 'not_run', 'sessions': []}
                for a in assignments]
        records = SequenceRecords(self.root)
        records.begin(rows)
        deadline = self.clock() + self.plan.get('time_limit_seconds', 7200)
        stop = None
        try:
            for index, row in enumerate(rows):
                if stop:
                    row['reason'] = stop
                    continue
                case = cases[row['case']]
                row['status'] = 'started'
                start = time.monotonic()
                try:
                    project = Project(self.root / 'sequences' / row['sequence_id'], case, row['arm'])
                    row['setup_seconds'] = time.monotonic() - start
                    for session in range(1 + self.plan['recipient_sessions']):
                        if self.clock() >= deadline:
                            raise ExecutionStopped('Experiment elapsed-time limit reached')
                        project.set_session(session)
                        model = self.plan['models'][row['donor'] if session == 0 else row['receiver']]
                        result = self.sessions.run(project, model, True if session == 0 else row['native_tools'],
                                                   f"{row['sequence_id']}.session-{session}")
                        result['score'] = self.scorer.score(case, session, result)
                        row['sessions'].append(result)
                        records.record(row)
                        if result.get('stop_reason'):
                            raise ExecutionStopped(result['stop_reason'])
                    row['status'] = 'complete'
                except Exception as exc:
                    # An infrastructure/measurement failure stops comparison; no
                    # post-treatment deletion or substitution of failed units.
                    stop = f'{type(exc).__name__}: {exc}'
                    row.update(status='stopped', reason=stop)
                records.record(row)
                print(f'{index + 1}/{len(rows)} sequences recorded', flush=True)
        finally:
            records.finish(rows)
            self.client.finish()
        report = ReportBuilder(self.plan).build(rows, self.client.records, stop, provenance=self.provenance)
        report['created_at'] = utc_now().isoformat()
        write_json(self.root / 'report.json', report)
        return report


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--plan', type=Path, default=Path(__file__).with_name('plan.json'))
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--calibrate-only', action='store_true')
    args = cli.parse_args()
    diagnostic = read_json(args.plan).get('schema') == 'EAL/model-transfer-diagnostic-plan/2'
    if diagnostic:
        from .diagnostics import DiagnosticPilot, load_diagnostic_plan
        plan = load_diagnostic_plan(args.plan)
    else:
        plan = load_plan(args.plan)
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
        'plan_sha256': hashlib.sha256(args.plan.read_bytes()).hexdigest(),
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
        result = implementation(plan, args.output, transport).run()
    except ExecutionStopped as exc:
        write_json(args.output / 'report.json', {'status': 'blocked', 'reason': str(exc), 'api_attempts': 0})
        raise SystemExit(str(exc)) from exc
    print(json.dumps({k: result[k] for k in ('status', 'planned_sequences', 'planned_sessions',
                                           'api_attempts', 'estimated_cost_usd') if k in result}))
    if result['execution_status'] != 'complete':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
