"""Recompute a report from retained records and optional independent annotations."""
from __future__ import annotations

import argparse
from pathlib import Path

from experiments.transfer_study.workspace import read_json, write_json
from .design import load_plan
from .journal import AttemptJournal
from .reporting import ReportBuilder
from .records import SequenceRecords
from .annotation_provenance import annotation_provenance, processing_provenance


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--rows', type=Path, help='Derived annotated rows; original rows are retained')
    parser.add_argument('--cost-ledger', type=Path)
    args = parser.parse_args()
    output = args.output or args.run / 'analysis.json'
    if output.exists():
        raise ValueError('Use a new analysis output path; original records are retained')
    diagnostic = read_json(args.run / 'plan.json').get('schema') == 'EAL/model-transfer-diagnostic-plan/2'
    if diagnostic:
        from .diagnostics import load_diagnostic_plan
        from .diagnostic_reporting import DiagnosticReportBuilder
        plan = load_diagnostic_plan(args.run / 'plan.json')
    else:
        plan = load_plan(args.run / 'plan.json')
    rows = read_json(args.rows) if args.rows else SequenceRecords(args.run).load()
    calls = AttemptJournal(args.run).read()
    incomplete = any(r['status'] != 'complete' for r in rows)
    stop = 'Execution incomplete; retain unobserved outcomes and unknown request costs' if incomplete else None
    provenance_path = args.run / 'provenance.json'
    provenance = read_json(provenance_path) if provenance_path.exists() else None
    report = (DiagnosticReportBuilder(plan).build(rows, calls, stop) if diagnostic else
              ReportBuilder(plan).build(rows, calls, stop, provenance))
    if args.cost_ledger:
        if diagnostic:
            raise ValueError('Adoption costs belong to the principal workflow comparison')
        from .adoption_costs import assess_costs
        report['adoption_costs'] = assess_costs(report, read_json(args.cost_ledger), plan, (provenance or {}).get('run_id'))
    report['interpretation'] = 'Recomputed from retained scores and declared annotations; raw answers were not repaired.'
    report['annotation_provenance'] = annotation_provenance(rows)
    report['processing_provenance'] = processing_provenance()
    report['rows_source'] = str(args.rows or args.run / 'rows.json')
    write_json(output, report)


if __name__ == '__main__':
    main()
