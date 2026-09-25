"""Real model calls, real HTTP measurements, and durable one-attempt records."""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import importlib.metadata
import json
import os
import random
import subprocess
import time
from pathlib import Path

import jsonschema

from eal.providers import ProviderError, response_cost
from eal.responses_provider import ResponsesProvider
from eal.tool_acquisition import strict_json

from .api import build_id, serve, utc_now
from .materials import ARMS, PROFILES, SYSTEM, operations, prompt_for, source_for
from .oracle import grade, reference
from .routes import ROOT, TrialTools


HERE = Path(__file__).resolve().parent


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def event(path: Path, value):
    with path.open("a") as stream:
        stream.write(json.dumps({"at": utc_now(), **value}, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def schedule(model: str, repetitions: int, seed: int):
    rng = random.Random(f"{seed}:{model}")
    blocks = [(repeat, profile) for repeat in range(repetitions) for profile in PROFILES]
    rng.shuffle(blocks)
    assignments = []
    for repeat, profile in blocks:
        arms = list(ARMS)
        rng.shuffle(arms)
        for arm in arms:
            assignment_id = hashlib.sha256(f"{seed}:{model}:{repeat}:{profile}:{arm}".encode()).hexdigest()[:20]
            assignments.append({"id": assignment_id, "model": model, "repeat": repeat,
                                "profile": profile, "arm": arm, "block": f"{repeat}:{profile}"})
    return assignments


def make_provider(spec: dict, plan: dict):
    capabilities = {"native_tools": True, "tool_reasoning_compatible": True}
    if spec["reasoning_effort"]:
        capabilities["reasoning_effort"] = spec["reasoning_effort"]
    return ResponsesProvider(model=spec["id"], api_key_env="OPENAI_API_TOKEN",
                             sampling=spec["sampling"], pricing=spec["pricing"],
                             capabilities=capabilities, timeout_seconds=plan["provider_timeout_seconds"])


class Budget:
    def __init__(self, limit: float):
        self.limit, self.estimated_usd, self.unknown_reserve = limit, 0.0, 0.0

    def reserve(self, messages, tools, output_limit, pricing):
        # Conservative admission allowance, not a provider billing reservation.
        input_allowance = 2 * len(json.dumps([messages, tools], ensure_ascii=False).encode()) + 4096
        maximum = (input_allowance * pricing["input_usd_per_million"]
                   + output_limit * pricing["output_usd_per_million"]) / 1_000_000
        if self.estimated_usd + self.unknown_reserve + maximum > self.limit:
            raise ValueError("Configured model cost allowance exhausted")
        self.unknown_reserve += maximum
        return maximum

    def settle(self, reserved, response, provider):
        cost = response_cost(response, provider.identity()) if response else None
        if cost is not None:
            self.unknown_reserve -= reserved
            self.estimated_usd += cost
        return cost


async def trial(assignment, spec, plan, workspace, provider, budget):
    arm, profile = assignment["arm"], PROFILES[assignment["profile"]]
    workload = {"service": "orders-api", "build_id": build_id(), "run_id": assignment["id"],
                "concurrent_clients": 10, "request_count": profile["request_count"], "timeout_seconds": 3}
    context = {key: workload[key] for key in ("service", "build_id", "run_id")}
    context["dataset"] = "measured_controlled_api"
    source = source_for(workload, context)
    prompt = prompt_for(arm, source, workload)
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    advertised = operations(arm)
    handles, calls = [], []
    answer, truth, failure = None, None, None
    stop_model = False
    started = time.monotonic()
    result = {**assignment, "model_spec": spec, "started_at": utc_now(), "state": "running",
              "source_digest": hashlib.sha256(source.encode()).hexdigest(), "model_calls": calls}
    write_json(workspace / "trial.json", result)
    write_json(workspace / "prompt.json", {"messages": messages, "operations": advertised})
    with serve(profile, workload["run_id"]) as api:
        tools = TrialTools(workspace, source, {"port": api["port"], "input": workload, "context": context})
        try:
            for turn in range(plan["max_model_calls_per_trial"]):
                if len(json.dumps(messages).encode()) > plan["max_transcript_bytes"]:
                    failure = "transcript_limit"
                    break
                try:
                    reserved = budget.reserve(messages, advertised, plan["max_output_tokens_per_call"], spec["pricing"])
                except ValueError:
                    failure, stop_model = "cost_allowance_exhausted", True
                    break
                event(workspace / "events.jsonl", {"type": "model_call_started", "turn": turn,
                                                    "reserved_usd": reserved})
                call_started = time.monotonic()
                try:
                    response = await provider.complete_request(messages, plan["max_output_tokens_per_call"],
                                                               operations=advertised, native_tools=True)
                except ProviderError as exc:
                    cost = budget.settle(reserved, exc.response, provider)
                    calls.append({"turn": turn, "error": str(exc), "estimated_usd": cost,
                                  "response": dataclasses.asdict(exc.response) if exc.response else None,
                                  "seconds": time.monotonic() - call_started})
                    event(workspace / "events.jsonl", {"type": "model_call_failed", **calls[-1]})
                    failure, stop_model = "provider_error", True
                    break
                cost = budget.settle(reserved, response, provider)
                calls.append({"turn": turn, "response": dataclasses.asdict(response), "estimated_usd": cost,
                              "seconds": time.monotonic() - call_started})
                event(workspace / "events.jsonl", {"type": "model_call_completed", **calls[-1]})
                if response.model != spec["id"] or cost is None:
                    failure, stop_model = "model_identity_or_usage_unverified", True
                    break
                handle = response.metadata.get("responses_replay_handle")
                handles.append(handle)
                native = response.metadata["native_tool_call"]
                messages.append({"role": "assistant", "content": None, "tool_calls": [native],
                                 "_responses_replay_handle": handle})
                try:
                    operation = strict_json(response.text)
                    definition = next(item for item in advertised if item["operation"] == operation.get("operation"))
                    jsonschema.validate(operation, definition["input_schema"])
                    if operation["operation"] == "finish":
                        answer = {key: value for key, value in operation.items() if key != "operation"}
                        break
                    packet = await tools.execute(arm)
                except (ValueError, KeyError, TypeError, StopIteration, jsonschema.ValidationError) as exc:
                    packet = {"error": type(exc).__name__, "message": str(exc)[:2000]}
                messages.append({"role": "tool", "tool_call_id": native["id"], "content": json.dumps(packet)})
                write_json(workspace / "transcript.json", messages)
                write_json(workspace / "tool-trace.json", tools.trace)
                await asyncio.sleep(plan["minimum_call_interval_seconds"])
            if answer is None and failure is None:
                failure = "model_call_limit"
        except Exception as exc:
            failure = f"host_error:{type(exc).__name__}"
            event(workspace / "events.jsonl", {"type": "host_error", "category": type(exc).__name__})
        finally:
            provider.discard_replay_handles(handles)
            if tools.report_path.exists():
                try:
                    report = strict_json(tools.report_path.read_text())
                    truth = reference(report, workload, context, tools.assessed_at or utc_now())
                except (ValueError, KeyError, TypeError) as exc:
                    failure = f"reference_error:{type(exc).__name__}"
            if truth and tools.host_status is not None and tools.host_status != truth["status"]:
                failure = "host_reference_disagreement"
            outcome = grade(answer, truth, collected=tools.packet is not None, host_status=tools.host_status)
            if failure:
                outcome["correct"] = False
            result.update(state="complete" if answer and not failure else "failed", failure=failure,
                          answer=answer, reference=truth, outcome=outcome,
                          host_status=tools.host_status, completed_at=utc_now(),
                          seconds=time.monotonic() - started, stop_model=stop_model,
                          collected=tools.packet is not None, tool_route="mcp" if arm == "eal_mcp" else "direct")
            write_json(workspace / "transcript.json", messages)
            write_json(workspace / "tool-trace.json", tools.trace)
            write_json(workspace / "server-events.json", api["events"])
            write_json(workspace / "trial.json", result)
    return result


async def run(output: Path, specs: list[dict], plan: dict, *, mode: str, provider_factory=make_provider):
    if tuple(plan["arms"]) != ARMS or tuple(plan["profiles"]) != tuple(PROFILES):
        raise ValueError("Plan arms and profiles differ from the frozen executable materials")
    if not specs or len({spec["id"] for spec in specs}) != len(specs):
        raise ValueError("Select at least one model, without duplicate snapshots")
    output.mkdir(parents=True, exist_ok=False)
    repetitions = plan[f"{mode}_repetitions"]
    assignments = [item for spec in specs for item in schedule(spec["id"], repetitions, plan["seed"])]
    files = [*HERE.glob("*.py"), *HERE.glob("*.json"), HERE / "Dockerfile", HERE / "requirements.lock",
             *ROOT.joinpath("src/eal").rglob("*.py")]
    commit = os.environ.get("EAL_SOURCE_COMMIT")
    if not commit:
        commit = (subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
                  if (ROOT / ".git").exists() else "source-snapshot-only")
    manifest = {"schema": "eal-api-experiment-run/1", "mode": mode, "started_at": utc_now(), "plan": plan,
                "models": specs, "assignments": assignments,
                "commit": commit,
                "github_run_id": os.environ.get("GITHUB_RUN_ID"), "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
                "files": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
                "dependencies": {name: importlib.metadata.version(name) for name in ("mcp", "httpx", "jsonschema", "antlr4-python3-runtime")}}
    write_json(output / "manifest.json", manifest)
    if not os.environ.get("OPENAI_API_TOKEN"):
        write_json(output / "preflight.json", {"ready": False, "reason": "OPENAI_API_TOKEN is absent", "model_calls": 0})
        return False
    write_json(output / "preflight.json", {"ready": True, "credential": "OPENAI_API_TOKEN", "value_retained": False})
    all_results = []
    for spec in specs:
        budget = Budget(plan[f"{mode}_max_usd_per_model"])
        stopped = False
        for assignment in (item for item in assignments if item["model"] == spec["id"]):
            workspace = output / "trials" / assignment["id"]
            if stopped:
                result = {**assignment, "state": "not_attempted", "failure": "earlier_model_stop", "model_calls": [],
                          "outcome": grade(None, None, collected=False)}
                write_json(workspace / "trial.json", result)
            else:
                provider = provider_factory(spec, plan)
                result = await trial(assignment, spec, plan, workspace, provider, budget)
                stopped = result["stop_model"]
            all_results.append(result)
            event(output / "ledger.jsonl", {"type": "trial_terminal", "id": assignment["id"],
                                           "state": result["state"], "correct": result["outcome"]["correct"]})
        write_json(output / f"budget-{spec['id']}.json", {"estimated_usd": budget.estimated_usd,
                   "unknown_charge_reserve_usd": budget.unknown_reserve, "limit_usd": budget.limit})
    complete = all(item["state"] == "complete" for item in all_results)
    write_json(output / "completion.json", {"complete": complete, "completed_at": utc_now(), "trials": len(all_results),
                                           "planned": len(assignments), "model_calls": sum(len(x["model_calls"]) for x in all_results)})
    return complete
