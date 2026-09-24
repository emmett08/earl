#!/usr/bin/env python3
"""A4 continuation template for the untouched suffix after the exact A3 stop.

Dry freezing is possible only after A3 ends with its repeated-provider-failure
stop. Paid probing and execution additionally require a separate, exact-freeze
independent review attestation. Earlier attempts, including failures and probes,
remain in their original ledgers and are never retried or rewritten.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from eal.providers import ProviderError, load_provider, response_cost  # noqa: E402
import run_mechanisms_960 as study  # noqa: E402
import consolidate_mechanisms_960 as a2_composite  # noqa: E402
import continue_mechanisms_960_a3 as a3  # noqa: E402
import consolidate_mechanisms_960_a3 as a3_composite  # noqa: E402

SCHEMA = "eal2-mechanisms-960-a4-freeze/1"
LEDGER = "eal2-mechanisms-960-a4-ledger/1"
PROBE = "eal2-mechanisms-960-a4-separate-probe/1"
REVIEW = "eal2-mechanisms-960-a4-exact-freeze-review/1"
SOURCE_SCRIPTS = {
    "original_runner": ROOT / "scripts/run_mechanisms_960.py",
    "a2_runner": ROOT / "scripts/continue_mechanisms_960.py",
    "a2_composite": ROOT / "scripts/consolidate_mechanisms_960.py",
    "a3_runner": ROOT / "scripts/continue_mechanisms_960_a3.py",
    "a3_composite": ROOT / "scripts/consolidate_mechanisms_960_a3.py",
}


def sources(original_dir: Path, a2_dir: Path, a3_dir: Path) -> tuple[dict, dict, dict, dict, dict, list]:
    """Validate exact earlier freezes, terminal rows, probes, and their bytes."""
    original_dir, a2_dir, a3_dir = (p.resolve() for p in (original_dir, a2_dir, a3_dir))
    summary, joined, unused_freeze, unused_a2_probe, unused_a3_probe, paths = (
        a3_composite.compose(original_dir, a2_dir, a3_dir))
    a3_ledger = study.strict_json((a3_dir / "ledger.json").read_text(encoding="utf-8"))
    a3_rows = a3_ledger["attempts"]
    start = summary["attempted"]
    if (a3_ledger["status"] != "stopped_repeated_provider_failures"
            or not 468 < start < 960 or summary["unattempted"] != 960 - start
            or len(a3_rows) != start - 468 or len(a3_rows) % 2
            or a3.failure_stop(a3_rows, a3_composite._read(a3_dir / "freeze.json")[0]["failure_policy"])
            != "stopped_repeated_provider_failures"):
        raise ValueError("A4 requires the exact terminal A3 repeated-provider-failure stop")
    # The A3 runner dispatches complete two-slot batches and stops at the first
    # crossed threshold. A forged ledger with extra attempted batches is invalid.
    a3_policy = a3_composite._read(a3_dir / "freeze.json")[0]["failure_policy"]
    if a3.failure_stop(a3_rows[:-2], a3_policy):
        raise ValueError("A3 attempts continued after its frozen stop threshold")
    frozen = study.strict_json((original_dir / "freeze.json").read_text(encoding="utf-8"))
    a2_probe = study.strict_json((a2_dir / "probe.json").read_text(encoding="utf-8"))
    a3_probe = study.strict_json((a3_dir / "probe.json").read_text(encoding="utf-8"))
    if [row["index"] for row in joined["attempts"]] != list(range(start)):
        raise ValueError("Earlier assignment prefix has a gap or duplicate")
    for path, expected in paths:
        a2_composite._again(path, expected)
    return frozen, summary, joined, a2_probe, a3_probe, paths


def prepare(original_dir: Path, a2_dir: Path, a3_dir: Path) -> dict:
    frozen, summary, joined, a2_probe, a3_probe, paths = sources(original_dir, a2_dir, a3_dir)
    start = summary["attempted"]
    indexes = list(range(start, 960))
    rates = frozen["provider_identity"]["pricing"]
    probe_reserve = ((512 + 4096) * rates["input_usd_per_million"]
                     + 16 * rates["output_usd_per_million"]) / 1e6
    rows = joined["attempts"]
    known_by_segment = {
        "original": sum(r["cost_usd"] for r in rows[:132] if r["cost_usd"] is not None),
        "a2": sum(r["cost_usd"] for r in rows[132:468] if r["cost_usd"] is not None),
        "a3": sum(r["cost_usd"] for r in rows[468:] if r["cost_usd"] is not None),
    }
    unknown = summary["unknown_charge_attempt_indexes"]
    unknown_reserve = sum(frozen["schedule"][i]["reserve_usd"] for i in unknown)
    remaining_reserve = sum(frozen["schedule"][i]["reserve_usd"] for i in indexes)
    cap = frozen["plan"]["max_configured_model_cost_usd"]
    if cap != 5:
        raise ValueError("A4 only applies to the original $5 configured cap")
    if (sum(known_by_segment.values()) + a2_probe["cost_usd"] + a3_probe["cost_usd"]
            + unknown_reserve + probe_reserve + remaining_reserve > cap):
        raise ValueError("All prior known costs, unknown reservations, three probes and suffix exceed $5 cap")
    input_hashes = summary["input_file_sha256"]
    expected_names = {"original_freeze", "original_ledger", "a2_freeze", "a2_ledger",
                      "a2_probe", "a3_freeze", "a3_ledger", "a3_probe"}
    if set(input_hashes) != expected_names or set(input_hashes.values()) != {sha for _, sha in paths}:
        raise ValueError("Prior source file pin set differs")
    result = {
        "schema": SCHEMA, "source_freeze_sha256": frozen["freeze_sha256"],
        "a2_freeze_sha256": a2_composite.A2_SEMANTIC_FREEZE,
        "a3_freeze_sha256": a3_composite.A3_SEMANTIC_FREEZE,
        "source_file_sha256": input_hashes,
        "source_script_sha256": {name: study.digest(path.read_bytes()) for name, path in SOURCE_SCRIPTS.items()},
        "script_sha256": study.digest(Path(__file__).read_bytes()),
        "start_index": start, "indexes": indexes,
        "case_prompt_sha256": [frozen["schedule"][i]["prompt_sha256"] for i in indexes],
        "known_prior_model_usd": known_by_segment,
        "known_prior_probe_usd": {"a2": a2_probe["cost_usd"], "a3": a3_probe["cost_usd"]},
        "prior_failed_indexes": [r["index"] for r in rows if r["state"] == "failed"],
        "prior_unknown_charge_indexes": unknown,
        "unknown_prior_failed_call_reserved_usd": unknown_reserve,
        "probe_reserved_usd": probe_reserve, "continuation_reserved_usd": remaining_reserve,
        "configured_cap_usd": cap, "max_inflight": 1,
        "failure_policy": {
            "no_retry": True,
            "continue_after": ["response-less ProviderError, unknown actual charge reserved",
                               "metered accepted-model ProviderError with finish_reason=length"],
            "stop_consecutive_provider_failures": 3,
            "stop_total_provider_failures": 24,
            "threshold_scope": "new A4 attempts only; all prior failures retained separately",
            "stop_immediately_after_attempt": ["response_model_mismatch", "unknown_billed_usage",
                                               "any other failure kind"],
            "unknown_charge_reservation": "frozen per-case maximum for each failed slot",
        },
        "amendment": "A4: retain every original/A2/A3 attempt and probe, never retry any slot; "
                     "after the exact A3 provider-failure stop, dispatch only the untouched original-order "
                     "suffix one at a time, under independently attested freeze and A4-only thresholds.",
    }
    result["freeze_sha256"] = study.digest(result)
    return result


def verify(continuation: dict, original_dir: Path, a2_dir: Path, a3_dir: Path) -> dict:
    if continuation.get("schema") != SCHEMA or not isinstance(continuation.get("freeze_sha256"), str):
        raise ValueError("Wrong A4 freeze schema")
    if study.digest({k: v for k, v in continuation.items() if k != "freeze_sha256"}) != continuation["freeze_sha256"]:
        raise ValueError("A4 freeze digest differs")
    if continuation != prepare(original_dir, a2_dir, a3_dir):
        raise ValueError("A4 freeze differs from the exact current source files, code, schedule or budget")
    frozen, unused_summary, unused_joined, unused_a2_probe, unused_a3_probe, paths = (
        sources(original_dir, a2_dir, a3_dir))
    for path, expected in paths:
        a2_composite._again(path, expected)
    return frozen


def _initial(continuation: dict, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    freeze_path, ledger_path = output / "freeze.json", output / "ledger.json"
    if freeze_path.exists():
        if study.strict_json(freeze_path.read_text(encoding="utf-8")) != continuation:
            raise ValueError("A4 directory contains another freeze")
    else:
        study.write(freeze_path, continuation)
    if ledger_path.exists():
        ledger = study.strict_json(ledger_path.read_text(encoding="utf-8"))
    else:
        ledger = {"schema": LEDGER, "freeze_sha256": continuation["freeze_sha256"],
                  "status": "frozen", "attempts": []}
        study.write(ledger_path, ledger)
    if ledger.get("schema") != LEDGER or ledger.get("freeze_sha256") != continuation["freeze_sha256"]:
        raise ValueError("A4 ledger belongs to another freeze")
    return ledger


def verify_review(continuation: dict, output: Path) -> dict:
    """Fail closed until a distinct reviewer attests exact saved freeze bytes."""
    freeze_path, attestation_path = output / "freeze.json", output / "review-attestation.json"
    if not freeze_path.is_file() or not attestation_path.is_file():
        raise ValueError("Paid A4 calls require an independently reviewed exact saved freeze")
    review = study.strict_json(attestation_path.read_text(encoding="utf-8"))
    required = {"schema", "status", "freeze_sha256", "freeze_file_sha256", "script_sha256",
                "source_file_sha256", "reviewer_id", "review_report_path", "review_report_sha256",
                "limitations"}
    if not isinstance(review, dict) or set(review) != required or review["schema"] != REVIEW:
        raise ValueError("A4 review attestation has an incomplete schema")
    if (review["status"] != "exact_freeze_independent_ai_review_accepted"
            or review["freeze_sha256"] != continuation["freeze_sha256"]
            or review["freeze_file_sha256"] != study.digest(freeze_path.read_bytes())
            or review["script_sha256"] != continuation["script_sha256"]
            or review["source_file_sha256"] != continuation["source_file_sha256"]):
        raise ValueError("Independent A4 review does not bind these exact source and freeze bytes")
    if (not isinstance(review["reviewer_id"], str) or not review["reviewer_id"].strip()
            or review["reviewer_id"] == "/root/study960/fixture24/a4_template"
            or not isinstance(review["limitations"], list) or not review["limitations"]
            or any(not isinstance(x, str) or not x for x in review["limitations"])):
        raise ValueError("A4 review must identify a separate reviewer and its limitations")
    report = study.local_file(ROOT, review["review_report_path"])
    if (not report.is_relative_to(ROOT / "docs/reviews")
            or study.digest(report.read_bytes()) != review["review_report_sha256"]):
        raise ValueError("A4 review report is missing, changed or outside docs/reviews")
    return review


async def probe(continuation: dict, frozen: dict, output: Path) -> dict:
    _initial(continuation, output)
    verify_review(continuation, output)
    path = output / "probe.json"
    if path.exists():
        raise ValueError("An existing A4 probe is never retried or overwritten")
    provider = load_provider(study.local_file(ROOT, frozen["provider_file"]))
    if provider.identity() != frozen["provider_identity"]:
        raise ValueError("Provider identity changed since original freeze")
    if not os.environ.get("OPENAI_API_TOKEN"):
        raise ValueError("Configured credential is absent before probe")
    pending = {"schema": PROBE, "state": "pending", "continuation_freeze_sha256": continuation["freeze_sha256"],
               "started_at": datetime.now(timezone.utc).isoformat(), "cost_usd": None}
    study.write(path, pending)
    start = time.monotonic()
    response, failure = None, None
    try:
        response = await provider.complete([
            {"role": "system", "content": "Connection probe. Reply exactly OK."},
            {"role": "user", "content": "OK"}], 16)
    except ProviderError as exc:
        response, failure = exc.response, type(exc).__name__
    except Exception as exc:
        failure = type(exc).__name__
    cost = response_cost(response, frozen["provider_identity"]) if response else None
    if response and (response.input_tokens is None or response.output_tokens is None or cost is None):
        failure = "unknown_billed_usage"
    if response and response.model not in frozen["plan"]["accepted_response_models"]:
        failure = "response_model_mismatch"
    row = {**pending, "state": "failed" if failure else "completed", "error_kind": failure,
           "duration_seconds": time.monotonic() - start, "response": asdict(response) if response else None,
           "cost_usd": cost}
    study.write(path, row)
    return {"probe_state": row["state"], "model": response.model if response else None,
            "configured_cost_usd": cost, "error_kind": failure}


def continuable_failure(row: dict) -> bool:
    """Preserve only the two precisely specified failed ProviderError forms."""
    return a3.continuable_failure(row)


def failure_stop(rows: list[dict], policy: dict) -> str | None:
    failures = [row for row in rows if row["state"] == "failed"]
    if any(not continuable_failure(row) for row in failures):
        return "stopped_identity_usage_or_other_failure"
    if len(failures) >= policy["stop_total_provider_failures"]:
        return "stopped_repeated_provider_failures"
    consecutive = 0
    for row in rows:
        consecutive = consecutive + 1 if row["state"] == "failed" else 0
        if consecutive >= policy["stop_consecutive_provider_failures"]:
            return "stopped_repeated_provider_failures"
    return None


async def execute(continuation: dict, frozen: dict, output: Path) -> dict:
    ledger = _initial(continuation, output)
    verify_review(continuation, output)
    if ledger["status"] in {"completed", "completed_with_failures"} or str(ledger["status"]).startswith("stopped_"):
        raise ValueError("A terminal A4 ledger cannot be resumed")
    probe_path = output / "probe.json"
    if not probe_path.is_file():
        raise ValueError("A separate completed A4 connection probe is required")
    probe_result = study.strict_json(probe_path.read_text(encoding="utf-8"))
    if (probe_result.get("schema") != PROBE or probe_result.get("state") != "completed"
            or probe_result.get("continuation_freeze_sha256") != continuation["freeze_sha256"]
            or probe_result.get("cost_usd") is None or not isinstance(probe_result.get("response"), dict)):
        raise ValueError("A4 probe is incomplete, unbilled or belongs to another freeze")
    measured_probe = study.ModelResponse(**probe_result["response"])
    if (measured_probe.model not in frozen["plan"]["accepted_response_models"]
            or response_cost(measured_probe, frozen["provider_identity"]) != probe_result["cost_usd"]):
        raise ValueError("A4 probe model, usage or configured charge differs")
    provider = load_provider(study.local_file(ROOT, frozen["provider_file"]))
    if provider.identity() != frozen["provider_identity"]:
        raise ValueError("Provider identity changed since original freeze")
    if not os.environ.get("OPENAI_API_TOKEN"):
        raise ValueError("Configured credential is absent before A4 execution")
    rows = ledger["attempts"]
    if (ledger["status"] not in {"frozen", "running"}
            or [row.get("index") for row in rows] != continuation["indexes"][:len(rows)]):
        raise ValueError("A4 ledger is not an exact frozen original-order prefix")
    allowed = set(frozen["plan"]["accepted_response_models"])
    for row in rows:
        a2_composite._check_row(row, frozen["schedule"][row["index"]], frozen["provider_identity"], allowed)
        if row["state"] == "failed" and not continuable_failure(row):
            raise ValueError("A4 has a non-continuable failure")
    if failure_stop(rows, continuation["failure_policy"]):
        raise ValueError("A4 failures crossed the frozen stop threshold")
    spent = (sum(continuation["known_prior_model_usd"].values())
             + sum(continuation["known_prior_probe_usd"].values())
             + continuation["unknown_prior_failed_call_reserved_usd"] + probe_result["cost_usd"])
    spent += sum(r["cost_usd"] if r["cost_usd"] is not None else
                 frozen["schedule"][r["index"]]["reserve_usd"] for r in rows)
    queued = continuation["indexes"][len(rows):]
    if continuation["max_inflight"] != 1:
        raise ValueError("A4 must dispatch at concurrency one")
    for position, i in enumerate(queued):
        remaining = sum(frozen["schedule"][j]["reserve_usd"] for j in queued[position:])
        if spent + remaining > continuation["configured_cap_usd"]:
            ledger["status"] = "stopped_configured_budget"
            study.write(output / "ledger.json", ledger)
            break
        case = frozen["schedule"][i]
        rows.append({"index": i, "case_id": case["id"], "prompt_sha256": case["prompt_sha256"],
                     "state": "pending"})
        ledger["status"] = "running"
        study.write(output / "ledger.json", ledger)
        result = await study.one_case(i, case, provider, frozen["provider_identity"], allowed,
                                      frozen["plan"]["max_output_tokens"])
        rows[-1] = result
        spent += result["cost_usd"] if result["cost_usd"] is not None else case["reserve_usd"]
        study.write(output / "ledger.json", ledger)
        terminal = failure_stop(rows, continuation["failure_policy"])
        if terminal:
            ledger["status"] = terminal
            study.write(output / "ledger.json", ledger)
            break
    else:
        ledger["status"] = "completed_with_failures" if any(r["state"] == "failed" for r in rows) else "completed"
        study.write(output / "ledger.json", ledger)
    return {"status": ledger["status"], "continuation_attempted": len(rows),
            "completed": sum(r["state"] == "completed" for r in rows),
            "malformed": sum(r["state"] == "malformed" for r in rows),
            "failed": sum(r["state"] == "failed" for r in rows),
            "known_configured_cost_including_prior_and_probes_usd":
                (sum(continuation["known_prior_model_usd"].values())
                 + sum(continuation["known_prior_probe_usd"].values()) + probe_result["cost_usd"]
                 + sum(r["cost_usd"] for r in rows if r["cost_usd"] is not None)),
            "unknown_failed_call_reserved_usd": continuation["unknown_prior_failed_call_reserved_usd"]
                + sum(frozen["schedule"][r["index"]]["reserve_usd"] for r in rows if r["cost_usd"] is None)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("a2", type=Path)
    parser.add_argument("a3", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    original_dir, a2_dir, a3_dir, output = (
        p.resolve() for p in (args.original, args.a2, args.a3, args.output))
    if any(output == p or output.is_relative_to(p) for p in (original_dir, a2_dir, a3_dir)):
        raise ValueError("A4 output must be separate from all immutable source ledgers")
    candidate = prepare(original_dir, a2_dir, a3_dir)
    _initial(candidate, output)
    frozen = verify(candidate, original_dir, a2_dir, a3_dir)
    if args.probe:
        result = asyncio.run(probe(candidate, frozen, output))
    elif args.execute:
        result = asyncio.run(execute(candidate, frozen, output))
    else:
        result = {"status": "frozen_no_model_calls", "freeze_sha256": candidate["freeze_sha256"],
                  "remaining_slots": len(candidate["indexes"]), "start_index": candidate["start_index"],
                  "known_prior_model_usd": candidate["known_prior_model_usd"],
                  "known_prior_probe_usd": candidate["known_prior_probe_usd"],
                  "unknown_prior_failed_call_reserved_usd": candidate["unknown_prior_failed_call_reserved_usd"],
                  "probe_reserved_usd": candidate["probe_reserved_usd"],
                  "continuation_reserved_usd": candidate["continuation_reserved_usd"]}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
