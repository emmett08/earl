#!/usr/bin/env python3
"""A2-C1 continuation: attempt only the 672 A2 slots never sent to the API.

The A2 HTTP 500 at index 125 remains a failed, possibly billed observation.
C1 keeps the exact A2 schedule and original A2 ledger immutable. A failed or
pending C1 request stops C1; no request is retried under this version.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import time

import run as study
from eal.providers import ModelResponse, ProviderError, response_cost
from eal.runtime import strict_json

HERE = Path(__file__).resolve().parent
CONTINUATION_SCHEMA = "eal2-deployment-800-continuation/1"
LEDGER_SCHEMA = "eal2-deployment-800-continuation-ledger/1"
MAX_TOTAL_SERVER_FAILURES = 8
MAX_CONSECUTIVE_SERVER_FAILURES = 2


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources(a2: Path) -> tuple[dict, dict, dict]:
    freeze_path = a2 / "freeze.json"
    ledger_path = a2 / "ledger.json"
    frozen, old = study.read_json(freeze_path), study.read_json(ledger_path)
    if (frozen.get("schema") != study.FREEZE_SCHEMA
            or frozen.get("freeze_sha256") != study.digest(
                {k: v for k, v in frozen.items() if k != "freeze_sha256"})
            or old.get("freeze_sha256") != frozen["freeze_sha256"]
            or old.get("status") != "stopped_provider_or_integrity_failure"
            or old.get("failures") != ["deployment-0125"]):
        raise ValueError("A2 frozen failure state has changed")
    for path, expected in frozen["materials"].items():
        if file_hash(Path(path)) != expected:
            raise ValueError("Original A2 frozen material changed: " + path)
    cases = frozen["cases"]
    if (len(cases) != 800 or len(old["attempts"]) != 128
            or {c["case_id"] for c in cases[:128]} != set(old["attempts"])):
        raise ValueError("A2 must contain exactly the first 128 assigned attempts")
    for case in cases[:128]:
        row = old["attempts"][case["case_id"]]
        if (row.get("index") != case["index"]
                or row.get("prompt_sha256") != study.digest(row.get("messages"))
                or row.get("retry_count") != 0
                or row.get("status") != ("failed" if case["index"] == 125 else "completed")):
            raise ValueError("A2 attempted payload or status changed")
    if old["attempts"]["deployment-0125"].get("usage") is not None:
        raise ValueError("A2 failure unexpectedly acquired measured usage")
    fresh = study.prepare()
    # The host's acquisition trace contains run timestamps. Fixed prompts
    # must come from A2's literal frozen cases, while allocation fields and
    # all non-acquisition prompts are reproducible from pinned source.
    def allocation(case: dict) -> dict:
        return {k: v for k, v in case.items() if not (case["stage"] == "fixed" and k == "messages")}

    if ([allocation(c) for c in fresh["cases"]] != [allocation(c) for c in cases]
            or fresh["materials"] != frozen["materials"]
            or fresh["provider_identities"] != frozen["provider_identities"]):
        raise ValueError("Rebuilt current schedule or provider differs from A2")
    manifest = study.read_json(HERE / frozen["plan"]["corpus"])
    evidence_basis = []
    for root in manifest["roots"]:
        for state in root["states"]:
            eal, _, _ = study._host_assessment(root, state, HERE)
            graph = study._graph_assessment(root, state)
            if (eal["status"] != state["expected"] or graph["status"] != state["expected"]
                    or eal["claim"] != root["claim"] or graph["claim"] != root["claim"]):
                raise ValueError("Dynamic host assessment changed claim or reference status")
            evidence_basis.append({"root_id": root["id"], "state_id": state["id"],
                                   "claim": root["claim"], "scope": root["context"],
                                   "expected": state["expected"],
                                   "source_sha256": file_hash(HERE / root["source"]),
                                   "graph_sha256": file_hash(HERE / root["graph"]),
                                   "record_sha256": {name: file_hash(HERE / path)
                                                     for name, path in state["checker_evidence"].items()}})
    old_spend = sum(r["usage"]["model_cost_usd"] for r in old["attempts"].values()
                    if r.get("usage") is not None)
    case = cases[125]
    rate = frozen["provider_identities"][case["model"]]["pricing"]
    cap = frozen["plan"]["max_output_tokens"]["recipient"]
    maximum_unknown = ((2 * frozen["plan"]["max_prompt_bytes"])
                       * frozen["plan"]["cache_write_reserve_multiplier"]
                       * rate["input_usd_per_million"]
                       + cap * rate["output_usd_per_million"]) / 1_000_000
    descriptor = {"schema": CONTINUATION_SCHEMA,
                  "amendment": "A2-C1-never-attempted-only",
                  "source_freeze_sha256": frozen["freeze_sha256"],
                  "source_freeze_file_sha256": file_hash(freeze_path),
                  "source_ledger_file_sha256": file_hash(ledger_path),
                  "source_a2_directory": str(a2.resolve()),
                  "runner_sha256": file_hash(Path(__file__)),
                  "recomputed_evidence_basis_sha256": study.digest(evidence_basis),
                  "dynamic_host_trace_note": "Acquisition started_at and collection IDs are volatile; source, graph, exact scope, evidence files, claims and statuses are recomputed and pinned. Every actual dynamic recipient request is stored with prompt SHA256 in the C1 ledger.",
                  "attempt_case_ids": [c["case_id"] for c in cases if c["case_id"] not in old["attempts"]],
                  "original_completed_count": 127,
                  "original_failed_case_id": "deployment-0125",
                  "original_configured_spend_usd": old_spend,
                  "failed_unknown_billing_reserve_usd": maximum_unknown,
                  "failure_policy": {
                      "eligible": "Only a no-response HTTP 500–504 on an independent fixed or recipient case; retain failed row without retry and reserve its full per-case conservative cost.",
                      "maximum_total_server_failures_including_A2": MAX_TOTAL_SERVER_FAILURES,
                      "maximum_consecutive_server_failures": MAX_CONSECUTIVE_SERVER_FAILURES,
                      "stop": "Stop after the third consecutive eligible server failure, at the eighth total failure, and on any author-chain, identity, usage, other provider, budget or integrity failure. Complete batches already in flight remain logged."
                  },
                  "created_at": datetime.now(timezone.utc).isoformat()}
    if len(descriptor["attempt_case_ids"]) != 672:
        raise AssertionError("Continuation size changed")
    descriptor["continuation_sha256"] = study.digest(descriptor)
    return frozen, old, descriptor


async def execute(a2: Path, out: Path, *, resume: bool, freeze_only: bool) -> dict:
    frozen, old, descriptor = sources(a2)
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    path, ledger_path = out / "continuation-freeze.json", out / "ledger.json"
    if path.exists():
        if not resume:
            raise ValueError("An existing C1 freeze needs explicit --resume")
        saved = study.read_json(path)
        if (saved["continuation_sha256"] != study.digest(
                {k: v for k, v in saved.items() if k != "continuation_sha256"})
                or {k: v for k, v in saved.items() if k != "created_at" and k != "continuation_sha256"}
                != {k: v for k, v in descriptor.items() if k != "created_at" and k != "continuation_sha256"}):
            raise ValueError("C1 continuation source or code changed")
        descriptor = saved
    else:
        if resume:
            raise ValueError("No existing C1 freeze")
        study.write_json(path, descriptor)
    ledger = study.read_json(ledger_path) if ledger_path.exists() else {
        "schema": LEDGER_SCHEMA, "continuation_sha256": descriptor["continuation_sha256"],
        "status": "frozen", "attempts": {}, "failures": []}
    if not ledger_path.exists():
        study.write_json(ledger_path, ledger)
    if ledger.get("continuation_sha256") != descriptor["continuation_sha256"]:
        raise ValueError("C1 ledger freeze mismatch")
    if ledger.get("status") not in ("frozen", "running"):
        raise ValueError("C1 is terminal; re-entry would dispatch after a stop")
    cases = frozen["cases"]
    by_id = {c["case_id"]: c for c in cases}
    excluded = set(old["attempts"])
    dispatch_order = ([c for c in cases if c["stage"] == "fixed"]
                      + [c for turn in range(3) for c in cases
                         if c["stage"] == "author" and c["turn"] == turn]
                      + [c for c in cases if c["stage"] == "recipient"])
    continuation_order = [c["case_id"] for c in dispatch_order if c["case_id"] not in excluded]
    if (len(continuation_order) != 672
            or set(ledger["attempts"]) != set(continuation_order[:len(ledger["attempts"])])):
        raise ValueError("C1 attempts are not a contiguous dispatch prefix")
    for case_id, row in ledger["attempts"].items():
        retained_server_failure = (row.get("status") == "failed"
                                   and row.get("eligible_server_failure") is True
                                   and row.get("usage") is None
                                   and row.get("response") is None
                                   and isinstance(row.get("unknown_billing_reserve_usd"), (float, int))
                                   and row["unknown_billing_reserve_usd"] >= 0)
        if (case_id not in by_id or case_id in excluded or row.get("case_id") != case_id
                or row.get("index") != by_id[case_id]["index"]
                or not ((row.get("status") == "completed" and row.get("usage") is not None)
                        or retained_server_failure)
                or row.get("prompt_sha256") != study.digest(row.get("messages"))):
            raise ValueError("Unresolved or altered C1 attempt: no silent retry")
    failed_rows = {k for k, row in ledger["attempts"].items() if row["status"] == "failed"}
    if len(ledger["failures"]) != len(failed_rows) or set(ledger["failures"]) != failed_rows:
        raise ValueError("C1 failure list and retained failed rows differ")
    chronological = ([old["attempts"][c["case_id"]] for c in dispatch_order if c["case_id"] in excluded]
                     + [ledger["attempts"][k] for k in continuation_order[:len(ledger["attempts"])]])
    prior_consecutive = 0
    prior_max_consecutive = 0
    for previous_row in chronological:
        prior_consecutive = (prior_consecutive + 1 if previous_row["status"] == "failed" else 0)
        prior_max_consecutive = max(prior_max_consecutive, prior_consecutive)
    if (1 + len(failed_rows) >= MAX_TOTAL_SERVER_FAILURES
            or prior_max_consecutive > MAX_CONSECUTIVE_SERVER_FAILURES):
        ledger["status"] = "stopped_server_failure_threshold"
        study.write_json(ledger_path, ledger)
        return {"status": ledger["status"], "attempted": len(ledger["attempts"]),
                "reason": "Previously persisted failure threshold; no new provider calls"}
    if freeze_only:
        return {"status": "frozen", "a2_attempted": 128,
                "continuation_assigned": 672, "continuation_attempted": 0,
                "unknown_billing_reserve_usd": descriptor["failed_unknown_billing_reserve_usd"]}

    plan, manifest, providers = study._load()
    if {k: p.identity() for k, p in providers.items()} != frozen["provider_identities"]:
        raise ValueError("Provider identity drift")
    snapshots = {}
    for root in manifest["roots"]:
        for state in root["states"]:
            eal, records, _ = study._host_assessment(root, state, HERE)
            graph = study._graph_assessment(root, state)
            snapshots[root["id"] + "/" + state["id"]] = {
                "eal": eal, "graph": graph, "records": records}
    roots = {r["id"]: r for r in manifest["roots"]}
    spent = descriptor["original_configured_spend_usd"] + descriptor["failed_unknown_billing_reserve_usd"]
    spent += sum(r["usage"]["model_cost_usd"] if r["status"] == "completed"
                 else r["unknown_billing_reserve_usd"] for r in ledger["attempts"].values())
    lock = asyncio.Lock()

    async def one(case: dict) -> str:
        nonlocal spent
        if case["case_id"] in excluded or case["case_id"] in ledger["attempts"]:
            return "previous"
        messages, packet = study._prompt(case, ledger, cases, manifest, snapshots)
        prompt_bytes = len(study.canonical(messages))
        if prompt_bytes > plan["max_prompt_bytes"]:
            raise ValueError("Dynamic prompt exceeds cap: " + case["case_id"])
        identity = frozen["provider_identities"][case["model"]]
        rate = identity["pricing"]
        output_cap = plan["max_output_tokens"]["author" if case["stage"] == "author" else "recipient"]
        reserve = ((2 * plan["max_prompt_bytes"]) * plan["cache_write_reserve_multiplier"]
                   * rate["input_usd_per_million"]
                   + output_cap * rate["output_usd_per_million"]) / 1_000_000
        async with lock:
            if spent + reserve > plan["max_cost_usd"]:
                ledger["status"] = "stopped_budget"
                study.write_json(ledger_path, ledger)
                return "stop"
            row = {"case_id": case["case_id"], "index": case["index"],
                   "status": "pending", "messages": messages,
                   "prompt_sha256": study.digest(messages), "prompt_bytes": prompt_bytes,
                   "retry_count": 0, "usage": None, "reserved_cost_usd": reserve}
            ledger["attempts"][case["case_id"]] = row
            # Reserve every in-flight assignment under the same lock. Eight
            # concurrent requests must not each see the same unreserved cap.
            spent += reserve
            ledger["status"] = "running"
            study.write_json(ledger_path, ledger)
        start = time.monotonic()
        try:
            provider = providers[case["model"]]
            if case.get("delivery") == "native_request":
                operation = study._native_operation(roots[case["root_id"]], case["format"])
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
                root = roots[case["root_id"]]
                required = {"operation": operation[0]["operation"],
                            "artifact_id": root["id"], "claim": root["claim"],
                            **root["context"]}
                accepted = request == required
                status = (snapshots[root["id"] + "/" + case["state_id"]][case["format"]]["status"]
                          if accepted else None)
                recipient = {"status": None, "explanation": None, "format_valid": accepted}
            elif case["stage"] == "author":
                value, candidate_error = study._candidate(result.text, case["format"])
                recipient = {"candidate_parses": value is not None,
                             "candidate_error": candidate_error,
                             "candidate_sha256": study.digest(value) if value is not None else None}
                status = None
            else:
                root = roots[case["root_id"]]
                recipient = study.answer(result.text, root["claim"])
                if case["stage"] == "fixed" and case["delivery"] == "host_owned":
                    status = snapshots[root["id"] + "/" + case["state_id"]][case["format"]]["status"]
                elif case["stage"] == "recipient":
                    status = packet["status"] if packet["status"] in study.STATUS else None
                else:
                    status = recipient["status"]
            row.update(status="completed", duration_seconds=time.monotonic() - start,
                       response={"text": result.text, "model": result.model, "metadata": result.metadata},
                       usage={"input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
                              "cached_input_tokens": result.metadata.get("cached_input_tokens", 0),
                              "reasoning_tokens": result.metadata.get("reasoning_tokens", 0),
                              "model_cost_usd": cost},
                       recipient=recipient, accepted_status=status,
                       native_request_accepted=accepted, host_packet=packet,
                       exact_status_correct=(status == case["expected"] if "expected" in case else None),
                       false_support=(status == "supported" and case["expected"] != "supported"
                                      if "expected" in case else None))
            async with lock:
                spent += cost - reserve
                study.write_json(ledger_path, ledger)
            return "completed"
        except ProviderError as exc:
            failed = exc.response
            measured_cost = response_cost(failed, identity) if failed else None
            eligible = (case["stage"] in ("fixed", "recipient") and failed is None
                        and re.search(r"\bHTTP 50[0-4]\b", str(exc)) is not None)
            row.update(status="failed", duration_seconds=time.monotonic() - start,
                       error=type(exc).__name__ + ": " + str(exc),
                       eligible_server_failure=eligible,
                       unknown_billing_reserve_usd=reserve if eligible else None,
                       response=({"text": failed.text, "model": failed.model,
                                  "metadata": failed.metadata} if failed else None),
                       usage=({"input_tokens": failed.input_tokens,
                               "output_tokens": failed.output_tokens,
                               "model_cost_usd": measured_cost}
                              if measured_cost is not None else None))
        except Exception as exc:
            eligible = False
            row.update(status="failed", duration_seconds=time.monotonic() - start,
                       error=type(exc).__name__ + ": " + str(exc)[:200])
        async with lock:
            # The in-flight reservation remains for unknown billing. If the
            # endpoint returned usage, reconcile only that measured charge.
            if row.get("usage") is not None:
                spent += row["usage"]["model_cost_usd"] - reserve
            if not eligible:
                ledger["status"] = "stopped_provider_or_integrity_failure"
            ledger["failures"].append(case["case_id"])
            study.write_json(ledger_path, ledger)
        return "server_failure" if eligible else "stop"

    async def batch(block: list[dict]) -> bool:
        # Preexisting attempts are already counted in this chronological tail.
        # A crash with a persisted pending request fails before reaching here.
        consecutive = 0
        for previous_row in ([old["attempts"][c["case_id"]] for c in dispatch_order
                              if c["case_id"] in excluded]
                             + [ledger["attempts"][k] for k in continuation_order
                                if k in ledger["attempts"]]):
            consecutive = consecutive + 1 if previous_row["status"] == "failed" else 0
        width = plan["concurrency"]
        for n in range(0, len(block), width):
            group = block[n:n + width]
            statuses = await asyncio.gather(*(one(c) for c in group))
            within_group_threshold = False
            for status in statuses:
                if status == "server_failure":
                    consecutive += 1
                elif status == "completed":
                    consecutive = 0
                within_group_threshold |= consecutive > MAX_CONSECUTIVE_SERVER_FAILURES
            failures = 1 + len(ledger["failures"])
            if ("stop" in statuses
                    or within_group_threshold
                    or failures >= MAX_TOTAL_SERVER_FAILURES):
                if ledger["status"] not in ("stopped_provider_or_integrity_failure", "stopped_budget"):
                    ledger["status"] = "stopped_server_failure_threshold"
                    study.write_json(ledger_path, ledger)
                return False
        return True

    if not await batch([c for c in cases if c["stage"] == "fixed"]):
        return {"status": ledger["status"], "attempted": len(ledger["attempts"]), "reserved_spent": spent}
    for turn in range(3):
        if not await batch([c for c in cases if c["stage"] == "author" and c["turn"] == turn]):
            return {"status": ledger["status"], "attempted": len(ledger["attempts"]), "reserved_spent": spent}
    if not await batch([c for c in cases if c["stage"] == "recipient"]):
        return {"status": ledger["status"], "attempted": len(ledger["attempts"]), "reserved_spent": spent}
    if len(ledger["attempts"]) != 672:
        raise AssertionError("Continuation count changed")
    ledger["status"] = "complete_with_recorded_failures" if ledger["failures"] else "complete"
    study.write_json(ledger_path, ledger)
    return {"status": "complete_with_A2_recorded_failure", "attempted": 672,
            "A2_attempted": 128, "reserved_spent": spent,
            "continuation_sha256": descriptor["continuation_sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("a2", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--freeze-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(execute(args.a2, args.output,
                                         resume=args.resume, freeze_only=args.freeze_only)), indent=2))


if __name__ == "__main__":
    main()
