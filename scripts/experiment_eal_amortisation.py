#!/usr/bin/env python3
"""Reproducible byte accounting for repeated use of authored EAL/2 arguments.

This is a deterministic sensitivity analysis over existing exposed synthetic
cases. Byte counts are measured; token densities, authoring, revision, cache,
and host costs are explicitly *assumed*. No provider call is made.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import experiment_negative_revisions as prior

OUTPUT = ROOT / "benchmarks/results/2026-09-23-eal-amortisation/offline.json"

# A compact human-readable contract for the model-only full-replay comparison.
# These words are part of the measured packet, not a claim that the model follows it.
METHOD_REFERENCE = (
    "Evaluate engineering/sampled-negative/1 for the exact proposition query. "
    "For mode counterexample, one correctly typed, in-window bound violation "
    "supports finding=true, even on a partial trace. For mode non_detection, "
    "finding=true needs sampled endpoints and maximum-gap coverage, no bound "
    "violation, adequate detector limit and declared sensitivity. Partial or "
    "wrong-scope records cannot prove a negative claim. Apply evidence requirements, "
    "all declared objections and independent defences to each argument route. "
    "Return the named claim's computed status."
)


def encoded_bytes(text: str) -> int:
    return len(text.encode("utf-8"))


def compact(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def source_and_records(item: dict) -> tuple[str, dict]:
    source = (prior.COUNTER if item["track"] == "counterexample" else prior.CLOSURE).read_text()
    if not item.get("linked", True):
        source = prior.unlinked_source(source)
    program = prior.parse(source)
    values: dict[str, dict] = {}
    if item["track"] == "counterexample":
        values = {
            "first_record": {"passed": True, "subject": "rig-9", "scope": "vibration-interval-9",
                             "property": {"operator": "lt", "value": 1}},
            "second_record": {"passed": True, "subject": "rig-9", "scope": "vibration-interval-9",
                              "property": {"operator": "lt", "value": 1}},
        }
        if item["step"] == "single_matching_test":
            del values["second_record"]
        if item["step"] == "tests_wrong_property":
            values["first_record"]["property"]["value"] = 2
            values["second_record"]["property"]["value"] = 2
        if item["defence"]:
            values["defence_record"] = {
                "independently_explained": True, "subject": "rig-9",
                "scope": "vibration-interval-9",
                "sample_time": 8 if item["step"] == "defence_wrong_sample" else 4,
            }
    if item["trace"] is not None:
        values["trace_record"] = item["trace"]
    return source, {name: prior.observation(program, name, value)
                    for name, value in values.items()}


def packets(source: str, records: dict, target: str, status: str) -> tuple[str, str, int]:
    question = f"What is the current status of claim {target}? Reply with its status.\n"
    prefix = question + "EAL/2 source (use the entire authored graph):\n"
    raw = (
        prefix + source + "\nMethod and graph instructions:\n" + METHOD_REFERENCE
        + "\nAssessment time and context: " + compact({"now": prior.NOW, "context": prior.CONTEXT})
        + "\nCurrent observation records: " + compact(records) + "\n"
    )
    # This is deliberately identical for both host implementations. It tests
    # whether a computed answer can avoid replay, not which language is better.
    concise = question + "Computed assessment: " + compact({
        "claim": target, "status": status,
        "source_sha256": sha256(source.encode("utf-8")).hexdigest(),
        "records_sha256": prior.canonical_digest(records),
    }) + "\n"
    return raw, concise, encoded_bytes(source)


def threshold(setup: float, gain_per_query: float) -> int | None:
    """First integer query count at which total gain strictly exceeds setup."""
    if gain_per_query <= 0:
        return None
    return int(setup // gain_per_query) + 1


def run() -> dict:
    prior_result = prior.run()
    if prior_result["passed"] != prior_result["total"]:
        raise ValueError("The underlying status experiment failed")
    rows = []
    for spec, result in zip(prior.rows_spec(), prior_result["cases"], strict=True):
        if spec["step"] != result["step"] or spec["track"] != result["track"]:
            raise ValueError("Developmental case order changed")
        target = ("property_supported" if spec["track"] == "counterexample"
                  else "qualified_absence")
        if result["actual"][target] != result["reference"][target]:
            raise ValueError("EAL and the narrow independent checker disagree")
        source, records = source_and_records(spec)
        if sha256(source.encode()).hexdigest() != result["source_sha256"]:
            raise ValueError("Source changed relative to assessed result")
        if prior.canonical_digest(records) != result["records_sha256"]:
            raise ValueError("Records changed relative to assessed result")
        full, concise, source_size = packets(source, records, target, result["actual"][target])
        rows.append({
            "track": spec["track"], "step": spec["step"], "claim": target,
            "status": result["actual"][target],
            "full_replay_utf8_bytes": encoded_bytes(full),
            "eal_host_utf8_bytes": encoded_bytes(concise),
            "equal_checker_host_utf8_bytes": encoded_bytes(concise),
            "source_utf8_bytes_in_full": source_size,
            "raw_records_utf8_bytes_in_full": encoded_bytes(compact(records)),
            "packet_sha256": {"full": sha256(full.encode()).hexdigest(),
                              "host": sha256(concise.encode()).hexdigest()},
        })
    n = len(rows)
    aggregate = {
        "cases": n,
        "full_replay_utf8_bytes": sum(r["full_replay_utf8_bytes"] for r in rows),
        "eal_host_utf8_bytes": sum(r["eal_host_utf8_bytes"] for r in rows),
        "equal_checker_host_utf8_bytes": sum(r["equal_checker_host_utf8_bytes"] for r in rows),
        "source_utf8_bytes_in_full": sum(r["source_utf8_bytes_in_full"] for r in rows),
    }
    aggregate["replay_minus_host_utf8_bytes"] = (
        aggregate["full_replay_utf8_bytes"] - aggregate["eal_host_utf8_bytes"])
    scenarios = []
    # These are declared hypothetical assumptions, not measured token use or
    # provider prices. Cached-source discounts only the source portion.
    for tokens_per_byte in (0.20, 0.25, 0.33):
        for cached_source_discount in (0.0, 0.5, 0.9):
            for host_equivalent_input_tokens in (0, 25, 100):
                reusable_byte_saving = (
                    aggregate["replay_minus_host_utf8_bytes"]
                    - cached_source_discount * aggregate["source_utf8_bytes_in_full"]
                ) / n
                per_query_gain = (tokens_per_byte * reusable_byte_saving
                                  - host_equivalent_input_tokens)
                # These hypothetical costs are incremental host integration
                # and host upkeep. Authorship of the EAL file is common to
                # both full EAL replay and EAL-host delivery and cancels.
                setup = 10_000 + 2 * 1_000
                scenarios.append({
                    "assumed_tokens_per_utf8_byte": tokens_per_byte,
                    "assumed_cached_source_discount": cached_source_discount,
                    "assumed_host_input_token_equivalent_per_query": host_equivalent_input_tokens,
                    "assumed_incremental_host_setup_input_token_equivalent": 10_000,
                    "assumed_host_update_count": 2,
                    "assumed_incremental_host_update_input_token_equivalent_each": 1_000,
                    "derived_input_token_equivalent_gain_per_query": round(per_query_gain, 3),
                    "first_total_query_count_to_cover_assumed_setup": threshold(setup, per_query_gain),
                })
    return {
        "schema": "EAL/amortisation-offline/1", "status": "deterministic-sensitivity-only",
        "source_experiment": "scripts/experiment_negative_revisions.py",
        "packet_unit": "exact UTF-8 bytes, not provider tokens",
        "case_rows": rows, "aggregate": aggregate, "sensitivity": scenarios,
        "limits": [
            "Exposed synthetic cases, repeated evenly in the illustrative scenario; no independent users or model responses.",
            "The equal-checker control has the same concise result packet and matches these fixed-case statuses, but is not a general checker or measured authoring comparison.",
            "The full replay packet is one plausible prompt, not an optimised lower bound; cache and retrieval effects are sensitivity parameters.",
            "Token densities, one-time work, host costs and revisions are assumed scenarios, not measured provider usage or prices.",
            "Answer quality, semantic authoring fidelity, latency, and real provider cost are unmeasured.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="recompute and compare the retained result")
    args = parser.parse_args()
    if args.verify:
        if not OUTPUT.exists():
            raise SystemExit(f"No retained result to verify: {OUTPUT}")
        current = run()
        if current != json.loads(OUTPUT.read_text()):
            raise SystemExit("Retained result differs from recomputation")
        print(json.dumps({"verified": True, "cases": current["aggregate"]["cases"]}))
        return
    if OUTPUT.exists():
        raise SystemExit(f"Refusing to replace retained result: {OUTPUT}")
    result = run()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(OUTPUT), "aggregate": result["aggregate"]}, indent=2))


if __name__ == "__main__":
    main()
