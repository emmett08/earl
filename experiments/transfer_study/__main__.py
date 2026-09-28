"""Operator and participant CLI for the cross-session handover experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analysis import analyse, export_answers, save_ratings
from .design import StudyDesign
from .model_gateway import ModelGateway
from .operations import SessionOperations
from .workspace import StudyRun, write_json


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(prog="python -m experiments.transfer_study")
    commands = cli.add_subparsers(dest="action", required=True)
    check = commands.add_parser("check-plan")
    check.add_argument("plan", type=Path)
    init = commands.add_parser("init")
    init.add_argument("plan", type=Path)
    init.add_argument("output", type=Path)
    init.add_argument("--seed", type=int, required=True)
    for name in ("open", "invoke", "tool", "register", "assess", "submit", "close",
                 "blind-export", "score", "analyse"):
        command = commands.add_parser(name)
        command.add_argument("output", type=Path)
        if name in ("open", "invoke", "tool", "register", "assess", "submit", "close"):
            if name == "open":
                command.add_argument("case_id")
                command.add_argument("slot_id")
                command.add_argument("stage", choices=("initial", "later"))
            else:
                command.add_argument("session_id")
        if name == "invoke":
            command.add_argument("--prompt-file", type=Path, required=True)
            command.add_argument("--context-file", type=Path)
        if name == "tool":
            command.add_argument("--timeout", type=int, default=120)
            command.add_argument("argv", nargs=argparse.REMAINDER)
        if name in ("register", "assess"):
            command.add_argument("--registry", required=True)
            command.add_argument("--entry", required=True)
            command.add_argument("--claim", required=True)
        if name == "register":
            command.add_argument("--source", required=True)
            command.add_argument("--context", required=True, help="JSON object of EAL environment fields")
        if name == "assess":
            command.add_argument("--prompt-file", type=Path, required=True)
        if name == "submit":
            command.add_argument("--answer-file", type=Path, required=True)
            command.add_argument("--effort-minutes", type=float, required=True)
        if name == "close":
            command.add_argument("--status", choices=("no_answer", "withdrawn", "invalid_measurement"),
                                 required=True)
            command.add_argument("--reason", required=True)
            command.add_argument("--effort-minutes", type=float)
        if name in ("blind-export", "analyse"):
            command.add_argument("--file", type=Path, required=True)
        if name == "score":
            command.add_argument("--ratings", type=Path, required=True)
    return cli


def main() -> None:
    args = parser().parse_args()
    if args.action == "check-plan":
        design = StudyDesign.load(args.plan)
        value = {"study_id": design.study_id, "cases": len(design.cases),
                 "models": list(design.models), "sha256": design.digest}
    elif args.action == "init":
        run = StudyRun.create(args.plan, args.output, args.seed)
        value = run.allocation
    else:
        run = StudyRun(args.output)
        if args.action == "open":
            value = run.open(args.case_id, args.slot_id, args.stage)
        elif args.action == "invoke":
            value = ModelGateway(run).invoke(
                args.session_id, args.prompt_file.read_text(encoding="utf-8"),
                context_path=args.context_file)
        elif args.action == "tool":
            argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
            value = SessionOperations(run).tool(args.session_id, argv, args.timeout)
        elif args.action == "register":
            value = SessionOperations(run).register(
                args.session_id, source=args.source, registry=args.registry,
                entry_id=args.entry, claim=args.claim, context=json.loads(args.context))
        elif args.action == "assess":
            value = SessionOperations(run).assess(
                args.session_id, registry=args.registry, entry_id=args.entry,
                claim=args.claim, prompt=args.prompt_file.read_text(encoding="utf-8"))
        elif args.action == "submit":
            value = run.submit(args.session_id,
                               args.answer_file.read_text(encoding="utf-8"),
                               args.effort_minutes)
        elif args.action == "close":
            value = run.close(args.session_id, args.status, args.reason, args.effort_minutes)
        elif args.action == "blind-export":
            value = export_answers(run)
            write_json(args.file, value)
        elif args.action == "score":
            value = save_ratings(run, args.ratings)
        elif args.action == "analyse":
            value = analyse(run)
            write_json(args.file, value)
        else:
            raise AssertionError(args.action)
    print(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
