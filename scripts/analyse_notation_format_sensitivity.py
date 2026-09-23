#!/usr/bin/env python3
"""Post-hoc format/claim-map sensitivity; never rewrite primary records or call models."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import analyse_notation_transfer as primary

SCHEMA = "EAL/notation-format-sensitivity/2"
FENCE = re.compile(r"\A```(?:json)?\r?\n(?P<body>[\s\S]*?)\r?\n```\Z")


def fence_answer(text, expected):
    """Admit one whole json/unlabelled fence, with surrounding whitespace only.

    Opening and closing fences occupy their own lines. The unchanged body must
    satisfy the primary JSON/schema contract: no extraction, repair or coercion.
    """
    if not isinstance(text, str):
        return None
    match = FENCE.fullmatch(text.strip(" \t\r\n"))
    return primary.admitted_answer({"text": match["body"]}, expected) if match else None


def claim_map_answer(text, expected):
    """Read exact requested labels from strict raw JSON; ignore other top-level fields.

    This is label agreement only, never primary contract success. No fence
    removal, text extraction, missing-label repair or value coercion occurs.
    """
    if not isinstance(text, str):
        return None
    try:
        decoded = primary.strict_json(text)
        if (not isinstance(decoded, dict) or not isinstance(decoded.get("claims"), dict)
                or set(decoded["claims"]) != set(expected)
                or any(value not in primary.STATUSES for value in decoded["claims"].values())):
            return None
        return decoded["claims"]
    except (ValueError, TypeError):
        return None


def trial_result(record, task):
    strict = (primary.admitted_answer(record.get("response"), task["expected"])
              if record["state"] == "responded" else None)
    recovered = (fence_answer((record.get("response") or {}).get("text"), task["expected"])
                 if record["state"] == "malformed_response" else None)
    sensitivity = strict if strict is not None else recovered
    claim_map = (claim_map_answer((record.get("response") or {}).get("text"), task["expected"])
                 if record["state"] in {"responded", "malformed_response"} else None)
    result = dict(trial_id=record["trial_id"], task_id=record["task_id"],
                  repetition=record["repetition"], condition=record["condition"],
                  primary_state=record["state"], freeze_digest=record["freeze_digest"],
                  messages_digest=record["messages_digest"],
                  primary_record_digest=primary.digest(record),
                  response_text_sha256=(hashlib.sha256(record["response"]["text"].encode()).hexdigest()
                                        if isinstance(record.get("response"), dict)
                                        and isinstance(record["response"].get("text"), str) else None),
                  recovered_by_fence_removal=recovered is not None,
                  recovered_by_claim_map_only=strict is None and claim_map is not None, modes={})
    analysis_records = {}
    for mode, answer in (("strict", strict), ("fence_only", sensitivity), ("claim_map_only", claim_map)):
        scores = {}
        # These copies are used only in memory for paired sensitivity contrasts.
        analysis_record = dict(record)
        for oracle in primary.ORACLES:
            reference = (task["expected"] if oracle == "full_information" else
                         task["available_information_references"][record["condition"]["information"]])
            score = primary.expected_score(reference, answer)
            scores[oracle] = dict(correct=score["correct"], false_support=score["unjustified"])
            analysis_record[primary.ORACLES[oracle]] = score
        admission = "claim_map_admitted" if mode == "claim_map_only" else "wellformed"
        result["modes"][mode] = {admission: answer is not None, "metrics": scores}
        analysis_records[mode] = analysis_record
    return result, analysis_records


def summarise(rows, scheduled, uncertain):
    count = len(rows)
    result = dict(scheduled=scheduled, finalized_attempts=count, uncertain_attempts=uncertain,
                  missing_scheduled=scheduled - count - uncertain,
                  provider_errors=sum(r["primary_state"] == "provider_error" for r in rows),
                  primary_malformed_responses=sum(r["primary_state"] == "malformed_response" for r in rows),
                  recovered_by_fence_removal=sum(r["recovered_by_fence_removal"] for r in rows),
                  recovered_by_claim_map_only=sum(r["recovered_by_claim_map_only"] for r in rows), modes={})
    for mode in ("strict", "fence_only", "claim_map_only"):
        admission = "claim_map_admitted" if mode == "claim_map_only" else "wellformed"
        result["modes"][mode] = {
            admission: primary.rate(sum(r["modes"][mode][admission] for r in rows), count),
            "metrics": {oracle: {metric: primary.rate(
                sum(r["modes"][mode]["metrics"][oracle][metric] for r in rows), count)
                for metric in ("correct", "false_support")} for oracle in primary.ORACLES}}
    return result


def analyse(root):
    """Read one validated snapshot, retaining all finalized failures in denominators."""
    root = Path(root)
    frozen, schedule, records, uncertain, missing = primary.load_run(root)
    rows, mode_records = [], {mode: {} for mode in ("strict", "fence_only", "claim_map_only")}
    for trial_id, record in records.items():
        result, analysis_records = trial_result(record, frozen["tasks"][record["task_id"]])
        rows.append(result)
        for mode in mode_records:
            mode_records[mode][trial_id] = analysis_records[mode]
    result = dict(
        schema=SCHEMA, scoring_schema=frozen["scoring_schema"], freeze_digest=frozen["freeze_digest"],
        analysis_kind="post-hoc response-format sensitivity",
        selected_after_observing="Formatting failures in retained live responses; not prespecified.",
        acceptance_rule="Strict primary JSON, or exactly one whole ```json or unlabelled ``` block; "
                        "fences on separate lines, surrounding whitespace allowed. Its body must satisfy "
                        "the unchanged primary JSON/schema contract. Provider errors are never recovered.",
        claim_map_only_rule="Separately exploratory after observing extra top-level fields: strict raw JSON "
                            "object with claims containing exactly requested identifiers and valid status labels. "
                            "Ignore only other top-level fields and basis shape. No fence removal or repair. "
                            "This mode measures label agreement, not contract success or reasoning quality; "
                            "provider errors are never recovered.",
        interpretation="Primary outcomes remain unchanged. This is a descriptive sensitivity to output-format "
                       "compliance, not a validated reasoning score or proof of the cause of a notation difference. "
                       "False support counts only admitted answers; low false support alongside malformed "
                       "responses does not establish safe reasoning. No population p-values.",
        scheduled=len(schedule), finalized_attempts=len(records), uncertain_attempts=len(uncertain),
        missing_scheduled=len(missing), all_scheduled_finalized=not uncertain and not missing,
        uncertain_trial_ids=sorted(uncertain), missing_trial_ids=missing,
        analysis_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        primary_validator_sha256=hashlib.sha256(Path(primary.__file__).read_bytes()).hexdigest(),
        totals=summarise(rows, len(schedule), len(uncertain)), conditions=[], tasks=[], task_conditions=[],
        paired_comparisons={mode: primary.comparisons(frozen, items) for mode, items in mode_records.items()},
        trials=rows,
        uncertain_records=[dict(trial_id=r["trial_id"], freeze_digest=r["freeze_digest"],
                                messages_digest=r["messages_digest"], primary_record_digest=primary.digest(r))
                           for r in uncertain.values()])
    for condition in primary.conditions():
        chosen = [r for r in rows if r["condition"] == condition]
        scheduled_count = sum(r["condition"] == condition for r in schedule.values())
        uncertain_count = sum(r["condition"] == condition for r in uncertain.values())
        result["conditions"].append({**condition, **summarise(chosen, scheduled_count, uncertain_count)})
        for task_id in sorted(frozen["tasks"]):
            subset = [r for r in chosen if r["task_id"] == task_id]
            expected = sum(r["condition"] == condition and r["task_id"] == task_id for r in schedule.values())
            unknown = sum(r["condition"] == condition and r["task_id"] == task_id for r in uncertain.values())
            result["task_conditions"].append(dict(task_id=task_id, **condition,
                                                   **summarise(subset, expected, unknown)))
    for task_id, task in sorted(frozen["tasks"].items()):
        chosen = [r for r in rows if r["task_id"] == task_id]
        expected = sum(r["task_id"] == task_id for r in schedule.values())
        unknown = sum(r["task_id"] == task_id for r in uncertain.values())
        result["tasks"].append(dict(task_id=task_id, family=task["family"],
                                   **summarise(chosen, expected, unknown)))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    # Output is stdout only: the analyser cannot overwrite any primary run file.
    print(json.dumps(analyse(args.run), indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
