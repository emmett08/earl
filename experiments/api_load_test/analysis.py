"""Prespecified paired summaries; missing attempts remain in denominators."""

from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path
import random
import statistics

from .materials import ARMS, PROFILES


def paired_interval(pairs: list[dict], *, alpha: float, seed: int, draws: int):
    if len(pairs) < 20 or any(sum(row["profile"] == name for row in pairs) < 5 for name in PROFILES):
        return None
    groups = [[row["difference"] for row in pairs if row["profile"] == name] for name in PROFILES]
    rng = random.Random(seed)
    estimates = sorted(statistics.mean(statistics.mean(rng.choices(group, k=len(group))) for group in groups)
                       for _ in range(draws))
    return [estimates[max(0, math.floor(draws * alpha / 2))],
            estimates[min(draws - 1, math.ceil(draws * (1 - alpha / 2)) - 1)]]


def decision_interval(pairs: list[dict], *, alpha: float):
    """Hoeffding bound for independent paired differences in [-1, 1]."""
    if len(pairs) < 20 or any(sum(row["profile"] == name for row in pairs) < 5 for name in PROFILES):
        return None
    mean = statistics.mean(row["difference"] for row in pairs)
    radius = math.sqrt(2 * math.log(2 / alpha) / len(pairs))
    return [max(-1, mean - radius), min(1, mean + radius)]


def summarise(output: Path) -> dict:
    manifest = json.loads((output / "manifest.json").read_text())
    plan = manifest["plan"]
    rows = []
    for assignment in manifest["assignments"]:
        path = output / "trials" / assignment["id"] / "trial.json"
        row = json.loads(path.read_text()) if path.exists() else {**assignment, "state": "not_attempted"}
        rows.append(row)
    by_cell = defaultdict(list)
    for row in rows:
        by_cell[row["model"], row["arm"]].append(row)
    cells = []
    for (model, arm), values in sorted(by_cell.items()):
        calls = [call for row in values for call in row.get("model_calls", [])]
        responses = [call["response"] for call in calls if call.get("response")]
        known_costs = [call["estimated_usd"] for call in calls if call.get("estimated_usd") is not None]
        outcome = lambda name: sum(bool(row.get("outcome", {}).get(name)) for row in values)
        cells.append({"model": model, "arm": arm, "assigned": len(values),
                      "completed": sum(row.get("state") == "complete" for row in values),
                      "correct": outcome("correct"), "accuracy": outcome("correct") / len(values),
                      "false_support": outcome("false_support"),
                      "unsupported_assertion_without_collection": outcome("unsupported_assertion_without_collection"),
                      "model_calls": len(calls),
                      "input_tokens_known": sum(item.get("input_tokens") or 0 for item in responses),
                      "output_tokens_known": sum(item.get("output_tokens") or 0 for item in responses),
                      "reasoning_tokens_known": sum(item.get("metadata", {}).get("reasoning_tokens", 0) for item in responses),
                      "estimated_usd_known": sum(known_costs), "unknown_cost_calls": len(calls) - len(known_costs),
                      "median_seconds_attempted": statistics.median([row["seconds"] for row in values if "seconds" in row])
                          if any("seconds" in row for row in values) else None})
    contrasts = []
    for spec in manifest["models"]:
        lookup = {(row["block"], row["arm"]): row for row in rows if row["model"] == spec["id"]}
        for comparator in ARMS[1:]:
            pairs = []
            for (block, arm), eal in lookup.items():
                if arm != "eal_mcp":
                    continue
                baseline = lookup[block, comparator]
                pairs.append({"profile": eal["profile"], "difference": int(bool(eal.get("outcome", {}).get("correct")))
                              - int(bool(baseline.get("outcome", {}).get("correct")))})
            primary = comparator in {"json_prompt", "plain_brief"}
            # Eight planned primary contrasts across all four snapshots even
            # when this invocation executes a selected subset of models.
            alpha = 0.05 / 8 if primary else 0.05
            interval = decision_interval(pairs, alpha=alpha)
            complete = all(row.get("state") == "complete" for row in lookup.values())
            contrast = {"model": spec["id"], "class": spec["class"], "size": spec["size"],
                        "comparator": comparator, "primary": primary, "paired_blocks": len(pairs),
                        "accuracy_difference": statistics.mean(row["difference"] for row in pairs),
                        "interval": interval, "interval_level": 1 - alpha,
                        "exploratory_bootstrap_interval": paired_interval(
                            pairs, alpha=alpha, seed=plan["seed"], draws=plan["bootstrap_replicates"]),
                        "interpretation": "descriptive_only"}
            if manifest["mode"] == "study" and complete and interval is not None:
                contrast["interpretation"] = ("bounded_advantage" if interval[0] > plan["practical_difference"] else
                                              "bounded_disadvantage" if interval[1] < -plan["practical_difference"] else
                                              "inconclusive")
            contrasts.append(contrast)
    return {"schema": "eal-api-experiment-summary/1", "mode": manifest["mode"],
            "assigned": len(rows), "complete": all(row.get("state") == "complete" for row in rows),
            "cells": cells, "contrasts": contrasts,
            "scope": plan["scope"],
            "interval_method": "Hoeffding bounds for independent paired differences; eight primary contrasts use Bonferroni levels. Profile-stratified paired bootstrap is exploratory only. Secondary bounds are unadjusted.",
            "limitations": ["One controlled API; no production or universal model-class claim.",
                            "Small/large are product tiers, not known parameter counts.",
                            "Fresh HTTP measurements differ across arms; the reference is specific to each trial.",
                            "EAL combines notation, MCP execution and checking; this is not a notation-only effect.",
                            "Smoke runs establish execution only; incomplete runs remain descriptive."]}


def markdown(summary: dict) -> str:
    lines = ["# API load-test experiment", "", f"Mode: **{summary['mode']}**. Complete: **{summary['complete']}**.", "",
             "| Model | Arm | Correct / assigned | False support | Calls | Known cost (USD) |",
             "| --- | --- | ---: | ---: | ---: | ---: |"]
    for cell in summary["cells"]:
        lines.append(f"| {cell['model']} | {cell['arm']} | {cell['correct']}/{cell['assigned']} | "
                     f"{cell['false_support']} | {cell['model_calls']} | {cell['estimated_usd_known']:.4f} |")
    lines += ["", "Costs use the frozen standard token rates. Missing usage remains unknown; the report is not a provider invoice.",
              "", "## Paired contrasts", "", "| Model | EAL minus comparator | Difference | Interval | Interpretation |",
              "| --- | --- | ---: | --- | --- |"]
    for row in summary["contrasts"]:
        interval = "Insufficient blocks" if row["interval"] is None else f"[{row['interval'][0]:.3f}, {row['interval'][1]:.3f}]"
        lines.append(f"| {row['model']} | {row['comparator']} | {row['accuracy_difference']:.3f} | {interval} | {row['interpretation']} |")
    lines += ["", summary["scope"], ""]
    return "\n".join(lines)
