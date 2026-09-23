"""Frozen model sequences with explicit, score-free evidence hand-offs.

Each stage starts a fresh host. Identical prefixes within a task/repetition are
executed once and reused across conditions. Charged usage is counted once in
the campaign and in full for the standalone cost of each sequence.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile
import time

from .agent import AgentBudget
from .benchmark import check_task, evaluate_task, load_suite, prepare_task, score_answer, suite_digest
from .experiment import _code_identity, _digest, _positive_integer, _provider_config, aggregate_experiment, make_schedule
from .providers import provider_from_config
from .runtime import strict_json

SCHEMA = "EAL/relay-plan/1"
SCORER = "common-endpoint-status/1"
HANDOFFS = {"none", "answer", "evidence", "transcript"}


def _write(path: Path, value: dict) -> None:
    """Commit a complete checkpoint; readers never observe partial JSON."""
    encoded = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _positive_cost(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite")


def load_relay_plan(path: str | Path) -> dict:
    plan = strict_json(Path(path).read_text())
    allowed = {"schema", "name", "suite", "split", "task_ids", "repetitions", "order_seed", "concurrency",
               "bootstrap_samples", "per_mcp_call_usd", "budget", "conditions", "notes", "protocol",
               "max_campaign_model_cost_usd", "max_handoff_bytes"}
    if not isinstance(plan, dict) or plan.get("schema") != SCHEMA or set(plan) - allowed:
        raise ValueError(f"Expected {SCHEMA} with recognised fields")
    for key in ("name", "suite", "protocol"):
        if not isinstance(plan.get(key), str) or not plan[key]:
            raise ValueError(f"{key} must be a nonempty string")
    if plan.get("split") not in {"development", "held_out"}:
        raise ValueError("A fixed split is required")
    for key, default, maximum in (("repetitions", 2, 100), ("concurrency", 1, 4),
                                 ("bootstrap_samples", 2000, 20000), ("max_handoff_bytes", 1048576, 8388608)):
        _positive_integer(plan.get(key, default), key, maximum)
    if type(plan.get("order_seed", 0)) is not int:
        raise ValueError("order_seed must be an integer")
    if "task_ids" in plan:
        ids = plan["task_ids"]
        if not isinstance(ids, list) or not ids or any(not isinstance(x, str) for x in ids) or len(ids) != len(set(ids)):
            raise ValueError("task_ids must be nonempty unique strings")
    _positive_cost(plan.get("max_campaign_model_cost_usd"), "max_campaign_model_cost_usd")
    cost = plan.get("per_mcp_call_usd")
    if cost is not None and (isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0):
        raise ValueError("per_mcp_call_usd must be nonnegative and finite or null")
    AgentBudget(**plan.get("budget", {}))
    conditions = plan.get("conditions")
    if not isinstance(conditions, list) or not 1 <= len(conditions) <= 32:
        raise ValueError("One through 32 conditions are required")
    names = set()
    for condition in conditions:
        if not isinstance(condition, dict) or set(condition) != {"id", "stages"}:
            raise ValueError("A condition contains id and stages")
        name = condition["id"]
        if not isinstance(name, str) or not name or name in names or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in name):
            raise ValueError("Condition IDs must be unique path-safe lowercase names")
        names.add(name)
        stages = condition["stages"]
        if not isinstance(stages, list) or not 1 <= len(stages) <= 4:
            raise ValueError("A sequence has one through four stages")
        for i, stage in enumerate(stages):
            if not isinstance(stage, dict) or set(stage) - {"provider", "model_class", "arm", "interaction_mode", "handoff", "budget"}:
                raise ValueError("Unrecognised stage settings")
            for key in ("provider", "model_class"):
                if not isinstance(stage.get(key), str) or not stage[key]:
                    raise ValueError(f"Each stage needs {key}")
            if stage.get("arm") not in {"unaided", "delegated"}:
                raise ValueError("stage.arm must be unaided or delegated")
            if stage.get("interaction_mode", "text") not in {"text", "native"}:
                raise ValueError("Invalid interaction mode")
            if stage["arm"] == "unaided" and stage.get("interaction_mode", "text") != "text":
                raise ValueError("Unaided stages cannot use native tools")
            if stage.get("handoff", "none") not in HANDOFFS or i == 0 and stage.get("handoff", "none") != "none":
                raise ValueError("Invalid handoff; first stages must have none")
            AgentBudget(**{**plan.get("budget", {}), **stage.get("budget", {})})
    return plan


def handoff_packet(previous: dict, mode: str) -> dict | None:
    """Allow-list model-visible records. Oracle, score and reference stay private.

    Evidence contains the complete prior stage's actual tool events, including
    failures. Transcript additionally includes the externally visible messages;
    neither mode requests or fabricates a provider's private reasoning.
    """
    if mode not in HANDOFFS:
        raise ValueError("Unknown handoff mode")
    if mode == "none":
        return None
    report = previous["report"]
    final = report.get("final") or {}
    packet = {"schema": "EAL/stage-handoff/1", "mode": mode,
              "producer_model": report.get("provider", {}).get("model"),
              "response_models": sorted({a["response_model"] for a in report.get("attempts", []) if a.get("response_model")}),
              "status": report.get("status"), "stop_reason": report.get("stop_reason"),
              "claims": {name: {"status": value.get("status") if isinstance(value, dict) else value}
                         for name, value in final.get("claims", {}).items()},
              "verification": final.get("verification", "unverified")}
    if mode in {"evidence", "transcript"}:
        packet.update(source=final.get("source"), tool_events=report.get("tool_calls", []),
                      source_revisions=report.get("source_revisions", []),
                      prior_stage=previous.get("inputs", {}).get("prior_stage"))
    if mode == "transcript":
        packet["conversation"] = report.get("conversation", [])
    packet = strict_json(json.dumps(packet, allow_nan=False))
    packet["content_digest"] = _digest(packet)
    return packet


def freeze_relay(path: str | Path) -> dict:
    path = Path(path).resolve()
    plan = load_relay_plan(path)
    suite_path = (path.parent / plan["suite"]).resolve()
    suite = load_suite(suite_path)
    tasks = [t for t in suite["tasks"] if t["split"] == plan["split"] and ("task_ids" not in plan or t["id"] in plan["task_ids"])]
    if not tasks or "task_ids" in plan and set(plan["task_ids"]) != {t["id"] for t in tasks}:
        raise ValueError("Task selection is empty or outside the split")
    providers, identities, references = {}, {}, {}
    for condition in plan["conditions"]:
        for stage in condition["stages"]:
            name = stage["provider"]
            config = _provider_config((path.parent / name).resolve())
            provider = provider_from_config(config, workspace=(path.parent / name).resolve().parent)
            identity = provider.identity()
            if stage.get("interaction_mode", "text") == "native" and not identity.get("capabilities", {}).get("native_tools"):
                raise ValueError("Native stage requires configured native tool support")
            providers[name], identities[name] = config, identity
    with tempfile.TemporaryDirectory(prefix="eal-relay-reference-") as temporary:
        for i, task in enumerate(tasks):
            check = check_task(task, suite_path.parent, Path(temporary) / str(i))
            if not check["passed"]:
                raise ValueError(f"Reference failed: {task['id']}: {check['errors']}")
            service, inputs = prepare_task(task, suite_path.parent, Path(temporary) / f"inputs-{i}")
            references[task["id"]] = {"inputs": inputs, "language_reference": service.describe(),
                                     "expected": task["expected"], "oracle": task.get("oracle"),
                                     "draft_source": (suite_path.parent / task["draft_source"]).read_text() if task.get("draft_source") else None}
    protocol = strict_json((path.parent / plan["protocol"]).read_text())
    result = {"schema": "EAL/relay-freeze/1", "plan": plan, "protocol": protocol,
              "provider_configurations": providers, "provider_identities": identities,
              "suite_digest": suite_digest(suite_path, suite), "suite_version": suite["version"],
              "task_references": references, "runtime": _code_identity(), "scorer": SCORER,
              "schedule": make_schedule(plan, [t["id"] for t in tasks])}
    result["freeze_digest"] = _digest(result)
    result["frozen_at"] = datetime.now(timezone.utc).isoformat()
    return result


def _failed(task: dict, provider: dict, reason: str, *, unknown_usage: bool = False) -> dict:
    report = {"status": "incomplete", "stop_reason": reason, "provider": provider, "final": None,
              "attempts": [], "tool_calls": [], "repairs": 0, "latency_seconds": 0,
              "usage": {"token_usage_complete": not unknown_usage, "total_tokens": None if unknown_usage else 0,
                        "model_cost_complete": not unknown_usage, "model_cost_usd": None if unknown_usage else 0}}
    return {"task_id": task["id"], "report": report, "score": score_answer(task["expected"]["claims"], report),
            "cost": {"model_usd": None if unknown_usage else 0, "tool_usd": 0, "total_usd": None if unknown_usage else 0}}


def combine_sequence(task: dict, condition: dict, stages: list[dict], stage_keys: list[str], terminal: dict | None = None) -> dict:
    reports = [s["report"] for s in stages]
    endpoint = terminal or stages[-1]
    report = dict(endpoint["report"])
    known = all(r.get("usage", {}).get("token_usage_complete", False) for r in reports)
    costs = [s["cost"]["model_usd"] for s in stages]
    total_costs = [s["cost"]["total_usd"] for s in stages]
    report.update(attempts=[a for r in reports for a in r.get("attempts", [])],
                  repairs=sum(r.get("repairs", 0) for r in reports),
                  latency_seconds=sum(r.get("latency_seconds", 0) for r in reports),
                  usage={"token_usage_complete": known,
                         "total_tokens": sum(r["usage"]["total_tokens"] for r in reports) if known else None})
    # Primary scoring is identical for model-only and tool-using endpoints.
    score = score_answer(task["expected"]["claims"], endpoint["report"])
    return {"task_id": task["id"], "family": task["family"], "condition": condition,
            "arm": condition["stages"][-1]["arm"], "report": report, "score": score,
            "endpoint_operational_score": endpoint["score"], "stage_keys": stage_keys,
            "stage_endpoint_correct": [score_answer(task["expected"]["claims"], r)["correct"] for r in reports],
            "cost": {"model_usd": sum(costs) if all(c is not None for c in costs) else None,
                     "total_usd": sum(total_costs) if all(c is not None for c in total_costs) else None},
            "declared_model_class": " -> ".join(s["model_class"] for s in condition["stages"])}


async def run_relay(path: str | Path, output: str | Path, *, resume: bool = False,
                    freeze_only: bool = False, progress=None) -> dict:
    path, output = Path(path).resolve(), Path(output).resolve()
    current = freeze_relay(path)
    if resume:
        freeze = strict_json((output / "freeze.json").read_text())
        if freeze["freeze_digest"] != current["freeze_digest"]:
            raise ValueError("Resume refused: protocol, code, tasks or configuration changed")
    else:
        output.mkdir(parents=True, exist_ok=False)
        freeze = current
        _write(output / "freeze.json", freeze)
    for directory in ("stages", "trials"):
        (output / directory).mkdir(exist_ok=True)
    if freeze_only:
        return {"status": "frozen", "scheduled_trials": len(freeze["schedule"]), "freeze_digest": freeze["freeze_digest"]}
    plan = freeze["plan"]
    suite_path = (path.parent / plan["suite"]).resolve()
    tasks = {t["id"]: t for t in load_suite(suite_path)["tasks"]}
    conditions = {c["id"]: c for c in plan["conditions"]}
    cache, locks, trials = {}, {}, []
    charged, reserved, unknown = 0.0, 0.0, False
    for record_path in sorted((output / "stages").glob("*.json")):
        if record_path.name.endswith(".inflight.json"):
            continue
        record = strict_json(record_path.read_text())
        if record["sha256"] != _digest(record["trial"]) or record["freeze_digest"] != freeze["freeze_digest"]:
            raise ValueError("Stage checkpoint integrity mismatch")
        cache[record_path.stem] = record["trial"]
        cost = record["trial"]["cost"]["model_usd"]
        charged += cost or 0
        unknown |= cost is None
    # An interrupted request may already have been billed. Detect all such
    # requests before scheduling anything new, including a different prefix.
    unknown |= any(marker.name.removesuffix(".inflight.json") not in cache
                   for marker in (output / "stages").glob("*.inflight.json"))
    semaphore = asyncio.Semaphore(plan.get("concurrency", 1))

    async def stage_run(task, scheduled, stage, packet):
        nonlocal charged, reserved, unknown
        config = freeze["provider_configurations"][stage["provider"]]
        settings = {k: v for k, v in stage.items() if k not in {"model_class", "provider", "handoff", "budget"}}
        settings.setdefault("interaction_mode", "text")
        budget = AgentBudget(**{**plan.get("budget", {}), **stage.get("budget", {})})
        key = _digest({"task": task["id"], "repetition": scheduled["repetition"], "config": config,
                       "settings": settings, "budget": asdict(budget), "prior_stage": packet})
        async with locks.setdefault(key, asyncio.Lock()):
            if key in cache:
                return key, cache[key]
            identity = freeze["provider_identities"][stage["provider"]]
            marker = output / "stages" / (key + ".inflight.json")
            if marker.exists():
                trial = _failed(task, identity, "interrupted_unknown_usage", unknown_usage=True)
                unknown = True
            elif unknown or charged + reserved >= plan["max_campaign_model_cost_usd"]:
                return key, _failed(task, identity, "campaign_cost_unverifiable" if unknown else "campaign_cost_budget_exhausted")
            elif packet is not None and len(json.dumps(packet, ensure_ascii=False).encode()) > plan.get("max_handoff_bytes", 1048576):
                trial = _failed(task, identity, "handoff_byte_budget_exhausted")
            else:
                # Reserve a stage threshold, bounded by remaining campaign funds.
                # Both limits are post-response thresholds, not invoice caps.
                available = plan["max_campaign_model_cost_usd"] - charged - reserved
                if budget.max_model_cost_usd is not None and available < budget.max_model_cost_usd:
                    return key, _failed(task, identity, "campaign_cost_budget_exhausted")
                allocation = budget.max_model_cost_usd or available
                reserved += allocation
                _write(marker, {"freeze_digest": freeze["freeze_digest"], "stage_key": key,
                                "task_id": task["id"], "started_at": datetime.now(timezone.utc).isoformat()})
                provider_path = (path.parent / stage["provider"]).resolve()
                provider = provider_from_config(config, workspace=provider_path.parent)
                try:
                    trial = await evaluate_task(task, suite_path.parent, provider, arm=stage["arm"], budget=budget,
                                                per_mcp_call_usd=plan.get("per_mcp_call_usd"), host_mode="stateful",
                                                interaction_mode=stage.get("interaction_mode", "text"), prior_stage=packet)
                except Exception as exc:
                    trial = _failed(task, identity, "harness_exception_" + type(exc).__name__, unknown_usage=True)
                finally:
                    reserved -= allocation
            _write(output / "stages" / (key + ".json"), {"freeze_digest": freeze["freeze_digest"],
                                                        "trial": trial, "sha256": _digest(trial)})
            marker.unlink(missing_ok=True)
            cost = trial["cost"]["model_usd"]
            charged += cost or 0
            unknown |= cost is None
            cache[key] = trial
            return key, trial

    async def execute(scheduled):
        async with semaphore:
            target = output / "trials" / (scheduled["trial_id"] + ".json")
            if target.exists():
                record = strict_json(target.read_text())
                if record["sha256"] != _digest(record["trial"]) or record["freeze_digest"] != freeze["freeze_digest"]:
                    raise ValueError("Trial checkpoint integrity mismatch")
                trials.append(record["trial"])
                return
            task, condition = tasks[scheduled["task_id"]], conditions[scheduled["condition_id"]]
            stages, keys = [], []
            terminal = None
            start = time.monotonic()
            for stage in condition["stages"]:
                packet = handoff_packet(stages[-1], stage.get("handoff", "none")) if stages else None
                key, trial = await stage_run(task, scheduled, stage, packet)
                stages.append(trial)
                keys.append(key)
                if trial["cost"]["model_usd"] is None or trial["report"]["stop_reason"].startswith(("campaign_", "handoff_")):
                    terminal = trial
                    break
            result = combine_sequence(task, condition, stages, keys, terminal)
            result.update(scheduled, freeze_digest=freeze["freeze_digest"], stage_count=len(stages),
                          scheduling_wall_seconds=time.monotonic() - start)
            _write(target, {"trial": result, "sha256": _digest(result), "freeze_digest": freeze["freeze_digest"]})
            trials.append(result)
            if progress:
                progress({"completed": len(trials), "scheduled": len(freeze["schedule"]), "condition": condition["id"],
                          "correct": result["score"]["correct"], "unique_stages": len(cache), "known_model_cost_usd": charged})

    status = "completed"
    jobs = [asyncio.create_task(execute(row)) for row in freeze["schedule"]]
    try:
        await asyncio.gather(*jobs)
    except BaseException:
        status = "interrupted"
        for job in jobs:
            job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)
        raise
    finally:
        drift = _code_identity()["source_digest"] != freeze["runtime"]["source_digest"] or suite_digest(suite_path) != freeze["suite_digest"]
        report = {"schema": "EAL/relay-report/1", "status": status, "scorer": SCORER,
                  "freeze_digest": freeze["freeze_digest"], "reference_or_implementation_drift": drift,
                  "scheduled_trials": len(freeze["schedule"]), "completed_trials": len(trials),
                  "unique_stages": len(cache), "known_unique_model_cost_usd": charged,
                  "unique_model_cost_usd": None if unknown else charged,
                  "stage_uses": sum(len(t["stage_keys"]) for t in trials),
                  "aggregate": aggregate_experiment(trials, freeze["schedule"], seed=plan.get("order_seed", 0), samples=plan.get("bootstrap_samples", 2000)),
                  "trial_files": ["trials/" + t["trial_id"] + ".json" for t in sorted(trials, key=lambda t: t["trial_id"])],
                  "interpretation": "Identical prefixes share a single recorded output within task/repetition. Sequence cost and latency include all stages as if run alone. Campaign model cost counts unique stages once. Incomplete charged usage remains unknown. Endpoint correctness is distinct from checked source and evidence. Tasks are exposed synthetic regression cases."}
        _write(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--freeze-only", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(run_relay(args.plan, args.output, resume=args.resume, freeze_only=args.freeze_only,
                                  progress=lambda value: print(json.dumps(value), flush=True)))
    print(json.dumps({key: result[key] for key in ("status", "scheduled_trials", "freeze_digest")}))


if __name__ == "__main__":
    main()
