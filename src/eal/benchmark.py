"""Known-answer engineering tasks and paired text-model delegation measurements.

Reference task checking uses the same parser, collector and interpreter as MCP.
Model answers are scored against committed answers, never against another model.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
from typing import Any

from .parser import parse
from .runtime import ReasoningService, bounded_path, strict_json

SCHEMA = "EAL/engineering-tasks/1"
STATUSES = {"supported", "contested", "unsupported", "out_of_scope", "unresolved"}


def load_suite(path: str | Path) -> dict:
    path = Path(path).resolve()
    suite = strict_json(path.read_text())
    if not isinstance(suite, dict) or suite.get("schema") != SCHEMA or not isinstance(suite.get("tasks"), list):
        raise ValueError(f"Expected {SCHEMA} task suite")
    names = set()
    for task in suite["tasks"]:
        if not isinstance(task, dict) or not isinstance(task.get("id"), str) or task["id"] in names:
            raise ValueError("Task identifiers must be unique strings")
        names.add(task["id"])
        if task.get("split") not in {"development", "held_out"}:
            raise ValueError("Each task must have a fixed development or held_out split")
        for field in ("source", "observations"):
            if not isinstance(task.get(field), str):
                raise ValueError(f"Task {task['id']} requires {field}")
            bounded_path(path.parent, task[field]).read_text()
        if not isinstance(task.get("expected", {}).get("claims"), dict):
            raise ValueError(f"Task {task['id']} requires known claim answers")
        if any(status not in STATUSES - {"unresolved"} for status in task["expected"]["claims"].values()):
            raise ValueError("Known answers must use interpreter claim statuses")
    return suite


def task_inputs(task: dict, root: Path) -> dict:
    """Return observable task data without the answer key or explanatory oracle."""
    observations = strict_json(bounded_path(root, task["observations"]).read_text())
    if task.get("collect") is not None:
        observations = {name: value for name, value in observations.items() if name in task["collect"]}
    return {"source": bounded_path(root, task["source"]).read_text(),
            "observations": observations,
            "context": task["context"], "now": task["now"]}


def prepare_task(task: dict, root: Path, workspace: Path) -> tuple[ReasoningService, dict]:
    inputs = task_inputs(task, root)
    program = parse(inputs["source"])
    bindings: dict[str, dict] = {}
    for evidence_id, envelope in inputs["observations"].items():
        if evidence_id not in program.evidence:
            raise ValueError(f"Task observation {evidence_id} is undeclared")
        tool = program.evidence[evidence_id].tool
        if tool in bindings and bindings[tool] != envelope:
            raise ValueError(f"Fixture tool {tool} has inconsistent observations")
        bindings[tool] = envelope
    workspace.mkdir(parents=True, exist_ok=True)
    registry = []
    for tool, envelope in bindings.items():
        filename = f"{tool}.json"
        (workspace / filename).write_text(json.dumps(envelope, allow_nan=False))
        declaration = program.tools[tool]
        registry.extend([f"[tools.{tool}]", 'kind="json_file"', f"path={json.dumps(filename)}",
                         f"version={json.dumps(declaration.version)}", f"mode={json.dumps(declaration.mode)}", ""])
    registry_path = workspace / "tools.toml"
    registry_path.write_text("\n".join(registry))
    return ReasoningService(workspace, registry_path), inputs


def check_task(task: dict, root: Path, workspace: Path) -> dict:
    service, inputs = prepare_task(task, root, workspace)
    validation = service.validate(inputs["source"])
    expected = task["expected"]
    errors = []
    if validation["valid"] != expected.get("valid", True):
        errors.append(f"valid: expected {expected.get('valid', True)}, observed {validation['valid']}")
    assessment = validation
    if validation["valid"]:
        collection = service.collect(inputs["source"], inputs["context"], task.get("collect"))
        assessment = service.reason(inputs["source"], inputs["context"], collection["collection_id"], inputs["now"])
        for section in ("claims", "arguments", "assumptions", "objections"):
            for name, wanted in expected.get(section, {}).items():
                actual = assessment.get(section, {}).get(name, {}).get("status")
                if actual != wanted:
                    errors.append(f"{section}.{name}: expected {wanted}, observed {actual}")
        for path, wanted in expected.get("values", {}).items():
            actual: Any = assessment
            for part in path.split("."):
                actual = actual.get(part) if isinstance(actual, dict) else None
            matches = (math.isclose(actual, wanted, rel_tol=1e-10, abs_tol=1e-12)
                       if isinstance(wanted, (float, int)) and not isinstance(wanted, bool)
                       and isinstance(actual, (float, int)) and not isinstance(actual, bool)
                       else actual == wanted)
            if not matches:
                errors.append(f"{path}: expected {wanted!r}, observed {actual!r}")
    return {"id": task["id"], "family": task["family"], "passed": not errors,
            "errors": errors, "assessment": assessment}


def check_suite(path: str | Path) -> dict:
    path = Path(path).resolve()
    suite = load_suite(path)
    with tempfile.TemporaryDirectory(prefix="eal-tasks-") as temporary:
        results = [check_task(task, path.parent, Path(temporary) / str(index))
                   for index, task in enumerate(suite["tasks"])]
    return {"schema": "EAL/task-check/1", "suite": suite["version"],
            "passed": all(result["passed"] for result in results), "tasks": results}


def score_answer(expected: dict[str, str], report: dict) -> dict:
    """Separate unjustified positive answers from correct qualified/unresolved ones."""
    final = report.get("final") or {}
    supplied = final.get("claims", {}) if isinstance(final, dict) else {}
    answers = {name: value.get("status") if isinstance(value, dict) else value
               for name, value in supplied.items()} if isinstance(supplied, dict) else {}
    answers = {name: value if isinstance(value, str) and value in STATUSES else "unresolved" for name, value in answers.items()}
    details = {}
    for name, wanted in expected.items():
        actual = answers.get(name, "unresolved")
        if actual == wanted:
            category = "correct"
        elif actual == "supported":
            category = "unjustified"
        elif actual in {"unresolved", "unsupported", "out_of_scope"}:
            category = "unresolved"
        else:
            category = "incorrect"
        details[name] = {"expected": wanted, "actual": actual, "category": category}
    extra = sorted(set(answers) - set(expected))
    categories = {item["category"] for item in details.values()}
    correct = bool(expected) and categories == {"correct"} and not extra and report.get("status") == "completed"
    return {"correct": correct, "correctly_resolved": correct and all(v == "supported" for v in expected.values()),
            "justified_unresolved": correct and any(v != "supported" for v in expected.values()),
            "unjustified": "unjustified" in categories or any(answers[k] == "supported" for k in extra),
            "unresolved": "unresolved" in categories or report.get("status") != "completed",
            "unexpected_claims": extra, "claims": details}


def source_correspondence(reference: str, actual: Any) -> bool:
    """Check a revised draft against the full independent reference representation.

    A model cannot obtain benchmark credit by weakening a claim, dropping a
    premise, changing an interval or attaching its identifier to another claim.
    Declaration order and formatting are immaterial; all semantic fields count.
    """
    if not isinstance(actual, str):
        return False
    try:
        wanted, supplied = asdict(parse(reference)), asdict(parse(actual))
    except (ValueError, TypeError, RecursionError):
        return False
    wanted.pop("source_digest", None)
    supplied.pop("source_digest", None)
    # Python equality conflates true with 1 and false with 0. EAL predicates
    # distinguish these types, so source identity must preserve JSON types.
    return json.dumps(wanted, sort_keys=True, allow_nan=False) == json.dumps(supplied, sort_keys=True, allow_nan=False)


def workflow_score(required: list[str], report: dict) -> dict:
    """Check successful protocol steps, including retrieval of the final trace."""
    completed = set()
    final = report.get("final") or {}
    for event in report.get("tool_calls", []):
        if event.get("status") != "ok":
            continue
        operation = event.get("tool", "").removeprefix("eal_")
        result = event.get("result", {})
        if operation in {"validate", "reason"} and result.get("valid") is not True:
            continue
        if operation == "explain" and event.get("arguments", {}).get("assessment_id") != final.get("assessment_id"):
            continue
        completed.add(operation)
    missing = sorted(set(required) - completed)
    return {"complete": not missing, "missing_operations": missing}


def summarise(trials: list[dict]) -> dict:
    summaries = {}
    for arm in ("unaided", "delegated"):
        rows = [trial for trial in trials if trial["arm"] == arm]
        correct = sum(row["score"]["correct"] for row in rows)
        resolved = sum(row["score"]["correctly_resolved"] for row in rows)
        costs = [row["cost"]["total_usd"] for row in rows]
        complete = bool(rows) and all(cost is not None for cost in costs)
        total = sum(costs) if complete else None
        token_values = [row["report"].get("usage", {}).get("total_tokens") for row in rows]
        tokens_complete = bool(rows) and all(row["report"].get("usage", {}).get("token_usage_complete", False)
                                            and value is not None for row, value in zip(rows, token_values))
        summaries[arm] = {"tasks": len(rows), "correct": correct, "correctly_resolved": resolved,
                          "unjustified": sum(row["score"]["unjustified"] for row in rows),
                          "unresolved": sum(row["score"]["unresolved"] for row in rows),
                          "justified_unresolved": sum(row["score"]["justified_unresolved"] for row in rows),
                          "repairs": sum(row["report"].get("repairs", 0) for row in rows),
                          "attempts": sum(len(row["report"].get("attempts", [])) for row in rows),
                          "total_tokens": sum(token_values) if tokens_complete else None,
                          "token_usage_complete": tokens_complete,
                          "total_cost_usd": total, "cost_complete": complete,
                          "cost_per_correct_task_usd": total / correct if total is not None and correct else None,
                          "cost_per_correctly_resolved_task_usd": total / resolved if total is not None and resolved else None,
                          "latency_seconds": sum(row["report"].get("latency_seconds", 0) for row in rows)}
    return summaries


async def evaluate_models(path: str | Path, provider, *, split: str = "held_out", budget=None,
                          per_mcp_call_usd: float | None = None, task_ids: list[str] | None = None) -> dict:
    """Run paired named-provider trials. No simulated answers or default free costs."""
    from mcp import StdioServerParameters
    from .agent import AgentBudget, run_agent, run_unaided
    from .discovery import describe_language

    if per_mcp_call_usd is not None and (isinstance(per_mcp_call_usd, bool)
            or not math.isfinite(per_mcp_call_usd) or per_mcp_call_usd < 0):
        raise ValueError("per_mcp_call_usd must be a finite nonnegative declared cost")
    path = Path(path).resolve()
    suite = load_suite(path)
    selected = [task for task in suite["tasks"] if task["split"] == split and (task_ids is None or task["id"] in task_ids)]
    if not selected:
        raise ValueError("No tasks match this fixed split and selection")
    budget = budget or AgentBudget()
    trials = []
    for index, task in enumerate(selected):
        with tempfile.TemporaryDirectory(prefix="eal-model-trial-") as temporary:
            workspace = Path(temporary)
            reference = check_task(task, path.parent, workspace / "reference")
            if not reference["passed"]:
                raise ValueError(f"Reference task {task['id']} failed: {reference['errors']}")
            _, inputs = prepare_task(task, path.parent, workspace / "model")
            model_inputs = dict(inputs)
            # Language competence is not the experimental intervention: both
            # arms receive the same executable-language reference, no answers.
            model_inputs["language_reference"] = describe_language()
            if task.get("draft_source"):
                model_inputs.pop("source")
                model_inputs["draft_source"] = bounded_path(path.parent, task["draft_source"]).read_text()
            prompt = task["question"] + "\nAssess these claim identifiers: " + ", ".join(task["expected"]["claims"]) + "."
            prompt += "\nReturn the supported, contested, unsupported or out_of_scope status for every requested claim."
            if task.get("collect") is not None:
                model_inputs["collect_only"] = task["collect"]
            server = StdioServerParameters(command=sys.executable, args=["-m", "eal.server", "--workspace", str(workspace / "model"),
                                                                       "--registry", str(workspace / "model" / "tools.toml")])
            # Alternating order avoids giving one arm every first/warm request.
            arms = ("unaided", "delegated") if index % 2 == 0 else ("delegated", "unaided")
            for arm in arms:
                if arm == "unaided":
                    report = await run_unaided(prompt, provider, budget=budget, initial_data=model_inputs,
                                               required_claims=tuple(task["expected"]["claims"]))
                else:
                    report = await run_agent(prompt, provider, server, budget=budget,
                                             required_claims=tuple(task["expected"]["claims"]), initial_data=model_inputs)
                usage = report.get("usage", {})
                model_cost = usage.get("model_cost_usd") if usage.get("model_cost_complete", False) else None
                calls = len(report.get("tool_calls", []))
                tool_cost = 0.0 if arm == "unaided" else calls * per_mcp_call_usd if per_mcp_call_usd is not None else None
                score = score_answer(task["expected"]["claims"], report)
                if arm == "delegated":
                    final = report.get("final") or {}
                    corresponds = source_correspondence(inputs["source"], final.get("source"))
                    score["source_correspondence"] = corresponds
                    if not corresponds:
                        score.update(correct=False, correctly_resolved=False, justified_unresolved=False)
                        score["unjustified"] |= any(item["actual"] == "supported" for item in score["claims"].values())
                    if task.get("workflow"):
                        workflow = workflow_score(task["workflow"], report)
                        score["workflow"] = workflow
                        if not workflow["complete"]:
                            score.update(correct=False, correctly_resolved=False, justified_unresolved=False)
                trials.append({"task_id": task["id"], "family": task["family"], "split": task["split"], "arm": arm,
                               "inputs": model_inputs, "question": prompt, "expected": task["expected"]["claims"],
                               "report": report, "score": score,
                               "cost": {"model_usd": model_cost, "mcp_calls": calls, "tool_usd": tool_cost,
                                        "per_mcp_call_usd": per_mcp_call_usd,
                                        "total_usd": model_cost + tool_cost if model_cost is not None and tool_cost is not None else None}})
    content = {"suite": suite, "inputs": {task["id"]: task_inputs(task, path.parent) for task in suite["tasks"]},
               "drafts": {task["id"]: bounded_path(path.parent, task["draft_source"]).read_text()
                          for task in suite["tasks"] if task.get("draft_source")}}
    digest = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    identity = provider.identity()
    return {"schema": "EAL/model-benchmark/1", "suite": suite["version"], "suite_digest": digest,
            "measurement_kind": identity.get("measurement_kind", "unclassified"),
            "provider": identity, "budget": asdict(budget), "split": split,
            "trials": trials, "summary": summarise(trials),
            "interpretation": "Paired results apply only to this provider, settings, task split and declared cost model. Tool cost is the supplied all-in cost per MCP call; absent costs remain unknown."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=Path("benchmarks/engineering-v1/suite.json"))
    parser.add_argument("--check-tasks", action="store_true")
    parser.add_argument("--summary", action="store_true", help="Print concise task-check output; --output still saves the full report")
    parser.add_argument("--provider", type=Path)
    parser.add_argument("--split", choices=["development", "held_out"], default="held_out")
    parser.add_argument("--task", action="append", dest="task_ids")
    parser.add_argument("--per-mcp-call-usd", type=float)
    parser.add_argument("--max-iterations", type=int, default=16)
    parser.add_argument("--max-total-tokens", type=int, default=64000)
    parser.add_argument("--max-elapsed-seconds", type=float, default=120)
    parser.add_argument("--max-model-cost-usd", type=float)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.check_tasks:
        report = check_suite(args.suite)
        success = report["passed"]
    else:
        if args.provider is None:
            parser.error("--provider is required for actual model trials; use --check-tasks for deterministic reference cases")
        from .providers import load_provider
        from .agent import AgentBudget
        budget = AgentBudget(max_iterations=args.max_iterations, max_total_tokens=args.max_total_tokens,
                             max_elapsed_seconds=args.max_elapsed_seconds, max_model_cost_usd=args.max_model_cost_usd)
        report = asyncio.run(evaluate_models(args.suite, load_provider(args.provider), split=args.split,
                                           budget=budget, per_mcp_call_usd=args.per_mcp_call_usd, task_ids=args.task_ids))
        success = True
    encoded = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
        print(json.dumps({"output": str(args.output), "passed": success,
                          "summary": report.get("summary", {"tasks": len(report.get("tasks", []))})}))
    else:
        if args.summary and args.check_tasks:
            print(json.dumps({"suite": report["suite"], "passed": report["passed"], "count": len(report["tasks"]),
                              "tasks": [{key: task[key] for key in ("id", "passed", "errors")} for task in report["tasks"]]}, indent=2))
        else:
            print(encoded)
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
