#!/usr/bin/env python3
"""Audit and summarise the retained 48-request artifact handoff pilot.

This reads the complete frozen schedule and provider responses from the archive.
It performs no model requests. The state is the paired presentation unit and
the four roots, rather than the twelve correlated states, are the independent
task units.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import tarfile

from eal.providers import ModelResponse, response_cost
from eal.runtime import strict_json
from run_artifact_live_pilot import ARMS, STATUSES, _answer, _check_frozen


def _load(archive: tarfile.TarFile, name: str) -> dict:
    member = archive.getmember(name)
    if not member.isfile() or member.size > 2_000_000:
        raise ValueError(f"Invalid archived JSON member: {name}")
    stream = archive.extractfile(member)
    if stream is None:
        raise ValueError(f"Missing archived JSON member: {name}")
    return strict_json(stream.read().decode("utf-8"))


def _named_claim(text: str, claim: str) -> str | None:
    """Diagnostic only: extract the named status despite extra output fields."""
    try:
        value = strict_json(text)
    except ValueError:
        return None
    claims = value.get("claims") if isinstance(value, dict) else None
    status = claims.get(claim) if isinstance(claims, dict) else None
    return status if status in STATUSES else None


def _audit(frozen: dict, trials: dict, *, complete: bool) -> list[dict]:
    _check_frozen(frozen)
    cases = frozen["cases"]
    attempts = trials["attempts"]
    if trials["freeze_digest"] != frozen["freeze_digest"]:
        raise ValueError("Attempt ledger does not match its frozen schedule")
    if complete and (trials["status"] != "complete" or len(attempts) != 48):
        raise ValueError("The dated-model trial is incomplete")
    if len(attempts) > len(cases):
        raise ValueError("More attempts than scheduled cases")
    rows = []
    for index, attempt in enumerate(attempts):
        case = cases[index]
        for field in ("root_id", "state_id", "arm", "prompt_digest"):
            if attempt[field] != case[field]:
                raise ValueError(f"Attempt {index} differs from the frozen schedule")
        if attempt["index"] != index:
            raise ValueError(f"Attempt {index} has an incorrect index")
        raw = attempt.get("response")
        usage = attempt.get("usage")
        if raw is None or usage is None:
            raise ValueError(f"Attempt {index} lacks response or billed usage")
        response = ModelResponse(
            raw["text"], usage["input_tokens"], usage["output_tokens"],
            raw["model"], raw["metadata"]
        )
        if response.model != frozen["expected_response_model"] and complete:
            raise ValueError(f"Unexpected model on completed attempt {index}")
        if response.metadata.get("cached_input_tokens", 0) != usage["cached_input_tokens"]:
            raise ValueError(f"Cached-token count differs on attempt {index}")
        cost = response_cost(response, frozen["provider_identity"])
        if cost is None or abs(cost - usage["model_cost_usd"]) > 1e-12:
            raise ValueError(f"Recomputed cost differs on attempt {index}")
        if not isinstance(attempt["duration_seconds"], (int, float)) or attempt["duration_seconds"] < 0:
            raise ValueError(f"Invalid duration on attempt {index}")
        if complete:
            if attempt["status"] != "completed":
                raise ValueError(f"Unexpected failed attempt {index} in complete run")
            parsed = _answer(response.text, case["claim"])
            scored = attempt["recipient"]
            for field in ("status", "format_valid", "explanation"):
                if scored[field] != parsed[field]:
                    raise ValueError(f"Stored recipient parsing differs on attempt {index}")
            if scored["correct"] != (parsed["status"] == case["expected"]):
                raise ValueError(f"Stored correctness differs on attempt {index}")
            named = _named_claim(response.text, case["claim"])
            rows.append({
                "index": index, "root": case["root_id"], "state": case["state_id"],
                "arm": case["arm"], "expected": case["expected"],
                "strict_status": parsed["status"], "format_valid": parsed["format_valid"],
                "strict_correct": scored["correct"], "named_status": named,
                "named_correct": named == case["expected"],
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cached_input_tokens": usage["cached_input_tokens"],
                "cost_usd_estimate": cost, "duration_seconds": attempt["duration_seconds"]
            })
    return rows


def analyse(path: Path) -> dict:
    archive_bytes = path.read_bytes()
    with tarfile.open(path, "r:gz") as archive:
        frozen = _load(archive, "pilot-output-dated/freeze.json")
        trials = _load(archive, "pilot-output-dated/trials.json")
        first_freeze = _load(archive, "pilot-output/freeze.json")
        first_trials = _load(archive, "pilot-output/trials.json")
    rows = _audit(frozen, trials, complete=True)
    first = _audit(first_freeze, first_trials, complete=False)
    if first or len(first_trials["attempts"]) != 1 or first_trials["status"] != "stopped_provider_failure":
        raise ValueError("Unexpected alias-discovery attempt ledger")
    initial_attempt = first_trials["attempts"][0]
    if initial_attempt["status"] != "failed" or "Returned model differs" not in initial_attempt["error"]:
        raise ValueError("Initial attempt did not stop on the documented identity mismatch")
    all_cost = sum(row["cost_usd_estimate"] for row in rows)
    first_cost = initial_attempt["usage"]["model_cost_usd"]
    by_arm = {}
    for arm in ARMS:
        group = [row for row in rows if row["arm"] == arm]
        by_arm[arm] = {
            "n": len(group), "strict_correct": sum(row["strict_correct"] for row in group),
            "format_valid": sum(row["format_valid"] for row in group),
            "named_correct_diagnostic": sum(row["named_correct"] for row in group),
            "false_support_strict": sum(row["strict_status"] == "supported" and row["expected"] != "supported" for row in group),
            "false_support_named_diagnostic": sum(row["named_status"] == "supported" and row["expected"] != "supported" for row in group),
            "input_tokens": sum(row["input_tokens"] for row in group),
            "output_tokens": sum(row["output_tokens"] for row in group),
            "cached_input_tokens": sum(row["cached_input_tokens"] for row in group),
            "model_cost_usd_estimate": round(sum(row["cost_usd_estimate"] for row in group), 10),
            "median_wall_seconds": round(statistics.median(row["duration_seconds"] for row in group), 3),
        }
    by_root = {}
    for root in sorted({row["root"] for row in rows}):
        by_root[root] = {arm: sum(row["strict_correct"] for row in rows if row["root"] == root and row["arm"] == arm)
                         for arm in ARMS}
    paired = {}
    for other in ("raw_graph", "apply_eal", "checked_packet"):
        a = {(row["root"], row["state"]): row["strict_correct"] for row in rows if row["arm"] == "raw_eal"}
        b = {(row["root"], row["state"]): row["strict_correct"] for row in rows if row["arm"] == other}
        if a.keys() != b.keys():
            raise ValueError("Paired arms have different task states")
        paired[other + "_vs_raw_eal"] = {
            "gains": sum(not a[key] and b[key] for key in a),
            "losses": sum(a[key] and not b[key] for key in a),
            "ties": sum(a[key] == b[key] for key in a),
        }
    return {
        "schema": "eal2-artifact-live-pilot-analysis/1",
        "archive_sha256": hashlib.sha256(archive_bytes).hexdigest(),
        "archive_bytes": len(archive_bytes),
        "freeze_digest": frozen["freeze_digest"],
        "initial_freeze_digest": first_freeze["freeze_digest"],
        "provider_identity": frozen["provider_identity"],
        "expected_response_model": frozen["expected_response_model"],
        "scheduled_cases": len(frozen["cases"]), "completed_cases": len(rows),
        "initial_stopped_attempts": 1,
        "initial_returned_model": initial_attempt["response"]["model"],
        "initial_cost_usd_estimate": first_cost,
        "complete_cost_usd_estimate": round(all_cost, 10),
        "all_49_attempts_cost_usd_estimate": round(all_cost + first_cost, 10),
        "by_arm": by_arm, "by_root": by_root, "paired_state_diagnostic": paired,
        "rows": rows,
        "interpretation": (
            "Selected four-root synthetic feasibility pilot. Exact output and named-claim "
            "scores are distinct. Twelve states are correlated within four roots; the "
            "checked packet supplies the status. No EAL-specific superiority or "
            "general model-reasoning conclusion follows."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyse(args.archive)
    data = json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data, end="")


if __name__ == "__main__":
    main()
