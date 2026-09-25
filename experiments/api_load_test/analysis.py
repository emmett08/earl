"""Descriptive paired outcomes for a fixed, reviewed development case suite.

Cases are selected rather than probability-sampled. These observed differences
are finite-suite quantities, with no superiority or equivalence inference.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics

OUTCOMES = ("correct", "status_correct", "metrics_correct", "evidence_selection_correct",
            "scope_correct", "failed_checks_correct", "unknown_checks_correct", "false_support", "false_rejection",
            "false_unavailable", "correct_unavailable", "unsupported_assertion_without_collection")


def _correct(row):
    return row["state"] == "complete" and bool(row.get("outcome", {}).get("correct"))


def _table(pairs):
    counts = Counter((_correct(a), _correct(b)) for a, b in pairs)
    return {"both_correct": counts[True, True], "reference_only_correct": counts[True, False],
            "comparator_only_correct": counts[False, True], "both_incorrect": counts[False, False]}


def summarise(output: Path) -> dict:
    manifest = json.loads((output / "manifest.json").read_text())
    if manifest["schema"] != "eal-api-experiment-run/3":
        raise ValueError("Earlier runs retain their original reports; this analysis requires a v3 manifest")
    rows, identities = [], set()
    for assignment in manifest["assignments"]:
        if assignment["id"] in identities:
            raise ValueError("Duplicate assignment ID")
        identities.add(assignment["id"])
        path = output / "trials" / assignment["id"] / "trial.json"
        row = json.loads(path.read_text()) if path.exists() else {**assignment, "state": "not_attempted"}
        if any(row.get(key) != value for key, value in assignment.items()):
            raise ValueError("Trial identity differs from the frozen assignment")
        if row.get("state") not in {"complete", "failed", "not_attempted"}:
            raise ValueError("Trial state must be complete, failed or not_attempted before analysis")
        row = {**row, "transport": row.get("transport", manifest["transport"])}
        rows.append(row)
    if not rows:
        raise ValueError("No assigned development cases")
    by_cell = defaultdict(list)
    for row in rows:
        by_cell[row["model"], row["transport"], row["arm"]].append(row)
    cells = []
    for (model, transport, arm), values in sorted(by_cell.items()):
        calls = [call for row in values for call in row.get("model_calls", [])]
        responses = [call["response"] for call in calls if call.get("response")]
        costs = [call["estimated_usd"] for call in calls if call.get("estimated_usd") is not None]
        outcomes = {key: sum(bool(row.get("outcome", {}).get(key)) for row in values) for key in OUTCOMES}
        outcomes["correct"] = sum(_correct(row) for row in values)
        states = Counter(row["state"] for row in values)
        cells.append({"model": model, "transport": transport, "arm": arm,
                      "assigned": len(values), "distinct_cases": len({row["case_id"] for row in values}),
                      "completed": states["complete"], "failed": states["failed"],
                      "not_attempted": states["not_attempted"], "states": dict(states),
                      "failure_categories": dict(sorted(Counter(
                          row.get("failure") or "unspecified" for row in values if row["state"] == "failed").items())),
                      "not_attempted_reasons": dict(sorted(Counter(
                          row.get("failure") or "no_retained_trial" for row in values
                          if row["state"] == "not_attempted").items())),
                      "provider_error_categories": dict(sorted(Counter(
                          call.get("category") or "unclassified" for call in calls if call.get("error")).items())),
                      "protocol_errors": sum(len(row.get("protocol_errors", [])) for row in values), **outcomes,
                      "accuracy": outcomes["correct"] / len(values),
                      "model_calls": len(calls),
                      "input_tokens_known": sum(item.get("input_tokens") or 0 for item in responses),
                      "output_tokens_known": sum(item.get("output_tokens") or 0 for item in responses),
                      "reasoning_tokens_known": sum(item.get("metadata", {}).get("reasoning_tokens", 0) for item in responses),
                      "estimated_usd_known": sum(costs), "unknown_cost_calls": len(calls) - len(costs),
                      "median_seconds_attempted": (statistics.median(row["seconds"] for row in values if "seconds" in row)
                                                    if any("seconds" in row for row in values) else None)})
    contrasts = []
    arms = manifest["plan"]["arms"]
    comparisons = [("eal_mcp", arm) for arm in arms if arm != "eal_mcp"] if "eal_mcp" in arms else []
    if {"plain_validator", "plain_explicit"} <= set(arms):
        comparisons.append(("plain_validator", "plain_explicit"))
    for model, transport in sorted({(row["model"], row["transport"]) for row in rows}):
        values = [row for row in rows if row["model"] == model and row["transport"] == transport]
        lookup = {}
        for row in values:
            key = (row["block"], row["arm"])
            if key in lookup:
                raise ValueError("Duplicate paired block and arm")
            lookup[key] = row
        for reference_arm, comparator in comparisons:
            pairs = []
            blocks = sorted({block for block, arm in lookup if arm in {reference_arm, comparator}})
            for block in blocks:
                if (block, reference_arm) not in lookup or (block, comparator) not in lookup:
                    raise ValueError("A planned comparison is missing its paired assignment")
                reference_row = lookup[block, reference_arm]
                baseline = lookup[block, comparator]
                if reference_row["case_id"] != baseline["case_id"]:
                    raise ValueError("Paired assignments address different cases")
                pairs.append((reference_row, baseline))
            if not pairs:
                raise ValueError("No assignments in planned paired comparison")
            table = _table(pairs)
            completed_pairs = [(a, b) for a, b in pairs if a["state"] == b["state"] == "complete"]
            cases = Counter(a["case_id"] for a, _ in pairs)
            contrasts.append({"model": model, "transport": transport,
                              "reference_arm": reference_arm, "comparator": comparator,
                              "paired_blocks": len(pairs), "paired_cases": len(cases),
                              "paired_completed": len(completed_pairs),
                              "case_repetitions": dict(sorted(cases.items())),
                              **table, "completed_pair_table": _table(completed_pairs),
                              "accuracy_difference": (table["reference_only_correct"] - table["comparator_only_correct"]) / len(pairs),
                              "interpretation": "development_suite_descriptive"})
    return {"schema": "eal-api-experiment-summary/3", "mode": manifest["mode"],
            "assigned": len(rows), "distinct_cases": len({row["case_id"] for row in rows}),
            "completed": sum(row["state"] == "complete" for row in rows),
            "failed": sum(row["state"] == "failed" for row in rows),
            "not_attempted": sum(row["state"] == "not_attempted" for row in rows),
            "complete": all(row["state"] == "complete" for row in rows),
            "cells": cells, "contrasts": contrasts, "scope": manifest["plan"]["scope"],
            "inference": "Reviewed development cases; no confirmatory inference authorised.",
            "limitations": ["Observed differences describe this finite suite, not a sampled task population.",
                            "Repeated sessions on one case are repetitions, not additional distinct cases.",
                            "Native and text-mediated transports are reported separately.",
                            "EAL combines notation, MCP execution and checking; the contrast does not isolate notation.",
                            "The ordinary validator uses explicit prose with direct checking; its contrast estimates the combined checking addition on this suite.",
                            "Missing, malformed and failed assignments remain in the denominator.",
                            "An efficacy study needs new held-out cases and a frozen, simulation-checked information plan."]}


def markdown(summary: dict) -> str:
    lines = ["# API load-test development pilot", "",
             f"Mode: **{summary['mode']}**. Complete: **{summary['complete']}**. "
             f"Distinct reviewed cases: **{summary['distinct_cases']}**.", "", summary["inference"], "",
             "## Assignment completion", "",
             "| Model | Transport | Arm | Assigned | Completed | Failed | Not attempted | Failure categories |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |"]
    for cell in summary["cells"]:
        categories = "; ".join(f"{key}: {count}" for key, count in cell["failure_categories"].items()) or "—"
        lines.append(f"| {cell['model']} | {cell['transport']} | {cell['arm']} | {cell['assigned']} | "
                     f"{cell['completed']} | {cell['failed']} | {cell['not_attempted']} | {categories} |")
    lines += ["", "Failed conversations and unattempted assignments count as incorrect in the assigned denominator. "
              "They are reported separately from completed answers with incorrect decisions.", "",
              "## Assigned-answer scores and resource use", "",
             "| Model | Transport | Arm | Correct / assigned | False support | False rejection | Calls | Unknown-cost calls | Known USD |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for cell in summary["cells"]:
        lines.append(f"| {cell['model']} | {cell['transport']} | {cell['arm']} | "
                     f"{cell['correct']}/{cell['assigned']} | {cell['false_support']} | {cell['false_rejection']} | "
                     f"{cell['model_calls']} | {cell['unknown_cost_calls']} | {cell['estimated_usd_known']:.4f} |")
    lines += ["", "Costs use frozen token rates; unknown usage remains unknown. HTTP requests and model calls are not independent cases.",
              "", "## Paired case outcomes", "",
              "| Model | Transport | Reference | Comparator | Cases / blocks | Both correct | Reference only | Comparator only | Both incorrect | Difference |",
              "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in summary["contrasts"]:
        lines.append(f"| {row['model']} | {row['transport']} | {row['reference_arm']} | {row['comparator']} | "
                     f"{row['paired_cases']}/{row['paired_blocks']} | {row['both_correct']} | {row['reference_only_correct']} | "
                     f"{row['comparator_only_correct']} | {row['both_incorrect']} | {row['accuracy_difference']:+.3f} |")
    lines += ["", "Differences are reference-arm minus comparator accuracy on the assigned development cases. "
              "A zero difference establishes an observed tie on this suite; it does not establish equivalence.",
              "", "## Full-answer disagreements among completed pairs", "",
              "| Model | Transport | Reference | Comparator | Completed pairs | Reference only correct | Comparator only correct |",
              "| --- | --- | --- | --- | ---: | ---: | ---: |"]
    for row in summary["contrasts"]:
        table = row["completed_pair_table"]
        lines.append(f"| {row['model']} | {row['transport']} | {row['reference_arm']} | {row['comparator']} | {row['paired_completed']} | "
                     f"{table['reference_only_correct']} | {table['comparator_only_correct']} |")
    lines += ["", "This diagnostic separates completed-answer disagreements from execution failures. "
              "Completion selects a subset; it does not replace the assigned denominator or establish an efficacy effect.",
              "", "## Decision components", "",
              "| Model | Transport | Arm | Evidence selection | Scope | Failed criteria | Unknown criteria | Status | Metrics | Assigned |",
              "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for cell in summary["cells"]:
        lines.append(f"| {cell['model']} | {cell['transport']} | {cell['arm']} | {cell['evidence_selection_correct']} | "
                     f"{cell['scope_correct']} | {cell['failed_checks_correct']} | {cell['unknown_checks_correct']} | {cell['status_correct']} | "
                     f"{cell['metrics_correct']} | {cell['assigned']} |")
    lines += ["", summary["scope"], "", "An efficacy study requires new held-out cases, an explicit effect margin "
              "and multiplicity family, and sample planning calibrated for paired discordance and dependence.", ""]
    return "\n".join(lines)
