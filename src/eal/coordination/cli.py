"""Command-line lifecycle and role-scoped gateway for registered EAL runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .service import Coordinator, strict_json
from .workers import CommandWorker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    start = commands.add_parser("start", help="Pin a trusted task and initialize durable coordination")
    start.add_argument("--run", type=Path, required=True)
    source = start.add_mutually_exclusive_group(required=True)
    source.add_argument("--spec", type=Path, help="JSON with server, task and optional budgets/transport")
    source.add_argument("--demo", type=Path, help="Trusted demo manifest created by coordinator_demo")
    start.add_argument("--task-id", help="Task to select from the demo manifest")
    start.add_argument("--runtime", type=Path, help="Use the supplied Lab runtime instead of durable JSON")
    start.add_argument("--wall-seconds", type=int)
    for name in ("status", "resume", "cancel", "reserve", "query", "lookup", "record", "export", "execute"):
        command = commands.add_parser(name)
        command.add_argument("--run", type=Path, required=True)
        if name == "reserve":
            command.add_argument("--role", choices=("assessor", "reviewer"), required=True)
            command.add_argument("--execution-mode", choices=("actual_host_agent", "provider", "software_test"), required=True)
            command.add_argument("--context-out", type=Path)
        if name in {"query", "lookup", "record"}:
            command.add_argument("--call-id", required=True)
        if name == "lookup":
            command.add_argument("--finding-id", required=True)
        if name == "record":
            command.add_argument("--response", type=Path, required=True)
            command.add_argument("--execution-id", required=True)
            command.add_argument("--execution-mode", choices=("actual_host_agent", "provider", "software_test"), required=True)
        if name == "export":
            command.add_argument("--output", type=Path, required=True)
        if name == "execute":
            command.add_argument("--execution-mode", choices=("actual_host_agent", "provider", "software_test"), required=True)
            command.add_argument("--worker-argv", required=True, help="JSON argv of a trusted worker executable; no shell")
            command.add_argument("--worker-environment", type=Path, help="Private JSON environment file; values are never exported")
    args = parser.parse_args()
    try:
        if args.operation == "start":
            if args.spec:
                spec = strict_json(args.spec.read_bytes())
                if set(spec) - {"server", "task", "budgets", "transport"} or not {"server", "task"} <= set(spec):
                    raise ValueError("Run spec requires server/task and only declared optional fields")
            else:
                manifest = strict_json(args.demo.read_bytes())
                selected = [t for t in manifest["tasks"] if t["task_id"] == args.task_id]
                if len(selected) != 1:
                    raise ValueError("Choose one exact trusted demo task ID")
                spec = {"server": manifest["server"], "task": selected[0]}
            if args.runtime is not None:
                spec["transport"] = {"kind": "lab", "runtime": str(args.runtime)}
            if args.wall_seconds is not None:
                spec["budgets"] = {**spec.get("budgets", {}), "wall_seconds": args.wall_seconds}
            coordinator = Coordinator.start(args.run, **spec)
            result = coordinator.status()
        else:
            coordinator = Coordinator(args.run)
            if args.operation in {"status", "resume", "cancel"}:
                result = getattr(coordinator, args.operation)()
            elif args.operation == "reserve":
                result = coordinator.reserve_worker(args.role, execution_mode=args.execution_mode)
                if args.context_out:
                    args.context_out.parent.mkdir(parents=True, exist_ok=True)
                    args.context_out.write_text(json.dumps(result["context"], indent=2) + "\n")
            elif args.operation == "query":
                result = coordinator.query(args.call_id)
            elif args.operation == "lookup":
                result = coordinator.lookup(args.call_id, args.finding_id)
            elif args.operation == "record":
                result = coordinator.record(args.call_id, args.response.read_bytes(), args.execution_id,
                                            execution_mode=args.execution_mode)
            elif args.operation == "export":
                result = coordinator.export(args.output)
            else:
                environment = None if args.worker_environment is None else strict_json(args.worker_environment.read_bytes())
                worker = CommandWorker(json.loads(args.worker_argv), execution_mode=args.execution_mode,
                                       timeout_seconds=coordinator.config["budgets"]["worker_seconds"],
                                       max_output_bytes=coordinator.config["budgets"]["max_worker_output_bytes"],
                                       environment=environment, workspace=coordinator.server.workspace)
                result = coordinator.run(worker)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 1 if (result.get("accepted") is False or result.get("status") in {"failed", "cancelled", "expired"}) else 0
    except (ValueError, OSError, KeyError) as error:
        print(json.dumps({"error": {"type": type(error).__name__, "message": str(error)}}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
