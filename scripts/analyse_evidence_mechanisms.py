#!/usr/bin/env python3
"""Reanalyse retained notation-transfer trials without calling a model.

This is a post-outcome descriptive analysis. It separates output-contract
admission, label agreement, proposal copying, and paired changes under the two
frozen references. Neither a copied label nor a public basis proves reasoning.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import analyse_notation_format_sensitivity as sensitivity
import analyse_notation_transfer as primary

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "benchmarks/results/2026-09-23-notation-transfer-live"
OUTPUT = ROOT / "benchmarks/results/2026-09-23-evidence-mechanisms/analysis.json"
SCHEMA = "EAL/evidence-mechanisms-retrospective/1"
MODES = ("strict", "claim_map")
ORACLES = ("full_information", "available_information")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_sources(run: Path, frozen: dict, records: dict) -> dict:
    manifest = primary.strict_json((run / "records-manifest.json").read_text())
    require(manifest["freeze_digest"] == frozen["freeze_digest"], "Manifest freeze mismatch")
    archive_digest = sha256((run / "trials.tar.gz").read_bytes())
    require(archive_digest == manifest["archive_sha256"], "Trial archive digest mismatch")
    members = dict(primary.trial_files(run))
    require(manifest["trial_count"] == len(records) == len(members), "Manifest trial count mismatch")
    require({Path(name).name for name in members} == set(manifest["trial_sha256"]),
            "Manifest trial filenames mismatch")
    for name, content in members.items():
        require(sha256(content) == manifest["trial_sha256"][Path(name).name],
                f"Manifest digest mismatch: {name}")
    return {"archive_sha256": archive_digest,
            "manifest_sha256": sha256((run / "records-manifest.json").read_bytes()),
            "freeze_digest": frozen["freeze_digest"],
            "primary_validator_sha256": sha256(Path(primary.__file__).read_bytes()),
            "claim_map_parser_sha256": sha256(Path(sensitivity.__file__).read_bytes()),
            "analysis_script_sha256": sha256(Path(__file__).read_bytes())}


def one_trial(record: dict, task: dict) -> dict:
    condition = record["condition"]
    proposal = primary.proposal(task["expected"], condition["candidate_quality"],
                                record["repetition"])
    strict = (primary.admitted_answer(record.get("response"), task["expected"])
              if record["state"] == "responded" else None)
    claim_map = (sensitivity.claim_map_answer((record.get("response") or {}).get("text"),
                                               task["expected"])
                 if record["state"] in {"responded", "malformed_response"} else None)
    require((strict is not None) == (record["state"] == "responded"),
            f"Primary admission mismatch: {record['trial_id']}")
    require(strict is None or strict == claim_map,
            f"Claim-map parser changed a strict answer: {record['trial_id']}")
    item = {"trial_id": record["trial_id"], "task_id": record["task_id"],
            "repetition": record["repetition"], "condition_id": condition["id"],
            "state": record["state"], "proposal": proposal,
            "strict_answer": strict, "claim_map_answer": claim_map, "modes": {}}
    for mode, answer in (("strict", strict), ("claim_map", claim_map)):
        mode_row = {"admitted": answer is not None,
                    "copied_proposal": answer == proposal if answer is not None and proposal is not None else None,
                    "oracles": {}}
        for oracle in ORACLES:
            ref = (task["expected"] if oracle == "full_information" else
                   task["available_information_references"][condition["information"]])
            score = primary.expected_score(ref, answer)
            if mode == "strict":
                require(score == record[primary.ORACLES[oracle]],
                        f"Primary score mismatch: {record['trial_id']} / {oracle}")
            proposal_correct = proposal == ref if proposal is not None else None
            mode_row["oracles"][oracle] = {
                "reference": ref,
                "correct": score["correct"],
                "false_support": score["unjustified"],
                "proposal_correct": proposal_correct,
                "corrected_wrong_proposal": score["correct"] if proposal_correct is False else None,
                "damaged_correct_proposal": not score["correct"] if proposal_correct is True else None,
                "copied_wrong_proposal": answer == proposal if answer is not None and proposal_correct is False else None,
            }
        item["modes"][mode] = mode_row
    return item


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    result = {"attempts": n,
              "states": dict(sorted(Counter(row["state"] for row in rows).items())),
              "proposal_present_attempts": sum(row["proposal"] is not None for row in rows),
              "modes": {}}
    for mode in MODES:
        admitted = [row for row in rows if row["modes"][mode]["admitted"]]
        present = [row for row in admitted if row["proposal"] is not None]
        copied = sum(row["modes"][mode]["copied_proposal"] for row in present)
        mode_result = {
            "admitted": len(admitted),
            "copied_proposal": copied,
            "proposal_present_attempts": result["proposal_present_attempts"],
            "admitted_with_proposal": len(present),
            "oracles": {},
        }
        for oracle in ORACLES:
            values = [row["modes"][mode]["oracles"][oracle] for row in rows]
            correct_proposals = [v for v in values if v["proposal_correct"] is True]
            wrong_proposals = [v for v in values if v["proposal_correct"] is False]
            copied_wrong = sum(v["copied_wrong_proposal"] is True for v in wrong_proposals)
            mode_result["oracles"][oracle] = {
                "correct": sum(v["correct"] for v in values),
                "false_support": sum(v["false_support"] for v in values),
                "correct_proposal_attempts": len(correct_proposals),
                "damaged_correct_proposal": sum(v["damaged_correct_proposal"] for v in correct_proposals),
                "wrong_proposal_attempts": len(wrong_proposals),
                "corrected_wrong_proposal": sum(v["corrected_wrong_proposal"] for v in wrong_proposals),
                "copied_wrong_proposal": copied_wrong,
            }
        result["modes"][mode] = mode_result
    return result


def pair_specs() -> list[tuple[str, str, str]]:
    result = [("notation_raw_only", "eal_raw_only", "json_raw_only")]
    for n in ("eal", "json"):
        for quality in ("correct", "incorrect"):
            prefix = f"{n}_{quality}_answer"
            result.extend([
                (f"{n}_{quality}_raw_minus_answer", prefix + "_raw", prefix),
                (f"{n}_{quality}_assessed_minus_raw", prefix + "_assessed", prefix + "_raw"),
                (f"{n}_{quality}_raw_minus_irrelevant", prefix + "_raw", prefix + "_irrelevant"),
            ])
    return result


def pair_summary(pairs: list[tuple[dict, dict]], mode: str, oracle: str) -> dict:
    compared = []
    for left, right in pairs:
        a = left["modes"][mode]["oracles"][oracle]
        b = right["modes"][mode]["oracles"][oracle]
        compared.append({"task_id": left["task_id"], "repetition": left["repetition"],
                         "left_trial_id": left["trial_id"], "right_trial_id": right["trial_id"],
                         "left_correct": a["correct"], "right_correct": b["correct"],
                         "left_copied_proposal": left["modes"][mode]["copied_proposal"],
                         "right_copied_proposal": right["modes"][mode]["copied_proposal"],
                         "reference_changed": a["reference"] != b["reference"],
                         "proposal_correctness_changed": a["proposal_correct"] != b["proposal_correct"]})
    return {
        "pairs": len(pairs),
        "both_correct": sum(c["left_correct"] and c["right_correct"] for c in compared),
        "left_only_correct": sum(c["left_correct"] and not c["right_correct"] for c in compared),
        "right_only_correct": sum(not c["left_correct"] and c["right_correct"] for c in compared),
        "neither_correct": sum(not c["left_correct"] and not c["right_correct"] for c in compared),
        "left_recovers_right_failure": sum(c["left_correct"] and not c["right_correct"] for c in compared),
        "left_damages_right_success": sum(not c["left_correct"] and c["right_correct"] for c in compared),
        "reference_changed_pairs": sum(c["reference_changed"] for c in compared),
        "proposal_correctness_changed_pairs": sum(c["proposal_correctness_changed"] for c in compared),
        "paired_blocks": compared,
    }


def pairs_by_task(trials: list[dict], tasks: dict) -> list[dict]:
    indexed = {(row["task_id"], row["repetition"], row["condition_id"]): row for row in trials}
    result = []
    for name, left_id, right_id in pair_specs():
        groups = defaultdict(list)
        for task_id, repetition, condition_id in sorted(indexed):
            if condition_id == left_id:
                left, right = indexed[(task_id, repetition, left_id)], indexed[(task_id, repetition, right_id)]
                require(left["proposal"] == right["proposal"] or name == "notation_raw_only",
                        f"Pair proposal mismatch: {name} / {task_id} / {repetition}")
                groups[task_id].append((left, right))
        require(set(groups) == set(tasks) and all(len(group) == 2 for group in groups.values()),
                f"Incomplete paired contrast: {name}")
        all_pairs = [pair for group in groups.values() for pair in group]
        result.append({"name": name, "left": left_id, "right": right_id,
                       "modes": {mode: {oracle: pair_summary(all_pairs, mode, oracle)
                                        for oracle in ORACLES} for mode in MODES},
                       "by_task": {task: {mode: {oracle: pair_summary(group, mode, oracle)
                                                 for oracle in ORACLES} for mode in MODES}
                                   for task, group in sorted(groups.items())}})
    return result


def verify_reanalysis(run: Path, frozen: dict, trials: list[dict], totals: dict,
                      conditions: list[dict]) -> None:
    report = primary.strict_json((run / "report.json").read_text())
    posthoc = primary.strict_json((run / "format-sensitivity.json").read_text())
    require(posthoc["freeze_digest"] == frozen["freeze_digest"], "Sensitivity freeze mismatch")
    require(report["scheduled"] == report["attempted"] == len(trials) == 180,
            "Expected 180 fully retained trials")
    require(totals["states"] == {"malformed_response": 18, "provider_error": 1, "responded": 161},
            "Unexpected primary admission totals")
    require(totals["modes"]["claim_map"]["admitted"] ==
            posthoc["totals"]["modes"]["claim_map_only"]["claim_map_admitted"]["count"],
            "Claim-map admission disagrees with recorded sensitivity")
    for mode, historical in (("strict", "strict"), ("claim_map", "claim_map_only")):
        for oracle in ORACLES:
            aggregate = totals["modes"][mode]["oracles"][oracle]
            frozen_metrics = posthoc["totals"]["modes"][historical]["metrics"][oracle]
            require(aggregate["correct"] == frozen_metrics["correct"]["count"] and
                    aggregate["false_support"] == frozen_metrics["false_support"]["count"],
                    f"Mode totals disagree with archived sensitivity: {mode}/{oracle}")
    for row in conditions:
        archived = report["conditions"][row["condition_id"]]
        strict = row["modes"]["strict"]["oracles"]
        require(row["attempts"] == archived["attempted"] and
                strict["full_information"]["correct"] == archived["correct"] and
                strict["available_information"]["correct"] == archived["available_information_correct"],
                f"Primary condition totals disagree: {row['condition_id']}")
    sensitivity_trials = {row["trial_id"]: row for row in posthoc["trials"]}
    require(set(sensitivity_trials) == {row["trial_id"] for row in trials},
            "Sensitivity trial identities differ")
    for row in trials:
        old = sensitivity_trials[row["trial_id"]]
        require(row["modes"]["claim_map"]["admitted"] is
                old["modes"]["claim_map_only"]["claim_map_admitted"],
                f"Claim-map trial admission mismatch: {row['trial_id']}")
        for oracle in ORACLES:
            require(row["modes"]["claim_map"]["oracles"][oracle]["correct"] is
                    old["modes"]["claim_map_only"]["metrics"][oracle]["correct"],
                    f"Claim-map trial score mismatch: {row['trial_id']} / {oracle}")


def analyse(run: Path) -> dict:
    frozen, schedule, records, uncertain, missing = primary.load_run(run)
    require(not uncertain and not missing and len(schedule) == len(records),
            "Retrospective requires complete scheduled coverage")
    provenance = verify_sources(run, frozen, records)
    trials = [one_trial(records[trial_id], frozen["tasks"][records[trial_id]["task_id"]])
              for trial_id in sorted(records)]
    totals = summarise(trials)
    conditions = [{"condition_id": condition["id"], **summarise(
        [row for row in trials if row["condition_id"] == condition["id"]])}
        for condition in primary.conditions()]
    task_conditions = [{"task_id": task, "family": frozen["tasks"][task]["family"],
                        "condition_id": condition["id"], **summarise(
        [row for row in trials if row["task_id"] == task and row["condition_id"] == condition["id"]])}
        for task in sorted(frozen["tasks"]) for condition in primary.conditions()]
    verify_reanalysis(run, frozen, trials, totals, conditions)
    return {
        "schema": SCHEMA, "analysis_kind": "Post-outcome descriptive reanalysis; no model calls",
        "source": "benchmarks/results/2026-09-23-notation-transfer-live",
        "provenance": provenance, "tasks": sorted(frozen["tasks"]),
        "repetitions_per_task": frozen["plan"]["repetitions"],
        "denominators": "Attempts include malformed and provider-error responses. Copying has a proposal-present attempt denominator and an admitted-with-proposal denominator; missing answers never count as copies. A wrong/correct proposal is classified separately under each oracle. Pair recovery/damage counts are left-only/right-only correctness in matched task/repetition slots; they are descriptive outcome changes, not proof of a cognitive correction mechanism. Repetitions are dependent.",
        "limitations": ["The response label map and public basis do not establish a cognitive mechanism or valid derivation.",
                        "Claim-map admission ignores extra top-level fields; it is a post-hoc label diagnostic, not response-contract success.",
                        "Changing to irrelevant records changes the available-information reference; its pair outcomes are not a same-target causal contrast.",
                        "Five exposed task types cannot support population inference; these contrasts were selected after outcomes."],
        "totals": totals, "conditions": conditions, "task_conditions": task_conditions,
        "paired_contrasts": pairs_by_task(trials, frozen["tasks"]), "trials": trials,
    }


def compact(result: dict) -> dict:
    """Retain reviewable aggregates; the archive and --detailed recover every row."""
    small = deepcopy(result)
    small.pop("trials")
    for contrast in small["paired_contrasts"]:
        for partition in (contrast["modes"], *contrast["by_task"].values()):
            for mode in partition.values():
                for oracle in mode.values():
                    oracle.pop("paired_blocks")
    small["detail_note"] = "Use --detailed for all per-trial classifications and matched trial IDs; the original 180 raw responses remain in the verified archive."
    return small


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=RUN)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--detailed", action="store_true", help="Include every trial and matched trial ID")
    args = parser.parse_args()
    result = analyse(args.run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result if args.detailed else compact(result), indent=2,
                                      ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps({"output": str(args.output), "attempts": result["totals"]["attempts"],
                      "strict_correct_full": result["totals"]["modes"]["strict"]["oracles"]["full_information"]["correct"],
                      "claim_map_correct_full": result["totals"]["modes"]["claim_map"]["oracles"]["full_information"]["correct"]}))


if __name__ == "__main__":
    main()
