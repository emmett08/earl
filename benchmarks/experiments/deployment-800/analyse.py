#!/usr/bin/env python3
"""Read-only, attempt-level audit of the developmental 800-call archive."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import importlib.util
import json
import math
from pathlib import Path
import statistics


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("deployment800", HERE / "run.py")
assert SPEC and SPEC.loader
STUDY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STUDY)


def audit(directory: Path, effort_log: Path | None = None) -> dict:
    frozen = STUDY.read_json(directory / "freeze.json")
    ledger = STUDY.read_json(directory / "ledger.json")
    if frozen.get("schema") != STUDY.FREEZE_SCHEMA or frozen.get("freeze_sha256") != STUDY.digest(
            {k: v for k, v in frozen.items() if k != "freeze_sha256"}):
        raise ValueError("Frozen payload differs from its checksum")
    if ledger.get("schema") != STUDY.LEDGER_SCHEMA or ledger.get("freeze_sha256") != frozen["freeze_sha256"]:
        raise ValueError("Attempt ledger differs from the frozen programme")
    cases = {case["case_id"]: case for case in frozen["cases"]}
    if len(cases) != 800 or len(ledger["attempts"]) > 800:
        raise ValueError("Allocation count or attempted count is invalid")
    material_drift = [path for path, sha in frozen["materials"].items()
                      if not Path(path).exists() or STUDY.digest(Path(path).read_bytes()) != sha]
    arms = defaultdict(lambda: {"assigned": 0, "attempted": 0, "completed": 0,
                                "input_tokens": 0, "output_tokens": 0,
                                "cached_input_tokens": 0, "reasoning_tokens": 0,
                                "configured_cost_usd": 0.0, "exact_status": 0,
                                "false_support": 0, "native_accepted": 0,
                                "author_candidate_parses": 0, "durations_seconds": []})
    revisions = defaultdict(dict)
    for case in frozen["cases"]:
        arm = (case["stage"], case["model"], case["format"],
               case.get("delivery", "author_revision" if case["stage"] == "author" else "authored_packet"),
               case.get("instruction", None))
        arms[arm]["assigned"] += 1
    for key, row in ledger["attempts"].items():
        case = cases.get(key)
        if (case is None or row.get("case_id") != key or row.get("index") != case["index"]
                or row.get("prompt_sha256") != STUDY.digest(row.get("messages"))
                or row.get("prompt_bytes") != len(STUDY.canonical(row["messages"]))
                or row.get("retry_count") != 0):
            raise ValueError("Attempt index, prompt, case link or retry count is invalid")
        arm = (case["stage"], case["model"], case["format"],
               case.get("delivery", "author_revision" if case["stage"] == "author" else "authored_packet"),
               case.get("instruction", None))
        values = arms[arm]
        values["attempted"] += 1
        if row["status"] == "completed":
            values["completed"] += 1
        usage = row.get("usage")
        if usage is not None:
            for name in ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens"):
                amount = usage.get(name, 0)
                if type(amount) is not int or amount < 0:
                    raise ValueError("Usage must contain nonnegative integer token counts")
                values[name] += amount
            cost = usage.get("model_cost_usd")
            if not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
                raise ValueError("Configured-rate cost is missing or invalid")
            rates = frozen["provider_identities"][case["model"]]["pricing"]
            cached = usage.get("cached_input_tokens", 0)
            expected_cost = ((usage["input_tokens"] - cached) * rates["input_usd_per_million"]
                             + cached * rates.get("cached_input_usd_per_million", 0)
                             + usage["output_tokens"] * rates["output_usd_per_million"]) / 1_000_000
            if abs(cost - expected_cost) > 1e-8:
                raise ValueError("Logged configured cost differs from usage and pinned rates")
            values["configured_cost_usd"] += cost
        if row["status"] == "completed":
            if row["response"]["model"] != frozen["plan"]["response_model_aliases"].get(
                    case["model"], frozen["provider_identities"][case["model"]]["model"]):
                raise ValueError("Returned model differs from pinned snapshot")
            if case.get("delivery") == "native_request" and "native_tool_call" not in row["response"]["metadata"]:
                raise ValueError("Native arm lacks a recorded real function call")
            values["exact_status"] += int(row.get("exact_status_correct") is True)
            values["false_support"] += int(row.get("false_support") is True)
            values["native_accepted"] += int(row.get("native_request_accepted") is True)
            values["author_candidate_parses"] += int(row.get("recipient", {}).get("candidate_parses") is True)
            values["durations_seconds"].append(row["duration_seconds"])
            if case["stage"] == "author":
                revisions[case["author_group"]][case["turn"]] = row["response"]["text"]
        elif row["status"] not in {"failed", "pending"}:
            raise ValueError("Unknown attempt status")
    if ledger["status"] == "complete" and (len(ledger["attempts"]) != 800
                                          or any(r["status"] != "completed" for r in ledger["attempts"].values())):
        raise ValueError("Complete marker does not match 800 completed rows")
    labelled = []
    for key, value in sorted(arms.items(), key=lambda pair: tuple(str(v) for v in pair[0])):
        stage, model, fmt, delivery, instructed = key
        labelled.append({"stage": stage, "model": model, "format": fmt,
                         "delivery": delivery, "instructed": instructed,
                         **{k: v for k, v in value.items() if k != "durations_seconds"},
                         "median_api_seconds": statistics.median(value["durations_seconds"])
                         if value["durations_seconds"] else None})
    summed = {key: sum(row[key] for row in labelled) for key in (
        "assigned", "attempted", "completed", "input_tokens", "output_tokens",
        "cached_input_tokens", "reasoning_tokens", "configured_cost_usd", "exact_status",
        "false_support", "native_accepted", "author_candidate_parses")}
    effort = (STUDY.read_json(effort_log) if effort_log else
              STUDY.read_json(HERE / "effort-log.template.json"))
    labour_keys = ("human_authoring_review", "agent_review", "evidence_acquisition",
                   "host_compute_and_transport", "explanation_adjudication")
    effort_complete = all(effort.get(name, {}).get("status") == "measured" for name in labour_keys)
    author_diffs = {"groups_with_three_completed": 0, "second_source_changed": 0,
                    "third_source_changed": 0}
    for answers in revisions.values():
        if set(answers) == {0, 1, 2}:
            author_diffs["groups_with_three_completed"] += 1
            author_diffs["second_source_changed"] += int(answers[0] != answers[1])
            author_diffs["third_source_changed"] += int(answers[1] != answers[2])
    return {
        "schema": "eal2-deployment-800-analysis/1", "freeze_sha256": frozen["freeze_sha256"],
        "status": ledger["status"], "review_status": frozen["review_status"],
        "material_drift": material_drift, "totals": summed, "arms": labelled,
        "author_revision_changes": author_diffs,
        "primary_provider_tokens_per_faithful_qualified_decision": {
            "status": "unavailable", "reason": "Post-author source fidelity and recipient explanation have not been independently adjudicated; eight roots share a generator."},
        "all_in_cost_per_correctly_accepted_decision": {
            "status": "unavailable" if not effort_complete else "pending_faithful_decision_adjudication",
            "reason": "Authoring/review/acquisition/host/explanation effort and faithful accepted denominator require observed records."},
        "limitations": ["Developer A/B are isolated model sessions, not human engineers",
                        "One template generator underlies eight domain variants",
                        "The source and graph are single-author synthetic material",
                        "The balanced incomplete Stage 1 is an A1 amendment to erroneous original arithmetic",
                        "A forced one-call native function request has no recipient explanation turn",
                        "No physical telemetry authenticity or two-percentage-point noninferiority inference"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--effort-log", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.directory, args.effort_log)
    contents = json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(contents, encoding="utf-8")
    else:
        print(contents)


if __name__ == "__main__":
    main()
