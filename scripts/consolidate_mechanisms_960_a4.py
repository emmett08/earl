#!/usr/bin/env python3
"""Read-only, analysis-only composite of the exact original, A2, A3 and A4.

The four paid ledgers remain independent. This accepts only a terminal A4
ledger over the untouched suffix, retains each failed call and unknown charge,
and writes a new, non-resumable analysis directory. All three connection
probes are separate from the 960 assigned decisions.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_mechanisms_960 as study  # noqa: E402
import consolidate_mechanisms_960 as a2_composite  # noqa: E402
import consolidate_mechanisms_960_a3 as a3_composite  # noqa: E402
import continue_mechanisms_960_a4 as a4  # noqa: E402
import analyse_mechanisms_960 as analyser  # noqa: E402

SCHEMA = "eal2-mechanisms-960-a4-analysis-composite/1"
A4_SEMANTIC_FREEZE = "0da0b96efc128f41a523819dfbcee70489639da28cf6197abeae9589a9c0eebd"
A4_FREEZE_FILE = "8f7910b1334a45d8f9df3ec33212d47dc079060c1371a65959bcb838df31abd0"
START = 726
END = 960
FINISHED = {"completed", "completed_with_failures"}
STOPPED = {"stopped_repeated_provider_failures",
           "stopped_identity_usage_or_other_failure", "stopped_configured_budget"}


def _read(path: Path):
    return a3_composite._read(path)


def _check_terminal(ledger: dict, freeze: dict, original: dict, probe: dict) -> list[dict]:
    if (ledger.get("schema") != a4.LEDGER or ledger.get("freeze_sha256") != A4_SEMANTIC_FREEZE
            or ledger.get("status") not in FINISHED | STOPPED):
        raise ValueError("A4 ledger is live, unknown, or belongs to another freeze")
    rows = ledger.get("attempts")
    if (not isinstance(rows, list) or len(rows) > END - START
            or [row.get("index") for row in rows] != list(range(START, START + len(rows)))):
        raise ValueError("A4 attempts must be an exact, disjoint original-order prefix")
    if (freeze.get("start_index") != START or freeze.get("indexes") != list(range(START, END))
            or freeze.get("case_prompt_sha256") !=
            [case["prompt_sha256"] for case in original["schedule"][START:END]]):
        raise ValueError("A4 freeze does not assign precisely the untouched suffix")
    allowed = set(original["plan"]["accepted_response_models"])
    for row in rows:
        a2_composite._check_row(row, original["schedule"][row["index"]],
                                original["provider_identity"], allowed)
    policy = freeze["failure_policy"]
    stopped = a4.failure_stop(rows, policy)
    before_last = a4.failure_stop(rows[:-1], policy) if rows else None
    state = ledger["status"]
    if state in FINISHED:
        if len(rows) != END - START or stopped:
            raise ValueError("A4 cannot declare completion with missing slots or a crossed stop")
        if (state == "completed_with_failures") != any(r["state"] == "failed" for r in rows):
            raise ValueError("A4 completion status disagrees with failed attempts")
    elif state == "stopped_configured_budget":
        if len(rows) == END - START or stopped:
            raise ValueError("Budget stop cannot hide a full suffix or a failure stop")
        spent = (sum(freeze["known_prior_model_usd"].values())
                 + sum(freeze["known_prior_probe_usd"].values())
                 + freeze["unknown_prior_failed_call_reserved_usd"] + probe["cost_usd"]
                 + sum((r["cost_usd"] if r["cost_usd"] is not None else
                        original["schedule"][r["index"]]["reserve_usd"]) for r in rows))
        remaining = sum(case["reserve_usd"] for case in original["schedule"][START + len(rows):])
        if spent + remaining <= freeze["configured_cap_usd"]:
            raise ValueError("A4 budget stop is not supported by the frozen accounting")
    elif state != stopped or before_last:
        raise ValueError("A4 failure stop does not occur exactly at its last attempt")
    return rows


def compose(original_dir: Path, a2_dir: Path, a3_dir: Path, a4_dir: Path):
    original_dir, a2_dir, a3_dir, a4_dir = (
        p.resolve() for p in (original_dir, a2_dir, a3_dir, a4_dir))
    prior, joined, original_freeze_raw, a2_probe_raw, a3_probe_raw, prior_paths = (
        a3_composite.compose(original_dir, a2_dir, a3_dir))
    if prior["attempted"] != START or prior["unattempted"] != END - START:
        raise ValueError("Only the exact 726-attempt A3 stop may precede A4")
    a4_freeze, unused_freeze_raw, a4_freeze_sha = _read(a4_dir / "freeze.json")
    a4_ledger, unused_ledger_raw, a4_ledger_sha = _read(a4_dir / "ledger.json")
    a4_probe, a4_probe_raw, a4_probe_sha = _read(a4_dir / "probe.json")
    a4_review, a4_review_raw, a4_review_sha = _read(a4_dir / "review-attestation.json")
    if (a4_freeze_sha != A4_FREEZE_FILE
            or a4_freeze.get("freeze_sha256") != A4_SEMANTIC_FREEZE
            or a4_freeze != a4.prepare(original_dir, a2_dir, a3_dir)):
        raise ValueError("A4 freeze is not the exact reviewed continuation")
    original = a4.verify(a4_freeze, original_dir, a2_dir, a3_dir)
    if a4.verify_review(a4_freeze, a4_dir) != a4_review:
        raise ValueError("A4 review attestation changed during verification")
    if (a4_probe.get("schema") != a4.PROBE or a4_probe.get("state") != "completed"
            or a4_probe.get("continuation_freeze_sha256") != A4_SEMANTIC_FREEZE
            or a4_probe.get("cost_usd") is None
            or not isinstance(a4_probe.get("response"), dict)):
        raise ValueError("Separate A4 probe is incomplete or belongs to another freeze")
    measured = study.ModelResponse(**a4_probe["response"])
    if (measured.model not in original["plan"]["accepted_response_models"]
            or study.response_cost(measured, original["provider_identity"]) != a4_probe["cost_usd"]):
        raise ValueError("A4 probe model, usage or configured charge differs")
    new = _check_terminal(a4_ledger, a4_freeze, original, a4_probe)
    paths = [*prior_paths, (a4_dir / "freeze.json", a4_freeze_sha),
             (a4_dir / "ledger.json", a4_ledger_sha),
             (a4_dir / "probe.json", a4_probe_sha),
             (a4_dir / "review-attestation.json", a4_review_sha)]
    for path, digest in paths:
        a2_composite._again(path, digest)
    all_rows = joined["attempts"] + new
    if [r["index"] for r in all_rows] != list(range(len(all_rows))):
        raise ValueError("Composite has a gap or duplicate assignment")
    unknown = [r["index"] for r in all_rows if r.get("cost_usd") is None]
    if any(r["state"] != "failed" for r in all_rows if r["index"] in unknown):
        raise ValueError("Unknown charges cannot be imputed as zero")
    known = sum(r["cost_usd"] for r in all_rows if r["cost_usd"] is not None)
    input_hashes = {
        "original_freeze": prior["input_file_sha256"]["original_freeze"],
        "original_ledger": prior["input_file_sha256"]["original_ledger"],
        "a2_freeze": prior["input_file_sha256"]["a2_freeze"],
        "a2_ledger": prior["input_file_sha256"]["a2_ledger"],
        "a2_probe": prior["input_file_sha256"]["a2_probe"],
        "a3_freeze": prior["input_file_sha256"]["a3_freeze"],
        "a3_ledger": prior["input_file_sha256"]["a3_ledger"],
        "a3_probe": prior["input_file_sha256"]["a3_probe"],
        "a4_freeze": a4_freeze_sha, "a4_ledger": a4_ledger_sha,
        "a4_probe": a4_probe_sha, "a4_review_attestation": a4_review_sha,
    }
    if (a4_freeze["source_file_sha256"] != {k: v for k, v in input_hashes.items()
                                                if not k.startswith("a4_")}
            or set(input_hashes.values()) != {digest for _, digest in paths}):
        raise ValueError("A4 source pin set differs from the composite")
    summary = {
        "schema": SCHEMA, "source_freeze_sha256": original["freeze_sha256"],
        "a2_freeze_sha256": a2_composite.A2_SEMANTIC_FREEZE,
        "a3_freeze_sha256": a3_composite.A3_SEMANTIC_FREEZE,
        "a4_freeze_sha256": A4_SEMANTIC_FREEZE,
        "a4_review_status": a4_review["status"],
        "input_file_sha256": input_hashes,
        "assignments": END, "attempted": len(all_rows), "unattempted": END - len(all_rows),
        "index_ranges": {"original": [0, 131], "a2": [132, 467], "a3": [468, 725],
                         "a4": [START, START + len(new) - 1] if new else []},
        "source_terminal_statuses": {"a3": "stopped_repeated_provider_failures",
                                     "a4": a4_ledger["status"]},
        "state_counts": dict(Counter(r["state"] for r in all_rows)),
        "unknown_charge_attempt_indexes": unknown,
        "known_study_model_cost_usd": known,
        "actual_unknown_charges_usd": None if unknown else 0,
        "separate_probes": {
            "a2_configured_rate_usd": prior["separate_probes"]["a2_configured_rate_usd"],
            "a3_configured_rate_usd": prior["separate_probes"]["a3_configured_rate_usd"],
            "a4_configured_rate_usd": a4_probe["cost_usd"],
            "excluded_from_960_decisions": True,
        },
        "limitations": [
            "Analysis-only composite; four paid source ledgers and all failed slots are unchanged.",
            "Unknown failed-call charges are not zero; configured-rate known model cost excludes them.",
            "A2, A3 and A4 connection probes are outside the 960 assigned decisions.",
            "A4 review attestation is an independent AI review of a developmental exact freeze.",
            "Any A4 terminal stop leaves the untouched suffix unattempted; no result is imputed.",
            "Selected synthetic tasks and author-constructed references remain developmental.",
        ],
    }
    ledger = {
        "schema": study.LEDGER, "freeze_sha256": original["freeze_sha256"],
        "status": ("composite_completed_with_failures" if len(all_rows) == END else
                   "composite_terminal_with_unattempted"),
        "attempts": all_rows, "analysis_only": True,
        "composite_provenance_sha256": study.digest(summary),
    }
    return (summary, ledger, original_freeze_raw, a2_probe_raw, a3_probe_raw,
            a4_probe_raw, a4_review_raw, paths)


def write_new(output: Path, summary: dict, ledger: dict, original_freeze_raw: bytes,
              a2_probe_raw: bytes, a3_probe_raw: bytes, a4_probe_raw: bytes,
              a4_review_raw: bytes, paths):
    output = output.resolve()
    if (output.exists() or any(output == p.parent or output.is_relative_to(p.parent)
                               for p, _ in paths)):
        raise ValueError("Composite must be a new directory outside every source")
    for path, digest in paths:
        a2_composite._again(path, digest)
    output.mkdir(parents=True, mode=0o700)
    (output / "freeze.json").write_bytes(original_freeze_raw)
    (output / "probe-a2.json").write_bytes(a2_probe_raw)
    (output / "probe-a3.json").write_bytes(a3_probe_raw)
    (output / "probe-a4.json").write_bytes(a4_probe_raw)
    (output / "a4-review-attestation.json").write_bytes(a4_review_raw)
    study.write(output / "ledger.json", ledger)
    study.write(output / "composition.json", summary)
    analysis = analyser.analyse(output)
    if (analysis["scheduled"] != END or analysis["attempted"] != summary["attempted"]
            or analysis["unknown_cost_attempts"] !=
            len(summary["unknown_charge_attempt_indexes"])
            or not math.isclose(analysis["known_configured_model_cost_usd"],
                                summary["known_study_model_cost_usd"],
                                rel_tol=0, abs_tol=1e-9)):
        raise AssertionError("Analyser disagrees with composite accounting")
    study.write(output / "analysis.json", analysis)
    return {
        "output": str(output), "status": analysis["status"],
        "attempted": analysis["attempted"], "unattempted": analysis["unattempted"],
        "failed": analysis["failed"], "malformed": analysis["malformed"],
        "unknown_charge_attempts": analysis["unknown_cost_attempts"],
        "known_study_model_cost_usd": analysis["known_configured_model_cost_usd"],
        "separate_probes_usd": summary["separate_probes"],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("original", type=Path)
    ap.add_argument("a2", type=Path)
    ap.add_argument("a3", type=Path)
    ap.add_argument("a4", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = compose(args.original, args.a2, args.a3, args.a4)
    print(json.dumps(write_new(args.output, *result), sort_keys=True))


if __name__ == "__main__":
    main()
