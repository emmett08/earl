"""Replay the frozen v2 scorer and regenerate the paper's numerical results.

Uses only Python's standard library. Makes no network or model calls.
The archived oracle and summary modules are byte-identical to run commit
3490076dd78404caa1326d9aae704f964910c4c8, not the current experiment scorer.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile

import v2_oracle as oracle
import v2_summary as analysis

PAPER = Path(__file__).resolve().parents[1]
MODELS = ["gpt-4.1-nano-2025-04-14", "gpt-4.1-mini-2025-04-14", "gpt-4.1-2025-04-14",
          "gpt-5.4-nano-2026-03-17", "gpt-5.4-mini-2026-03-17", "gpt-5.4-2026-03-05"]
LABELS = ["4.1 nano", "4.1 mini", "4.1 full", "5.4 nano", "5.4 mini", "5.4 full"]
ARMS = ["eal_mcp", "json_prompt", "plain_brief", "plain_explicit", "plain_review"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(path.read_text())


def reproduce(data: Path, output: Path):
    provenance = load(data / "provenance.json")
    for name, digest in provenance["derived_file_sha256"].items():
        require(hashlib.sha256((data / name).read_bytes()).hexdigest() == digest, f"Changed input: {name}")
    manifest = load(data / "historical-manifest.json")
    for filename, original in (("v2_oracle.py", "oracle.py"), ("v2_summary.py", "analysis.py")):
        require(hashlib.sha256((PAPER / "analysis" / filename).read_bytes()).hexdigest()
                == manifest["files"][f"experiments/api_load_test/{original}"], "Changed historical scorer")
    cases_list = [json.loads(line) for line in (data / "cases.jsonl").read_text().splitlines()]
    cases = {row["id"]: row for row in cases_list}
    trials = [json.loads(line) for line in (data / "trials.jsonl").read_text().splitlines()]
    by_id = {row["id"]: row for row in trials}
    require(len(by_id) == len(trials) == len(manifest["assignments"]), "Trial identity count differs")
    require(len(cases) == len(cases_list), "Duplicate case")
    case_hashes = load(data / "case-manifest.json")["cases"]
    require(set(cases) == set(case_hashes), "Case catalogue differs")
    for key, case in cases.items():
        require(hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest() == case_hashes[key],
                f"Case content differs: {key}")
    specs = {row["id"]: row for row in manifest["models"]}
    cost = Decimal(0)
    calls = 0
    host_checks = 0
    for assigned in manifest["assignments"]:
        row = by_id[assigned["id"]]
        require(all(row.get(k) == v for k, v in assigned.items()), "Assignment changed")
        truth = oracle.reference(cases[row["case_id"]])
        if row["state"] != "not_attempted":
            require(row["reference"] == truth, f"Reference differs: {row['id']}")
            require(row["case_sha256"] == case_hashes[row["case_id"]], "Trial case hash differs")
            grade = oracle.grade(row.get("answer"), truth, collected=row.get("collected", False),
                                 inspected_report_ids=row.get("inspected_report_ids", []))
            checks = row.get("host_checks", [])
            grade["host_agrees_with_reference"] = all(x["agrees"] for x in checks) if checks else None
            if row.get("failure"):
                grade["correct"] = False
            require(grade == row["outcome"], f"Original score differs: {row['id']}")
            host_checks += len(checks)
        else:
            require(not row.get("answer") and not row.get("model_calls"), "Unattempted trial has output")
        for call in row.get("model_calls", []):
            calls += 1
            response = call.get("response")
            require(response is not None, "This archive unexpectedly lacks response accounting")
            require(response["model"] == row["model"], "Model snapshot mismatch")
            rates = specs[row["model"]]["pricing"]
            cached = response["metadata"].get("cached_input_tokens", 0)
            amount = ((response["input_tokens"] - cached) * Decimal(str(rates["input_usd_per_million"]))
                      + cached * Decimal(str(rates["cached_input_usd_per_million"]))
                      + response["output_tokens"] * Decimal(str(rates["output_usd_per_million"]))) / 1_000_000
            require(abs(amount - Decimal(str(call["estimated_usd"]))) < Decimal("0.0000000001"),
                    "Frozen-rate cost mismatch")
            cost += amount
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "manifest.json").write_text(json.dumps(manifest))
        for row in trials:
            dest = root / "trials" / row["id"] / "trial.json"
            dest.parent.mkdir(parents=True)
            dest.write_text(json.dumps(row))
        summary = analysis.summarise(root)
    require(summary == load(data / "original-summary.json"), "Historical summary differs")
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n")
    cells = {(r["model"], r["arm"]): r for r in summary["cells"]}
    rows = []
    disposition = []
    costs = []
    for model, label in zip(MODELS, LABELS):
        rows.append(label + " & " + " & ".join(f"{cells[model, arm]['correct']}/40" for arm in ARMS) + r" \\")
        selected = [r for r in trials if r["model"] == model]
        states = Counter(r["state"] for r in selected)
        disposition.append(label + " & " + " & ".join(str(states[k]) for k in
                           ("complete", "failed", "not_attempted")) + r" \\")
        costs.append(label + " & " + " & ".join(f"{cells[model, arm]['estimated_usd_known']:.4f}" for arm in ARMS) + r" \\")
    (output / "accuracy-rows.tex").write_text("\n".join(rows) + "\n")
    (output / "disposition-rows.tex").write_text("\n".join(disposition) + "\n")
    (output / "cost-rows.tex").write_text("\n".join(costs) + "\n")
    totals = {"assigned": len(trials), "states": dict(Counter(r["state"] for r in trials)),
              "correct": sum(r["correct"] for r in summary["cells"]), "model_calls": calls,
              "estimated_usd": str(cost), "unknown_cost_calls": 0,
              "host_checks_recorded": host_checks,
              "case_reference_statuses": dict(Counter(oracle.reference(c)["status"] for c in cases.values())),
              "failures": dict(Counter(r.get("failure") for r in trials if r.get("failure"))),
              "historical_scores_and_summary": "exact_match"}
    (output / "reproduction.json").write_text(json.dumps(totals, sort_keys=True, indent=2) + "\n")
    components = {
        "schema": "eal-paper-error-components/1",
        "complete_incorrect": [
            {"id": row["id"], "model": row["model"], "arm": row["arm"],
             "case_id": row["case_id"], "family": cases[row["case_id"]]["family"],
             "failed_components": sorted(key for key, value in row["outcome"].items()
                                         if key.endswith("_correct") and value is False)}
            for row in trials if row["state"] == "complete" and not row["outcome"]["correct"]
        ],
        "provider_stops": [
            {"id": row["id"], "model": row["model"], "arm": row["arm"],
             "last_call": row["model_calls"][-1]}
            for row in trials if row.get("failure") == "provider_error"
        ],
        "recorded_host_agreement_flags": dict(Counter(str(check["agrees"])
            for row in trials for check in row.get("host_checks", []))),
    }
    (output / "error-components.json").write_text(json.dumps(components, sort_keys=True, indent=2) + "\n")
    print(json.dumps(totals, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=PAPER / "data")
    parser.add_argument("--output", type=Path, default=PAPER / "results")
    args = parser.parse_args()
    reproduce(args.data, args.output)
