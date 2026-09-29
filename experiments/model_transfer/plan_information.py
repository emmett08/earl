"""Plan a fresh evaluation using retained pilot trajectories; never call a model."""
from __future__ import annotations

import argparse
from pathlib import Path
from .records import SequenceRecords
from .annotation_provenance import annotation_provenance, processing_provenance

from experiments.transfer_study.workspace import read_json, write_json
from .design import AssignmentSchedule, load_plan
from .information_design import AllocationPlanner
from .journal import AttemptJournal
from .pilot_data import PilotExtractor, data_fingerprint
from .resources import ResourceSummary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--config', type=Path, default=Path(__file__).with_name('information-design.json'))
    parser.add_argument('--rows', type=Path, help='Derived annotated rows; original pilot rows remain unchanged')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evaluation-plan', type=Path, help='Write a runnable plan only if an empirical allocation qualifies')
    parser.add_argument('--allow-scripted', action='store_true', help='Label synthetic/unverified inputs as rehearsal; never propose evaluation')
    args = parser.parse_args()
    if args.output.exists() or args.evaluation_plan and args.evaluation_plan.exists():
        raise ValueError('Use new output paths; retained records cannot be overwritten')
    plan = load_plan(args.run / 'plan.json')
    rows = read_json(args.rows) if args.rows else SequenceRecords(args.run).load()
    assignments = AssignmentSchedule(plan).allocations()
    expected = {r['sequence_id']: r for r in assignments}
    if len(rows) != len(expected) or {r['sequence_id'] for r in rows} != set(expected):
        raise ValueError('Pilot planning must retain exactly the planned sequence denominator')
    if any(any(row.get(key) != value for key, value in expected[row['sequence_id']].items()) for row in rows):
        raise ValueError('Pilot row identity differs from the saved assignment')
    calls = AttemptJournal(args.run).read()
    provenance_path = args.run / 'provenance.json'
    provenance = read_json(provenance_path) if provenance_path.exists() else {}
    accounting = ResourceSummary().summarise([s for row in rows for s in row['sessions']], calls,
        session_ids={f"{row['sequence_id']}.session-{i}" for row in rows for i in range(plan['recipient_sessions'] + 1)},
        include_unassigned=True)
    provenance = {**provenance, 'pilot_accounting_complete': accounting['accounting_complete']}
    config = read_json(args.config)
    report = AllocationPlanner(config).plan(PilotExtractor().extract(rows, calls, plan['recipient_sessions']),
        plan, provenance, data_fingerprint(plan, rows, calls), allow_scripted=args.allow_scripted)
    report['rows_source'] = str(args.rows or args.run / 'rows.json')
    report['annotation_provenance'] = annotation_provenance(rows)
    report['processing_provenance'] = processing_provenance()
    if report['proposed_evaluation_plan'] is not None:
        report['proposed_evaluation_plan']['pilot_annotation_provenance'] = report['annotation_provenance']
    report['pilot_accounting_errors'] = accounting['accounting_errors']
    write_json(args.output, report)
    if args.evaluation_plan and report['proposed_evaluation_plan'] is not None:
        write_json(args.evaluation_plan, report['proposed_evaluation_plan'])
    print(report['status'])


if __name__ == '__main__':
    main()
