#!/usr/bin/env python3
"""Frozen developmental paid test of lexical candidates and exact family routing.

Freeze first, audit freeze.json, then explicitly execute. One model call per
case; pending or failed calls are never retried or silently resumed.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import random
import sys
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from eal.providers import ModelResponse, ProviderError, load_provider, response_cost  # noqa: E402
from eal.runtime import strict_json  # noqa: E402


HERE = Path(__file__).resolve().parent
PLAN = HERE / "plan.json"
FIXTURE = HERE.parent / "kubernetes-host-revisions"
SPEC = importlib.util.spec_from_file_location("k8s_host_revision_fixture", FIXTURE / "run.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)

FREEZE_SCHEMA = "eal2-family-selection-freeze/1"
LEDGER_SCHEMA = "eal2-family-selection-ledger/1"
SYSTEM = (
    "You nominate a reviewed task family for an engineering query. The candidates are lexical "
    "suggestions, not verified applicability. If the task clearly identifies one operation, select "
    "one listed family and copy the task's typed cluster and namespace values exactly, even when "
    "you do not know whether a reviewed tuple exists. If the operation is ambiguous, irrelevant or "
    "no suitable family was retrieved, abstain. Do not assess evidence or invent a claim status. "
    "Reply with exactly one JSON object with keys action, family_id, bindings, claim, reason. "
    "For select: action='select', a listed family_id, bindings with cluster and namespace strings, "
    "that family's listed claim, and a reason of at most 280 characters. For abstain: action='abstain', "
    "family_id, bindings and claim null, and a short reason. No Markdown."
)


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def read_json(path: Path) -> Any:
    return strict_json(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)


def load_plan(path: Path = PLAN) -> dict:
    plan = read_json(path)
    required = {"schema", "study_kind", "fixture", "provider_configs", "provider_order",
                "response_model_aliases", "max_prompt_bytes", "max_output_tokens",
                "max_cost_usd", "input_reserve_multiplier", "order_seed", "cases"}
    if not isinstance(plan, dict) or set(plan) != required or plan["schema"] != "eal2-family-selection-paid/1":
        raise ValueError("Invalid paid selection plan")
    if plan["study_kind"] != "developmental_synthetic":
        raise ValueError("This runner admits developmental synthetic fixtures only")
    if (Path(path.parent / plan["fixture"]).resolve() != FIXTURE
            or plan["provider_order"] != ["nano", "luna", "sol_high"]
            or set(plan["provider_configs"]) != set(plan["provider_order"])):
        raise ValueError("Unexpected fixture or provider matrix")
    for key in ("max_prompt_bytes", "max_output_tokens", "input_reserve_multiplier"):
        if type(plan[key]) is not int or not 1 <= plan[key] <= 8192:
            raise ValueError(f"Invalid {key}")
    if not 0 < plan["max_cost_usd"] <= 2 or type(plan["order_seed"]) is not int:
        raise ValueError("Invalid bounded budget or order seed")
    if not isinstance(plan["cases"], list) or len(plan["cases"]) != 12:
        raise ValueError("Expected exactly twelve frozen task cases")
    if len({row.get("id") for row in plan["cases"]}) != 12:
        raise ValueError("Duplicate task case")
    return plan


def _providers(plan: dict, plan_path: Path) -> dict:
    result = {}
    for name in plan["provider_order"]:
        path = (plan_path.parent / plan["provider_configs"][name]).resolve()
        if path.parent != HERE.parent / "campaign-config":
            raise ValueError("Provider configuration escapes the campaign configuration")
        result[name] = load_provider(path)
    return result


def _materials(plan: dict, plan_path: Path) -> dict[str, str]:
    paths = [plan_path, HERE / "run.py",
             ROOT / "grammar/EAL.g4", ROOT / "pyproject.toml",
             *(FIXTURE / name for name in ("source.eal", "manifest.json", "artifacts.toml",
                                            "families.toml", "run.py")),
             *((plan_path.parent / plan["provider_configs"][name]).resolve()
               for name in plan["provider_order"])]
    paths.extend(sorted((ROOT / "src/eal").rglob("*.py")))
    return {path.relative_to(ROOT).as_posix(): digest(path.read_bytes()) for path in paths}


def _runtime_versions() -> dict[str, str]:
    return {
        "python": ".".join(str(part) for part in sys.version_info[:3]),
        "antlr4-python3-runtime": version("antlr4-python3-runtime"),
        "mcp": version("mcp"),
        "jsonschema": version("jsonschema"),
        "httpx": version("httpx"),
    }


def _query_and_revision(manifest: dict, item: dict) -> tuple[dict, dict]:
    queries = {row["id"]: row for row in manifest["queries"]}
    revisions = {row["id"]: row for row in manifest["revisions"]}
    if item.get("query_id") not in queries or item.get("revision_id") not in revisions:
        raise ValueError("Case references a missing query or evidence revision")
    return queries[item["query_id"]], revisions[item["revision_id"]]


def _metadata(host, suggestions: list[dict]) -> list[dict]:
    rows = []
    for suggestion in suggestions:
        family_id = suggestion["family_id"]
        family = host.families.families[family_id]
        rows.append({
            "family_id": family_id, "description": family.description,
            "parameters": {name: {"type": spec.kind, "allowed_values": list(spec.values)}
                           for name, spec in family.parameters.items()},
            "claims": sorted({claim for case in family.cases for claim in case.claims}),
            "lexical_score": suggestion["score"],
        })
    return rows


def _reference_check(item: dict, query: dict, suggestions: list[dict], host, revision: dict) -> str | None:
    reference = item["reference"]
    candidates = {row["family_id"] for row in suggestions}
    relevant = set(query["relevant"])
    bindings = {"cluster": item["cluster"], "namespace": item["namespace"]}
    if reference in fixture.ALL_FAMILIES:
        if reference not in relevant or reference not in candidates or bindings != fixture.CONTEXT:
            raise ValueError("Reference family is unavailable or scoped incorrectly")
        packet = host.assess(reference, bindings, reference)
        expected = revision["expected_status"] if reference == "checkout_latency" else "supported"
        if packet["status"] != expected:
            raise ValueError(f"Reference host status differs for {item['id']}")
        return expected
    if reference == "retrieval_miss":
        if relevant != {"service_failover"} or candidates:
            raise ValueError("Synonym miss no longer reproduces")
    elif reference == "abstain_ambiguous":
        if len(relevant) < 2 or len(candidates & relevant) < 2:
            raise ValueError("Ambiguity no longer reproduces")
    elif reference == "abstain_no_target":
        if relevant:
            raise ValueError("No-target query acquired a reference family")
    elif reference == "unreviewed_no_accept":
        if relevant != {"checkout_latency"} or "checkout_latency" not in candidates:
            raise ValueError("Unseen tuple candidate changed")
        try:
            host.assess("checkout_latency", bindings, "checkout_latency")
        except ValueError as exc:
            if "No reviewed case" not in str(exc):
                raise
        else:
            raise ValueError("Unreviewed tuple unexpectedly resolved")
    else:
        raise ValueError("Unknown case reference category")
    return None


def prepare(plan_path: Path = PLAN, providers: dict | None = None) -> dict:
    plan_path = plan_path.resolve()
    plan = load_plan(plan_path)
    loaded = providers if providers is not None else _providers(plan, plan_path)
    if set(loaded) != set(plan["provider_order"]):
        raise ValueError("Provider identity matrix differs from plan")
    identities = {name: provider.identity() for name, provider in loaded.items()}
    for name, identity in identities.items():
        if (identity.get("model") != {"nano": "gpt-4.1-nano", "luna": "gpt-6-luna",
                                     "sol_high": "gpt-6-sol"}[name]
                or not {"input_usd_per_million", "output_usd_per_million"}
                <= identity.get("pricing", {}).keys()):
            raise ValueError("Model or configured rates differ from audited matrix")
    manifest = read_json(FIXTURE / "manifest.json")
    fixture._validate_manifest(manifest)
    base = []
    with tempfile.TemporaryDirectory(prefix="eal2-family-freeze-") as temporary:
        for item in plan["cases"]:
            if (set(item) != {"id", "query_id", "revision_id", "cluster", "namespace", "reference"}
                    or not all(isinstance(item[key], str) for key in item)):
                raise ValueError("Case requires exact task identity and scope")
            query, revision = _query_and_revision(manifest, item)
            workspace = Path(temporary) / item["id"]
            fixture._workspace(workspace, revision)
            host = fixture._host(workspace)
            suggestions = host.candidates(query["query"], limit=3)
            expected_status = _reference_check(item, query, suggestions, host, revision)
            candidate_metadata = _metadata(host, suggestions)
            messages = [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": (
                    "Task request: " + query["query"]
                    + "\nTrusted task scope: " + canonical({
                        "cluster": item["cluster"], "namespace": item["namespace"]}).decode()
                    + "\nCandidate families: " + canonical(candidate_metadata).decode()
                )},
            ]
            prompt_bytes = len(canonical(messages))
            if prompt_bytes > plan["max_prompt_bytes"]:
                raise ValueError("Prompt exceeds freeze byte bound")
            base.append({
                "task_id": item["id"], "revision_id": item["revision_id"],
                "reference": item["reference"], "expected_status": expected_status,
                "scope": {"cluster": item["cluster"], "namespace": item["namespace"]},
                "query": query["query"], "suggestions": suggestions,
                "candidate_metadata": candidate_metadata,
                "messages": messages, "prompt_bytes": prompt_bytes,
            })
    cases = []
    for task in base:
        for name in plan["provider_order"]:
            cases.append({"case_id": f'{task["task_id"]}__{name}', "model_class": name,
                          **task, "prompt_sha256": digest(task["messages"])})
    random.Random(plan["order_seed"]).shuffle(cases)
    rates = identities
    maximum_reserved = sum(_reserve(case, rates[case["model_class"]], plan)
                           for case in cases)
    if maximum_reserved > plan["max_cost_usd"]:
        raise ValueError("Full schedule exceeds the configured budget reserve")
    result = {
        "schema": FREEZE_SCHEMA,
        "study_kind": plan["study_kind"],
        "plan_path": plan_path.relative_to(ROOT).as_posix(),
        "materials": _materials(plan, plan_path),
        "runtime_versions": _runtime_versions(),
        "provider_identities": identities,
        "cases": cases,
        "maximum_reserved_usd": maximum_reserved,
        "model_calls": len(cases),
        "max_cost_usd": plan["max_cost_usd"],
        "analysis_scope": "single-author synthetic developmental routing",
    }
    result["freeze_sha256"] = digest(result)
    return result


def _reserve(case: dict, identity: dict, plan: dict) -> float:
    rates = identity["pricing"]
    input_upper = plan["input_reserve_multiplier"] * (case["prompt_bytes"] + 256)
    return (input_upper * rates["input_usd_per_million"]
            + plan["max_output_tokens"] * rates["output_usd_per_million"]) / 1_000_000


def _selection(text: str) -> dict:
    try:
        value = strict_json(text)
    except (ValueError, UnicodeError):
        return {"action": "invalid", "reason": "Malformed JSON"}
    if (not isinstance(value, dict)
            or set(value) != {"action", "family_id", "bindings", "claim", "reason"}
            or not isinstance(value["reason"], str)
            or len(value["reason"]) > 280):
        return {"action": "invalid", "reason": "Wrong field set or reason length"}
    if value["action"] == "abstain":
        if value["family_id"] is None and value["bindings"] is None and value["claim"] is None:
            return value
        return {"action": "invalid", "reason": "Abstention contains a selection"}
    if (value["action"] != "select" or not isinstance(value["family_id"], str)
            or not isinstance(value["claim"], str)
            or not isinstance(value["bindings"], dict)
            or set(value["bindings"]) != {"cluster", "namespace"}
            or any(type(value["bindings"][key]) is not str for key in value["bindings"])):
        return {"action": "invalid", "reason": "Selection schema or typed bindings invalid"}
    return value


def _route(case: dict, selection: dict) -> dict:
    reference = case["reference"]
    if selection["action"] == "invalid":
        return {"outcome": "malformed", "accepted_status": None, "selection_correct": False}
    if selection["action"] == "abstain":
        return {
            "outcome": "abstained", "accepted_status": None,
            "safe_abstention": reference in {
                "retrieval_miss", "abstain_ambiguous", "abstain_no_target", "unreviewed_no_accept"
            },
            "selection_correct": reference in {
                "abstain_ambiguous", "abstain_no_target", "unreviewed_no_accept"
            },
        }
    family = selection["family_id"]
    if family not in {row["family_id"] for row in case["suggestions"]}:
        return {"outcome": "unretrieved_candidate", "accepted_status": None, "selection_correct": False}
    if selection["bindings"] != case["scope"]:
        return {"outcome": "wrong_task_scope", "accepted_status": None, "selection_correct": False}
    manifest = read_json(FIXTURE / "manifest.json")
    _, revision = _query_and_revision(manifest, {
        "query_id": next(row["id"] for row in manifest["queries"] if row["query"] == case["query"]),
        "revision_id": case["revision_id"],
    })
    with tempfile.TemporaryDirectory(prefix="eal2-family-route-") as temporary:
        workspace = Path(temporary) / "instance"
        fixture._workspace(workspace, revision)
        host = fixture._host(workspace)
        started = time.perf_counter_ns()
        try:
            packet = host.assess(family, selection["bindings"], selection["claim"])
            final = host.finish(family, selection["bindings"], selection["claim"], packet["assessment_id"])
            trace = host.explain(family, selection["bindings"], selection["claim"], packet["assessment_id"])
            if packet != final:
                raise ValueError("Host final packet changed")
        except ValueError as exc:
            if not any(fragment in str(exc) for fragment in (
                    "No reviewed case exists", "Unknown or unauthorised family",
                    "not reviewed and granted", "unauthorised artefact",
                    "not an allowed typed value")):
                raise
            return {
                "outcome": "rejected_exact_binding", "accepted_status": None,
                "selection_correct": reference == "unreviewed_no_accept" and family == "checkout_latency"
                                     and selection["claim"] == "checkout_latency",
                "host_error": str(exc),
                "host_ms": round((time.perf_counter_ns() - started) / 1e6, 3),
            }
        if (reference not in fixture.ALL_FAMILIES or family != reference
                or selection["claim"] != reference):
            # A valid case selected for an irrelevant task is an unsafe decision;
            # preserve the host status but flag it as wrong-family acceptance.
            correct = False
        else:
            correct = packet["status"] == case["expected_status"]
        return {
            "outcome": "accepted", "accepted_status": packet["status"],
            "selection_correct": correct,
            "false_support": packet["status"] == "supported" and (
                case["expected_status"] is None or case["expected_status"] != "supported"
            ),
            "host_packet": packet, "host_trace": trace,
            "host_ms": round((time.perf_counter_ns() - started) / 1e6, 3),
            "packet_bytes": len(canonical(packet)), "trace_bytes": len(canonical(trace)),
        }


def _verify_freeze(frozen: dict, plan_path: Path, loaded: dict) -> None:
    if (frozen.get("schema") != FREEZE_SCHEMA
            or frozen.get("plan_path") != plan_path.resolve().relative_to(ROOT).as_posix()
            or frozen.get("freeze_sha256") != digest({key: value for key, value in frozen.items()
                                                      if key != "freeze_sha256"})):
        raise ValueError("Freeze integrity differs")
    for material, value in frozen["materials"].items():
        path = (ROOT / material).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or digest(path.read_bytes()) != value:
            raise ValueError("Source, plan, provider or implementation changed after freeze")
    if frozen["provider_identities"] != {key: provider.identity() for key, provider in loaded.items()}:
        raise ValueError("Provider identity changed after freeze")
    if frozen.get("runtime_versions") != _runtime_versions():
        raise ValueError("Runtime dependency versions changed after freeze")
    if frozen["model_calls"] != 36 or len(frozen["cases"]) != 36:
        raise ValueError("Frozen schedule differs from 36 calls")
    regenerated = prepare(plan_path, loaded)
    if frozen != regenerated:
        raise ValueError("Recomputed candidate schedule or prompts differ from freeze")


def _retained_response(response: ModelResponse | None, identity: dict) -> tuple[dict | None, dict | None]:
    if response is None:
        return None, None
    try:
        cost = response_cost(response, identity)
    except (TypeError, ValueError):
        cost = None
    return (
        {"text": response.text, "model": response.model, "metadata": response.metadata},
        {"input_tokens": response.input_tokens, "output_tokens": response.output_tokens,
         "cached_input_tokens": response.metadata.get("cached_input_tokens", 0),
         "model_cost_usd": cost},
    )


def _validate_completed_prefix(row: dict, index: int, case: dict, identity: dict, plan: dict) -> float:
    if (row.get("index") != index
            or row.get("case_id") != case["case_id"]
            or row.get("model_class") != case["model_class"]
            or row.get("prompt_sha256") != case["prompt_sha256"]
            or row.get("status") != "completed"
            or row.get("retry_count") != 0):
        raise ValueError("Completed ledger prefix differs from frozen call identity")
    response, usage = row.get("response"), row.get("usage")
    if (not isinstance(response, dict) or set(response) != {"text", "model", "metadata"}
            or not isinstance(response["text"], str)
            or not isinstance(response["metadata"], dict)
            or response["model"] != plan["response_model_aliases"].get(
                case["model_class"], identity["model"])
            or not isinstance(usage, dict)
            or set(usage) != {"input_tokens", "output_tokens", "cached_input_tokens",
                              "model_cost_usd"}):
        raise ValueError("Completed ledger response or usage structure differs")
    for key in ("input_tokens", "output_tokens", "cached_input_tokens"):
        if type(usage[key]) is not int or usage[key] < 0:
            raise ValueError("Completed ledger has invalid token usage")
    if usage["cached_input_tokens"] > usage["input_tokens"]:
        raise ValueError("Completed ledger cached tokens exceed input tokens")
    reported_cost = usage["model_cost_usd"]
    if (type(reported_cost) not in {int, float} or not math.isfinite(reported_cost)
            or reported_cost < 0):
        raise ValueError("Completed ledger has invalid configured cost")
    if response["metadata"].get("cached_input_tokens", 0) != usage["cached_input_tokens"]:
        raise ValueError("Completed ledger cache accounting differs from response metadata")
    recomputed = response_cost(ModelResponse(
        response["text"], usage["input_tokens"], usage["output_tokens"],
        response["model"], response["metadata"]), identity)
    if recomputed is None or not math.isclose(
            reported_cost, recomputed, rel_tol=1e-9, abs_tol=1e-12):
        raise ValueError("Completed ledger cost differs from configured token rates")
    if (not isinstance(row.get("selection"), dict) or not isinstance(row.get("route"), dict)
            or type(row.get("model_api_seconds")) not in {int, float}
            or not math.isfinite(row["model_api_seconds"])
            or row["model_api_seconds"] < 0):
        raise ValueError("Completed ledger lacks bounded result or latency")
    return recomputed


def _ledger_summary(ledger: dict, frozen: dict) -> dict:
    completed = [row for row in ledger["attempts"] if row["status"] == "completed"]
    measured = [row["usage"] for row in ledger["attempts"] if row["usage"] is not None]
    known = [usage for usage in measured if type(usage.get("model_cost_usd")) in {int, float}]
    unknown_cost_attempts = len(ledger["attempts"]) - len(known)
    by_model = {}
    for name in ("nano", "luna", "sol_high"):
        rows = [row for row in completed if row["model_class"] == name]
        by_model[name] = {
            "completed": len(rows),
            "accepted": sum(row["route"]["outcome"] == "accepted" for row in rows),
            "selection_correct": sum(bool(row["route"]["selection_correct"]) for row in rows),
            "safe_abstentions": sum(bool(row["route"].get("safe_abstention")) for row in rows),
            "false_support": sum(bool(row["route"].get("false_support")) for row in rows),
            "input_tokens": sum(row["usage"]["input_tokens"] for row in ledger["attempts"]
                                if row["model_class"] == name and row["usage"]
                                and type(row["usage"].get("input_tokens")) is int),
            "output_tokens": sum(row["usage"]["output_tokens"] for row in ledger["attempts"]
                                 if row["model_class"] == name and row["usage"]
                                 and type(row["usage"].get("output_tokens")) is int),
            "model_cost_usd": sum(row["usage"]["model_cost_usd"] for row in ledger["attempts"]
                                  if row["model_class"] == name and row["usage"]
                                  and type(row["usage"].get("model_cost_usd")) in {int, float}),
        }
    return {
        "schema": "eal2-family-selection-summary/1",
        "study_kind": "developmental_synthetic",
        "status": ledger["status"],
        "freeze_sha256": frozen["freeze_sha256"],
        "scheduled_calls": len(frozen["cases"]),
        "attempted_calls": len(ledger["attempts"]),
        "completed_calls": len(completed),
        "model_cost_usd": sum(row["model_cost_usd"] for row in known)
                          if unknown_cost_attempts == 0 else None,
        "known_model_cost_usd": sum(row["model_cost_usd"] for row in known),
        "unknown_cost_attempts": unknown_cost_attempts,
        "input_tokens": sum(row["input_tokens"] for row in measured
                            if type(row.get("input_tokens")) is int),
        "output_tokens": sum(row["output_tokens"] for row in measured
                             if type(row.get("output_tokens")) is int),
        "by_model": by_model,
        "author_review_effort": "unmeasured",
        "cost_per_correct_accepted_decision": None,
        "limits": "Single-author synthetic reference; no independent adjudication, live cluster evidence or verified model explanation.",
    }


async def execute(output: Path, *, providers: dict | None = None) -> dict:
    output = output.resolve()
    plan = load_plan(PLAN)
    loaded = providers if providers is not None else _providers(plan, PLAN)
    freeze_path, ledger_path = output / "freeze.json", output / "ledger.json"
    if not freeze_path.is_file() or not ledger_path.is_file():
        raise ValueError("Freeze and empty ledger must exist before paid execution")
    frozen = read_json(freeze_path)
    _verify_freeze(frozen, PLAN, loaded)
    ledger = read_json(ledger_path)
    if ledger.get("schema") != LEDGER_SCHEMA or ledger.get("freeze_sha256") != frozen["freeze_sha256"]:
        raise ValueError("Ledger identity differs from freeze")
    if ledger.get("status") not in {"frozen", "running", "stopped_budget", "complete"}:
        raise ValueError("Ledger is superseded or stopped and cannot be executed")
    if not isinstance(ledger.get("attempts"), list):
        raise ValueError("Attempt ledger must be a list")
    if any(row.get("status") != "completed" or row.get("usage") is None
           for row in ledger.get("attempts", [])):
        raise ValueError("Pending or failed call may have been billed; never retry silently")
    if len(ledger["attempts"]) > 36:
        raise ValueError("Ledger exceeds frozen schedule")
    spent = 0.0
    for index, row in enumerate(ledger["attempts"]):
        case = frozen["cases"][index]
        spent += _validate_completed_prefix(
            row, index, case, frozen["provider_identities"][case["model_class"]], plan)
    if ledger["status"] == "complete" and len(ledger["attempts"]) != 36:
        raise ValueError("Complete ledger has fewer calls than frozen schedule")
    for index in range(len(ledger["attempts"]), len(frozen["cases"])):
        case = frozen["cases"][index]
        name = case["model_class"]
        identity = frozen["provider_identities"][name]
        reserve = _reserve(case, identity, plan)
        if spent + reserve > plan["max_cost_usd"]:
            ledger["status"] = "stopped_budget"
            write_json(ledger_path, ledger)
            break
        row = {
            "index": index, "case_id": case["case_id"], "model_class": name,
            "prompt_sha256": case["prompt_sha256"], "status": "pending", "retry_count": 0,
            "usage": None,
        }
        ledger["attempts"].append(row)
        ledger["status"] = "running"
        write_json(ledger_path, ledger)  # Crash after this point may have incurred a charge.
        started = time.perf_counter_ns()
        response: ModelResponse | None = None
        try:
            response = await loaded[name].complete(case["messages"], plan["max_output_tokens"])
            duration = round((time.perf_counter_ns() - started) / 1e9, 3)
            cost = response_cost(response, identity)
            expected_model = plan["response_model_aliases"].get(name, identity["model"])
            if response.input_tokens is None or response.output_tokens is None or cost is None:
                raise ProviderError("Missing usage or configured cost", response=response)
            if response.model != expected_model:
                raise ProviderError("Returned model identity differs from frozen model", response=response)
            selection = _selection(response.text)
            route = _route(case, selection)
            row.update({
                "status": "completed", "model_api_seconds": duration,
                "response": {"text": response.text, "model": response.model,
                             "metadata": response.metadata},
                "usage": {
                    "input_tokens": response.input_tokens, "output_tokens": response.output_tokens,
                    "cached_input_tokens": response.metadata.get("cached_input_tokens", 0),
                    "model_cost_usd": cost,
                },
                "selection": selection, "route": route,
            })
            spent += cost
        except ProviderError as exc:
            measured = exc.response or response
            retained, usage = _retained_response(measured, identity)
            row.update({
                "status": "failed", "error": type(exc).__name__ + ": " + str(exc),
                "model_api_seconds": round((time.perf_counter_ns() - started) / 1e9, 3),
                "response": retained, "usage": usage,
            })
            ledger["status"] = "stopped_provider_failure"
        except Exception as exc:
            retained, usage = _retained_response(response, identity)
            row.update({
                "status": "failed", "error": type(exc).__name__,
                "model_api_seconds": round((time.perf_counter_ns() - started) / 1e9, 3),
                "response": retained, "usage": usage,
            })
            ledger["status"] = "stopped_host_failure" if usage and usage["model_cost_usd"] is not None else "stopped_unknown_usage"
        write_json(ledger_path, ledger)
        if row["status"] != "completed":
            break
    else:
        ledger["status"] = "complete"
        write_json(ledger_path, ledger)
    summary = _ledger_summary(ledger, frozen)
    write_json(output / "summary.json", summary)
    return summary


def freeze(output: Path, *, providers: dict | None = None) -> dict:
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Freeze requires a new empty output directory")
    frozen = prepare(PLAN, providers)
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_json(output / "freeze.json", frozen)
    write_json(output / "ledger.json", {
        "schema": LEDGER_SCHEMA, "status": "frozen",
        "freeze_sha256": frozen["freeze_sha256"], "attempts": [],
    })
    return {
        "status": "frozen", "requests": frozen["model_calls"],
        "reserved_usd": frozen["maximum_reserved_usd"],
        "cap_usd": frozen["max_cost_usd"],
        "freeze_sha256": frozen["freeze_sha256"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--freeze-only", action="store_true")
    action.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        frozen = prepare(PLAN)
        result = {
            "status": "offline_ready", "model_calls": frozen["model_calls"],
            "reserved_usd": frozen["maximum_reserved_usd"],
            "cap_usd": frozen["max_cost_usd"],
            "max_prompt_bytes_observed": max(row["prompt_bytes"] for row in frozen["cases"]),
            "model_calls_made": 0,
        }
    elif args.freeze_only:
        result = freeze(args.output)
    else:
        result = asyncio.run(execute(args.output))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
