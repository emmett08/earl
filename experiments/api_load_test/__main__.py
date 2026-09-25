"""Run or inspect the one API experiment; paid calls require the repository secret."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .analysis import markdown, summarise
from .api import serve
from .materials import PROFILES, source_for
from .oracle import reference
from .routes import TrialTools
from .runner import HERE, run, write_json


async def self_check(output: Path):
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for profile_name, profile in PROFILES.items():
        for arm in ("json_prompt", "eal_mcp"):
            run_id = f"self-check-{profile_name}-{arm}"
            with serve(profile, run_id) as api:
                workload = {"service": "orders-api", "build_id": api["build_id"], "run_id": run_id,
                            "concurrent_clients": 10, "request_count": profile["request_count"], "timeout_seconds": 3}
                context = {key: workload[key] for key in ("service", "build_id", "run_id")}
                context["dataset"] = "measured_controlled_api"
                tools = TrialTools(output / run_id, source_for(workload, context),
                                   {"port": api["port"], "input": workload, "context": context})
                packet = await tools.execute(arm)
                report = json.loads(tools.report_path.read_text())
                truth = reference(report, workload, context, tools.assessed_at)
                if arm == "eal_mcp" and tools.host_status != truth["status"]:
                    raise RuntimeError("MCP conclusion disagrees with independent reference")
                if packet["metrics"] != truth["metrics"]:
                    raise RuntimeError("Collector metrics disagree with independent reference")
                if profile_name in {"slow", "errors", "short_run"} and truth["status"] != "unsupported":
                    raise RuntimeError("Negative control did not produce the intended failure")
                if profile_name == "healthy" and truth["status"] != "supported":
                    raise RuntimeError("Healthy positive control failed on this host")
                write_json(tools.workspace / "tool-trace.json", tools.trace)
                results.append({"profile": profile_name, "arm": arm, "reference": truth,
                                "host_status": tools.host_status, "report_sha256": packet["provenance"]["report_sha256"]})
    write_json(output / "self-check.json", {"passed": True, "model_calls": 0, "results": results})
    print(json.dumps({"passed": True, "real_http_runs": len(results), "model_calls": 0}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "self-check", "analyse"):
        command = commands.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
        if name == "run":
            command.add_argument("--mode", choices=("smoke", "study"), default="smoke")
            command.add_argument("--model", action="append", help="Exact ID from models.json; omission runs all four")
    args = parser.parse_args()
    output = args.output.resolve()
    if args.command == "self-check":
        asyncio.run(self_check(output))
        return
    if args.command == "run":
        plan = json.loads((HERE / "plan.json").read_text())
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
