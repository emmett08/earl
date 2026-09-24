#!/usr/bin/env python3
"""Frozen, paired recipient study with a checked host and independent checker.

This runner never retries a provider request. A developmental study may use
agent-authored synthetic fixtures; a confirmatory study additionally requires
an external adjudication record. Neither designation implies observed results.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.equal_checker import evaluate as evaluate_checker, parity_suite  # noqa: E402
from eal.artifacts import Artifact, ArtifactRegistry  # noqa: E402
from eal.providers import ModelResponse, ProviderError, load_provider, response_cost  # noqa: E402
from eal.runtime import ReasoningService, ToolRegistry, bounded_path, load_method_registry, strict_json  # noqa: E402

ARMS = ("raw", "skill", "skill_route", "eal_host", "equal_checker")
STATUSES = frozenset({"supported", "contested", "unsupported", "out_of_scope"})
PLAN_SCHEMA = "eal2-cross-model-campaign/1"
FREEZE_SCHEMA = "eal2-cross-model-freeze/1"
LEDGER_SCHEMA = "eal2-cross-model-ledger/1"


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def read_json(path: Path) -> Any:
    return strict_json(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)


def relative_file(base: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError(f"Expected a bounded relative file path: {name!r}")
    path = (base / name).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file():
        raise ValueError(f"Required file is absent or escapes the campaign: {name!r}")
    return path


def _nonnegative(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be a finite nonnegative number")
    return float(value)


def _effort(value: dict, label: str) -> dict:
    fields = {"author_hours", "review_hours", "rate_usd_per_hour", "direct_usd"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} needs explicit author/review hours, hourly rate and direct cost")
    return {key: _nonnegative(value[key], f"{label}.{key}") for key in fields}


def _cost(value: dict) -> float:
    return (value["author_hours"] + value["review_hours"]) * value["rate_usd_per_hour"] + value["direct_usd"]


def _state_costs(value: Any, label: str) -> dict | None:
    if value is None or isinstance(value, dict) and value.get("status") == "unmeasured":
        return None
    keys = {"status", "acquisition_usd", "eal_compute_usd", "checker_compute_usd"}
    if not isinstance(value, dict) or set(value) != keys or value["status"] != "measured":
        raise ValueError(f"{label} needs measured acquisition and both compute costs")
    return {key: _nonnegative(value[key], f"{label}.{key}") for key in keys - {"status"}}


def load_plan(path: Path) -> dict:
    plan = read_json(path)
    required = {"schema", "study_kind", "corpus", "skill", "conditions", "repetitions", "order_seed",
                "max_prompt_bytes", "max_output_tokens", "max_cost_usd"}
    allowed = required | {"review_attestation", "response_model_aliases"}
    if not isinstance(plan, dict) or set(plan) - allowed or not required <= set(plan) or plan["schema"] != PLAN_SCHEMA:
        raise ValueError(f"Expected {PLAN_SCHEMA} with complete settings")
    if plan["study_kind"] not in {"developmental", "confirmatory"}:
        raise ValueError("study_kind must be developmental or confirmatory")
    for key, limit in (("repetitions", 10), ("max_prompt_bytes", 128_000), ("max_output_tokens", 4096)):
        if type(plan[key]) is not int or not 1 <= plan[key] <= limit:
            raise ValueError(f"{key} must be a positive bounded integer")
    if plan["max_prompt_bytes"] < 512 or type(plan["order_seed"]) is not int:
        raise ValueError("Invalid prompt limit or ordering seed")
    if not 0 < _nonnegative(plan["max_cost_usd"], "max_cost_usd") <= 1000:
        raise ValueError("max_cost_usd must be positive and no greater than 1000")
    if plan["study_kind"] == "confirmatory" and "review_attestation" not in plan:
        raise ValueError("Confirmatory calls require an independent review attestation")
    for key in ("corpus", "skill"):
        relative_file(path.parent, plan[key])
    if not isinstance(plan["conditions"], list) or not plan["conditions"]:
        raise ValueError("At least one explicit condition is required")
    seen = set()
    for condition in plan["conditions"]:
        if (not isinstance(condition, dict) or set(condition) != {"id", "arm", "model_class", "provider"}
                or not isinstance(condition["id"], str) or not condition["id"].isascii()
                or not condition["id"].replace("_", "").replace("-", "").isalnum()
                or condition["id"] in seen or condition["arm"] not in ARMS
                or not isinstance(condition["model_class"], str) or not condition["model_class"]):
            raise ValueError("Invalid condition identity, arm or model class")
        seen.add(condition["id"])
        relative_file(path.parent, condition["provider"])
    return plan


def _corpus(path: Path) -> dict:
    data = read_json(path)
    if not isinstance(data, dict) or data.get("schema") not in {
        "eal2-cross-model-delivery/1", "eal2-artifact-live-pilot/1"
    } or not isinstance(data.get("roots"), list):
        raise ValueError("Expected a versioned cross-model or existing pilot corpus")
    roots = data["roots"]
    if not roots or len({root.get("id") for root in roots}) != len(roots):
        raise ValueError("Corpus requires distinct independent roots")
    for root in roots:
        if not all(isinstance(root.get(k), str) and root[k] for k in ("id", "brief", "claim", "source", "now")):
            raise ValueError("Every root needs a brief, named claim, source and assessment time")
        if not isinstance(root.get("context"), dict):
            raise ValueError("Every root needs an explicit context")
        relative_file(path.parent, root["source"])
        if not isinstance(root.get("states"), list) or not root["states"]:
            raise ValueError("Every root needs evidence states")
        if len({state.get("id") for state in root["states"]}) != len(root["states"]):
            raise ValueError("Evidence state IDs must be distinct within each root")
        for revision, state in enumerate(root["states"]):
            if state.get("expected") not in STATUSES or not isinstance(state.get("id"), str):
                raise ValueError("Each state requires an expected status and distinct ID")
            relative_file(path.parent, state["registry"])
            if "revision" in state and state["revision"] != revision:
                raise ValueError("Revision indices must follow the chronological state order")
    return data


def _attestation(plan: dict, base: Path, corpus: dict, corpus_bytes: bytes) -> dict | None:
    if "review_attestation" not in plan:
        return None
    path = relative_file(base, plan["review_attestation"])
    review = read_json(path)
    if (not isinstance(review, dict) or review.get("schema") != "eal2-cross-model-review/1"
            or review.get("corpus_sha256") != digest(corpus_bytes)
            or review.get("status") != "adjudicated"):
        raise ValueError("Review does not attest the exact corpus in adjudicated form")
    entries = review.get("states")
    if not isinstance(entries, list):
        raise ValueError("Review needs root/state adjudications")
    expected = {(root["id"], state["id"]): state["expected"]
                for root in corpus["roots"] for state in root["states"]}
    observed = {}
    for entry in entries:
        key = (entry.get("root_id"), entry.get("state_id"))
        reviewers = entry.get("reviewers")
        if (key in observed or key not in expected or entry.get("expected") != expected[key]
                or not isinstance(entry.get("rationale"), str) or not entry["rationale"].strip()
                or not isinstance(entry.get("scope"), str) or not entry["scope"].strip()
                or not isinstance(reviewers, list) or len(set(reviewers)) < 2
                or any(not isinstance(name, str) or not name.strip() for name in reviewers)):
            raise ValueError("Review omits independent root/state adjudication, status, scope or rationale")
        observed[key] = entry
    if set(observed) != set(expected):
        raise ValueError("Review does not cover exactly all root/state oracles")
    comparison = review.get("comparator")
    if (not isinstance(comparison, dict) or comparison.get("independent_implementation") is not True
            or not isinstance(comparison.get("reviewers"), list)
            or len(set(comparison["reviewers"])) < 2):
        raise ValueError("Independent comparator implementation review is required")
    return review


def _records(collection: dict, workspace: Path, registry: ToolRegistry) -> list[dict]:
    """The same host-acquired envelopes are shown in every unaided arm."""
    result = []
    for _, row in sorted(collection["records"].items()):
        binding = registry.bindings[row["tool"]]
        if binding.kind != "json_file":
            raise ValueError("Frozen campaign permits only fixed JSON-file evidence acquisitions")
        data = bounded_path(workspace, binding.path).read_text(encoding="utf-8")
        try:
            envelope = strict_json(data)
        except ValueError:
            envelope = {"malformed_json_text": data}
        item = {k: v for k, v in row.items() if k not in {"run_id", "collection_id", "ingested_at"}}
        item["imported_envelope"] = envelope
        result.append(item)
    return result


def _host_assessment(root: dict, state: dict, corpus_dir: Path) -> tuple[dict, list[dict], dict]:
    source = relative_file(corpus_dir, root["source"])
    registry_file = relative_file(corpus_dir, state["registry"])
    workspace = source.parent
    with tempfile.TemporaryDirectory(prefix="eal-campaign-") as temporary:
        service = ReasoningService(workspace, registry_file, Path(temporary) / "runs.sqlite3",
                                   method_registry=load_method_registry(root.get("method_factory")))
        artifact = Artifact(source.name, digest(source.read_bytes()), service.method_registry.fingerprint,
                            (root["claim"],), root["context"], root["now"])
        # This frozen study predates complete-collection recipient gating. Its
        # intentionally stale and partial states test raw evaluator parity.
        catalogue = ArtifactRegistry(service, {root["id"]: artifact},
                                     historical_evaluator=True)
        start = time.monotonic()
        if hasattr(catalogue, "assess_claim"):
            packet = catalogue.assess_claim(root["id"], root["claim"])
            finished = catalogue.finish_claim(root["id"], packet["assessment_id"], root["claim"])
            status = finished["status"]
        else:
            packet = catalogue.assess(root["id"])
            finished = catalogue.finish(root["id"], packet["assessment_id"])
            status = finished["claims"][root["claim"]]
            packet = {**packet, "claim": root["claim"], "status": status, "scope": root["context"],
                      "decisive": {"summary": "See retained assessment trace"}}
        latency = time.monotonic() - start
        assessment = service.store.get(packet["assessment_id"], kind="assessment")
        collection = service.store.get(packet["collection_id"], kind="collection")
        records = _records(collection, workspace, service.runtime.registry)
        if status != state["expected"] or packet.get("status") != status:
            raise ValueError(f"EAL differs from frozen oracle for {root['id']}/{state['id']}")
        return packet, records, {"host_seconds": latency, "assessment": assessment, "collection": collection}


def _graph_path(root: dict, corpus_dir: Path) -> Path:
    graph = root.get("graph")
    if graph is None:
        return relative_file(ROOT, f"benchmarks/equal_checker_graphs/{root['id']}.json")
    # Corpus authors use project-root-relative graph paths for independent code.
    return relative_file(ROOT if graph.startswith("benchmarks/") else corpus_dir, graph)


def _checker_evidence(root: dict, state: dict, corpus_dir: Path) -> tuple[dict, list[Path]]:
    listed = state.get("checker_evidence")
    if listed is None:
        # The historical pilot predates the comparator manifest: resolve the
        # actual fixed files in its state registry, without deriving a graph.
        source = relative_file(corpus_dir, root["source"])
        bindings = ToolRegistry.load(relative_file(corpus_dir, state["registry"])).bindings
        paths = {tool: bounded_path(source.parent, binding.path) for tool, binding in bindings.items()}
    elif isinstance(listed, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in listed.items()):
        paths = {tool: relative_file(corpus_dir, name) for tool, name in listed.items()}
    else:
        raise ValueError("checker_evidence must map named tools to independent observation files")
    return {tool: read_json(path) for tool, path in paths.items()}, list(paths.values())


def _checker_assessment(root: dict, state: dict, corpus_dir: Path) -> tuple[dict, float]:
    graph = read_json(_graph_path(root, corpus_dir))
    evidence, _ = _checker_evidence(root, state, corpus_dir)
    start = time.monotonic()
    result = evaluate_checker(graph, evidence, root["now"])
    elapsed = time.monotonic() - start
    packet = result.as_dict()
    if packet.get("claim") != root["claim"] or packet.get("status") != state["expected"]:
        raise ValueError(f"Independent checker differs from frozen oracle for {root['id']}/{state['id']}")
    return packet, elapsed


def _packet_for_recipient(packet: dict, *, checker: bool) -> dict:
    if checker:
        return {"claim": packet["claim"], "status": packet["status"], "scope": packet["scope"],
                "decisive": packet["trace"], "verification": "independent_generic_checker"}
    return {key: packet.get(key) for key in ("claim", "status", "scope", "decisive", "assessed_at", "assessment_id", "verification")}


def _messages(arm: str, root: dict, source: str, records: list[dict], skill: str,
              eal_packet: dict, checker_packet: dict, candidates: list[dict]) -> list[dict[str, str]]:
    if arm == "skill_route":
        return [{"role": "system", "content":
                 "You may request one host assessment. Select the applicable registered artefact from the candidates. "
                 "Reply with exactly {\"operation\":\"assess\",\"artifact_id\":\"...\",\"claim\":\"...\"} "
                 "or {\"operation\":\"decline\"}. The host validates identity and performs the assessment.\n"
                 "Routing skill:\n" + skill},
                {"role": "user", "content": "Task: " + root["brief"] + "\nCandidates:\n"
                 + json.dumps(candidates, sort_keys=True, ensure_ascii=False)}]
    instruction = ("Assess only the named claim from the supplied task. Reply with exactly one JSON object "
                   "containing claims (the named claim mapped to supported, contested, unsupported, "
                   "or out_of_scope) and explanation (one concise sentence). Do not invent observations.")
    prompt = f"Task: {root['brief']}\nClaim ID: {root['claim']}\n"
    if arm in {"raw", "skill"}:
        if arm == "skill":
            instruction += "\nTask skill:\n" + skill
        prompt += "Argument source:\n" + source + "\nAcquired observations:\n" + json.dumps(records, sort_keys=True, ensure_ascii=False)
    else:
        packet = _packet_for_recipient(eal_packet if arm == "eal_host" else checker_packet,
                                       checker=arm == "equal_checker")
        prompt += ("Checked assessment (the host retains this status; explanation prose is advisory):\n"
                   + json.dumps(packet, sort_keys=True, ensure_ascii=False))
    return [{"role": "system", "content": instruction}, {"role": "user", "content": prompt}]


def _materials_for_state(root: dict, state: dict, base: Path) -> dict[str, str]:
    _, evidence_paths = _checker_evidence(root, state, base)
    files = [relative_file(base, root["source"]), _graph_path(root, base),
             relative_file(base, state["registry"]), *evidence_paths]
    registry = ToolRegistry.load(files[2])
    for binding in registry.bindings.values():
        if binding.kind != "json_file":
            raise ValueError("Only immutable file-backed acquisitions can be frozen")
        files.append(bounded_path(files[0].parent, binding.path))
    for tamper in state.get("tamper", []):
        tamper_registry = relative_file(base, tamper["registry"])
        _, tamper_evidence_paths = _checker_evidence(root, tamper, base)
        files.extend([tamper_registry, *tamper_evidence_paths])
        for binding in ToolRegistry.load(tamper_registry).bindings.values():
            files.append(bounded_path(files[0].parent, binding.path))
    return {str(p): digest(p.read_bytes()) for p in files}


def prepare(plan_path: Path, providers: dict[str, Any] | None = None, *, allow_unreviewed: bool = False) -> dict:
    """Execute both checkers offline, verify parity and freeze every prompt."""
    plan_path = plan_path.resolve()
    plan = load_plan(plan_path)
    corpus_path = relative_file(plan_path.parent, plan["corpus"])
    corpus = _corpus(corpus_path)
    if plan["study_kind"] == "confirmatory" and not allow_unreviewed:
        review = _attestation(plan, plan_path.parent, corpus, corpus_path.read_bytes())
    else:
        review = None
    skill_path = relative_file(plan_path.parent, plan["skill"])
    skill = skill_path.read_text(encoding="utf-8")
    if len(skill.encode("utf-8")) > 8_192:
        raise ValueError("Recipient skill exceeds the frozen 8192-byte limit")
    identities = {}
    for condition in plan["conditions"]:
        provider = providers[condition["id"]] if providers is not None else load_provider(
            relative_file(plan_path.parent, condition["provider"]))
        identities[condition["id"]] = provider.identity()
        if not {"input_usd_per_million", "output_usd_per_million"} <= set(identities[condition["id"]].get("pricing", {})):
            raise ValueError("Every model condition requires configured input and output rates")
        if condition["model_class"] == "reasoning" and identities[condition["id"]].get("capabilities", {}).get("reasoning_effort", "none") == "none":
            raise ValueError("Reasoning-class route requires an explicit non-none reasoning effort")
    materials = {str(path): digest(path.read_bytes()) for path in (plan_path, corpus_path, skill_path)}
    for path in [*sorted((ROOT / "src" / "eal").rglob("*.py")),
                 ROOT / "scripts" / "run_cross_model_campaign.py",
                 ROOT / "scripts" / "analyse_cross_model_campaign.py"]:
        materials[str(path)] = digest(path.read_bytes())
    comparator_code = ROOT / "benchmarks" / "equal_checker.py"
    materials[str(comparator_code)] = digest(comparator_code.read_bytes())
    if review is not None:
        review_path = relative_file(plan_path.parent, plan["review_attestation"])
        materials[str(review_path)] = digest(review_path.read_bytes())
    for condition in plan["conditions"]:
        p = relative_file(plan_path.parent, condition["provider"])
        materials[str(p)] = digest(p.read_bytes())
    parity = parity_suite(corpus_path.parent)
    if (not parity["passed"] or parity["cases_total"] != sum(len(root["states"]) for root in corpus["roots"])
            or parity["tamper_total"] < 4 or parity["tamper_pass"] != parity["tamper_total"]
            or parity["manifest_sha256"] != digest(corpus_path.read_bytes())
            or parity["checker_sha256"] != materials[str(comparator_code)]):
        raise ValueError("Independent checker fixture and envelope-tamper parity gate failed")
    snapshots, variable_costs, authored_challenges = {}, {}, []
    for root in corpus["roots"]:
        for revision, state in enumerate(root["states"]):
            materials.update(_materials_for_state(root, state, corpus_path.parent))
            eal, raw, trace = _host_assessment(root, state, corpus_path.parent)
            checker, checker_seconds = _checker_assessment(root, state, corpus_path.parent)
            key = root["id"] + "/" + state["id"]
            variable_costs[key] = _state_costs(state.get("costs"), key)
            snapshots[key] = {"eal": eal, "checker": checker, "raw_records": raw,
                              "host_seconds": trace["host_seconds"], "checker_seconds": checker_seconds,
                              "revision": revision, "expected": state["expected"],
                              "assessment": trace["assessment"], "collection": trace["collection"]}
        for item in root.get("tamper", []):
            materials.update(_materials_for_state(root, item, corpus_path.parent))
            variant = {**item, "expected": item["expected"]}
            host_challenge, _, _ = _host_assessment(root, variant, corpus_path.parent)
            checker_challenge, _ = _checker_assessment(root, variant, corpus_path.parent)
            authored_challenges.append({"root_id": root["id"], "state_id": item["id"],
                                        "kind": item.get("kind"), "oracle": item["expected"],
                                        "eal": host_challenge["status"], "checker": checker_challenge["status"]})
    # Generated envelope attacks exercise only the checker. Authored challenge
    # states above execute both implementations against the same oracle.
    if review is not None:
        expected_code = review["comparator"].get("implementation_sha256")
        implementation = ROOT / "benchmarks" / "equal_checker.py"
        if expected_code != digest(implementation.read_bytes()):
            raise ValueError("Comparator implementation differs from the independently reviewed checksum")
    candidates = [{"artifact_id": root["id"], "claim": root["claim"],
                   "description": root["brief"][:360]} for root in corpus["roots"]]
    cases = []
    rng = random.Random(plan["order_seed"])
    blocks = [(root, state, repetition) for root in corpus["roots"]
              for state in root["states"] for repetition in range(plan["repetitions"])]
    rng.shuffle(blocks)
    conditions = list(plan["conditions"])
    rng.shuffle(conditions)
    for block_index, (root, state, repetition) in enumerate(blocks):
        key = root["id"] + "/" + state["id"]
        snapshot = snapshots[key]
        ordered = conditions[block_index % len(conditions):] + conditions[:block_index % len(conditions)]
        for condition in ordered:
            messages = _messages(condition["arm"], root,
                                 relative_file(corpus_path.parent, root["source"]).read_text(encoding="utf-8"),
                                 snapshot["raw_records"], skill, snapshot["eal"], snapshot["checker"], candidates)
            byte_count = len(canonical(messages))
            if byte_count > plan["max_prompt_bytes"]:
                raise ValueError(f"Prompt exceeds byte cap: {key}/{condition['id']} ({byte_count})")
            cases.append({"index": len(cases), "case_id": f"case-{len(cases):06d}",
                          "root_id": root["id"], "state_id": state["id"], "revision": snapshot["revision"],
                          "repetition": repetition, "condition_id": condition["id"], "arm": condition["arm"],
                          "claim": root["claim"], "expected": state["expected"], "messages": messages,
                          "prompt_bytes": byte_count, "prompt_sha256": digest(messages),
                          "host_status": snapshot["eal"]["status"], "checker_status": snapshot["checker"]["status"],
                          "route_packet": (_packet_for_recipient(snapshot["eal"], checker=False)
                                           if condition["arm"] == "skill_route" else None)})
    fixed_costs = {}
    for root in corpus["roots"]:
        effort = root.get("effort", corpus.get("effort"))
        if effort is None or effort.get("status") == "unmeasured":
            if plan["study_kind"] == "confirmatory" and not allow_unreviewed:
                raise ValueError("Confirmatory cost accounting needs measured root effort")
            fixed_costs[root["id"]] = None
            continue
        if effort.get("status") != "measured":
            raise ValueError("Root effort must be explicitly measured or unmeasured")
        fixed_costs[root["id"]] = {key: _cost(_effort(value, f"{root['id']}.{key}"))
                                   for key, value in effort.items() if key != "status"}
        if plan["study_kind"] == "confirmatory" and not {"common", "skill", "skill_route", "eal_host", "equal_checker"} <= set(fixed_costs[root["id"]]):
            raise ValueError("Root effort must account for each source/skill/checker and common work")
    frozen = {"schema": FREEZE_SCHEMA, "study_kind": plan["study_kind"], "plan": plan,
              "materials": materials, "provider_identities": identities, "corpus_schema": corpus["schema"],
              "review": review, "fixed_costs_by_root_usd": fixed_costs,
              "variable_costs_by_state_usd": variable_costs,
              "comparator_checks": parity, "authored_challenge_pair_parity": authored_challenges,
              "snapshots": snapshots, "cases": cases,
              "frozen_at": datetime.now(timezone.utc).isoformat(),
              "interpretation": ("Exploratory synthetic fixture exercise; selection and review may have influenced outcomes"
                                 if plan["study_kind"] == "developmental" else
                                 "Prospective reviewed synthetic study; generalisation beyond sampled roots is untested")}
    frozen["freeze_sha256"] = digest(frozen)
    return frozen


def verify_freeze(frozen: dict) -> None:
    if frozen.get("schema") != FREEZE_SCHEMA or frozen.get("freeze_sha256") != digest({k: v for k, v in frozen.items() if k != "freeze_sha256"}):
        raise ValueError("Frozen schedule or host trace was modified")
    for case in frozen["cases"]:
        if (case["prompt_sha256"] != digest(case["messages"])
                or case["prompt_bytes"] != len(canonical(case["messages"]))):
            raise ValueError("Frozen prompt differs from its digest")
        snapshot = frozen["snapshots"][case["root_id"] + "/" + case["state_id"]]
        if (case["expected"] != snapshot["expected"] or case["host_status"] != snapshot["eal"]["status"]
                or case["checker_status"] != snapshot["checker"]["status"]):
            raise ValueError("Frozen assessment and oracle links differ")


def answer(text: str, claim: str) -> dict:
    try:
        parsed = strict_json(text)
        if (not isinstance(parsed, dict) or set(parsed) != {"claims", "explanation"}
                or not isinstance(parsed["claims"], dict) or set(parsed["claims"]) != {claim}
                or parsed["claims"][claim] not in STATUSES
                or not isinstance(parsed["explanation"], str)):
            raise ValueError("Response does not have the requested claim/status/explanation shape")
        return {"status": parsed["claims"][claim], "explanation": parsed["explanation"], "format_valid": True}
    except (ValueError, TypeError) as exc:
        return {"status": None, "explanation": None, "format_valid": False, "error": str(exc)}


def _route(text: str, case: dict) -> tuple[bool, str]:
    try:
        request = strict_json(text)
        if request == {"operation": "decline"}:
            return False, "model_declined"
        if (not isinstance(request, dict) or set(request) != {"operation", "artifact_id", "claim"}
                or request["operation"] != "assess" or request["artifact_id"] != case["root_id"]
                or request["claim"] != case["claim"]):
            return False, "incorrect_or_unauthorised_request"
        return True, "accepted"
    except (ValueError, TypeError):
        return False, "malformed_request"


def _route_second_messages(case: dict, request_text: str, packet: dict) -> list[dict[str, str]]:
    return [*case["messages"], {"role": "assistant", "content": request_text},
            {"role": "user", "content": "Host assessment result (the status remains authoritative):\n"
             + json.dumps(packet, sort_keys=True, ensure_ascii=False)
             + "\nReturn one JSON object with claims mapping the named claim to the checked status "
               "and explanation as one concise sentence."}]


def _reserve(case: dict, identity: dict, max_output_tokens: int) -> float:
    rate = identity["pricing"]
    return ((case["prompt_bytes"] + 256) * rate["input_usd_per_million"]
            + max_output_tokens * rate["output_usd_per_million"]) / 1_000_000


def _route_reserve(case: dict, identity: dict, max_output_tokens: int, max_prompt_bytes: int) -> float:
    """Reserve both calls, allowing the full bounded second prompt."""
    rates = identity["pricing"]
    return _reserve(case, identity, max_output_tokens) + (
        (max_prompt_bytes + 256) * rates["input_usd_per_million"]
        + max_output_tokens * rates["output_usd_per_million"]) / 1_000_000


async def _run_route_case(case: dict, row: dict, ledger: dict, ledger_path: Path, provider: Any,
                          identity: dict, plan: dict, plan_path: Path, spent_before: float) -> float:
    """One bounded model-originated request followed by optional checked answer."""
    total_start = time.monotonic()
    row["calls"] = []
    spent = 0.0

    async def call(messages: list[dict[str, str]]) -> ModelResponse | None:
        nonlocal spent
        subcall = {"index": len(row["calls"]), "status": "pending", "prompt_sha256": digest(messages),
                   "messages": messages, "usage": None}
        row["calls"].append(subcall)
        write_json(ledger_path, ledger)
        started = time.monotonic()
        try:
            response: ModelResponse = await provider.complete(messages, plan["max_output_tokens"])
            cost = response_cost(response, identity)
            expected_model = plan.get("response_model_aliases", {}).get(case["condition_id"], identity["model"])
            if response.input_tokens is None or response.output_tokens is None or cost is None:
                raise ProviderError("Missing billed token usage or configured cost", response=response)
            if response.model != expected_model:
                raise ProviderError("Response model differs from the frozen identity", response=response)
            subcall.update(status="completed", duration_seconds=time.monotonic() - started,
                           response={"text": response.text, "model": response.model, "metadata": response.metadata},
                           usage={"input_tokens": response.input_tokens, "output_tokens": response.output_tokens,
                                  "cached_input_tokens": response.metadata.get("cached_input_tokens", 0),
                                  "model_cost_usd": cost})
            spent += cost
            write_json(ledger_path, ledger)
            return response
        except ProviderError as exc:
            measured = exc.response
            cost = response_cost(measured, identity) if measured else None
            subcall.update(status="failed", duration_seconds=time.monotonic() - started,
                           error=type(exc).__name__ + ": " + str(exc),
                           response=({"text": measured.text, "model": measured.model, "metadata": measured.metadata}
                                     if measured else None),
                           usage=({"input_tokens": measured.input_tokens, "output_tokens": measured.output_tokens,
                                   "cached_input_tokens": measured.metadata.get("cached_input_tokens", 0),
                                   "model_cost_usd": cost} if measured and cost is not None else None))
            if cost is not None:
                spent += cost
            row.update(status="failed", error=subcall["error"], duration_seconds=time.monotonic() - total_start)
            ledger["status"] = "stopped_provider_failure"
            write_json(ledger_path, ledger)
            return None
        except Exception as exc:
            subcall.update(status="failed", duration_seconds=time.monotonic() - started,
                           error=type(exc).__name__)
            row.update(status="failed", error=subcall["error"], duration_seconds=time.monotonic() - total_start)
            ledger["status"] = "stopped_unknown_usage"
            write_json(ledger_path, ledger)
            return None

    first = await call(case["messages"])
    if first is None:
        return spent
    accepted, reason = _route(first.text, case)
    row.update(route_requested=accepted, route_reason=reason, route_host_seconds=0.0)
    final = first
    if accepted:
        try:
            corpus_path = relative_file(plan_path.parent, plan["corpus"])
            corpus = _corpus(corpus_path)
            root = next(r for r in corpus["roots"] if r["id"] == case["root_id"])
            state = next(s for s in root["states"] if s["id"] == case["state_id"])
            live, _, trace = _host_assessment(root, state, corpus_path.parent)
            if live["status"] != case["host_status"]:
                raise ValueError("Routed host status changed since freeze")
            row["route_host_seconds"] = trace["host_seconds"]
            row["routed_assessment_id"] = live["assessment_id"]
            second_messages = _route_second_messages(case, first.text, _packet_for_recipient(live, checker=False))
            second_bytes = len(canonical(second_messages))
            if second_bytes > plan["max_prompt_bytes"]:
                raise ValueError("Routed second prompt exceeds frozen byte cap")
            rates = identity["pricing"]
            second_reserve = ((second_bytes + 256) * rates["input_usd_per_million"]
                              + plan["max_output_tokens"] * rates["output_usd_per_million"]) / 1_000_000
            if spent_before + spent + second_reserve > plan["max_cost_usd"]:
                row.update(status="failed", error="Budget stop before routed second call",
                           duration_seconds=time.monotonic() - total_start)
                ledger["status"] = "stopped_budget_after_route"
                write_json(ledger_path, ledger)
                return spent
            final = await call(second_messages)
            if final is None:
                return spent
        except Exception as exc:
            row.update(status="failed", error=type(exc).__name__ + ": " + str(exc),
                       duration_seconds=time.monotonic() - total_start)
            ledger["status"] = "stopped_host_failure"
            write_json(ledger_path, ledger)
            return spent
    parsed = answer(final.text, case["claim"]) if accepted else {
        "status": None, "explanation": None, "format_valid": False, "error": reason}
    authoritative = case["host_status"] if accepted else None
    calls = row["calls"]
    row.update(status="completed", duration_seconds=time.monotonic() - total_start,
               model_api_seconds=sum(x["duration_seconds"] for x in calls),
               response={"text": final.text, "model": final.model, "metadata": final.metadata},
               recipient=parsed, accepted_status=authoritative,
               recipient_contradicted_host=(parsed["status"] != authoritative if accepted else None),
               exact_status_correct=authoritative == case["expected"], false_support=False,
               usage={"input_tokens": sum(x["usage"]["input_tokens"] for x in calls),
                      "output_tokens": sum(x["usage"]["output_tokens"] for x in calls),
                      "cached_input_tokens": sum(x["usage"]["cached_input_tokens"] for x in calls),
                      "model_cost_usd": sum(x["usage"]["model_cost_usd"] for x in calls)})
    write_json(ledger_path, ledger)
    return spent


async def run(plan_path: Path, output: Path, *, freeze_only: bool = False, resume: bool = False,
              providers: dict[str, Any] | None = None) -> dict:
    plan_path, output = plan_path.resolve(), output.resolve()
    plan = load_plan(plan_path)
    loaded = providers or {c["id"]: load_provider(relative_file(plan_path.parent, c["provider"]))
                           for c in plan["conditions"]}
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    freeze_path, ledger_path = output / "freeze.json", output / "ledger.json"
    if freeze_path.exists():
        if not resume:
            raise ValueError("Existing output requires --resume")
        frozen = read_json(freeze_path)
        verify_freeze(frozen)
        for material, recorded in frozen["materials"].items():
            if digest(Path(material).read_bytes()) != recorded:
                raise ValueError("Material changed since freeze")
        if frozen["provider_identities"] != {key: p.identity() for key, p in loaded.items()}:
            raise ValueError("Provider identity changed since freeze")
    else:
        if resume:
            raise ValueError("There is no frozen study to resume")
        frozen = prepare(plan_path, loaded)
        write_json(freeze_path, frozen)
    if ledger_path.exists():
        ledger = read_json(ledger_path)
        if ledger.get("freeze_sha256") != frozen["freeze_sha256"]:
            raise ValueError("Attempt ledger refers to another frozen study")
    else:
        ledger = {"schema": LEDGER_SCHEMA, "freeze_sha256": frozen["freeze_sha256"],
                  "status": "frozen", "attempts": []}
        write_json(ledger_path, ledger)
    if freeze_only:
        return {"status": "frozen", "requests": len(frozen["cases"]), "attempts": len(ledger["attempts"]),
                "study_kind": plan["study_kind"], "freeze_sha256": frozen["freeze_sha256"]}
    if any(row.get("status") != "completed" or row.get("usage") is None for row in ledger["attempts"]):
        raise ValueError("Failed/pending call may have been billed; reconcile manually, never retry silently")
    if len(ledger["attempts"]) > len(frozen["cases"]):
        raise ValueError("Attempt count exceeds frozen schedule")
    for index, row in enumerate(ledger["attempts"]):
        case = frozen["cases"][index]
        if (row.get("index"), row.get("case_id"), row.get("prompt_sha256")) != (index, case["case_id"], case["prompt_sha256"]):
            raise ValueError("Attempt ledger differs from the frozen schedule")
    spent = sum(row["usage"]["model_cost_usd"] for row in ledger["attempts"])
    for index in range(len(ledger["attempts"]), len(frozen["cases"])):
        case = frozen["cases"][index]
        identity = frozen["provider_identities"][case["condition_id"]]
        reserve = (_route_reserve(case, identity, plan["max_output_tokens"], plan["max_prompt_bytes"])
                   if case["arm"] == "skill_route" else _reserve(case, identity, plan["max_output_tokens"]))
        if spent + reserve > plan["max_cost_usd"]:
            ledger["status"] = "stopped_budget"
            write_json(ledger_path, ledger)
            break
        row = {"index": index, "case_id": case["case_id"], "prompt_sha256": case["prompt_sha256"],
               "status": "pending", "retry_count": 0, "usage": None}
        ledger["attempts"].append(row)
        ledger["status"] = "running"
        write_json(ledger_path, ledger)  # Crash after this point may be billable.
        if case["arm"] == "skill_route":
            spent += await _run_route_case(case, row, ledger, ledger_path, loaded[case["condition_id"]],
                                           identity, plan, plan_path, spent)
            if row["status"] != "completed":
                break
            continue
        start = time.monotonic()
        try:
            result: ModelResponse = await loaded[case["condition_id"]].complete(case["messages"], plan["max_output_tokens"])
            cost = response_cost(result, identity)
            if result.input_tokens is None or result.output_tokens is None or cost is None:
                raise ProviderError("Missing billed token usage or configured cost", response=result)
            expected_model = plan.get("response_model_aliases", {}).get(case["condition_id"], identity["model"])
            if result.model != expected_model:
                raise ProviderError("Response model differs from the frozen identity", response=result)
            parsed = answer(result.text, case["claim"])
            authoritative = (case["host_status"] if case["arm"] == "eal_host" else
                             case["checker_status"] if case["arm"] == "equal_checker" else parsed["status"])
            row.update(status="completed", duration_seconds=time.monotonic() - start,
                       model_api_seconds=time.monotonic() - start,
                       response={"text": result.text, "model": result.model, "metadata": result.metadata},
                       recipient=parsed, accepted_status=authoritative,
                       recipient_contradicted_host=(parsed["status"] != authoritative if case["arm"] in {"eal_host", "equal_checker"} else None),
                       exact_status_correct=authoritative == case["expected"],
                       false_support=authoritative == "supported" and case["expected"] != "supported",
                       usage={"input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
                              "cached_input_tokens": result.metadata.get("cached_input_tokens", 0),
                              "model_cost_usd": cost})
            spent += cost
        except ProviderError as exc:
            measured = exc.response
            cost = response_cost(measured, identity) if measured else None
            row.update(status="failed", duration_seconds=time.monotonic() - start,
                       error=type(exc).__name__ + ": " + str(exc),
                       response=({"text": measured.text, "model": measured.model, "metadata": measured.metadata}
                                 if measured else None),
                       usage=({"input_tokens": measured.input_tokens, "output_tokens": measured.output_tokens,
                               "cached_input_tokens": measured.metadata.get("cached_input_tokens", 0),
                               "model_cost_usd": cost} if measured and cost is not None else None))
            ledger["status"] = "stopped_provider_failure"
        except Exception as exc:
            row.update(status="failed", duration_seconds=time.monotonic() - start,
                       error=type(exc).__name__)
            ledger["status"] = "stopped_unknown_usage"
        write_json(ledger_path, ledger)
        if row["status"] != "completed":
            break
    else:
        ledger["status"] = "complete"
        write_json(ledger_path, ledger)
    return {"status": ledger["status"], "study_kind": plan["study_kind"], "requests": len(frozen["cases"]),
            "attempts": len(ledger["attempts"]), "configured_rate_model_cost_usd": spent,
            "freeze_sha256": frozen["freeze_sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--freeze-only", action="store_true")
    parser.add_argument("--preflight", action="store_true",
                        help="Check corpus, host and comparator offline; allow pending review but forbid model calls")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        if args.resume or args.freeze_only:
            parser.error("--preflight cannot be combined with execution flags")
        provisional = prepare(args.plan, allow_unreviewed=True)
        summary = {"schema": "eal2-cross-model-preflight/1", "status": "offline_only_review_pending"
                   if provisional["study_kind"] == "confirmatory" and provisional["review"] is None else "offline_ready",
                   "model_calls": 0, "study_kind": provisional["study_kind"],
                   "requests": len(provisional["cases"]),
                   "root_count": len({c["root_id"] for c in provisional["cases"]}),
                   "comparator_checker_only_generated_attacks": {
                       k: provisional["comparator_checks"][k] for k in
                              ("passed", "parity", "cases_total", "tamper_pass", "tamper_total")},
                   "authored_eal_checker_challenge_pairs": len(provisional["authored_challenge_pair_parity"]),
                   "all_effort_measured": all(v is not None for v in provisional["fixed_costs_by_root_usd"].values()),
                   "note": "Preflight is not a frozen or authorised paid study; independent review is still required."}
        write_json(args.output / "preflight.json", summary)
        print(json.dumps(summary, sort_keys=True, allow_nan=False))
        return
    print(json.dumps(asyncio.run(run(args.plan, args.output, freeze_only=args.freeze_only, resume=args.resume)),
                     sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
