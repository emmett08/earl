#!/usr/bin/env python3
"""Read-only analysis of the exact 960-case freeze and all attempted responses."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_mechanisms_960 as study  # noqa: E402


def _difference(rows: list[dict], cases: list[dict], left: str, right: str,
                *, metric: str = "available_information_correct") -> dict:
    mapped = {(row["index"]): row for row in rows}
    paired: dict[str, dict] = defaultdict(dict)
    for index, case in enumerate(cases):
        if index not in mapped or case["arm"] not in {left, right}:
            continue
        key = (case["notation"], case["reference"])
        paired[case["root_id"]].setdefault(key, {})[case["arm"]] = mapped[index]
    roots = {}
    for root, cells in paired.items():
        if len(cells) == 4 and all(set(arms) == {left, right} for arms in cells.values()):
            roots[root] = sum(int(arms[left][metric]) - int(arms[right][metric])
                              for arms in cells.values()) / 4
    complete = len(roots) == 24
    return {"left": left, "right": right, "metric": metric, "paired_roots": len(roots),
            "coverage_complete": complete, "root_differences": roots,
            "selected_root_mean_difference": statistics.mean(roots.values()) if complete else None}


def analyse(directory: Path) -> dict:
    directory = directory.resolve()
    frozen = study.strict_json((directory / "freeze.json").read_text(encoding="utf-8"))
    study.verify_freeze(frozen)
    ledger = study.strict_json((directory / "ledger.json").read_text(encoding="utf-8"))
    if ledger.get("schema") != study.LEDGER or ledger.get("freeze_sha256") != frozen["freeze_sha256"]:
        raise ValueError("Ledger does not identify the exact analysed freeze")
    cases, rows = frozen["schedule"], ledger["attempts"]
    if len(cases) != 960 or len(rows) > 960:
        raise ValueError("Invalid schedule or attempt count")
    indexes = [row.get("index") for row in rows]
    if len(indexes) != len(set(indexes)) or any(type(i) is not int or not 0 <= i < 960 for i in indexes):
        raise ValueError("Duplicated or out-of-bounds attempt")
    cells = defaultdict(list)
    families = defaultdict(list)
    parsed = []
    all_usage = Counter()
    model_cost = 0.0
    for row in rows:
        case = cases[row["index"]]
        if (row.get("case_id"), row.get("prompt_sha256")) != (case["id"], case["prompt_sha256"]):
            raise ValueError("Stored attempt does not match the frozen case")
        if row["state"] not in {"pending", "failed", "malformed", "completed"}:
            raise ValueError("Unknown attempt state")
        response = row.get("response")
        if row["state"] in {"completed", "malformed"}:
            if response is None or response["model"] not in frozen["plan"]["accepted_response_models"]:
                raise ValueError("Completed attempt does not have a pinned response model")
            expected = study._answer(response["text"], case["claim"])
            if (expected is None) != (row["state"] == "malformed"):
                raise ValueError("Stored response classification differs from strict parser")
            actual = expected["claims"][case["claim"]] if expected else None
            recomputed = {
                "answered_status": actual, "admitted": actual is not None,
                "available_information_correct": actual == case["available_reference"] if actual else False,
                "full_information_agreement": actual == case["full_information_reference"] if actual else False,
                "false_support": actual == "supported" and case["available_reference"] != "supported",
                "proposal_adopted": actual == case["proposal"] if actual and case["proposal"] else None,
            }
            if any(row.get(k) != v for k, v in recomputed.items()):
                raise ValueError("Stored scoring disagrees with the raw model answer")
            cost = study.response_cost(study.ModelResponse(**response), frozen["provider_identity"])
            if cost != row["cost_usd"]:
                raise ValueError("Recorded cost differs from frozen rates and provider usage")
        usage = row.get("usage")
        if usage:
            for key in ("input_tokens", "output_tokens", "cached_input_tokens"):
                if type(usage.get(key)) is not int or usage[key] < 0:
                    raise ValueError("Invalid measured token usage")
                all_usage[key] += usage[key]
        if row.get("cost_usd") is not None:
            model_cost += row["cost_usd"]
        parsed.append({"case": case, "row": row})
        cells[(case["arm"], case["notation"], case["reference"])].append(row)
        families[case["family"]].append(row)

    by_cell = {}
    for key in sorted(cells):
        items = cells[key]
        confusion = Counter((cases[row["index"]]["available_reference"],
                             row.get("answered_status") or "<no-admitted-answer>") for row in items)
        by_cell["/".join(key)] = {
            "attempted": len(items), "scheduled": 24,
            "correct_available": sum(row.get("available_information_correct", False) for row in items),
            # The frozen runner's hidden valid-state label is a continuity
            # comparator only for proposal-only calls. In arms that supply
            # invalid records, the available-information label is primary.
            "full_information_agreement": (sum(row.get("full_information_agreement", False)
                                               for row in items) if key[0] == "wrong_proposal_only" else None),
            "false_support": sum(row.get("false_support", False) for row in items),
            "malformed": sum(row["state"] == "malformed" for row in items),
            "provider_or_identity_failure": sum(row["state"] == "failed" for row in items),
            "proposal_adopted": sum(row.get("proposal_adopted") is True for row in items),
            "confusion": {" -> ".join(k): v for k, v in sorted(confusion.items())},
        }

    terminal = [row for row in rows if row["state"] != "pending"]
    contrasts = [
        _difference(terminal, cases, "valid_raw_no_proposal", "invalid_raw_no_proposal"),
        _difference(terminal, cases, "wrong_proposal_valid_raw", "wrong_proposal_only"),
        _difference(terminal, cases, "correct_proposal_valid_raw", "wrong_proposal_valid_raw"),
        _difference(terminal, cases, "wrong_proposal_valid_raw", "wrong_proposal_invalid_raw"),
        _difference(terminal, cases, "wrong_proposal_valid_raw_eligibility", "wrong_proposal_valid_raw"),
        _difference(terminal, cases, "wrong_proposal_valid_raw_method", "wrong_proposal_valid_raw"),
        _difference(terminal, cases, "wrong_proposal_valid_raw_status", "wrong_proposal_valid_raw"),
        _difference(terminal, cases, "wrong_proposal_invalid_raw_forged_status", "wrong_proposal_invalid_raw"),
    ]
    # A notation/reference effect is paired within the same root and content arm.
    for field, left, right in (("notation", "eal", "json"),
                               ("reference", "compact", "historical_length")):
        group = defaultdict(dict)
        for item in parsed:
            case, row = item["case"], item["row"]
            if row["state"] == "pending":
                continue
            group[(case["root_id"], case["arm"], case["reference" if field == "notation" else "notation"])][case[field]] = row
        complete = len(group) == 24 * 10 * 2 and all(set(pair) == {left, right} for pair in group.values())
        root_diff = defaultdict(list)
        for (root, _arm, _other), pair in group.items():
            if set(pair) == {left, right}:
                root_diff[root].append(int(pair[left]["available_information_correct"])
                                       - int(pair[right]["available_information_correct"]))
        contrasts.append({"left": left, "right": right, "field": field,
                          "paired_cells": sum(set(pair) == {left, right} for pair in group.values()),
                          "coverage_complete": complete,
                          "root_differences": {k: statistics.mean(v) for k, v in root_diff.items()},
                          "selected_root_mean_difference": statistics.mean(statistics.mean(v)
                             for v in root_diff.values()) if complete else None})

    # The planned unit is root. These fixed-root descriptive statistics are
    # deliberately not advertised as population confidence intervals.
    valid_invalid = {}
    records = {(case["root_id"], case["arm"], case["notation"], case["reference"]): row
               for case, row in ((item["case"], item["row"]) for item in parsed)
               if row["state"] != "pending"}
    for root in frozen["roots"]:
        pairs = []
        for notation in ("eal", "json"):
            for reference in ("compact", "historical_length"):
                a = records.get((root["id"], "valid_raw_no_proposal", notation, reference))
                b = records.get((root["id"], "invalid_raw_no_proposal", notation, reference))
                if a and b:
                    pairs.append({"notation": notation, "reference": reference,
                                  "valid_answer": a.get("answered_status"),
                                  "invalid_answer": b.get("answered_status"),
                                  "both_reference_matched": a.get("available_information_correct", False)
                                       and b.get("available_information_correct", False)})
        valid_invalid[root["id"]] = pairs
    return {
        "schema": "eal2-mechanisms-960-analysis/2", "freeze_sha256": frozen["freeze_sha256"],
        "status": ledger["status"], "scheduled": 960, "attempted": len(rows),
        "completed": sum(row["state"] == "completed" for row in rows),
        "malformed": sum(row["state"] == "malformed" for row in rows),
        "failed": sum(row["state"] == "failed" for row in rows),
        "pending": sum(row["state"] == "pending" for row in rows),
        "unattempted": 960 - len(rows), "usage": dict(all_usage),
        "known_configured_model_cost_usd": model_cost,
        "unknown_cost_attempts": sum(row["state"] in {"pending", "failed"} and
                                     row.get("cost_usd") is None for row in rows),
        "outcome_by_cell": by_cell,
        "by_family": {family: {"attempted": len(items),
                      "correct_available": sum(row.get("available_information_correct", False) for row in items),
                      "false_support": sum(row.get("false_support", False) for row in items)}
                      for family, items in sorted(families.items())},
        "contrasts": contrasts, "raw_valid_to_invalid_pairs": valid_invalid,
        "interpretation": "Selected-root developmental, conditional on pre-authored synthetic sources. "
            "Available-information correctness uses only records in each arm. Missing or malformed answers are "
            "attempted failures, with false-support risk unknown; a non-support label is not imputed. "
            "The comparison identifies supplied-information effects, not hidden model cognition, live truth, "
            "human brief-to-source fidelity, or EAL-specific benefit over an equal checker. "
            "Configured model rates omit authoring/review, acquisition, host and checker costs."
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyse(args.run_directory)
    if args.output:
        study.write(args.output, result)
    print(json.dumps({k: result[k] for k in ("status", "attempted", "completed", "malformed", "failed",
                                             "unattempted", "usage", "known_configured_model_cost_usd")}, sort_keys=True))


if __name__ == "__main__":
    main()
