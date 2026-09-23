"""Frozen, repeated, paired experiments across model and host conditions.

Every completed trial is saved before the next summary update. Provider calls
are made only by run_experiment; --freeze-only performs no generation requests.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import random
import statistics
import sys
import tempfile
import time
import tomllib
from typing import Callable

from .benchmark import check_task, evaluate_task, load_suite, prepare_task, score_answer, suite_digest, summarise
from .runtime import strict_json

SCHEMA = "EAL/experiment-plan/1"
SCORING_VERSION = "alpha-equivalence+evidence-trace/1"


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _positive_integer(value, name, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be an integer from 1 to {maximum}")


def load_plan(path: str | Path) -> dict:
    plan = strict_json(Path(path).read_text())
    if not isinstance(plan, dict) or plan.get("schema") != SCHEMA:
        raise ValueError(f"Expected {SCHEMA}")
    allowed = {"schema", "name", "suite", "split", "task_ids", "repetitions", "order_seed", "sampling_seeds",
               "concurrency", "per_mcp_call_usd", "budget", "conditions", "bootstrap_samples", "notes"}
    if set(plan) - allowed:
        raise ValueError("Unknown experiment-plan settings")
    if not isinstance(plan.get("suite"), str) or not isinstance(plan.get("name"), str) or not plan["name"]:
        raise ValueError("Experiment name and suite path are required")
    if plan.get("split", "held_out") not in {"development", "held_out"}:
        raise ValueError("split must be development or held_out")
    _positive_integer(plan.get("repetitions", 2), "repetitions", 100)
    _positive_integer(plan.get("concurrency", 1), "concurrency", 4)
    _positive_integer(plan.get("bootstrap_samples", 2000), "bootstrap_samples", 20_000)
    if type(plan.get("order_seed", 0)) is not int:
        raise ValueError("order_seed must be an integer")
    seeds = plan.get("sampling_seeds")
    if seeds is not None and (not isinstance(seeds, list) or len(seeds) != plan.get("repetitions", 2)
                              or any(type(seed) is not int for seed in seeds)):
        raise ValueError("sampling_seeds must give one integer per repetition")
    if "task_ids" in plan and (not isinstance(plan["task_ids"], list) or not plan["task_ids"]
            or any(not isinstance(name, str) for name in plan["task_ids"]) or len(set(plan["task_ids"])) != len(plan["task_ids"])):
        raise ValueError("task_ids must be a nonempty unique list")
    cost = plan.get("per_mcp_call_usd")
    if cost is not None and (isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0):
        raise ValueError("per_mcp_call_usd must be finite and nonnegative or null")
    conditions = plan.get("conditions")
    if not isinstance(conditions, list) or not 1 <= len(conditions) <= 24:
        raise ValueError("One through 24 explicit conditions are required")
    names = set()
    from .agent import AgentBudget
    for condition in conditions:
        if not isinstance(condition, dict) or set(condition) - {"id", "provider", "model_class", "arm", "host_mode", "interaction_mode", "seed_supported", "budget"}:
            raise ValueError("Unknown condition settings")
        name = condition.get("id")
        if not isinstance(name, str) or not name or name in names or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in name):
            raise ValueError("Condition IDs must be unique path-safe identifiers")
        names.add(name)
        if not all(isinstance(condition.get(key), str) and condition[key] for key in ("provider", "model_class")):
            raise ValueError("Each condition requires a provider configuration path and declared model_class")
        if condition.get("arm") not in {"unaided", "delegated"}:
            raise ValueError("Every condition explicitly selects unaided or delegated")
        if condition.get("host_mode", "stateful") not in {"stateful", "legacy"}:
            raise ValueError("host_mode must be stateful or legacy")
        if condition.get("interaction_mode", "text") not in {"text", "native"}:
            raise ValueError("interaction_mode must be text or native")
        if type(condition.get("seed_supported", False)) is not bool:
            raise ValueError("seed_supported must be a boolean")
        if condition["arm"] == "unaided" and condition.get("interaction_mode", "text") != "text":
            raise ValueError("An unaided baseline has no native tool interaction")
        AgentBudget(**{**plan.get("budget", {}), **condition.get("budget", {})})
    return plan


def make_schedule(plan: dict, task_ids: list[str]) -> list[dict]:
    """Seeded block ordering with rotating condition positions within task blocks."""
    repetitions = plan.get("repetitions", 2)
    rng = random.Random(plan.get("order_seed", 0))
    seeds = plan.get("sampling_seeds") or [plan.get("order_seed", 0) + repetition for repetition in range(repetitions)]
    conditions = [condition["id"] for condition in plan["conditions"]]
    rng.shuffle(conditions)
    tasks = list(task_ids)
    rng.shuffle(tasks)
    blocks = [(task, repetition, index) for repetition in range(repetitions) for index, task in enumerate(tasks)]
    rng.shuffle(blocks)
    schedule = []
    for task, repetition, index in blocks:
        offset = (index + repetition) % len(conditions)
        order = conditions[offset:] + conditions[:offset]
        # Reverse alternating complete sweeps for a counterbalanced rather
        # than permanently adjacent sequence when the condition count is odd.
        if (index + repetition) // len(conditions) % 2:
            order = list(reversed(order))
        for position, condition in enumerate(order):
            schedule.append({"trial_id": f"trial-{len(schedule):05d}", "schedule_index": len(schedule),
                             "block_id": f"{task}/repeat-{repetition}", "task_id": task,
                             "repetition": repetition, "sampling_seed": seeds[repetition],
                             "condition_id": condition, "condition_position": position})
    return schedule


def _code_identity() -> dict:
    package = Path(__file__).resolve().parent
    files = {str(path.relative_to(package)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(package.rglob("*.py"))}
    dependencies = {}
    for name in ("antlr4-python3-runtime", "mcp", "httpx", "jsonschema"):
        try:
            dependencies[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            dependencies[name] = None
    return {"python": platform.python_version(), "platform": platform.platform(),
            "dependencies": dependencies, "source_files": files, "source_digest": _digest(files)}


def _provider_config(path: Path, seed: int | None = None) -> dict:
    with path.open("rb") as stream:
        raw = tomllib.load(stream)
    if not isinstance(raw.get("provider"), dict):
        raise ValueError("Provider configuration requires a [provider] table")
    config = dict(raw["provider"])
    if seed is not None:
        config["sampling"] = {**config.get("sampling", {}), "seed": seed}
    return config


def freeze_experiment(plan_path: str | Path) -> dict:
    """Validate and freeze references, schemas, code and schedule without requests."""
    from .discovery import describe_language
    from .providers import provider_from_config
    plan_path = Path(plan_path).resolve()
    plan = load_plan(plan_path)
    suite_path = (plan_path.parent / plan["suite"]).resolve()
    suite = load_suite(suite_path)
    split = plan.get("split", "held_out")
    tasks = [task for task in suite["tasks"] if task["split"] == split
             and ("task_ids" not in plan or task["id"] in plan["task_ids"])]
    if not tasks or "task_ids" in plan and set(plan["task_ids"]) != {task["id"] for task in tasks}:
        raise ValueError("Task selection is empty or includes identifiers outside the selected split")
    checks, references = [], {}
    with tempfile.TemporaryDirectory(prefix="eal-reference-freeze-") as temporary:
        for index, task in enumerate(tasks):
            check = check_task(task, suite_path.parent, Path(temporary) / str(index))
            checks.append({key: check[key] for key in ("id", "family", "passed", "errors")})
            service, inputs = prepare_task(task, suite_path.parent, Path(temporary) / f"reference-{index}")
            reference = {"inputs": inputs, "language_reference": service.describe(),
                         "expected": task["expected"], "oracle": task.get("oracle"),
                         "methods_factory": task.get("methods"),
                         "method_registry_fingerprint": service.method_registry.fingerprint}
            if task.get("draft_source"):
                reference["draft_source"] = (suite_path.parent / task["draft_source"]).read_text()
            references[task["id"]] = reference
    if not all(check["passed"] for check in checks):
        raise ValueError(f"Reference tasks failed: {checks}")
    providers = {}
    for condition in plan["conditions"]:
        path = (plan_path.parent / condition["provider"]).resolve()
        provider = provider_from_config(_provider_config(path), workspace=path.parent)
        providers[condition["id"]] = provider.identity()
    definition = {"schema": "EAL/experiment-freeze/1", "plan": plan,
                  "suite_version": suite["version"], "suite_digest": suite_digest(suite_path, suite),
                  "reference_checks": checks, "task_ids": [task["id"] for task in tasks],
                  "task_references": references, "task_reference_digest": _digest(references),
                  "provider_identities": providers, "scoring_version": SCORING_VERSION,
                  "language_reference_digest": _digest(describe_language()), "runtime": _code_identity(),
                  "schedule": make_schedule(plan, [task["id"] for task in tasks])}
    definition["freeze_digest"] = _digest(definition)
    definition["frozen_at"] = datetime.now(timezone.utc).isoformat()
    return definition


def _quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    location = (len(ordered) - 1) * fraction
    lower = int(location)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (location - lower)


def cluster_interval(rows: list[dict], value: Callable[[dict], float | None], *, seed: int = 0,
                     samples: int = 2000) -> dict:
    """Task-cluster bootstrap retains repeated outcomes together within a task."""
    by_task = {}
    for row in rows:
        result = value(row)
        if result is None:
            return {"estimate": None, "interval_95": None, "reason": "incomplete_measurements"}
        by_task.setdefault(row["task_id"], []).append(float(result))
    means = [statistics.mean(values) for values in by_task.values()]
    if not means:
        return {"estimate": None, "interval_95": None, "reason": "no_observations"}
    estimate = statistics.mean(means)
    if len(means) < 2:
        return {"estimate": estimate, "interval_95": None, "task_clusters": len(means), "reason": "fewer_than_two_tasks"}
    rng = random.Random(seed)
    replicates = [statistics.mean(rng.choices(means, k=len(means))) for _ in range(samples)]
    return {"estimate": estimate, "interval_95": [_quantile(replicates, .025), _quantile(replicates, .975)],
            "task_clusters": len(means), "bootstrap_samples": samples,
            "method": "percentile_task_cluster_bootstrap", "zero_observed_variance": len(set(means)) == 1}


def aggregate_experiment(trials: list[dict], schedule: list[dict], *, seed: int = 0, samples: int = 2000) -> dict:
    conditions = sorted({item["condition_id"] for item in schedule})
    summaries = {}
    for condition in conditions:
        rows = [trial for trial in trials if trial["condition_id"] == condition]
        expected = [item for item in schedule if item["condition_id"] == condition]
        totals = summarise(rows)
        arm = rows[0]["arm"] if rows else None
        successful = totals.get(arm, {}) if arm else {}
        statuses = {}
        for row in rows:
            for claim in row["score"]["claims"].values():
                key = claim["expected"]
                entry = statuses.setdefault(key, {"claims": 0, "correct": 0})
                entry["claims"] += 1
                entry["correct"] += claim["category"] == "correct"
        by_task = {}
        for row in rows:
            by_task.setdefault(row["task_id"], []).append(int(row["score"]["correct"]))
        summaries[condition] = {**successful, "scheduled_trials": len(expected), "completed_trials": len(rows),
                               "coverage_complete": len(rows) == len(expected), "claim_status_breakdown": statuses,
                               "declared_model_classes": sorted({row.get("declared_model_class", "unclassified") for row in rows}),
                               "response_model_identities": sorted({attempt["response_model"] for row in rows
                                    for attempt in row["report"].get("attempts", []) if isinstance(attempt.get("response_model"), str)}),
                               "host_conditions": sorted({str(row.get("host_mode")) + "/" + str(row.get("interaction_mode")) for row in rows}),
                               "task_repeat_outcomes": by_task,
                               "correct_rate": cluster_interval(rows, lambda row: float(row["score"]["correct"]), seed=seed, samples=samples),
                               "latency_seconds_per_trial": cluster_interval(rows, lambda row: row["report"].get("latency_seconds"), seed=seed, samples=samples),
                               "cost_usd_per_trial": cluster_interval(rows, lambda row: row["cost"]["total_usd"], seed=seed, samples=samples)}
    comparisons = []
    indexed = {(row["condition_id"], row["block_id"]): row for row in trials}
    for i, left in enumerate(conditions):
        for right in conditions[i + 1:]:
            blocks = sorted({row["block_id"] for row in trials if row["condition_id"] == left}
                            & {row["block_id"] for row in trials if row["condition_id"] == right})
            differences = []
            for block in blocks:
                a, b = indexed[left, block], indexed[right, block]
                cost_a, cost_b = a["cost"]["total_usd"], b["cost"]["total_usd"]
                latency_a, latency_b = a["report"].get("latency_seconds"), b["report"].get("latency_seconds")
                differences.append({"task_id": a["task_id"], "correct_difference": int(b["score"]["correct"]) - int(a["score"]["correct"]),
                                    "cost_difference": cost_b - cost_a if cost_a is not None and cost_b is not None else None,
                                    "latency_difference": latency_b - latency_a if latency_a is not None and latency_b is not None else None})
            comparisons.append({"left": left, "right": right, "direction": "right_minus_left", "paired_blocks": len(blocks),
                                "correct_rate_difference": cluster_interval(differences, lambda row: row["correct_difference"], seed=seed, samples=samples),
                                "cost_difference_usd": cluster_interval(differences, lambda row: row["cost_difference"], seed=seed, samples=samples),
                                "latency_difference_seconds": cluster_interval(differences, lambda row: row["latency_difference"], seed=seed, samples=samples)})
    return {"conditions": summaries, "paired_comparisons": comparisons,
            "uncertainty_interpretation": "Repeated calls within the same task remain one task cluster. Intervals describe variation across this finite task suite; tasks are not a random population sample. A zero-variance interval cannot exclude unseen failures. No inference to every model or all engineering tasks follows."}


async def run_experiment(plan_path: str | Path, output: str | Path, *, freeze_only: bool = False,
                         progress: Callable[[dict], None] | None = None) -> dict:
    from .agent import AgentBudget
    from .providers import provider_from_config
    plan_path = Path(plan_path).resolve()
    output = Path(output).resolve()
    freeze = freeze_experiment(plan_path)
    output.mkdir(parents=True, exist_ok=False)
    (output / "freeze.json").write_text(json.dumps(freeze, indent=2, allow_nan=False) + "\n")
    if freeze_only:
        return {"status": "frozen", "freeze_digest": freeze["freeze_digest"], "scheduled_trials": len(freeze["schedule"])}
    (output / "trials").mkdir()
    plan = freeze["plan"]
    suite_path = (plan_path.parent / plan["suite"]).resolve()
    suite = load_suite(suite_path)
    tasks = {task["id"]: task for task in suite["tasks"]}
    conditions = {condition["id"]: condition for condition in plan["conditions"]}
    trials, index = [], []
    semaphore = asyncio.Semaphore(plan.get("concurrency", 1))
    journal = output / "trials.jsonl"
    async def execute(scheduled):
        async with semaphore:
            condition = conditions[scheduled["condition_id"]]
            provider_path = (plan_path.parent / condition["provider"]).resolve()
            applied_seed = scheduled["sampling_seed"] if condition.get("seed_supported", False) else None
            provider = provider_from_config(_provider_config(provider_path, applied_seed), workspace=provider_path.parent)
            budget = AgentBudget(**{**plan.get("budget", {}), **condition.get("budget", {})})
            started = datetime.now(timezone.utc).isoformat()
            timer = time.monotonic()
            try:
                expected_identity = json.loads(json.dumps(freeze["provider_identities"][condition["id"]]))
                if applied_seed is not None:
                    expected_identity["sampling"] = {**expected_identity.get("sampling", {}), "seed": applied_seed}
                if provider.identity() != expected_identity:
                    raise ValueError("Provider configuration changed after the experiment freeze")
                trial = await evaluate_task(tasks[scheduled["task_id"]], suite_path.parent, provider,
                                            arm=condition["arm"], budget=budget,
                                            host_mode=condition.get("host_mode", "stateful"),
                                            interaction_mode=condition.get("interaction_mode", "text"),
                                            per_mcp_call_usd=plan.get("per_mcp_call_usd"))
            except Exception as exc:
                report = {"status": "incomplete", "stop_reason": "harness_exception", "exception_type": type(exc).__name__,
                          "provider": provider.identity(), "attempts": [], "tool_calls": [], "repairs": 0,
                          "final": None, "latency_seconds": time.monotonic() - timer,
                          "usage": {"token_usage_complete": False, "model_cost_complete": False}}
                trial = {"task_id": scheduled["task_id"], "arm": condition["arm"], "family": tasks[scheduled["task_id"]]["family"],
                         "report": report, "score": score_answer(tasks[scheduled["task_id"]]["expected"]["claims"], report),
                         "cost": {"total_usd": None, "model_usd": None, "tool_usd": None},
                         "measurement_warning": "Harness failed outside a completed host report; billed usage, if any, is unknown."}
            trial.update(scheduled)
            trial.update(started_at=started, finished_at=datetime.now(timezone.utc).isoformat(),
                         wall_latency_seconds=time.monotonic() - timer,
                         declared_model_class=condition["model_class"], applied_sampling_seed=provider.identity().get("sampling", {}).get("seed"),
                         condition=condition, budget=asdict(budget), freeze_digest=freeze["freeze_digest"])
            filename = f"trials/{scheduled['trial_id']}.json"
            encoded = json.dumps(trial, indent=2, allow_nan=False) + "\n"
            (output / filename).write_text(encoded)
            entry = {"trial_id": scheduled["trial_id"], "condition_id": scheduled["condition_id"], "task_id": scheduled["task_id"],
                     "repetition": scheduled["repetition"], "file": filename, "sha256": hashlib.sha256(encoded.encode()).hexdigest(),
                     "score": trial["score"], "cost": trial["cost"], "stop_reason": trial["report"]["stop_reason"]}
            with journal.open("a") as stream:
                stream.write(json.dumps(entry, allow_nan=False) + "\n")
                stream.flush()
            trials.append(trial)
            index.append(entry)
            if progress:
                progress({"completed": len(trials), "scheduled": len(freeze["schedule"]), "condition": scheduled["condition_id"],
                          "task": scheduled["task_id"], "repetition": scheduled["repetition"], "correct": trial["score"]["correct"],
                          "stop_reason": trial["report"]["stop_reason"], "model_cost_usd": trial["cost"].get("model_usd")})
    state = "completed"
    try:
        await asyncio.gather(*(execute(scheduled) for scheduled in freeze["schedule"]))
    except BaseException:
        state = "interrupted"
        raise
    finally:
        try:
            drift = suite_digest(suite_path) != freeze["suite_digest"] or _code_identity()["source_digest"] != freeze["runtime"]["source_digest"]
        except Exception:
            drift = True
        report = {"schema": "EAL/experiment-report/1", "name": plan["name"], "status": state,
                  "freeze_digest": freeze["freeze_digest"], "reference_or_implementation_drift": drift,
                  "scoring_version": SCORING_VERSION, "scheduled_trials": len(freeze["schedule"]), "completed_trials": len(trials),
                  "trial_artifacts": sorted(index, key=lambda entry: entry["trial_id"]),
                  "aggregate": aggregate_experiment(trials, freeze["schedule"], seed=plan.get("order_seed", 0), samples=plan.get("bootstrap_samples", 2000))}
        (output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="New directory; existing reports are never overwritten")
    parser.add_argument("--freeze-only", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(run_experiment(args.plan, args.output, freeze_only=args.freeze_only,
                                        progress=lambda value: print(json.dumps(value), flush=True)))
    print(json.dumps({"status": report["status"], "output": str(args.output), "freeze_digest": report["freeze_digest"],
                      "scheduled_trials": report["scheduled_trials"], "completed_trials": report.get("completed_trials", 0)}))


if __name__ == "__main__":
    main()
