"""Recompute a report from version-2 records, including interrupted API journals."""
from __future__ import annotations

import argparse
from pathlib import Path

from experiments.transfer_study.workspace import read_json, write_json
from .design import load_plan
from .journal import AttemptJournal
from .reporting import ReportBuilder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = args.output or args.run / 'analysis.json'
    if output.exists():
        raise ValueError('Use a new analysis output path; original records are retained')
    plan = load_plan(args.run / 'plan.json')
    rows = read_json(args.run / 'rows.json')
    calls = AttemptJournal(args.run).read()
    incomplete = any(r['status'] != 'complete' for r in rows)
    stop = 'Execution incomplete; retain unobserved outcomes and unknown request costs' if incomplete else None
    report = ReportBuilder(plan).build(rows, calls, stop)
    report['interpretation'] = 'Recomputed from retained scores; raw answers were not rescored or repaired.'
    write_json(output, report)


if __name__ == '__main__':
    main()
