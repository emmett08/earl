#!/usr/bin/env python3
"""Read-only assignment and individual-request analysis of A3."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import statistics

import run_a3 as study


def audit(directory: Path) -> dict:
    frozen = study.study.read_json(directory / "freeze.json")
    ledger = study.study.read_json(directory / "ledger.json")
    study.verify(frozen)
    base = frozen["base"]
    cases = {c["case_id"]: c for c in base["cases"]}
    if (ledger.get("schema") != study.LEDGER_SCHEMA
            or ledger.get("a3_freeze_sha256") != frozen["a3_freeze_sha256"]
            or len(cases) != 800 or len(ledger["attempts"]) > 800):
        raise ValueError("Wrong A3 attempt ledger or allocation")
    arms = defaultdict(lambda: {"assigned": 0, "attempted_slots": 0,
                                "completed_slots": 0, "failed_slots": 0,
                                "actual_requests": 0, "retries": 0,
                                "input_tokens": 0, "cached_input_tokens": 0,
                                "output_tokens": 0, "reasoning_tokens": 0,
                                "configured_cost_usd": 0.0,
                                "unknown_billing_reserve_usd": 0.0,
                                "exact_status": 0, "false_support": 0,
                                "native_accepted": 0,
                                "author_candidate_parses": 0,
                                "slot_durations_seconds": [],
                                "request_durations_seconds": []})

    def arm(case: dict) -> tuple:
        return (case["stage"], case["model"], case["format"],
                case.get("delivery", "author_revision" if case["stage"] == "author" else "authored_packet"),
                case.get("instruction"))

    for case in cases.values():
        arms[arm(case)]["assigned"] += 1
    revisions = defaultdict(dict)
    for case_id, row in ledger["attempts"].items():
        case = cases[case_id]
        if (row["index"] != case["index"] or row["case_id"] != case_id
                or row["prompt_sha256"] != study.study.digest(row["messages"])
                or row["retry_count"] != len(row["requests"]) - 1
                or len(row["requests"]) not in (1, 2)):
            raise ValueError("A3 assigned slot, prompt or retry sequence changed")
        value = arms[arm(case)]
        value["attempted_slots"] += 1
        value["actual_requests"] += len(row["requests"])
        value["retries"] += len(row["requests"]) - 1
        value["completed_slots"] += row["status"] == "completed"
        value["failed_slots"] += row["status"] == "failed"
        if row.get("duration_seconds") is not None:
            value["slot_durations_seconds"].append(row["duration_seconds"])
        for n, req in enumerate(row["requests"]):
            if (req["request_id"] != case_id + f"/request-{n}"
                    or req["prompt_sha256"] != row["prompt_sha256"]
                    or req["status"] not in ("completed", "failed", "pending")):
                raise ValueError("A3 request-level identity/prompt changed")
            if req.get("duration_seconds") is not None:
                value["request_durations_seconds"].append(req["duration_seconds"])
            usage = req.get("usage")
            if usage is None:
                value["unknown_billing_reserve_usd"] += req["reserved_cost_usd"]
                continue
            for name in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens"):
                number = usage.get(name, 0)
                if type(number) is not int or number < 0:
                    raise ValueError("Invalid reported token usage")
                value[name] += number
            cost = usage["model_cost_usd"]
            rates = base["provider_identities"][case["model"]]["pricing"]
            expected = ((usage["input_tokens"] - usage["cached_input_tokens"])
                        * rates["input_usd_per_million"]
                        + usage["cached_input_tokens"] * rates["cached_input_usd_per_million"]
                        + usage["output_tokens"] * rates["output_usd_per_million"]) / 1_000_000
            if not math.isfinite(cost) or abs(cost - expected) > 1e-8:
                raise ValueError("Configured cost differs from reported usage")
            value["configured_cost_usd"] += cost
        if row["status"] == "completed":
            if row["response"]["model"] != base["plan"]["response_model_aliases"].get(
                    case["model"], base["provider_identities"][case["model"]]["model"]):
                raise ValueError("Returned model differs from frozen assignment")
            if case.get("delivery") == "native_request" and "native_tool_call" not in row["response"]["metadata"]:
                raise ValueError("Native mode lacks recorded function call")
            value["exact_status"] += row.get("exact_status_correct") is True
            value["false_support"] += row.get("false_support") is True
            value["native_accepted"] += row.get("native_request_accepted") is True
            value["author_candidate_parses"] += row.get("recipient", {}).get("candidate_parses") is True
            if case["stage"] == "author":
                revisions[case["author_group"]][case["turn"]] = row["response"]["text"]
    if ledger["status"] in ("complete", "complete_with_recorded_failures"):
        if (len(ledger["attempts"]) != 800
                or any(r["status"] not in ("completed", "failed") for r in ledger["attempts"].values())):
            raise ValueError("A3 terminal completion mismatches 800 assigned slots")
    labelled = []
    for key, value in sorted(arms.items(), key=lambda p: tuple(str(v) for v in p[0])):
        stage, model, fmt, delivery, instructed = key
        labelled.append({"stage": stage, "model": model, "format": fmt,
                         "delivery": delivery, "instructed": instructed,
                         **{k: v for k, v in value.items()
                            if k not in ("slot_durations_seconds", "request_durations_seconds")},
                         "median_slot_seconds": statistics.median(value["slot_durations_seconds"])
                         if value["slot_durations_seconds"] else None,
                         "median_request_seconds": statistics.median(value["request_durations_seconds"])
                         if value["request_durations_seconds"] else None})
    numeric = ("assigned", "attempted_slots", "completed_slots", "failed_slots",
               "actual_requests", "retries", "input_tokens", "cached_input_tokens",
               "output_tokens", "reasoning_tokens", "configured_cost_usd",
               "unknown_billing_reserve_usd", "exact_status", "false_support",
               "native_accepted", "author_candidate_parses")
    totals = {name: sum(row[name] for row in labelled) for name in numeric}
    changes = {"groups_with_three_completed": 0, "second_source_changed": 0,
               "third_source_changed": 0}
    for answers in revisions.values():
        if set(answers) == {0, 1, 2}:
            changes["groups_with_three_completed"] += 1
            changes["second_source_changed"] += answers[0] != answers[1]
            changes["third_source_changed"] += answers[1] != answers[2]
    return {"schema": "eal2-deployment-800-a3-analysis/1",
            "a3_freeze_sha256": frozen["a3_freeze_sha256"],
            "status": ledger["status"], "review_status": base["review_status"],
            "totals": totals, "arms": labelled,
            "author_revision_changes": changes,
            "provider_only_configured_cost_per_exact_status_usd": (
                totals["configured_cost_usd"] / totals["exact_status"]
                if totals["exact_status"] else None),
            "qualified_decision_denominator": "unavailable: source and explanation fidelity not yet adjudicated",
            "all_in_cost_per_correctly_accepted_decision": "unavailable: human labour, host/evidence costs, invoice and qualified denominator unmeasured",
            "limitations": ["Fresh A3 draw; A1/A2/C1 outcomes are separate stopped diagnostics",
                            "Eight synthetic domain variants share one source generator",
                            "Unknown-billing failures and GPT-6 cache-write premium are not invoiced",
                            "Retry count increases actual API requests above 800 assigned slots",
                            "Native function request has no recipient-produced explanation"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.directory)
    data = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data)


if __name__ == "__main__":
    main()
