"""Command-line access to the same operations exposed through MCP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .runtime import ReasoningService, bounded_path, strict_json, load_method_registry


def _context(workspace: Path, value: str | None) -> dict | None:
    if value is None:
        return None
    supplied = (bounded_path(workspace, value[1:]).read_text(encoding="utf-8")
                if value.startswith("@") else value)
    context = strict_json(supplied)
    if not isinstance(context, dict):
        raise ValueError("context must be a JSON object")
    return context


def main() -> None:
    parser = argparse.ArgumentParser(description="EAL engineering reasoning language")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--methods", help="Trusted host method-registry factory: package.module:function")
    parser.add_argument("--limits", type=Path, help="Host-owned TOML execution budgets")
    subcommands = parser.add_subparsers(dest="operation", required=True)
    subcommands.add_parser("describe")
    register = subcommands.add_parser("register", help="Register a workspace EAL file for later sessions")
    register.add_argument("source", help="Workspace-relative .eal file")
    register.add_argument("--entry-id", help="Stable developer name (defaults to the workspace path)")
    register.add_argument("--label")
    register.add_argument("--claim", action="append", dest="claims", help="Select a claim; repeat for more")
    register.add_argument("--context", help="Default JSON context, or @file relative to the workspace")
    register_tree = subcommands.add_parser("register-tree", help="Register EAL files in a workspace directory")
    register_tree.add_argument("directory", nargs="?", default=".")
    register_tree.add_argument("--context", help="Default JSON context, or @file relative to the workspace")
    register_tree.add_argument("--limit", type=int, default=512)
    sources = subcommands.add_parser("sources", help="List registered EAL sources and claims")
    sources.add_argument("--limit", type=int, default=50)
    sources.add_argument("--offset", type=int, default=0)
    find = subcommands.add_parser("find", help="Find registered source and claim metadata")
    find.add_argument("query", nargs="?")
    find.add_argument("--claim")
    find.add_argument("--context", help="Exact registered JSON context, or @file")
    find.add_argument("--path", help="Exact workspace-relative EAL path")
    find.add_argument("--limit", type=int, default=50)
    known = subcommands.add_parser("assess-known", help="Assess one registered claim and reuse eligible observations")
    known.add_argument("entry_id")
    known.add_argument("--claim", required=True)
    known.add_argument("--context", help="Operator-side JSON context override, or @file")
    known.add_argument("--now", help="ISO-8601 assessment time; defaults to current UTC")
    known.add_argument("--reuse", choices=("compatible", "fresh"), default="compatible")
    history = subcommands.add_parser("history", help="Find durable runs for a registered EAL file")
    history.add_argument("entry_id")
    history.add_argument("--source-digest", help="Historical source revision (defaults to the current revision)")
    history.add_argument("--limit", type=int, default=50)
    model_context = subcommands.add_parser("model-context", help="Prepare a checked packet for a text-only model")
    model_context.add_argument("entry_id")
    model_context.add_argument("--claim", required=True)
    model_context.add_argument("--question", required=True, help="The developer's question for the model")
    model_context.add_argument("--context", help="Operator-side JSON context override, or @file")
    model_context.add_argument("--now", help="ISO-8601 assessment time; defaults to current UTC")
    model_context.add_argument("--reuse", choices=("compatible", "fresh"), default="compatible")
    for operation in ("validate", "format", "plan", "collect", "reason", "compile-aspic"):
        command = subcommands.add_parser(operation)
        command.add_argument("source", help="Source file, relative to the workspace")
        if operation in ("collect", "reason", "compile-aspic"):
            command.add_argument("--context", required=True, help="JSON object, or @file relative to the workspace")
        if operation == "plan":
            command.add_argument("--claim", required=True, help="Declared claim to plan")
        if operation == "collect":
            selection = command.add_mutually_exclusive_group()
            selection.add_argument("--evidence", action="append", dest="evidence_ids")
            selection.add_argument("--claim", help="Collect the claim's complete evidence closure")
        if operation == "reason":
            command.add_argument("--collection", dest="collection_id")
            command.add_argument("--now", help="ISO-8601 assessment time; defaults to current UTC")
        if operation == "compile-aspic":
            command.add_argument("--collection", dest="collection_id", required=True)
            command.add_argument("--goal", required=True, help="Declared EAL claim to query")
            command.add_argument("--now", help="ISO-8601 assessment time; defaults to current UTC")
            command.add_argument('--semantics', choices=('grounded', 'preferred', 'stable'), default='grounded')
            command.add_argument('--query-mode', choices=('credulous', 'sceptical'), default='sceptical')
            command.add_argument('--preference', choices=('minimum_rank', 'last_link_rank', 'last_link_partial'))
    explain = subcommands.add_parser("explain")
    explain.add_argument("assessment_id")
    explain.add_argument("--claim")
    packet = subcommands.add_parser("packet")
    packet.add_argument("assessment_id")
    packet.add_argument("--claim")
    grounded = subcommands.add_parser("grounded")
    grounded.add_argument("graph", help="JSON file containing arguments and attacks")
    export = subcommands.add_parser("export-aspic")
    export.add_argument("result", help="JSON file containing theory and formal result")
    export.add_argument("--output", required=True, help="ASPIC+ graph JSON within the workspace")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    try:
        from .limits import ExecutionLimits, using_limits
        limits = ExecutionLimits.load(args.limits) if args.limits else ExecutionLimits()
        if args.operation == "export-aspic":
            from .aspic_export import MAX_INPUT_BYTES, export_aspic_view

            input_path = bounded_path(workspace, args.result)
            if input_path.stat().st_size > MAX_INPUT_BYTES:
                raise ValueError("ASPIC+ result exceeds the 4 MiB export input limit")
            supplied = strict_json(input_path.read_text(encoding="utf-8"))
            view = export_aspic_view(supplied, limits=limits)
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
            with using_limits(limits):
                result = solve_grounded(**graph)
        else:
            methods = load_method_registry(args.methods)
            registered_operation = args.operation in {
                "register", "register-tree", "sources", "find", "assess-known", "history", "model-context",
            }
            if registered_operation:
                from .knowledge import EALKnowledgeBase

                knowledge = EALKnowledgeBase(workspace, args.registry, args.database,
                                             method_registry=methods, limits=limits)
                service = knowledge.service
            else:
                service = ReasoningService(workspace, args.registry, args.database,
                                           method_registry=methods, limits=limits)
            if args.operation == "describe":
                result = service.describe()
            elif registered_operation:
                catalogue = knowledge.catalogue
                if args.operation == "register":
                    result = catalogue.register(args.source, entry_id=args.entry_id,
                                                context=_context(workspace, args.context),
                                                claims=args.claims, label=args.label)
                elif args.operation == "register-tree":
                    result = catalogue.register_tree(args.directory, context=_context(workspace, args.context),
                                                     limit=args.limit)
                elif args.operation == "sources":
                    result = {"entries": catalogue.list(limit=args.limit, offset=args.offset)}
                elif args.operation == "find":
                    result = {"matches": catalogue.find(args.query, claim=args.claim,
                                                         context=_context(workspace, args.context),
                                                         path=args.path, limit=args.limit)}
                elif args.operation == "history":
                    result = catalogue.runs(args.entry_id, source_digest=args.source_digest, limit=args.limit)
                elif args.operation == "assess-known":
                    result = knowledge.assess(
                        args.entry_id, args.claim, context=_context(workspace, args.context),
                        now=args.now, reuse=args.reuse,
                    )
                else:
                    from .knowledge import ModelContextAdapter

                    result = ModelContextAdapter(knowledge).prepare(
                        args.question, args.entry_id, args.claim, context=_context(workspace, args.context),
                        now=args.now, reuse=args.reuse,
                    )
            elif args.operation == "explain":
                result = service.explain(args.assessment_id, args.claim)
            elif args.operation == "packet":
                result = service.packet(args.assessment_id, args.claim)
            else:
                source = bounded_path(workspace, args.source).read_text(encoding="utf-8")
                if args.operation == "format":
                    result = service.format(source)
                elif args.operation == "validate":
                    result = service.validate(source)
                elif args.operation == "plan":
                    result = service.plan(source, args.claim)
                else:
                    context = _context(workspace, args.context)
                    if args.operation == "collect":
                        result = (service.collect_claim(source, context, args.claim) if args.claim
                                  else service.collect(source, context, args.evidence_ids))
                    elif args.operation == "reason":
                        result = service.reason(source, context, args.collection_id, args.now)
                    else:
                        result = service.compile_aspic(source, context, args.collection_id, args.goal, args.now,
                                                       semantics=args.semantics, query_mode=args.query_mode,
                                                       preference=args.preference)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        if result.get("valid") is False or any(record.get("status") == "error" for record in result.get("records", {}).values()):
            raise SystemExit(1)
    except (ValueError, KeyError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
