"""Command-line access to the same operations exposed through MCP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .runtime import ReasoningService, bounded_path, strict_json, load_method_registry


def main() -> None:
    parser = argparse.ArgumentParser(description="EAL engineering reasoning language")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--methods", help="Trusted host method-registry factory: package.module:function")
    subcommands = parser.add_subparsers(dest="operation", required=True)
    subcommands.add_parser("describe")
    for operation in ("validate", "format", "collect", "reason", "compile-aspic"):
        command = subcommands.add_parser(operation)
        command.add_argument("source", help="Source file, relative to the workspace")
        if operation in ("collect", "reason", "compile-aspic"):
            command.add_argument("--context", required=True, help="JSON object, or @file relative to the workspace")
        if operation == "collect":
            command.add_argument("--evidence", action="append", dest="evidence_ids")
        if operation == "reason":
            command.add_argument("--collection", dest="collection_id")
            command.add_argument("--now", help="ISO-8601 assessment time; defaults to current UTC")
        if operation == "compile-aspic":
            command.add_argument("--collection", dest="collection_id", required=True)
            command.add_argument("--goal", required=True, help="Declared EAL claim to query")
            command.add_argument("--now", help="ISO-8601 assessment time; defaults to current UTC")
    explain = subcommands.add_parser("explain")
    explain.add_argument("assessment_id")
    explain.add_argument("--claim")
    grounded = subcommands.add_parser("grounded")
    grounded.add_argument("graph", help="JSON file containing arguments and attacks")
    export = subcommands.add_parser("export-aspic")
    export.add_argument("result", help="JSON file containing theory and formal result")
    export.add_argument("--output", required=True, help="ASPIC+ graph JSON within the workspace")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    try:
        if args.operation == "export-aspic":
            from .aspic_export import MAX_INPUT_BYTES, export_aspic_view

            input_path = bounded_path(workspace, args.result)
            if input_path.stat().st_size > MAX_INPUT_BYTES:
                raise ValueError("ASPIC+ result exceeds the 4 MiB export input limit")
            supplied = strict_json(input_path.read_text(encoding="utf-8"))
            view = export_aspic_view(supplied)
            target = bounded_path(workspace, args.output)
            target.write_text(json.dumps(view, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                              encoding="utf-8")
            result = {"output": str(target), "argument_count": len(view["arguments"]),
                      "defeat_witness_count": len(view["defeats"]),
                      "formal_status": view["formal_status"]}
        elif args.operation == "grounded":
            from .dialectic import solve_grounded

            graph = strict_json(bounded_path(workspace, args.graph).read_text())
            if not isinstance(graph, dict) or set(graph) != {"arguments", "attacks"}:
                raise ValueError("Graph must contain exactly arguments and attacks")
            result = solve_grounded(**graph)
        else:
            service = ReasoningService(workspace, args.registry, args.database, method_registry=load_method_registry(args.methods))
            if args.operation == "describe":
                result = service.describe()
            elif args.operation == "explain":
                result = service.explain(args.assessment_id, args.claim)
            else:
                source = bounded_path(workspace, args.source).read_text(encoding="utf-8")
                if args.operation == "format":
                    result = service.format(source)
                elif args.operation == "validate":
                    result = service.validate(source)
                else:
                    context_text = bounded_path(workspace, args.context[1:]).read_text(encoding="utf-8") if args.context.startswith("@") else args.context
                    context = strict_json(context_text)
                    if not isinstance(context, dict):
                        raise ValueError("context must be a JSON object")
                    if args.operation == "collect":
                        result = service.collect(source, context, args.evidence_ids)
                    elif args.operation == "reason":
                        result = service.reason(source, context, args.collection_id, args.now)
                    else:
                        result = service.compile_aspic(source, context, args.collection_id, args.goal, args.now)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        if result.get("valid") is False or any(record.get("status") == "error" for record in result.get("records", {}).values()):
            raise SystemExit(1)
    except (ValueError, KeyError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
