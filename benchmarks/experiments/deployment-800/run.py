#!/usr/bin/env python3
"""Frozen 800-assignment synthetic deployment pilot with fail-closed ledger.

The base design's three delivery modes are direct, host-preassessed and an
actual native function request. Native request ends in a host-owned answer
after one billed model call. Author stages are linked; recipient sessions are
isolated. This is not a confirmatory human-developer investigation.
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

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from local_equal_checker import evaluate, parity_suite, validate_graph  # noqa: E402
from eal.providers import ModelResponse, ProviderError, load_provider, response_cost  # noqa: E402
from eal.runtime import ReasoningService, strict_json  # noqa: E402
from scripts.run_cross_model_campaign import (  # noqa: E402
    _checker_evidence, _host_assessment, _packet_for_recipient,
    answer, canonical, digest, read_json, write_json,
)

PLAN = HERE / "plan.json"
FREEZE_SCHEMA = "eal2-deployment-800-freeze/1"
LEDGER_SCHEMA = "eal2-deployment-800-ledger/1"
FORMATS = ("eal", "graph")
STATES = ("initial", "adverse", "restored")
STATUS = frozenset(("supported", "contested", "unsupported", "out_of_scope"))


def _materials(plan: dict, manifest: dict) -> dict[str, str]:
    paths = [HERE / "plan.json", HERE / plan["corpus"], HERE / "capability-probe.json",
             HERE / "generate_inputs.py",
             HERE / "run.py", HERE / "analyse.py", HERE / "effort-log.template.json",
             HERE / "local_equal_checker.py", ROOT / "benchmarks/equal_checker.py",
             ROOT / "src/eal/providers.py", ROOT / "scripts/run_cross_model_campaign.py"]
    paths += [HERE / p for p in plan["providers"].values()]
    paths += sorted((ROOT / "src/eal").rglob("*.py"))
    for root in manifest["roots"]:
        paths += [HERE / root["source"], HERE / root["graph"]]
        for state in root["states"]:
            paths += [HERE / state["registry"]]
            paths += [HERE / p for p in state["checker_evidence"].values()]
    review = HERE / plan["review_attestation"]
    if review.exists():
        paths.append(review)
    return {str(path.resolve()): digest(path.read_bytes()) for path in paths}


def _load() -> tuple[dict, dict, dict]:
    plan = read_json(PLAN)
    manifest = read_json(HERE / plan["corpus"])
    if (plan.get("schema") != "eal2-deployment-800-plan/1"
            or manifest.get("schema") != "eal2-deployment-800-corpus/1"
            or len(manifest.get("roots", [])) != 8
            or len({r["id"] for r in manifest["roots"]}) != 8):
        raise ValueError("Wrong plan/corpus schema or eight-root requirement")
    for root in manifest["roots"]:
        if [s["id"] for s in root["states"]] != list(STATES):
            raise ValueError("Root lacks the fixed three-state sequence")
    providers = {key: load_provider((HERE / filename).resolve())
                 for key, filename in plan["providers"].items()}
    if set(providers) != {"nano", "luna", "sol"}:
        raise ValueError("The three recipient/author identities have changed")
    for key, provider in providers.items():
        identity = provider.identity()
        if key != "nano" and (not identity["capabilities"]["native_tools"]
                              or not hasattr(provider, "complete_request")):
            raise ValueError("Native tool mode requires a real configured provider interface")
        if key == "nano" and identity["capabilities"]["native_tools"]:
            raise ValueError("Nano must not silently gain a third native mode")
    return plan, manifest, providers


def _review(plan: dict, manifest: dict, *, allow_pending: bool) -> dict | None:
    path = HERE / plan["review_attestation"]
    if not path.exists():
        if allow_pending:
            return None
        raise ValueError("Independent AI review record is required before paid calls")
    review = read_json(path)
    if (review.get("schema") != "eal2-deployment-800-review/1"
            or review.get("corpus_sha256") != digest((HERE / plan["corpus"]).read_bytes())
            or review.get("comparator_sha256") != digest((HERE / "local_equal_checker.py").read_bytes())
            or review.get("status") != "accepted_developmental"):
        raise ValueError("Review does not bind accepted synthetic corpus and comparator")
    expected = {(r["id"], s["id"]): s["expected"]
                for r in manifest["roots"] for s in r["states"]}
    received = {}
    for item in review.get("states", []):
        key = (item.get("root_id"), item.get("state_id"))
        reviewers = item.get("reviewers")
        if (key not in expected or key in received or item.get("expected") != expected[key]
                or not isinstance(reviewers, list) or len(set(reviewers)) < 2
                or any(not isinstance(name, str) or not name for name in reviewers)
                or not isinstance(item.get("rationale"), str) or not item["rationale"].strip()):
            raise ValueError("A root/state lacks two distinct reasoned independent AI reviews")
        received[key] = item
    if set(received) != set(expected) or review.get("reviewer_type") != "independent_ai_agents_unmasked_to_labels":
        raise ValueError("Developmental synthetic review must cover exactly 24 states and disclose unmasked agent reviewers")
    return review


def _direct_messages(root: dict, state: dict, fmt: str, instructed: bool,
                     delivery: str, eal_packet: dict, graph_packet: dict, records: list[dict]) -> list[dict]:
    system = ("Answer exactly one JSON object with claims mapping the named claim to supported, "
              "contested, unsupported or out_of_scope, and explanation as one concise sentence. "
              "Use only the specified claim and submitted observations.")
    if instructed:
        system += (" Verify asset, trial, collector, age, every positive condition, the specific "
                   "alert, and a separately matched answer before selecting the status.")
    prompt = f"Task: {root['brief']}\nClaim: {root['claim']}\n"
    if delivery == "direct":
        raw = (HERE / (root["source"] if fmt == "eal" else root["graph"])).read_text(encoding="utf-8")
        prompt += ("EAL/2 source" if fmt == "eal" else "Generic argument graph") + ":\n" + raw
        prompt += "\nAcquired observations:\n" + json.dumps(records, ensure_ascii=False, sort_keys=True)
    elif delivery == "host_owned":
        packet = _packet_for_recipient(eal_packet if fmt == "eal" else graph_packet,
                                       checker=fmt == "graph")
        prompt += ("Checked assessment from EAL/2 host" if fmt == "eal"
                   else "Checked assessment from equal generic-graph host")
        prompt += "; the host owns the final status:\n" + json.dumps(packet, ensure_ascii=False, sort_keys=True)
    elif delivery == "native_request":
        system = ("Request exactly one registered host operation using the supplied native function. "
                  "Use the exact root ID, claim and scope; the host will own the final status.")
        if instructed:
            system += " Check that task identity, claim and scope match before the request."
        prompt += ("Available registered " + ("EAL/2 artefact" if fmt == "eal" else "generic graph")
                   + ": " + json.dumps({"id": root["id"], "claim": root["claim"],
                                       "scope": root["context"]}, sort_keys=True))
    else:
        raise ValueError("Unknown delivery mode")
    return [{"role": "system", "content": system}, {"role": "user", "content": prompt}]


def _author_instruction(fmt: str) -> str:
    if fmt == "eal":
        return ("Return exactly JSON {\"source\":\"complete EAL/2 source\"}. Use language \"EAL/2\"; "
                "an environment with exact asset/trial requirements; declared deterministic tools; "
                "structured/1 reasoning; claim and argument; evidence with max_age 900 and "
                "value requirements; objections targeting an argument and, if applicable, another "
                "objection. Retain the exact named claim. Do not write Python or executable commands.")
    return ("Return exactly JSON {\"graph\":{...}} under generic-argument-graph/1. Include "
            "id, named claim, typed exact scope, evidence acquisition contracts with tool_version, "
            "mode, max_age_seconds, positive routes and objections with optional answers. "
            "Each predicate uses eq/lte/gte on a record and value path. Do not include an answer label.")


def _author_user(root: dict, turn: int, fmt: str) -> str:
    records = {s["id"]: {name: read_json(HERE / p)["value"]
                          for name, p in s["checker_evidence"].items()}
               for s in root["states"]}
    initial = root["brief"].split(" A current '", 1)[0]
    if turn == 0:
        task = (f"Draft a complete candidate for the initially known positive test. {initial}. "
                f"Root ID: {root['id']}; claim: {root['claim']}; scope: {root['context']}; "
                f"current submitted record: {records['initial']}. "
                "All acquisition records are synthetic and separately scoped to the current trial.")
    elif turn == 1:
        task = ("A new monitoring alert arrived. Revise the entire previous candidate to handle "
                "this specific adverse finding, without losing the positive evidence rules. "
                f"Full task: {root['brief']} Current submitted records: {records['adverse']}.")
    else:
        task = ("A separately acquired result now addresses the alert. Revise the entire previous "
                "candidate to accept only that exact matching resolution, retaining the open-alert "
                f"outcome if it is absent. Full task: {root['brief']} Current submitted records: "
                f"{records['restored']}.")
    return task + "\n" + _author_instruction(fmt)


def _recipient_messages(root: dict, packet: dict, fmt: str) -> list[dict]:
    return [{"role": "system", "content":
             "You are an isolated recipient of a candidate author artifact. Answer with exactly "
             "one JSON object with claims mapping the named claim to supported, contested, "
             "unsupported or out_of_scope and explanation as one sentence. A checked packet's "
             "status belongs to the host; describe its qualification without inventing observations."},
            {"role": "user", "content":
             f"Task: {root['brief']}\nClaim: {root['claim']}\nCandidate format: {fmt}\n"
             "Host packet (unavailable means authoring failed and no status may be accepted):\n"
             + json.dumps(packet, sort_keys=True, ensure_ascii=False)}]


def _native_operation(root: dict, fmt: str) -> list[dict]:
    name = "eal_assess_artifact" if fmt == "eal" else "generic_assess_graph"
    return [{"operation": name, "description": "Assess one pinned claim and scope; host owns final status",
             "input_schema": {"type": "object", "properties": {
                 "operation": {"type": "string", "const": name},
                 "artifact_id": {"type": "string", "enum": [root["id"]]},
                 "claim": {"type": "string", "enum": [root["claim"]]},
                 "asset": {"type": "string", "enum": [root["context"]["asset"]]},
                 "trial": {"type": "string", "enum": [root["context"]["trial"]]}},
                 "required": ["operation", "artifact_id", "claim", "asset", "trial"],
                 "additionalProperties": False}}]


def _graph_assessment(root: dict, state: dict) -> dict:
    graph = read_json(HERE / root["graph"])
    evidence, _ = _checker_evidence(root, state, HERE)
    checked = evaluate(graph, evidence, root["now"])
    if checked.claim != root["claim"] or checked.status != state["expected"]:
        raise ValueError("The independent targeted-route checker differs from the candidate reference")
    return checked.as_dict()


def _schedule(plan: dict, manifest: dict, snapshots: dict) -> list[dict]:
    rng = random.Random(plan["order_seed"])
    stage1 = []
    for root_index, root in enumerate(manifest["roots"]):
        for state_index, state in enumerate(root["states"]):
            snap = snapshots[root["id"] + "/" + state["id"]]
            for fmt in FORMATS:
                for instructed in (False, True):
                    # The historical text incorrectly multiplied all four
                    # format×instruction cells into 384. A1 assigns two
                    # complementary cells in each root/state block, with
                    # 12 appearances per cell across 24 blocks.
                    pair_is_matched = (fmt == "eal") == instructed
                    if pair_is_matched != bool((root_index * 3 + state_index) % 2):
                        continue
                    for model in ("nano", "luna", "sol"):
                        modes = ("direct", "host_owned") if model == "nano" else (
                            "direct", "host_owned", "native_request")
                        for delivery in modes:
                            messages = _direct_messages(root, state, fmt, instructed, delivery,
                                                        snap["eal"], snap["graph"], snap["records"])
                            stage1.append({"stage": "fixed", "root_id": root["id"],
                                           "state_id": state["id"], "format": fmt,
                                           "instruction": instructed, "delivery": delivery,
                                           "model": model, "messages": messages,
                                           "expected": state["expected"]})
    rng.shuffle(stage1)
    author = []
    for root in manifest["roots"]:
        for fmt in FORMATS:
            for model in ("luna", "sol"):
                group = f"{root['id']}/{fmt}/{model}"
                for turn, state in enumerate(STATES):
                    author.append({"stage": "author", "root_id": root["id"],
                                   "state_id": state, "format": fmt, "model": model,
                                   "author_group": group, "turn": turn,
                                   "user_prompt": _author_user(root, turn, fmt)})
    recipients = []
    # Each group's ten independent sessions use 4/3/3 states and 4/3/3 model
    # classes. Rotate class assignment by group to reduce imbalance by state.
    state_assignment = ["initial"] * 4 + ["adverse"] * 3 + ["restored"] * 3
    model_assignment = ["nano", "luna", "sol"] * 3 + ["nano"]
    for root in manifest["roots"]:
        for fmt in FORMATS:
            for model in ("luna", "sol"):
                group = f"{root['id']}/{fmt}/{model}"
                offset = len(recipients) // 10 % 3
                for n, state in enumerate(state_assignment):
                    recipient_model = model_assignment[(n + offset) % 10]
                    recipients.append({"stage": "recipient", "root_id": root["id"],
                                       "state_id": state, "format": fmt,
                                       "author_group": group, "recipient_index": n,
                                       "model": recipient_model, "expected":
                                       next(s["expected"] for s in root["states"] if s["id"] == state)})
    if (len(stage1), len(author), len(recipients)) != (384, 96, 320):
        raise AssertionError(f"Registered 800-call allocation changed: {len(stage1)}, {len(author)}, {len(recipients)}")
    cases = stage1 + author + recipients
    for index, case in enumerate(cases):
        case["index"] = index
        case["case_id"] = f"deployment-{index:04d}"
    return cases


def prepare(*, allow_pending_review: bool = False) -> dict:
    plan, manifest, providers = _load()
    review = _review(plan, manifest, allow_pending=allow_pending_review)
    probe = read_json(HERE / "capability-probe.json")
    if (probe.get("schema") != "eal2-deployment-800-capability-probe/1"
            or probe.get("status") != "passed" or probe.get("credential_retained") is not False
            or probe.get("native_operation_sha256") != digest(_native_operation(manifest["roots"][0], "eal"))):
        raise ValueError("Actual native capability probe is absent or mismatched")
    for name, provider in providers.items():
        record = probe.get(name, {})
        expected = plan["response_model_aliases"].get(name, provider.identity()["model"])
        if (record.get("configuration_sha256") != digest((HERE / plan["providers"][name]).read_bytes())
                or record.get("returned_model") != expected
                or (name != "nano" and (record.get("interface") != "native_single_function"
                                        or record.get("exact_root_claim_scope_request") is not True))):
            raise ValueError("Pinned product/operation capability probe changed")
    parity = parity_suite(HERE, HERE / "graphs")
    if (parity["cases_total"] != 24 or parity["parity"] != 24
            or parity["tamper_total"] != 120 or parity["tamper_pass"] != 120):
        raise ValueError("Independent comparator parity or envelope challenge failed")
    snapshots = {}
    for root in manifest["roots"]:
        for state in root["states"]:
            eal, records, _ = _host_assessment(root, state, HERE)
            graph = _graph_assessment(root, state)
            snapshots[root["id"] + "/" + state["id"]] = {
                "eal": eal, "graph": graph, "records": records, "expected": state["expected"]}
    cases = _schedule(plan, manifest, snapshots)
    max_prompt = plan["max_prompt_bytes"]
    for case in cases:
        if case["stage"] == "fixed" and len(canonical(case["messages"])) > max_prompt:
            raise ValueError(f"Fixed prompt exceeds cap: {case['case_id']}")
        if case["stage"] == "author" and len(case["user_prompt"].encode()) > max_prompt // 2:
            raise ValueError("Author user turn exceeds half the context byte cap")
    identities = {name: provider.identity() for name, provider in providers.items()}
    # Conservative reserve counts full maximum prompt bytes for dynamic turns;
    # actual configured-rate spend is calculated from provider-reported usage.
    reserve = 0.0
    for case in cases:
        rate = identities[case["model"]]["pricing"]
        cap = plan["max_output_tokens"]["author" if case["stage"] == "author" else "recipient"]
        reserve += ((2 * max_prompt) * plan["cache_write_reserve_multiplier"] * rate["input_usd_per_million"]
                    + cap * rate["output_usd_per_million"]) / 1_000_000
    if reserve > plan["max_cost_usd"]:
        raise ValueError(f"Conservative reserved cost {reserve:.4f} exceeds cap")
    frozen = {"schema": FREEZE_SCHEMA, "plan": plan, "cases": cases,
            "review_status": (review["status"] if review else "pending_independent_ai_review_unmasked"),
              "materials": _materials(plan, manifest), "provider_identities": identities,
              "parity": {key: parity[key] for key in ("parity", "cases_total", "tamper_pass", "tamper_total")},
              "conservative_reserve_usd": round(reserve, 6),
              "created_at": datetime.now(timezone.utc).isoformat()}
    frozen["freeze_sha256"] = digest(frozen)
    return frozen


def _author_messages(case: dict, ledger: dict, cases: list[dict]) -> list[dict]:
    previous = [c for c in cases if c.get("author_group") == case["author_group"]
                and c["stage"] == "author" and c["turn"] < case["turn"]]
    messages = [{"role": "system", "content":
                 "Author a complete candidate from the evolving synthetic brief. Your successive "
                 "outputs are linked and will be checked without hidden repairs. Return only the "
                 "requested JSON object; never assert physical truth from a synthetic record."}]
    for prior in [*previous, case]:
        messages.append({"role": "user", "content": prior["user_prompt"]})
        if prior is not case:
            result = ledger["attempts"].get(prior["case_id"])
            if not result or result["status"] != "completed":
                raise ValueError("Author revision cannot start before its own prior response")
            messages.append({"role": "assistant", "content": result["response"]["text"]})
    return messages


def _candidate(text: str, fmt: str) -> tuple[Any | None, str | None]:
    try:
        parsed = strict_json(text)
        field = "source" if fmt == "eal" else "graph"
        if not isinstance(parsed, dict) or set(parsed) != {field}:
            raise ValueError("Candidate has the wrong one-field wrapper")
        value = parsed[field]
        if fmt == "eal" and (not isinstance(value, str) or not 0 < len(value.encode()) <= 16_384):
            raise ValueError("EAL source exceeds cap or is not text")
        if fmt == "graph":
            if len(canonical(value)) > 16_384:
                raise ValueError("Graph exceeds the byte cap")
            validate_graph(value)
        return value, None
    except (ValueError, TypeError, KeyError) as exc:
        return None, type(exc).__name__ + ": " + str(exc)


def _candidate_packet(root: dict, state: dict, fmt: str, value: Any) -> dict:
    if value is None:
        return {"claim": root["claim"], "status": "unavailable", "reason": "invalid authored candidate"}
    try:
        if fmt == "graph":
            if (value["id"] != root["id"] or value["claim"] != root["claim"]
                    or any(value["scope"].get(key, {}).get("equals") != val
                           for key, val in root["context"].items())):
                raise ValueError("Authored graph changed root, claim or exact scope")
            evidence, _ = _checker_evidence(root, state, HERE)
            result = evaluate(value, evidence, root["now"])
            return {"claim": root["claim"], "status": result.status,
                    "scope": result.scope, "decisive": result.trace}
        workspace = (HERE / root["source"]).parent
        with tempfile.TemporaryDirectory(prefix="eal800-authored-") as temp:
            service = ReasoningService(workspace, HERE / state["registry"],
                                       Path(temp) / "runs.sqlite3")
            validation = service.validate(value)
            if not validation["valid"]:
                raise ValueError("Authored source failed syntax or binding validation")
            collection = service.collect(value, root["context"])
            result = service.reason(value, root["context"], collection["collection_id"], root["now"])
            if root["claim"] not in result["claims"]:
                raise ValueError("Authored source omitted the selected claim")
            return {"claim": root["claim"], "status": result["claims"][root["claim"]]["status"],
                    "scope": root["context"], "decisive": result["claims"][root["claim"]]}
    except (ValueError, KeyError, TypeError, OSError) as exc:
        return {"claim": root["claim"], "status": "unavailable",
                "reason": type(exc).__name__ + ": " + str(exc)[:200]}


def _prompt(case: dict, ledger: dict, cases: list[dict], manifest: dict, snapshots: dict) -> tuple[list[dict], dict | None]:
    if case["stage"] == "fixed":
        return case["messages"], None
    if case["stage"] == "author":
        return _author_messages(case, ledger, cases), None
    root = next(root for root in manifest["roots"] if root["id"] == case["root_id"])
    state = next(state for state in root["states"] if state["id"] == case["state_id"])
    parent = [c for c in cases if c["stage"] == "author"
              and c.get("author_group") == case["author_group"] and c["turn"] == 2][0]
    author = ledger["attempts"].get(parent["case_id"])
    if not author or author["status"] != "completed":
        raise ValueError("Recipient cannot start without the assigned author's final revision")
    value, error = _candidate(author["response"]["text"], case["format"])
    packet = _candidate_packet(root, state, case["format"], value)
    packet["candidate_error"] = error
    return _recipient_messages(root, packet, case["format"]), packet


def _audit_existing(frozen: dict, ledger: dict) -> None:
    if ledger.get("schema") != LEDGER_SCHEMA or ledger.get("freeze_sha256") != frozen["freeze_sha256"]:
        raise ValueError("Ledger belongs to another freeze")
    assigned = {case["case_id"]: case for case in frozen["cases"]}
    for key, row in ledger["attempts"].items():
        if (key not in assigned or row.get("case_id") != key
                or row.get("index") != assigned[key]["index"]
                or row.get("status") != "completed" or row.get("usage") is None
                or row.get("prompt_sha256") != digest(row.get("messages"))):
            raise ValueError("Unresolved/altered possibly billed attempt; never silently retry")


async def run(out: Path, *, resume: bool = False, freeze_only: bool = False) -> dict:
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    freeze_path, ledger_path = out / "freeze.json", out / "ledger.json"
    if freeze_path.exists():
        if not resume:
            raise ValueError("Existing freeze requires --resume")
        frozen = read_json(freeze_path)
        if frozen.get("freeze_sha256") != digest({k: v for k, v in frozen.items() if k != "freeze_sha256"}):
            raise ValueError("Freeze digest changed")
        for path, hash_value in frozen["materials"].items():
            if digest(Path(path).read_bytes()) != hash_value:
                raise ValueError("Source, fixture, code, review or provider material drift")
    else:
        if resume:
            raise ValueError("No freeze exists")
        frozen = prepare()
        write_json(freeze_path, frozen)
    plan, manifest, providers = _load()
    if frozen["provider_identities"] != {key: p.identity() for key, p in providers.items()}:
        raise ValueError("Provider identity changed since freeze")
    ledger = read_json(ledger_path) if ledger_path.exists() else {
        "schema": LEDGER_SCHEMA, "freeze_sha256": frozen["freeze_sha256"],
        "status": "frozen", "attempts": {}, "failures": []}
    if not ledger_path.exists():
        write_json(ledger_path, ledger)
    _audit_existing(frozen, ledger)
    if freeze_only:
        return {"status": "frozen", "assigned": len(frozen["cases"]),
                "reserve_usd": frozen["conservative_reserve_usd"], "attempted": 0}
    cases = frozen["cases"]
    snapshots = {}
    for root in manifest["roots"]:
        for state in root["states"]:
            eal, records, _ = _host_assessment(root, state, HERE)
            graph = _graph_assessment(root, state)
            snapshots[root["id"] + "/" + state["id"]] = {"eal": eal, "graph": graph, "records": records}
    root_by_id = {r["id"]: r for r in manifest["roots"]}
    lock = asyncio.Lock()
    spent = sum(row["usage"]["model_cost_usd"] for row in ledger["attempts"].values())

    async def one(case: dict) -> bool:
        nonlocal spent
        if case["case_id"] in ledger["attempts"]:
            return True
        identity = frozen["provider_identities"][case["model"]]
        messages, packet = _prompt(case, ledger, cases, manifest, snapshots)
        prompt_bytes = len(canonical(messages))
        if prompt_bytes > plan["max_prompt_bytes"]:
            raise ValueError(f"Dynamic prompt exceeds cap: {case['case_id']}")
        rates = identity["pricing"]
        output_cap = plan["max_output_tokens"]["author" if case["stage"] == "author" else "recipient"]
        reserve = ((2 * plan["max_prompt_bytes"]) * plan["cache_write_reserve_multiplier"] * rates["input_usd_per_million"]
                   + output_cap * rates["output_usd_per_million"]) / 1_000_000
        async with lock:
            if spent + reserve > plan["max_cost_usd"]:
                ledger["status"] = "stopped_budget"
                write_json(ledger_path, ledger)
                return False
            row = {"case_id": case["case_id"], "index": case["index"],
                   "status": "pending", "messages": messages, "prompt_sha256": digest(messages),
                   "prompt_bytes": prompt_bytes, "retry_count": 0, "usage": None}
            ledger["attempts"][case["case_id"]] = row
            ledger["status"] = "running"
            write_json(ledger_path, ledger)
        start = time.monotonic()
        try:
            provider = providers[case["model"]]
            if case.get("delivery") == "native_request":
                operation = _native_operation(root_by_id[case["root_id"]], case["format"])
                result: ModelResponse = await provider.complete_request(
                    messages, output_cap, operations=operation, native_tools=True)
            else:
                result = await provider.complete(messages, output_cap)
            cost = response_cost(result, identity)
            if result.input_tokens is None or result.output_tokens is None or cost is None:
                raise ProviderError("Missing measured token usage or configured rate", response=result)
            expected_model = plan["response_model_aliases"].get(case["model"], identity["model"])
            if result.model != expected_model:
                raise ProviderError("Returned model differs from assigned snapshot", response=result)
            accepted = None
            if case.get("delivery") == "native_request":
                request = strict_json(result.text)
                root = root_by_id[case["root_id"]]
                required = {"operation": operation[0]["operation"],
                            "artifact_id": root["id"], "claim": root["claim"],
                            **root["context"]}
                accepted = request == required
                status = snapshots[root["id"] + "/" + case["state_id"]][case["format"] if case["format"] == "eal" else "graph"]["status"] if accepted else None
                recipient = {"status": None, "explanation": None, "format_valid": accepted}
            elif case["stage"] == "author":
                value, candidate_error = _candidate(result.text, case["format"])
                recipient = {"candidate_parses": value is not None, "candidate_error": candidate_error,
                             "candidate_sha256": digest(value) if value is not None else None}
                status = None
            else:
                root = root_by_id[case["root_id"]]
                recipient = answer(result.text, root["claim"])
                if case["stage"] == "fixed" and case["delivery"] == "host_owned":
                    status = snapshots[root["id"] + "/" + case["state_id"]][case["format"] if case["format"] == "eal" else "graph"]["status"]
                elif case["stage"] == "recipient":
                    status = packet["status"] if packet["status"] in STATUS else None
                else:
                    status = recipient["status"]
            row.update(status="completed", duration_seconds=time.monotonic() - start,
                       response={"text": result.text, "model": result.model, "metadata": result.metadata},
                       usage={"input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
                              "cached_input_tokens": result.metadata.get("cached_input_tokens", 0),
                              "reasoning_tokens": result.metadata.get("reasoning_tokens", 0),
                              "model_cost_usd": cost},
                       recipient=recipient, accepted_status=status,
                       native_request_accepted=accepted,
                       host_packet=packet,
                       exact_status_correct=(status == case["expected"] if "expected" in case else None),
                       false_support=(status == "supported" and case["expected"] != "supported"
                                      if "expected" in case else None))
            async with lock:
                spent += cost
                write_json(ledger_path, ledger)
            return True
        except ProviderError as exc:
            failed = exc.response
            measured_cost = response_cost(failed, identity) if failed else None
            row.update(status="failed", duration_seconds=time.monotonic() - start,
                       error=type(exc).__name__ + ": " + str(exc),
                       response=({"text": failed.text, "model": failed.model,
                                  "metadata": failed.metadata} if failed else None),
                       usage=({"input_tokens": failed.input_tokens, "output_tokens": failed.output_tokens,
                               "model_cost_usd": measured_cost} if measured_cost is not None else None))
        except Exception as exc:
            row.update(status="failed", duration_seconds=time.monotonic() - start,
                       error=type(exc).__name__ + ": " + str(exc)[:200])
        async with lock:
            ledger["status"] = "stopped_provider_or_integrity_failure"
            ledger["failures"].append(case["case_id"])
            write_json(ledger_path, ledger)
        return False

    async def batch(block: list[dict]) -> bool:
        # Start at most concurrency in parallel, persist pending attempts before
        # a provider call, and stop subsequent batches on any failed attempt.
        width = plan["concurrency"]
        for n in range(0, len(block), width):
            part = block[n:n + width]
            results = await asyncio.gather(*(one(c) for c in part))
            if not all(results):
                return False
        return True

    if not await batch([c for c in cases if c["stage"] == "fixed"]):
        return {"status": ledger["status"], "attempted": len(ledger["attempts"]), "spent": spent}
    # Author turns are linked within a group. Run a same-turn wave before the
    # next; no group can see another group's assistant messages.
    for turn in range(3):
        if not await batch([c for c in cases if c["stage"] == "author" and c["turn"] == turn]):
            return {"status": ledger["status"], "attempted": len(ledger["attempts"]), "spent": spent}
    if not await batch([c for c in cases if c["stage"] == "recipient"]):
        return {"status": ledger["status"], "attempted": len(ledger["attempts"]), "spent": spent}
    ledger["status"] = "complete"
    write_json(ledger_path, ledger)
    return {"status": "complete", "attempted": len(ledger["attempts"]),
            "spent": spent, "freeze_sha256": frozen["freeze_sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--freeze-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output", type=Path, default=HERE / "run-private")
    args = parser.parse_args()
    if args.preflight:
        if args.resume or args.freeze_only:
            parser.error("Preflight cannot create or resume a paid freeze")
        frozen = prepare(allow_pending_review=True)
        print(json.dumps({"status": "offline_review_pending" if frozen["review_status"] == "pending_independent_ai_review_unmasked"
                          else "offline_reviewed", "model_calls": 0,
                          "assigned": len(frozen["cases"]), "parity": frozen["parity"],
                          "reserve_usd": frozen["conservative_reserve_usd"],
                          "models": {k: v["model"] for k, v in frozen["provider_identities"].items()}}, indent=2))
    else:
        print(json.dumps(asyncio.run(run(args.output, resume=args.resume,
                                         freeze_only=args.freeze_only)), indent=2))


if __name__ == "__main__":
    main()
