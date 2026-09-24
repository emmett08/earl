#!/usr/bin/env python3
"""Fresh A3 800-assignment draw with bounded, fully logged 5xx retry.

A1, A2 and C1 are separate stopped diagnostics. This runner does not read their
outcomes, pool their calls, replace failed slots or fabricate author history.
Each assigned slot can make one identical-payload retry after a response-less
HTTP 500–504. Every provider request and unknown billing reserve is logged.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

import run as study
from eal.providers import ModelResponse, ProviderError, response_cost
from eal.runtime import strict_json

HERE = Path(__file__).resolve().parent
PLAN = HERE / "plan-a3.json"
REVIEW_PROTOCOL = HERE / "postcall-review-protocol-a3.json"
study.PLAN = PLAN
FREEZE_SCHEMA = "eal2-deployment-800-a3-freeze/1"
LEDGER_SCHEMA = "eal2-deployment-800-a3-ledger/1"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def allocation(case: dict) -> dict:
    # Host acquisition traces include volatile started_at and collection IDs.
    # Freeze literal fixed messages; regenerate and compare all other fields.
    return {k: v for k, v in case.items() if not (case["stage"] == "fixed" and k == "messages")}


def prepare() -> dict:
    base = study.prepare()
    protocol = study.read_json(REVIEW_PROTOCOL)
    if (protocol.get("amendment") != base["plan"]["amendment"]
            or protocol.get("status") != "fixed_before_any_A3_model_output"
            or protocol.get("a3_plan_sha256") != file_hash(PLAN)
            or protocol.get("schedule_case_ids_sha256")
            != study.digest([c["case_id"] for c in base["cases"]])):
        raise ValueError("A3 pre-run review selection rule is absent or changed")
    manifest = study.read_json(HERE / base["plan"]["corpus"])
    basis = []
    for root in manifest["roots"]:
        for state in root["states"]:
            eal, _, _ = study._host_assessment(root, state, HERE)
            graph = study._graph_assessment(root, state)
            if (eal["claim"] != root["claim"] or graph["claim"] != root["claim"]
                    or eal["status"] != state["expected"] or graph["status"] != state["expected"]):
                raise ValueError("A3 reference claim/status changed")
            basis.append({"root_id": root["id"], "state_id": state["id"],
                          "claim": root["claim"], "scope": root["context"],
                          "expected": state["expected"],
                          "source_sha256": file_hash(HERE / root["source"]),
                          "graph_sha256": file_hash(HERE / root["graph"]),
                          "records": {name: file_hash(HERE / path)
                                      for name, path in state["checker_evidence"].items()}})
    if len(base["cases"]) != 800 or base["review_status"] != "accepted_developmental":
        raise ValueError("A3 needs 800 cases and the accepted synthetic AI review")
    plan = base["plan"]
    if (plan["concurrency"] != 2 or plan["retry_policy"]["max_retries_per_assigned_slot"] != 1
            or plan["retry_policy"]["maximum_total_double_failed_slots"] != 8
            or plan["retry_policy"]["maximum_consecutive_double_failed_slots"] != 2):
        raise ValueError("A3 bounded retry and concurrency plan changed")
    frozen = {"schema": FREEZE_SCHEMA, "amendment": plan["amendment"],
              "base": base, "a3_plan_sha256": file_hash(PLAN),
              "a3_runner_sha256": file_hash(Path(__file__)),
              "postcall_review_protocol_sha256": file_hash(REVIEW_PROTOCOL),
              "evidence_basis_sha256": study.digest(basis),
              "created_at": datetime.now(timezone.utc).isoformat(),
              "call_accounting": "800 assigned slots; actual requests can exceed 800 by the count of 5xx retries, all separately logged and charged/reserved. No A1/A2/C1 result is pooled."}
    frozen["a3_freeze_sha256"] = study.digest(frozen)
    return frozen


def verify(frozen: dict) -> None:
    if (frozen.get("schema") != FREEZE_SCHEMA
            or frozen.get("a3_freeze_sha256") != study.digest(
                {k: v for k, v in frozen.items() if k != "a3_freeze_sha256"})
            or frozen["a3_plan_sha256"] != file_hash(PLAN)
            or frozen["a3_runner_sha256"] != file_hash(Path(__file__))
            or frozen["postcall_review_protocol_sha256"] != file_hash(REVIEW_PROTOCOL)):
        raise ValueError("A3 freeze or code changed")
    base = frozen["base"]
    if base["freeze_sha256"] != study.digest({k: v for k, v in base.items() if k != "freeze_sha256"}):
        raise ValueError("A3 base freeze changed")
    for path, expected in base["materials"].items():
        if file_hash(Path(path)) != expected:
            raise ValueError("Pinned A3 source material drift: " + path)
    current = prepare()
    if ([allocation(c) for c in current["base"]["cases"]]
            != [allocation(c) for c in base["cases"]]
            or current["base"]["materials"] != base["materials"]
            or current["base"]["provider_identities"] != base["provider_identities"]
            or current["evidence_basis_sha256"] != frozen["evidence_basis_sha256"]):
        raise ValueError("A3 schedule, provider or evidence basis drift")


def dispatch_order(cases: list[dict]) -> list[dict]:
    return ([c for c in cases if c["stage"] == "fixed"]
            + [c for turn in range(3) for c in cases
               if c["stage"] == "author" and c["turn"] == turn]
            + [c for c in cases if c["stage"] == "recipient"])


def prior_audit(frozen: dict, ledger: dict) -> None:
    if (ledger.get("schema") != LEDGER_SCHEMA
            or ledger.get("a3_freeze_sha256") != frozen["a3_freeze_sha256"]
            or ledger.get("status") not in ("frozen", "running")):
        raise ValueError("A3 ledger mismatch or terminal run; no re-entry")
    order = dispatch_order(frozen["base"]["cases"])
    rows = ledger["attempts"]
    if set(rows) != {c["case_id"] for c in order[:len(rows)]}:
        raise ValueError("A3 attempts are not a dispatch prefix")
    failures = {k for k, r in rows.items() if r["status"] == "failed"}
    if len(ledger["failures"]) != len(failures) or set(ledger["failures"]) != failures:
        raise ValueError("A3 failed row/list mismatch")
    streak = high = 0
    for case in order[:len(rows)]:
        row = rows[case["case_id"]]
        if (row["case_id"] != case["case_id"] or row["index"] != case["index"]
                or row["prompt_sha256"] != study.digest(row["messages"])
                or row["prompt_bytes"] != len(study.canonical(row["messages"]))
                or row["status"] not in ("completed", "failed")
                or not 1 <= len(row["requests"]) <= 2
                or row["retry_count"] != len(row["requests"]) - 1):
            raise ValueError("Unresolved or altered possibly billed A3 attempt")
        for n, req in enumerate(row["requests"]):
            if (req["request_id"] != case["case_id"] + f"/request-{n}"
                    or req["prompt_sha256"] != row["prompt_sha256"]
                    or req["status"] not in ("completed", "failed")
                    or not isinstance(req["reserved_cost_usd"], (int, float))):
                raise ValueError("A3 request-level audit failed")
        if (row["status"] == "completed" and (row["usage"] is None
                                             or row["requests"][-1]["status"] != "completed")):
            raise ValueError("A3 completed outcome has no measured request")
        streak = streak + 1 if row["status"] == "failed" else 0
        high = max(high, streak)
    p = frozen["base"]["plan"]["retry_policy"]
    if len(failures) >= p["maximum_total_double_failed_slots"] or high > p["maximum_consecutive_double_failed_slots"]:
        raise ValueError("A3 persisted failure threshold reached; no dispatch")


async def run(out: Path, *, resume: bool, freeze_only: bool) -> dict:
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    freeze_path, ledger_path = out / "freeze.json", out / "ledger.json"
    if freeze_path.exists():
        if not resume:
            raise ValueError("Existing A3 freeze needs --resume")
        frozen = study.read_json(freeze_path)
        verify(frozen)
    else:
        if resume:
            raise ValueError("No A3 freeze to resume")
        frozen = prepare()
        study.write_json(freeze_path, frozen)
    ledger = study.read_json(ledger_path) if ledger_path.exists() else {
        "schema": LEDGER_SCHEMA, "a3_freeze_sha256": frozen["a3_freeze_sha256"],
        "status": "frozen", "attempts": {}, "failures": []}
    if not ledger_path.exists():
        study.write_json(ledger_path, ledger)
    prior_audit(frozen, ledger)
    base = frozen["base"]
    plan = base["plan"]
    if freeze_only:
        return {"status": "frozen", "assigned_slots": 800,
                "concurrency": 2, "zero_paid_calls": True,
                "base_reserve_usd": base["conservative_reserve_usd"],
                "cap_usd": plan["max_cost_usd"]}
    _, manifest, providers = study._load()
    if {key: p.identity() for key, p in providers.items()} != base["provider_identities"]:
        raise ValueError("A3 provider identity drift")
    snapshots = {}
    for root in manifest["roots"]:
        for state in root["states"]:
            eal, records, _ = study._host_assessment(root, state, HERE)
            graph = study._graph_assessment(root, state)
            snapshots[root["id"] + "/" + state["id"]] = {
                "eal": eal, "graph": graph, "records": records}
    roots = {r["id"]: r for r in manifest["roots"]}
    cases = base["cases"]
    spent = sum(req["usage"]["model_cost_usd"] if req.get("usage") else req["reserved_cost_usd"]
                for row in ledger["attempts"].values() for req in row["requests"])
    lock = asyncio.Lock()

    async def one(case: dict) -> str:
        nonlocal spent
        if case["case_id"] in ledger["attempts"]:
            return "previous"
        messages, packet = study._prompt(case, ledger, cases, manifest, snapshots)
        prompt_bytes = len(study.canonical(messages))
        if prompt_bytes > plan["max_prompt_bytes"]:
            raise ValueError("Dynamic prompt exceeds cap: " + case["case_id"])
        identity = base["provider_identities"][case["model"]]
        rate = identity["pricing"]
        output_cap = plan["max_output_tokens"]["author" if case["stage"] == "author" else "recipient"]
        reserve = ((2 * plan["max_prompt_bytes"]) * plan["cache_write_reserve_multiplier"]
                   * rate["input_usd_per_million"]
                   + output_cap * rate["output_usd_per_million"]) / 1_000_000
        row = {"case_id": case["case_id"], "index": case["index"], "status": "pending",
               "messages": messages, "prompt_sha256": study.digest(messages),
               "prompt_bytes": prompt_bytes, "retry_count": 0, "requests": [],
               "response": None, "usage": None, "host_packet": packet}
        start_total = time.monotonic()
        operation = study._native_operation(roots[case["root_id"]], case["format"]) if case.get("delivery") == "native_request" else None
        for request_no in range(2):
            async with lock:
                if ledger["status"] not in ("frozen", "running"):
                    if row["requests"]:
                        row.update(status="failed", error="Run stopped before the identical retry",
                                   duration_seconds=time.monotonic() - start_total,
                                   unknown_billing_reserve_usd=sum(
                                       r["reserved_cost_usd"] for r in row["requests"]
                                       if r["usage"] is None))
                        ledger["failures"].append(case["case_id"])
                        study.write_json(ledger_path, ledger)
                    return "stop"
                if spent + reserve > plan["max_cost_usd"]:
                    if row["requests"]:
                        # The first request was sent and may be billable.
                        # Finalise its assigned slot before stopping; a
                        # later resume must never repeat that first request.
                        row.update(status="failed", error="Budget cap prevented the bounded retry",
                                   duration_seconds=time.monotonic() - start_total,
                                   unknown_billing_reserve_usd=sum(
                                       r["reserved_cost_usd"] for r in row["requests"]
                                       if r["usage"] is None))
                        ledger["failures"].append(case["case_id"])
                    ledger["status"] = "stopped_budget"
                    study.write_json(ledger_path, ledger)
                    return "stop"
                req = {"request_id": case["case_id"] + f"/request-{request_no}",
                       "prompt_sha256": row["prompt_sha256"],
                       "native_operation_sha256": study.digest(operation) if operation else None,
                       "status": "pending", "reserved_cost_usd": reserve,
                       "usage": None, "response": None}
                row["requests"].append(req)
                row["retry_count"] = request_no
                ledger["attempts"][case["case_id"]] = row
                spent += reserve
                ledger["status"] = "running"
                study.write_json(ledger_path, ledger)
            start = time.monotonic()
            try:
                provider = providers[case["model"]]
                if operation:
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
                usage = {"input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
                         "cached_input_tokens": result.metadata.get("cached_input_tokens", 0),
                         "reasoning_tokens": result.metadata.get("reasoning_tokens", 0),
                         "model_cost_usd": cost}
                response = {"text": result.text, "model": result.model, "metadata": result.metadata}
                req.update(status="completed", duration_seconds=time.monotonic() - start,
                           usage=usage, response=response)
                row.update(response=response, usage=usage)
                async with lock:
                    spent += cost - reserve
                    study.write_json(ledger_path, ledger)
                try:
                    if operation:
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
                        value, error = study._candidate(result.text, case["format"])
                        recipient = {"candidate_parses": value is not None,
                                     "candidate_error": error,
                                     "candidate_sha256": study.digest(value) if value is not None else None}
                        accepted, status = None, None
                    else:
                        root = roots[case["root_id"]]
                        recipient = study.answer(result.text, root["claim"])
                        accepted = None
                        if case["stage"] == "fixed" and case["delivery"] == "host_owned":
                            status = snapshots[root["id"] + "/" + case["state_id"]][case["format"]]["status"]
                        elif case["stage"] == "recipient":
                            status = packet["status"] if packet["status"] in study.STATUS else None
                        else:
                            status = recipient["status"]
                    row.update(status="completed", duration_seconds=time.monotonic() - start_total,
                               recipient=recipient, accepted_status=status,
                               native_request_accepted=accepted,
                               exact_status_correct=(status == case["expected"] if "expected" in case else None),
                               false_support=(status == "supported" and case["expected"] != "supported"
                                              if "expected" in case else None))
                    async with lock:
                        study.write_json(ledger_path, ledger)
                    return "completed"
                except Exception as exc:
                    row.update(status="failed", error="IntegrityError: " + str(exc)[:200],
                               duration_seconds=time.monotonic() - start_total)
                    async with lock:
                        ledger["failures"].append(case["case_id"])
                        ledger["status"] = "stopped_integrity_failure"
                        study.write_json(ledger_path, ledger)
                    return "stop"
            except ProviderError as exc:
                returned = exc.response
                measured_cost = response_cost(returned, identity) if returned else None
                usage = ({"input_tokens": returned.input_tokens,
                          "output_tokens": returned.output_tokens,
                          "cached_input_tokens": returned.metadata.get("cached_input_tokens", 0),
                          "reasoning_tokens": returned.metadata.get("reasoning_tokens", 0),
                          "model_cost_usd": measured_cost}
                         if returned and measured_cost is not None else None)
                response = ({"text": returned.text, "model": returned.model,
                             "metadata": returned.metadata} if returned else None)
                eligible = (returned is None
                            and re.search(r"\bHTTP 50[0-4]\b", str(exc)) is not None)
                req.update(status="failed", duration_seconds=time.monotonic() - start,
                           error=type(exc).__name__ + ": " + str(exc),
                           eligible_identical_retry=eligible, usage=usage, response=response)
                async with lock:
                    if measured_cost is not None:
                        spent += measured_cost - reserve
                    study.write_json(ledger_path, ledger)
                if eligible and request_no == 0:
                    await asyncio.sleep(plan["retry_policy"]["retry_delay_seconds"])
                    continue
                row.update(status="failed", error=req["error"], response=response, usage=usage,
                           duration_seconds=time.monotonic() - start_total,
                           unknown_billing_reserve_usd=sum(r["reserved_cost_usd"] for r in row["requests"]
                                                           if r["usage"] is None))
                async with lock:
                    ledger["failures"].append(case["case_id"])
                    if not eligible or case["stage"] == "author":
                        ledger["status"] = "stopped_provider_or_author_failure"
                    study.write_json(ledger_path, ledger)
                return "double_failure" if eligible and case["stage"] != "author" else "stop"
            except Exception as exc:
                req.update(status="failed", duration_seconds=time.monotonic() - start,
                           error=type(exc).__name__ + ": " + str(exc)[:200])
                row.update(status="failed", error=req["error"],
                           duration_seconds=time.monotonic() - start_total,
                           unknown_billing_reserve_usd=sum(r["reserved_cost_usd"] for r in row["requests"]
                                                           if r["usage"] is None))
                async with lock:
                    ledger["failures"].append(case["case_id"])
                    ledger["status"] = "stopped_integrity_failure"
                    study.write_json(ledger_path, ledger)
                return "stop"
        raise AssertionError("A3 retry loop exhausted without outcome")

    async def batch(block: list[dict]) -> bool:
        streak = 0
        for case in dispatch_order(cases):
            row = ledger["attempts"].get(case["case_id"])
            if row is not None:
                streak = streak + 1 if row["status"] == "failed" else 0
        for n in range(0, len(block), plan["concurrency"]):
            statuses = await asyncio.gather(*(one(c) for c in block[n:n + plan["concurrency"]]))
            hit_streak = False
            for status in statuses:
                if status == "double_failure":
                    streak += 1
                elif status == "completed":
                    streak = 0
                hit_streak |= streak > plan["retry_policy"]["maximum_consecutive_double_failed_slots"]
            if ("stop" in statuses or hit_streak
                    or len(ledger["failures"]) >= plan["retry_policy"]["maximum_total_double_failed_slots"]):
                if ledger["status"] not in ("stopped_budget", "stopped_integrity_failure",
                                            "stopped_provider_or_author_failure"):
                    ledger["status"] = "stopped_failure_threshold"
                    study.write_json(ledger_path, ledger)
                return False
        return True

    if not await batch([c for c in cases if c["stage"] == "fixed"]):
        return {"status": ledger["status"], "assigned_attempted": len(ledger["attempts"]),
                "requests": sum(len(r["requests"]) for r in ledger["attempts"].values()),
                "reserved_spent_usd": spent}
    for turn in range(3):
        if not await batch([c for c in cases if c["stage"] == "author" and c["turn"] == turn]):
            return {"status": ledger["status"], "assigned_attempted": len(ledger["attempts"]),
                    "requests": sum(len(r["requests"]) for r in ledger["attempts"].values()),
                    "reserved_spent_usd": spent}
    if not await batch([c for c in cases if c["stage"] == "recipient"]):
        return {"status": ledger["status"], "assigned_attempted": len(ledger["attempts"]),
                "requests": sum(len(r["requests"]) for r in ledger["attempts"].values()),
                "reserved_spent_usd": spent}
    if len(ledger["attempts"]) != 800:
        raise AssertionError("A3 assigned-slot count changed")
    ledger["status"] = "complete_with_recorded_failures" if ledger["failures"] else "complete"
    study.write_json(ledger_path, ledger)
    return {"status": ledger["status"], "assigned_attempted": 800,
            "requests": sum(len(r["requests"]) for r in ledger["attempts"].values()),
            "reserved_spent_usd": spent, "a3_freeze_sha256": frozen["a3_freeze_sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--freeze-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.output, resume=args.resume,
                                     freeze_only=args.freeze_only)), indent=2))


if __name__ == "__main__":
    main()
