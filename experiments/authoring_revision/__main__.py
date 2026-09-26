"""Create, fill and inspect an authoring/revision study without model calls."""
from __future__ import annotations

import argparse
from pathlib import Path

from .analysis import analyse
from .assignments import freeze
from .protocol import canonical
from .recording import adjudicate, review, submit
from .replay import replay


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    new = commands.add_parser("freeze", help="Freeze matched tasks, oracle digest and allocation")
    new.add_argument("--plan", type=Path, required=True)
    new.add_argument("--oracle", type=Path, required=True)
    new.add_argument("--participants", type=Path, required=True)
    new.add_argument("--output", type=Path, required=True)
    record = commands.add_parser("submit", help="Snapshot an actual initial or revised implementation")
    record.add_argument("--run", type=Path, required=True)
    record.add_argument("--assignment", required=True)
    record.add_argument("--stage", choices=("initial", "revision"), required=True)
    record.add_argument("--active-seconds", type=float, required=True)
    record.add_argument("--artefact", type=Path)
    record.add_argument("--results", type=Path)
    record.add_argument("--failure", default="")
    execute = commands.add_parser("replay", help="Operator-run evaluator on frozen source and cases")
    execute.add_argument("--run", type=Path, required=True)
    execute.add_argument("--submission", required=True)
    execute.add_argument("--operator", required=True)
    execute.add_argument("--runner-version", required=True)
    execute.add_argument("--runner", type=Path, required=True)
    execute.add_argument("--timeout-seconds", type=float, default=120)
    for name in ("review", "adjudicate"):
        entry = commands.add_parser(name, help=f"Retain an independent {name} record")
        entry.add_argument("--run", type=Path, required=True)
        entry.add_argument("--input", type=Path, required=True)
    report = commands.add_parser("analyse", help="Score all assigned work against the frozen oracle")
    report.add_argument("--run", type=Path, required=True)
    report.add_argument("--oracle", type=Path, required=True)
    report.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "freeze":
        result = freeze(args.plan, args.oracle, args.participants, args.output)
    elif args.command == "submit":
        result = submit(args.run, args.assignment, args.stage, args.active_seconds,
                        args.artefact, args.results, args.failure)
    elif args.command == "replay":
        result = replay(args.run, args.submission, args.operator, args.runner_version,
                        args.runner,
                        args.timeout_seconds)
    elif args.command == "review":
        result = review(args.run, args.input)
    elif args.command == "adjudicate":
        result = adjudicate(args.run, args.input)
    else:
        result = analyse(args.run, args.oracle)
        if args.output:
            with args.output.open("xb") as stream:
                stream.write(canonical(result))
    print(canonical(result).decode(), end="")


if __name__ == "__main__":
    main()
