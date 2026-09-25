"""Run or inspect the one API experiment; paid calls require the repository secret."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .analysis import markdown, summarise
from .runner import HERE, run, write_json
from .self_check import self_check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "self-check", "analyse"):
        command = commands.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
        if name == "run":
            command.add_argument("--mode", choices=("smoke", "pilot"), default="pilot")
            command.add_argument("--transport", choices=("text", "native"), default="text",
                                 help="Text-mediated operations by default; native is a separate diagnostic")
            command.add_argument("--model", action="append", help="Exact ID from models.json; omission runs all six")
    args = parser.parse_args()
    output = args.output.resolve()
    if args.command == "self-check":
        asyncio.run(self_check(output))
        return
    if args.command == "run":
        plan = json.loads((HERE / "plan.json").read_text())
        plan["transport"] = args.transport
        specs = json.loads((HERE / "models.json").read_text())["models"]
        if args.model:
            if set(args.model) - {spec["id"] for spec in specs} or len(set(args.model)) != len(args.model):
                parser.error("Select unique, exact model IDs from models.json")
            specs = [spec for spec in specs if spec["id"] in args.model]
        complete = asyncio.run(run(output, specs, plan, mode=args.mode))
    else:
        complete = True
    summary = summarise(output)
    write_json(output / "summary.json", summary)
    (output / "summary.md").write_text(markdown(summary))
    print(markdown(summary))
    if not complete:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
