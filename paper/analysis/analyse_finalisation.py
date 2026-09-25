"""Measure recorded model calls after independently checked nano-v3 packets.

This is a conditional trace-prefix analysis, not a new model experiment. It
retains every assignment and never credits an unattempted assignment. Run from
any directory with the project's dependencies installed (including jsonschema).
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout
from decimal import Decimal
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile

PAPER = Path(__file__).resolve().parents[1]
ROOT = PAPER.parent
_spec = importlib.util.spec_from_file_location("finalisation_historical_replay",
                                             Path(__file__).with_name("reproduce_nano.py"))
historical = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(historical)
sys.path.insert(0, str(ROOT))
from experiments.api_load_test.conversation import finish_answer

ARMS = ("eal_mcp", "plain_validator")
DECISION_FIELDS = ("status", "failed_checks", "unknown_checks", "metrics")
IMPLEMENTATION_BASE = "70a1bb1b0153a9038398c1ae21232aa29d2d2c57"


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def accounting(calls, rates):
    """Use the historical rate card, retaining unknown charges as unknown."""
    cost, unknown = Decimal(0), 0
    tokens = Counter(input=0, cached_input=0, uncached_input=0, output=0,
                     reasoning_reported=0)
    for call in calls:
        response = call.get("response")
        if response is None:
            historical.require(call.get("estimated_usd") is None,
                               "Missing response has a settled charge")
            unknown += 1
            continue
        cached = response["metadata"].get("cached_input_tokens", 0)
        uncached = response["input_tokens"] - cached
        historical.require(0 <= cached <= response["input_tokens"], "Invalid cached usage")
        amount = (uncached * Decimal(str(rates["input_usd_per_million"]))
                  + cached * Decimal(str(rates["cached_input_usd_per_million"]))
                  + response["output_tokens"] * Decimal(str(rates["output_usd_per_million"]))) / 1_000_000
        historical.require(call.get("estimated_usd") is not None
                           and abs(amount - Decimal(str(call["estimated_usd"]))) < Decimal("1e-10"),
                           "Recorded charge differs from historical usage and rates")
        cost += amount
        tokens.update(input=response["input_tokens"], cached_input=cached,
                      uncached_input=uncached, output=response["output_tokens"],
                      reasoning_reported=response["metadata"].get("reasoning_tokens", 0))
    return {"calls": len(calls), "known_cost_usd": str(cost),
            "unknown_cost_calls": unknown, "recorded_tokens": dict(tokens)}


def percentage(numerator, denominator):
    return str((Decimal(numerator) / Decimal(denominator) * 100).quantize(Decimal("0.0001")))


def analyse(data):
    provenance = historical.load(data / "provenance.json")
    historical.require(provenance["archive_sha256"] == historical.ARCHIVE_SHA256,
                       "Unexpected source archive")
    # Reuse the complete frozen replay: input/source hashes, case identities,
    # every original grade, all receipt checks and the exact original summary.
    with tempfile.TemporaryDirectory() as temporary, redirect_stdout(io.StringIO()):
        replay = historical.reproduce(data, Path(temporary))
    manifest = historical.load(data / "historical-manifest.json")
    oracle = historical.original_module("oracle", manifest)
    trials = records(data / "trials.jsonl")
    cases = {row["id"]: row for row in records(data / "cases.jsonl")}
    receipts = {row["id"]: row for row in records(data / "receipts.jsonl")}
    rates = manifest["models"][0]["pricing"]
    groups, all_prefix, all_suffix = [], [], []
    response_histories, transient_suffixes = [], []
    for arm in ARMS:
        assigned = [row for row in trials if row["arm"] == arm]
        attempted = [row for row in assigned if row["state"] != "not_attempted"]
        prefix, suffix = [], []
        receipt_matches, target_matches, answers_accepted = 0, 0, 0
        packet_checks, boundaries = 0, Counter()
        for row in assigned:
            if row["state"] == "not_attempted":
                continue
            case = cases[row["case_id"]]
            truth = oracle.reference(case)
            candidates = []
            for item in receipts[row["id"]]["packets"]:
                packet = item["packet"]
                if not all(key in packet for key in ("report_id", *DECISION_FIELDS)):
                    continue
                check = oracle.packet_reference_check(case, packet["report_id"], packet,
                    checked=True, host_status=row.get("host_assessments", {}).get(
                        packet["report_id"], {}).get("host_status"))
                historical.require(check["agrees"], "Selected report receipt differs from raw rows")
                packet_checks += 1
                candidates.append(item)
            historical.require(bool(candidates), "Attempted checked arm has no successful receipt")
            # Choose the first valid selected-report receipt, without using the
            # target reference to skip an earlier wrong selection.
            first = min(candidates, key=lambda item: item["after_turn"])
            packet, boundary = first["packet"], first["after_turn"]
            receipt_matches += 1
            target_matches += packet["report_id"] == truth["report_id"]
            answer = finish_answer({"operation": "finish", **{
                key: packet[key] for key in DECISION_FIELDS}}, packet, case)
            historical.require(all(answer[key] == packet[key] for key in DECISION_FIELDS),
                               "Host finalisation altered a checked decision field")
            grade = oracle.grade(answer, truth, collected=row["collected"],
                                 inspected_report_ids=[packet["report_id"]])
            answers_accepted += grade["correct"]
            kept = [call for call in row["model_calls"] if call["turn"] <= boundary]
            removed = [call for call in row["model_calls"] if call["turn"] > boundary]
            prefix.extend(kept)
            suffix.extend(removed)
            boundaries[boundary] += 1
            states = []
            for call in row["model_calls"]:
                response = call.get("response") or {}
                states.append({"turn": call["turn"], "call_state": call["state"],
                    "response_status": response.get("metadata", {}).get("status"),
                    "response_present": bool(response), "category": call.get("category"),
                    "segment": "prefix" if call["turn"] <= boundary else "suffix"})
                if call["turn"] > boundary and call.get("retryable"):
                    transient_suffixes.append({"id": row["id"], "arm": arm,
                        "turn": call["turn"], "category": call.get("category"),
                        "http_status": call.get("diagnostics", {}).get("http_status"),
                        "known_cost": call.get("estimated_usd") is not None})
            response_histories.append({"id": row["id"], "arm": arm, "case_id": row["case_id"],
                "historical_state": row["state"], "historical_failure": row["failure"],
                "historical_answer_correct": row["outcome"]["correct"],
                "first_checked_packet_after_turn": boundary, "selected_report_id": packet["report_id"],
                "selected_receipt_matches_raw_rows": True,
                "selection_matches_target": packet["report_id"] == truth["report_id"],
                "reconstructed_answer_grade": grade, "calls": states})
        whole, kept, removed = (accounting(calls, rates) for calls in (prefix + suffix, prefix, suffix))
        groups.append({"arm": arm, "assigned": len(assigned), "attempted": len(attempted),
            "not_attempted": len(assigned) - len(attempted),
            "historical_states": dict(Counter(row["state"] for row in assigned)),
            "historical_correct": sum(row.get("outcome", {}).get("correct", False) for row in assigned),
            "historical_incorrect_completed": sum(row["state"] == "complete"
                and not row["outcome"]["correct"] for row in assigned),
            "receipt_checks": packet_checks, "first_receipts_match_selected_raw_report": receipt_matches,
            "first_selections_match_target": target_matches, "reconstructed_answers_accepted": answers_accepted,
            "first_packet_turn_counts": {str(turn): count for turn, count in sorted(boundaries.items())},
            "observed": whole, "retained_prefix": kept, "avoidable_suffix": removed,
            "suffix_call_percent": percentage(removed["calls"], whole["calls"]),
            "suffix_known_cost_percent": percentage(removed["known_cost_usd"], whole["known_cost_usd"])})
        all_prefix.extend(prefix)
        all_suffix.extend(suffix)
    total, prefix, suffix = (accounting(calls, rates) for calls in
                            (all_prefix + all_suffix, all_prefix, all_suffix))
    verification = {
        "historical_scores_and_summary": replay["scores_and_summary"],
        "checked_decision_fields_preserved": True,
        "all_reconstructed_target_answers_match": all(
            group["reconstructed_answers_accepted"] == group["attempted"] for group in groups),
    }
    return {"schema": "eal-paper-finalisation-opportunity/1",
        "method": "Observed trace prefixes through the first independently verified selected-report packet; current host finalisation is graded separately against the historical target reference.",
        "evidence": {"run_id": provenance["github_run_id"], "run_attempt": provenance["github_run_attempt"],
            "archive_sha256": provenance["archive_sha256"], "run_commit": provenance["run_commit"],
            "historical_plan_version": provenance["protocol"], "model": manifest["models"][0]["id"],
            "candidate_base_commit": IMPLEMENTATION_BASE,
            "candidate_files_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                for name in ("experiments/api_load_test/conversation.py", "experiments/api_load_test/materials.py")},
            "historical_pricing_usd_per_million": rates},
        "all_arms_assignments": len(trials),
        "all_arms_states": dict(Counter(row["state"] for row in trials)),
        "checked_arms": groups,
        "combined": {"assigned": sum(group["assigned"] for group in groups),
            "attempted": sum(group["attempted"] for group in groups),
            "not_attempted": sum(group["not_attempted"] for group in groups),
            "observed": total, "retained_prefix": prefix, "avoidable_suffix": suffix,
            "suffix_call_percent": percentage(suffix["calls"], total["calls"]),
            "suffix_known_cost_percent": percentage(suffix["known_cost_usd"], total["known_cost_usd"])},
        "verification": verification, "transient_failures_in_suffix": transient_suffixes,
        "limitations": [
            "This replay measures removable recorded suffixes conditional on retaining the observed selection and tool-result prefixes; a changed prompt or tool contract can change future selection.",
            "Reconstructed answers measure host retention of checked output, not model-authored accuracy or an observed new-run success rate.",
            "All unattempted assignments remain unattempted. No later dispatches or recovery outcomes are assumed.",
            "The observed HTTP503 occurred after a correct packet. Removing that recorded suffix does not establish when a future provider outage would occur or how a retry would behave.",
            "Known costs use the historical rate card and recorded token classes. The unknown charge remains unknown; no current price, latency, wall-clock saving or provider bill is estimated.",
            "The suffix percentages are retrospective descriptive measurements, without a preregistered improvement threshold or a test of statistical significance.",
            "Host validation, evidence selection, independent reference checks and case identity remain necessary; the analysis does not replace them with reference-derived answers."],
        "response_state_histories": response_histories}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=PAPER / "data" / "nano-v3")
    parser.add_argument("--output", type=Path, default=PAPER / "results" / "finalisation-opportunity.json")
    args = parser.parse_args()
    result = analyse(args.data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    historical.write(args.output, result)
    print(json.dumps({"verification": result["verification"],
                      "combined": result["combined"]}, indent=2))
