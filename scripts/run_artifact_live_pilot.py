#!/usr/bin/env python3
"""Bounded, resumable EAL artifact handoff feasibility study.

Four independent roots, three fixed evidence states and four recipient arms make
48 single-turn model requests. ``--freeze-only`` performs host assessments and
creates the exact request schedule without contacting a model endpoint. The
JSON representation is mechanically derived from the EAL AST; this isolates
recipient representation but does not test an independent JSON interpreter.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import random
import re
import tempfile
import time
from typing import Any

from eal.artifacts import Artifact, ArtifactRegistry
from eal.experiment import _code_identity
from eal.parser import parse
from eal.providers import ModelResponse, ProviderError, load_provider, response_cost
from eal.runtime import ReasoningService, ToolRegistry, bounded_path, load_method_registry, strict_json


ARMS = ("raw_eal", "raw_graph", "apply_eal", "checked_packet")
STATUSES = {"supported", "contested", "unsupported", "out_of_scope"}
GRAPH_FIELDS = ("environments", "tools", "evidence", "assumptions", "reasoning",
                "claims", "arguments", "objections", "patterns", "applications")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _without_run_identity(value: Any) -> Any:
    """Canonical host content while discarding randomly assigned collection IDs."""
    transient = {"run_id", "started_at", "ingested_at", "collection_id", "assessment_id"}
    if isinstance(value, dict):
        return {key: _without_run_identity(item) for key, item in value.items() if key not in transient}
    if isinstance(value, list):
        return [_without_run_identity(item) for item in value]
    return value


def _stable_freeze_digest(frozen: dict) -> str:
    retained = {key: value for key, value in frozen.items()
                if key not in {"cases", "host_snapshots", "freeze_digest", "stable_digest"}}
    retained["cases"] = [{"root_id": case["root_id"], "state_id": case["state_id"],
                          "arm": case["arm"], "claim": case["claim"], "expected": case["expected"],
                          "messages": case["messages"], "prompt_bytes": case["prompt_bytes"],
                          "prompt_digest": case["prompt_digest"],
                          "host": _without_run_identity(case["host"])}
                         for case in frozen["cases"]]
    retained["host_snapshots"] = _without_run_identity(frozen["host_snapshots"])
    return _digest(_canonical(retained))


def _check_frozen(frozen: dict) -> None:
    """Detect changed stored prompts, oracles, host traces and assessment links."""
    if not isinstance(frozen, dict) or len(frozen.get("cases", [])) != 48:
        raise ValueError("Frozen schedule does not contain exactly 48 requests")
    if frozen.get("stable_digest") != _stable_freeze_digest(frozen):
        raise ValueError("Frozen stable requests, oracle or host snapshot were modified")
    payload = {key: value for key, value in frozen.items() if key != "freeze_digest"}
    if frozen.get("freeze_digest") != _digest(_canonical(payload)):
        raise ValueError("Frozen complete host trace or request was modified")
    snapshots = frozen["host_snapshots"]
    for case in frozen["cases"]:
        messages = case["messages"]
        if case["prompt_digest"] != _digest(_canonical(messages)) or case["prompt_bytes"] != len(_canonical(messages)):
            raise ValueError("Stored prompt differs from its request digest")
        key = case["root_id"] + "/" + case["state_id"]
        snapshot = snapshots[key]
        packet = snapshot["packet"]
        if (case["host"]["assessment_id"] != packet["assessment_id"] or
                case["host"]["collection_id"] != packet["collection_id"] or
                case["host"]["claims"] != packet["claims"] or
                case["expected"] != packet["claims"].get(case["claim"]) or
                snapshot["assessment"].get("collection_id") != packet["collection_id"] or
                snapshot["collection"].get("source_digest") != packet["source_digest"]):
            raise ValueError("Stored host assessment, collection and oracle links differ")


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def _relative_file(base: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError("Fixture paths must be relative and remain inside the plan directory")
    path = bounded_path(base, name)
    if not path.is_file():
        raise ValueError(f"Fixture is not a regular file: {name}")
    return path


def load_plan(path: str | Path) -> dict:
    path = Path(path).resolve()
    plan = strict_json(path.read_text(encoding="utf-8"))
    if not isinstance(plan, dict) or set(plan) != {"schema", "roots"} or plan["schema"] != "eal2-artifact-live-pilot/1":
        raise ValueError("Expected a versioned artifact live pilot plan")
    roots = plan["roots"]
    if not isinstance(roots, list) or len(roots) != 4:
        raise ValueError("The bounded pilot requires exactly four independent roots")
    if len({root.get("id") for root in roots if isinstance(root, dict)}) != 4:
        raise ValueError("Root identifiers must be distinct")
    for root in roots:
        required = {"id", "brief", "source", "claim", "context", "now", "states"}
        if not isinstance(root, dict) or set(root) - (required | {"method_factory"}) or not required <= set(root):
            raise ValueError("Root has missing or unknown settings")
        if not all(isinstance(root[key], str) and root[key] for key in ("id", "brief", "claim", "now")):
            raise ValueError("Root ID, brief, claim and assessment time must be nonempty strings")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", root["id"]):
            raise ValueError("Root IDs must be valid artifact identifiers")
        if not isinstance(root["context"], dict) or len(root["brief"].encode("utf-8")) > 4096:
            raise ValueError("Root context or brief is invalid")
        if "method_factory" in root and not isinstance(root["method_factory"], str):
            raise ValueError("Method factory must be an import selector")
        _relative_file(path.parent, root["source"])
        states = root["states"]
        if not isinstance(states, list) or len(states) != 3 or len({s.get("id") for s in states if isinstance(s, dict)}) != 3:
            raise ValueError("Each root needs three distinct evidence states")
        for state in states:
            if not isinstance(state, dict) or set(state) != {"id", "registry", "expected"}:
                raise ValueError("State needs ID, registry and frozen expected status")
            if not isinstance(state["id"], str) or not state["id"] or state["expected"] not in STATUSES:
                raise ValueError("Invalid state identifier or expected status")
            _relative_file(path.parent, state["registry"])
    return plan


def _graph(source: str) -> str:
    """Render the same lowered typed declarations as an explicit JSON graph."""
    parsed = parse(source)
    data = asdict(parsed)
    value = {"schema": "EAL/2-typed-graph/1", **{key: data[key] for key in GRAPH_FIELDS}}
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _raw_records(collection: dict, workspace: Path, registry: ToolRegistry) -> list[dict]:
    """Show the full source-file observation and acquisition binding to both raw arms.

    Host-generated run IDs and ingestion timestamps are omitted so a resumed
    freeze produces byte-identical prompts. Eligibility errors remain visible,
    including the file's original value even when the host refused its binding.
    """
    records = []
    fields = ("evidence_id", "source_digest", "tool", "tool_version", "mode",
              "evidence_kind", "environment", "environment_fingerprint",
              "input_digest", "request_digest", "acquisition_request", "context", "status")
    for _, row in sorted(collection["records"].items()):
        binding = registry.bindings[row["tool"]]
        raw = bounded_path(workspace, binding.path).read_text(encoding="utf-8")
        try:
            envelope = strict_json(raw)
        except ValueError:
            envelope = {"malformed_json_bytes": raw}
        item = {key: row[key] for key in fields if key in row}
        item["imported_envelope"] = envelope
        if "error" in row:
            item["collection_error"] = row["error"]
        records.append(item)
    return records


def _messages(arm: str, brief: str, claim: str, source: str, graph: str,
              records: list[dict], checked: dict) -> list[dict[str, str]]:
    instruction = ("Assess the named claim using only this task's records. Return one JSON object "
                   "with exactly two fields: claims (an object mapping the named claim to supported, "
                   "contested, unsupported or out_of_scope) and explanation (one short sentence). "
                   "A missing or mismatched record does not establish support. Do not invent evidence.")
    if arm == "apply_eal":
        instruction += (" Apply each EAL/2 argument to its declared evidence, resolve each grounded "
                        "objection and defence at its exact target, and check scope and method result "
                        "before selecting the final claim status.")
    task = f"Task: {brief}\nClaim ID: {claim}\n"
    if arm == "checked_packet":
        task += ("Checked host assessment (the status is authoritative; your explanation is advisory):\n"
                 + json.dumps(checked, sort_keys=True, ensure_ascii=False))
    else:
        representation = source if arm != "raw_graph" else graph
        task += ("Argument representation:\n" + representation + "\nCollected records:\n"
                 + json.dumps(records, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
    return [{"role": "system", "content": instruction}, {"role": "user", "content": task}]


def _file_digests(workspace: Path, registry_path: Path, source_path: Path) -> dict[str, str]:
    registry = ToolRegistry.load(registry_path)
    if not registry.bindings or any(binding.kind != "json_file" for binding in registry.bindings.values()):
        raise ValueError("The pilot permits only fixed JSON file acquisitions")
    files = {source_path, registry_path}
    for binding in registry.bindings.values():
        target = bounded_path(workspace, binding.path)
        if not target.is_file():
            raise ValueError(f"Observation file is missing: {binding.path}")
        files.add(target)
    return {str(p.resolve()): _digest(p.read_bytes()) for p in sorted(files)}


def prepare(path: str | Path, provider_identity: dict, *, max_prompt_bytes: int = 16_000,
            max_output_tokens: int = 256, seed: int = 17,
            response_model: str | None = None) -> dict:
    """Freeze complete host and request material; make no provider call."""
    path = Path(path).resolve()
    plan = load_plan(path)
    if type(max_prompt_bytes) is not int or not 512 <= max_prompt_bytes <= 64_000:
        raise ValueError("max_prompt_bytes must be between 512 and 64000")
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 2048:
        raise ValueError("max_output_tokens must be between 1 and 2048")
    cases, snapshots, materials = [], {}, {str(path): _digest(path.read_bytes())}
    for root in plan["roots"]:
        source_path = _relative_file(path.parent, root["source"])
        if source_path.suffix != ".eal":
            raise ValueError("Registered pilot sources must have the .eal extension")
        source = source_path.read_text(encoding="utf-8")
        parsed_source = parse(source)
        graph = _graph(source)
        if root["claim"] not in parsed_source.claims:
            raise ValueError(f"Root {root['id']} selects a missing claim")
        for state in root["states"]:
            registry_path = _relative_file(path.parent, state["registry"])
            materials.update(_file_digests(source_path.parent, registry_path, source_path))
            with tempfile.TemporaryDirectory(prefix="eal-pilot-host-") as scratch:
                service = ReasoningService(source_path.parent, registry_path, Path(scratch) / "runs.sqlite3",
                                           method_registry=load_method_registry(root.get("method_factory")))
                artifact = Artifact(str(source_path.relative_to(source_path.parent)), _digest(source.encode("utf-8")),
                                    service.method_registry.fingerprint, (root["claim"],), root["context"], root["now"])
                registry = ArtifactRegistry(service, {root["id"]: artifact})
                packet = registry.assess(root["id"])
                authoritative = registry.finish(root["id"], packet["assessment_id"])
                observed = authoritative["claims"][root["claim"]]
                if observed != state["expected"]:
                    raise ValueError(f"Frozen oracle disagrees with the host for {root['id']}/{state['id']}: {observed}")
                collection = service.store.get(packet["collection_id"], kind="collection")
                assessment = service.store.get(packet["assessment_id"], kind="assessment")
                raw = _raw_records(collection, source_path.parent, service.runtime.registry)
                state_key = root["id"] + "/" + state["id"]
                snapshots[state_key] = {"packet": packet, "collection": collection,
                                        "assessment": assessment, "raw_observations": raw}
                checked = {"claims": authoritative["claims"],
                           "claim_statement": parsed_source.claims[root["claim"]].statement,
                           "context": root["context"], "source_digest": packet["source_digest"],
                           "assessed_at": packet["assessed_at"], "verification": "server_assessment"}
                for arm in ARMS:
                    messages = _messages(arm, root["brief"], root["claim"], source, graph, raw, checked)
                    size = len(_canonical(messages))
                    if size > max_prompt_bytes:
                        raise ValueError(f"Prompt exceeds {max_prompt_bytes} UTF-8 bytes: {root['id']}/{state['id']}/{arm} ({size})")
                    cases.append({"root_id": root["id"], "state_id": state["id"], "arm": arm,
                                  "claim": root["claim"], "expected": observed, "messages": messages,
                                  "prompt_bytes": size, "prompt_digest": _digest(_canonical(messages)),
                                  "host": {"claims": authoritative["claims"], "source_digest": packet["source_digest"],
                                           "method_registry_fingerprint": packet["method_registry_fingerprint"],
                                           "collection_id": packet["collection_id"], "assessment_id": packet["assessment_id"]}})
    rng = random.Random(seed)
    rng.shuffle(cases)
    if len(cases) != 48:
        raise AssertionError("Pilot plan did not produce 48 single-turn requests")
    expected_model = response_model or provider_identity.get("model")
    if not isinstance(expected_model, str) or not expected_model:
        raise ValueError("A nonempty expected response model is required")
    code = _code_identity()
    code["runner_sha256"] = _digest(Path(__file__).read_bytes())
    frozen = {"schema": "eal2-artifact-live-pilot-freeze/1", "source": str(path),
              "plan_sha256": materials[str(path)], "materials": materials, "provider_identity": provider_identity,
              "expected_response_model": expected_model,
              "code_identity": code, "host_snapshots": snapshots,
              "seed": seed, "max_prompt_bytes": max_prompt_bytes, "max_output_tokens": max_output_tokens,
              "request_count": 48, "cases": cases}
    frozen["stable_digest"] = _stable_freeze_digest(frozen)
    frozen["freeze_digest"] = _digest(_canonical(frozen))
    _check_frozen(frozen)
    return frozen


def _answer(text: str, claim: str) -> dict:
    try:
        parsed = strict_json(text)
        if not isinstance(parsed, dict) or set(parsed) != {"claims", "explanation"}:
            raise ValueError("response fields differ from required fields")
        if not isinstance(parsed["claims"], dict) or set(parsed["claims"]) != {claim}:
            raise ValueError("response did not name the exact claim")
        status = parsed["claims"][claim]
        if status not in STATUSES or not isinstance(parsed["explanation"], str):
            raise ValueError("response status or explanation is invalid")
        return {"status": status, "explanation": parsed["explanation"], "format_valid": True}
    except (ValueError, TypeError) as exc:
        return {"status": None, "explanation": None, "format_valid": False, "error": str(exc)}


def _cost_reserve(case: dict, provider_identity: dict, max_output_tokens: int, overhead_tokens: int = 256) -> float:
    """Preflight spending reserve, not a hard provider billing bound."""
    rates = provider_identity.get("pricing", {})
    if not {"input_usd_per_million", "output_usd_per_million"} <= rates.keys():
        raise ValueError("A priced provider identity is required for the spending stop")
    return ((case["prompt_bytes"] + overhead_tokens) * rates["input_usd_per_million"]
            + max_output_tokens * rates["output_usd_per_million"]) / 1_000_000


async def run(path: str | Path, output: str | Path, provider, *, freeze_only: bool = False,
              resume: bool = False, max_prompt_bytes: int = 16_000, max_output_tokens: int = 256,
              max_cost_usd: float = 0.25, seed: int = 17,
              response_model: str | None = None) -> dict:
    if not isinstance(max_cost_usd, (int, float)) or isinstance(max_cost_usd, bool) or not 0 < max_cost_usd <= 100:
        raise ValueError("max_cost_usd must be positive and at most 100")
    identity = provider.identity()
    frozen = prepare(path, identity, max_prompt_bytes=max_prompt_bytes,
                     max_output_tokens=max_output_tokens, seed=seed, response_model=response_model)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    freeze_path, trials_path = output / "freeze.json", output / "trials.json"
    if freeze_path.exists():
        if not resume:
            raise ValueError("Output already exists; select a fresh directory or --resume")
        prior = strict_json(freeze_path.read_text(encoding="utf-8"))
        _check_frozen(prior)
        if prior["stable_digest"] != frozen["stable_digest"] or prior["provider_identity"] != identity:
            raise ValueError("Frozen materials, requests or provider identity have changed")
        frozen = prior  # Preserve assessment trace IDs from the first freeze.
    else:
        if resume:
            raise ValueError("There is no frozen run to resume")
        _write(freeze_path, frozen)
    if trials_path.exists():
        trials = strict_json(trials_path.read_text(encoding="utf-8"))
        if not isinstance(trials, dict) or trials.get("freeze_digest") != frozen["freeze_digest"] or not isinstance(trials.get("attempts"), list):
            raise ValueError("Retained attempts do not match the frozen requests")
    else:
        trials = {"schema": "eal2-artifact-live-pilot-trials/1", "freeze_digest": frozen["freeze_digest"],
                  "attempts": [], "status": "frozen"}
        _write(trials_path, trials)
    if freeze_only:
        return {"status": "frozen", "requests": len(frozen["cases"]), "attempts": len(trials["attempts"]),
                "freeze_digest": frozen["freeze_digest"]}
    if any(row.get("status") != "completed" or row.get("usage") is None for row in trials["attempts"]):
        raise ValueError("An interrupted or failed request may have been billed; manual reconciliation is required")
    if len(trials["attempts"]) > len(frozen["cases"]):
        raise ValueError("Retained attempts exceed the frozen schedule")
    spent = sum(row["usage"]["model_cost_usd"] for row in trials["attempts"])
    for index in range(len(trials["attempts"]), len(frozen["cases"])):
        case = frozen["cases"][index]
        reserve = _cost_reserve(case, identity, max_output_tokens)
        if spent + reserve > max_cost_usd:
            trials["status"] = "stopped_budget"
            _write(trials_path, trials)
            break
        attempt = {"index": index, "root_id": case["root_id"], "state_id": case["state_id"],
                   "arm": case["arm"], "prompt_digest": case["prompt_digest"], "status": "pending",
                   "usage": None}
        trials["attempts"].append(attempt)
        trials["status"] = "running"
        _write(trials_path, trials)  # A crash now is unknown usage and forbids automatic retry.
        started = time.monotonic()
        try:
            response: ModelResponse = await provider.complete(case["messages"], max_output_tokens)
            actual_cost = response_cost(response, identity)
            if response.input_tokens is None or response.output_tokens is None or actual_cost is None:
                raise ProviderError("Provider returned incomplete billing usage", response=response)
            if response.model != frozen["expected_response_model"]:
                raise ProviderError("Returned model differs from the pinned provider identity", response=response)
            parsed = _answer(response.text, case["claim"])
            attempt.update(status="completed", duration_seconds=time.monotonic() - started,
                           response={"text": response.text, "model": response.model, "metadata": response.metadata},
                           recipient={**parsed, "correct": parsed["status"] == case["expected"]},
                           authoritative={"claims": case["host"]["claims"], "fixture_consistent": True,
                                          "assessment_id": case["host"]["assessment_id"]},
                           usage={"input_tokens": response.input_tokens, "output_tokens": response.output_tokens,
                                  "cached_input_tokens": response.metadata.get("cached_input_tokens", 0),
                                  "model_cost_usd": actual_cost})
            spent += actual_cost
        except ProviderError as exc:
            measured = exc.response
            known_cost = response_cost(measured, identity) if measured is not None else None
            attempt.update(status="failed", duration_seconds=time.monotonic() - started,
                           error=type(exc).__name__ + ": " + str(exc),
                           response=({"text": measured.text, "model": measured.model,
                                      "metadata": measured.metadata} if measured is not None else None),
                           usage=({"input_tokens": measured.input_tokens, "output_tokens": measured.output_tokens,
                                   "cached_input_tokens": measured.metadata.get("cached_input_tokens", 0),
                                   "model_cost_usd": known_cost} if measured is not None and known_cost is not None else None))
            if known_cost is not None:
                spent += known_cost
            trials["status"] = "stopped_provider_failure"
        except Exception as exc:
            attempt.update(status="failed", duration_seconds=time.monotonic() - started,
                           error=type(exc).__name__)
            trials["status"] = "stopped_unknown_usage"
        _write(trials_path, trials)
        if attempt["status"] != "completed":
            break
    else:
        trials["status"] = "complete"
        _write(trials_path, trials)
    return {"status": trials["status"], "requests": len(frozen["cases"]),
            "attempts": len(trials["attempts"]), "measured_cost_usd": spent,
            "budget_note": "The byte-based preflight reserve is not a hard invoice limit; actual token usage is checked after each call.",
            "freeze_digest": frozen["freeze_digest"]}


def verify(path: str | Path, output: str | Path, provider, *, max_prompt_bytes: int = 16_000,
           max_output_tokens: int = 256, seed: int = 17,
           response_model: str | None = None) -> dict:
    """Recheck all material/request identities and retained attempts without model access."""
    output = Path(output).resolve()
    frozen = strict_json((output / "freeze.json").read_text(encoding="utf-8"))
    computed = prepare(path, provider.identity(), max_prompt_bytes=max_prompt_bytes,
                       max_output_tokens=max_output_tokens, seed=seed, response_model=response_model)
    _check_frozen(frozen)
    if (frozen.get("stable_digest") != computed["stable_digest"] or
            frozen.get("materials") != computed["materials"] or
            frozen.get("code_identity") != computed["code_identity"]):
        raise ValueError("Frozen materials or requests changed")
    trials = strict_json((output / "trials.json").read_text(encoding="utf-8"))
    if trials.get("freeze_digest") != frozen["freeze_digest"] or not isinstance(trials.get("attempts"), list):
        raise ValueError("Trial ledger differs from frozen requests")
    if len(trials["attempts"]) > 48:
        raise ValueError("Trial ledger exceeds scheduled requests")
    spent = 0.0
    for index, row in enumerate(trials["attempts"]):
        case = frozen["cases"][index]
        if (row.get("index"), row.get("root_id"), row.get("state_id"), row.get("arm"), row.get("prompt_digest")) != (
                index, case["root_id"], case["state_id"], case["arm"], case["prompt_digest"]):
            raise ValueError("Retained attempt differs from scheduled request")
        usage = row.get("usage")
        if usage is not None:
            cost = usage.get("model_cost_usd")
            if not isinstance(cost, (int, float)) or isinstance(cost, bool) or cost < 0:
                raise ValueError("Retained usage cost is invalid")
            spent += cost
    return {"status": "verified", "requests": 48, "attempts": len(trials["attempts"]),
            "unknown_usage_attempts": sum(row.get("usage") is None for row in trials["attempts"]),
            "measured_cost_usd": spent, "freeze_digest": frozen["freeze_digest"]}


def preflight_summary(path: str | Path, *, max_prompt_bytes: int = 16_000,
                      max_output_tokens: int = 256) -> dict:
    """Deterministic, portable host fixture summary without a model or credential."""
    identity = {"provider": "offline-preflight", "adapter": "none", "model": "none", "pricing": {}}
    freeze = prepare(path, identity, max_prompt_bytes=max_prompt_bytes,
                     max_output_tokens=max_output_tokens)
    path = Path(path).resolve()
    plan = load_plan(path)
    sources = {root["id"]: {"path": root["source"],
                             "sha256": _digest(_relative_file(path.parent, root["source"]).read_bytes())}
               for root in plan["roots"]}
    states = [{"root": case["root_id"], "state": case["state_id"],
               "claim": case["claim"], "status": case["expected"],
               "method_registry_fingerprint": case["host"]["method_registry_fingerprint"]}
              for case in freeze["cases"] if case["arm"] == ARMS[0]]
    states.sort(key=lambda row: (row["root"], row["state"]))
    byte_stats = {}
    for arm in ARMS:
        counts = [case["prompt_bytes"] for case in freeze["cases"] if case["arm"] == arm]
        byte_stats[arm] = {"requests": len(counts), "min": min(counts), "max": max(counts),
                           "sum": sum(counts)}
    portable_schedule = [{"root": case["root_id"], "state": case["state_id"],
                          "arm": case["arm"], "prompt_sha256": case["prompt_digest"],
                          "expected": case["expected"],
                          "method_registry_fingerprint": case["host"]["method_registry_fingerprint"]}
                         for case in freeze["cases"]]
    return {"schema": "eal2-artifact-preflight/1", "status": "deterministic_host_preflight",
            "model_calls": 0, "root_count": 4, "state_count": 12, "planned_request_count": 48,
            "manifest_sha256": _digest(path.read_bytes()), "sources": sources, "states": states,
            "prompt_utf8_bytes": byte_stats, "code_source_digest": freeze["code_identity"]["source_digest"],
            "runner_sha256": freeze["code_identity"]["runner_sha256"],
            "portable_schedule_digest": _digest(_canonical(portable_schedule)),
            "interpretation": "Synthetic fixture and request construction check; no model accuracy, token, latency or EAL-specific superiority result."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path, nargs="?", help="Run directory; omit for --preflight-summary")
    parser.add_argument("--provider", type=Path, help="TOML [provider] file; key is read only from its named environment variable")
    parser.add_argument("--freeze-only", action="store_true", help="Assess fixtures and freeze requests without API calls")
    parser.add_argument("--verify", action="store_true", help="Recheck frozen materials and trial ledger without API calls")
    parser.add_argument("--preflight-summary", type=Path, help="Write deterministic fixture/byte summary without a provider")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--response-model", help="Exact returned model identity when the requested model is an alias")
    parser.add_argument("--max-prompt-bytes", type=int, default=16_000)
    parser.add_argument("--max-output-tokens", type=int, default=256)
    parser.add_argument("--max-cost-usd", type=float, default=0.25)
    args = parser.parse_args()
    if args.preflight_summary:
        if args.provider or args.freeze_only or args.verify or args.resume or args.response_model:
            parser.error("--preflight-summary cannot be combined with provider or run options")
        summary = preflight_summary(args.plan, max_prompt_bytes=args.max_prompt_bytes,
                                    max_output_tokens=args.max_output_tokens)
        _write(args.preflight_summary, summary)
        print(json.dumps({"status": summary["status"], "output": str(args.preflight_summary),
                          "planned_request_count": 48}, sort_keys=True))
        return
    if args.provider is None:
        parser.error("--provider is required to pin provider identity, including for --freeze-only")
    if args.output is None:
        parser.error("output directory is required for --freeze-only, --verify and live runs")
    if args.verify and (args.resume or args.freeze_only):
        parser.error("--verify cannot be combined with --resume or --freeze-only")
    provider = load_provider(args.provider)
    if args.verify:
        result = verify(args.plan, args.output, provider, max_prompt_bytes=args.max_prompt_bytes,
                        max_output_tokens=args.max_output_tokens, response_model=args.response_model)
    else:
        result = asyncio.run(run(args.plan, args.output, provider, freeze_only=args.freeze_only,
                                 resume=args.resume, max_prompt_bytes=args.max_prompt_bytes,
                                 max_output_tokens=args.max_output_tokens, max_cost_usd=args.max_cost_usd,
                                 response_model=args.response_model))
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
