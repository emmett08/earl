#!/usr/bin/env python3
"""Versioned A2 continuation over only never-attempted 960-study slots.

The original failed attempt is retained, never retried. A separate charged
connection probe and independent schedule audit precede continuation calls.
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

SCHEMA = "eal2-mechanisms-960-continuation-freeze/1"
LEDGER = "eal2-mechanisms-960-continuation-ledger/1"
PROBE = "eal2-mechanisms-960-separate-probe/1"


def original(original_dir: Path) -> tuple[dict, dict, str]:
    original_dir = original_dir.resolve()
    freeze_path, ledger_path = original_dir / "freeze.json", original_dir / "ledger.json"
    frozen = study.strict_json(freeze_path.read_text(encoding="utf-8"))
    study.verify_freeze(frozen)
    ledger_bytes = ledger_path.read_bytes()
    ledger = study.strict_json(ledger_bytes.decode("utf-8"))
    if ledger.get("schema") != study.LEDGER or ledger.get("freeze_sha256") != frozen["freeze_sha256"]:
        raise ValueError("Original terminal ledger is not attached to source freeze")
    rows = ledger["attempts"]
    if (ledger["status"] != "stopped_after_failed_batch" or len(rows) != 132
            or [row.get("index") for row in rows] != list(range(132))):
        raise ValueError("A2 continuation applies only to the retained 132-attempt stop")
    failed = [row for row in rows if row.get("state") == "failed"]
    if len(failed) != 1 or failed[0]["index"] != 129:
        raise ValueError("The single failed index 129 must remain present")
    if failed[0].get("response") is not None or failed[0].get("cost_usd") is not None:
        raise ValueError("The A2 stop assumes one response-less unknown-cost failure")
    for row in rows:
        case = frozen["schedule"][row["index"]]
        if (row.get("case_id"), row.get("prompt_sha256")) != (case["id"], case["prompt_sha256"]):
            raise ValueError("Original ledger row does not match its frozen prompt")
        if row["index"] != 129 and (row.get("state") not in {"completed", "malformed"}
                                    or row.get("cost_usd") is None):
            raise ValueError("Other original attempts are not terminal with known billing")
    return frozen, ledger, study.digest(ledger_bytes)


def prepare(original_dir: Path) -> dict:
    frozen, ledger, original_ledger_sha = original(original_dir)
    indexes = list(range(len(ledger["attempts"]), 960))
    if len(indexes) != 828:
        raise ValueError("Only 828 never-attempted slots may continue")
    rates = frozen["provider_identity"].get("pricing", {})
    probe_reserve = ((512 + 4096) * rates["input_usd_per_million"]
                     + 16 * rates["output_usd_per_million"]) / 1e6
    known = sum(row["cost_usd"] for row in ledger["attempts"] if row["cost_usd"] is not None)
    unknown_failure_reserve = frozen["schedule"][129]["reserve_usd"]
    remaining_reserve = sum(frozen["schedule"][i]["reserve_usd"] for i in indexes)
    cap = frozen["plan"]["max_configured_model_cost_usd"]
    if known + unknown_failure_reserve + probe_reserve + remaining_reserve > cap:
        raise ValueError("Original cost, unknown-failure/probe reserve and remaining schedule exceed cap")
    result = {"schema": SCHEMA, "source_freeze_sha256": frozen["freeze_sha256"],
              "source_freeze_file_sha256": study.digest((original_dir / "freeze.json").read_bytes()),
              "source_terminal_ledger_file_sha256": original_ledger_sha,
              "script_sha256": study.digest(Path(__file__).read_bytes()),
              "indexes": indexes, "case_prompt_sha256": [frozen["schedule"][i]["prompt_sha256"] for i in indexes],
              "known_original_model_usd": known, "failed_index": 129,
              "unknown_failure_reserved_usd": unknown_failure_reserve,
              "probe_reserved_usd": probe_reserve, "continuation_reserved_usd": remaining_reserve,
              "configured_cap_usd": cap,
              "failure_policy": {
                  "no_retry": True,
                  "continue_after": "response-less ProviderError only",
                  "stop_consecutive_provider_failures": 3,
                  "stop_total_provider_failures": 6,
                  "stop_immediately_after_batch": ["response_model_mismatch", "unknown_billed_usage",
                                                   "any other failure kind"],
                  "unknown_charge_reservation": "frozen per-case maximum for each failed slot"},
              "amendment": "A2: after an unmetered ProviderError, retain all 132 original assignments, "
                           "never retry index 129, probe separately and send only original indices 132..959. "
                           "Continue after isolated response-less provider failures up to frozen thresholds."}
    result["freeze_sha256"] = study.digest(result)
    return result


def verify(continuation: dict, original_dir: Path) -> dict:
    if continuation.get("schema") != SCHEMA:
        raise ValueError("Wrong continuation freeze schema")
    if study.digest({k: v for k, v in continuation.items() if k != "freeze_sha256"}) != continuation.get("freeze_sha256"):
        raise ValueError("Continuation freeze hash differs")
    if study.digest(Path(__file__).read_bytes()) != continuation["script_sha256"]:
        raise ValueError("Continuation runner changed after freeze")
    frozen, ledger, ledger_sha = original(original_dir)
    if (frozen["freeze_sha256"] != continuation["source_freeze_sha256"]
            or study.digest((original_dir / "freeze.json").read_bytes()) != continuation["source_freeze_file_sha256"]
            or ledger_sha != continuation["source_terminal_ledger_file_sha256"]):
        raise ValueError("Source stopped campaign changed after A2 freeze")
    if (continuation["indexes"] != list(range(132, 960))
            or continuation["case_prompt_sha256"] !=
            [frozen["schedule"][i]["prompt_sha256"] for i in range(132, 960)]):
        raise ValueError("Continuation changed original order or prompts")
    return frozen


def _initial(continuation: dict, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    freeze_path, ledger_path = output / "freeze.json", output / "ledger.json"
    if freeze_path.exists():
        existing = study.strict_json(freeze_path.read_text(encoding="utf-8"))
        if existing != continuation:
            raise ValueError("Continuation output directory has another freeze")
    else:
        study.write(freeze_path, continuation)
    if ledger_path.exists():
        ledger = study.strict_json(ledger_path.read_text(encoding="utf-8"))
    else:
        ledger = {"schema": LEDGER, "freeze_sha256": continuation["freeze_sha256"],
                  "status": "frozen", "attempts": []}
        study.write(ledger_path, ledger)
    if ledger.get("schema") != LEDGER or ledger.get("freeze_sha256") != continuation["freeze_sha256"]:
        raise ValueError("Continuation ledger belongs to another freeze")
    return ledger


async def probe(continuation: dict, frozen: dict, output: Path) -> dict:
    _initial(continuation, output)
    path = output / "probe.json"
    if path.exists():
        raise ValueError("An existing probe is never retried or overwritten")
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


async def execute(continuation: dict, frozen: dict, output: Path) -> dict:
    ledger = _initial(continuation, output)
    if ledger["status"] in {"completed", "completed_with_failures"} or ledger["status"].startswith("stopped_"):
        raise ValueError("A terminal continuation cannot be resumed")
    probe_path = output / "probe.json"
    if not probe_path.is_file():
        raise ValueError("A separate completed connection probe is required")
    probe_result = study.strict_json(probe_path.read_text(encoding="utf-8"))
    if (probe_result.get("schema") != PROBE or probe_result.get("state") != "completed"
            or probe_result.get("continuation_freeze_sha256") != continuation["freeze_sha256"]
            or probe_result.get("cost_usd") is None):
        raise ValueError("Probe is incomplete, unbilled or belongs to another freeze")
    provider = load_provider(study.local_file(ROOT, frozen["provider_file"]))
    if provider.identity() != frozen["provider_identity"]:
        raise ValueError("Provider changed since original freeze")
    if not os.environ.get("OPENAI_API_TOKEN"):
        raise ValueError("Configured credential is absent before continuation")
    rows = ledger["attempts"]
    if any(row.get("state") not in {"completed", "malformed", "failed"} or
           (row.get("cost_usd") is None and
            not (row.get("state") == "failed" and row.get("error_kind") == "ProviderError"
                 and row.get("response") is None)) for row in rows):
        raise ValueError("An unresolved continuation request may be billed; never retry it")
    if [row.get("index") for row in rows] != continuation["indexes"][:len(rows)]:
        raise ValueError("Continuation rows are not an exact frozen prefix")
    for row in rows:
        case = frozen["schedule"][row["index"]]
        if (row.get("case_id"), row.get("prompt_sha256")) != (case["id"], case["prompt_sha256"]):
            raise ValueError("Continuation row has a changed prompt")
    if failure_stop(rows, continuation["failure_policy"]):
        raise ValueError("Earlier failures crossed the frozen stop threshold; no further dispatch")
    spent = continuation["known_original_model_usd"] + continuation["unknown_failure_reserved_usd"]
    spent += probe_result["cost_usd"] + sum(
        row["cost_usd"] if row["cost_usd"] is not None else
        frozen["schedule"][row["index"]]["reserve_usd"] for row in rows)
    queued = continuation["indexes"][len(rows):]
    width = frozen["plan"]["max_inflight"]
    for offset in range(0, len(queued), width):
        batch = queued[offset:offset + width]
        remaining = sum(frozen["schedule"][i]["reserve_usd"] for i in queued[offset:])
        if spent + remaining > continuation["configured_cap_usd"]:
            ledger["status"] = "stopped_configured_budget"
            study.write(output / "ledger.json", ledger)
            break
        for i in batch:
            case = frozen["schedule"][i]
            rows.append({"index": i, "case_id": case["id"], "prompt_sha256": case["prompt_sha256"],
                         "state": "pending"})
        ledger["status"] = "running"
        study.write(output / "ledger.json", ledger)
        tasks = [asyncio.create_task(study.one_case(i, frozen["schedule"][i], provider,
                 frozen["provider_identity"], set(frozen["plan"]["accepted_response_models"]),
                 frozen["plan"]["max_output_tokens"])) for i in batch]
        for done in asyncio.as_completed(tasks):
            result = await done
            pos = next(j for j, row in enumerate(rows) if row["index"] == result["index"])
            rows[pos] = result
            spent += (result["cost_usd"] if result["cost_usd"] is not None else
                      frozen["schedule"][result["index"]]["reserve_usd"])
            study.write(output / "ledger.json", ledger)
        terminal = failure_stop(rows, continuation["failure_policy"])
        if terminal:
            ledger["status"] = terminal
            study.write(output / "ledger.json", ledger)
            break
    else:
        ledger["status"] = "completed_with_failures" if any(row["state"] == "failed" for row in rows) else "completed"
        study.write(output / "ledger.json", ledger)
    return {"status": ledger["status"], "continuation_attempted": len(rows),
            "completed": sum(row["state"] == "completed" for row in rows),
            "malformed": sum(row["state"] == "malformed" for row in rows),
            "failed": sum(row["state"] == "failed" for row in rows),
            "known_configured_cost_including_original_and_probe_usd":
                 (continuation["known_original_model_usd"] + probe_result["cost_usd"] +
                  sum(row["cost_usd"] for row in rows if row["cost_usd"] is not None)),
            "unknown_failed_call_reserved_usd":
                 continuation["unknown_failure_reserved_usd"] +
                 sum(frozen["schedule"][row["index"]]["reserve_usd"] for row in rows
                     if row["cost_usd"] is None)}


def failure_stop(rows: list[dict], policy: dict) -> str | None:
    """Apply only frozen no-retry failure thresholds after a full dispatched batch."""
    failures = [row for row in rows if row["state"] == "failed"]
    if any(row.get("error_kind") != "ProviderError" or row.get("response") is not None
           for row in failures):
        return "stopped_identity_usage_or_other_failure"
    if len(failures) >= policy["stop_total_provider_failures"]:
        return "stopped_repeated_provider_failures"
    consecutive = 0
    for row in rows:
        consecutive = consecutive + 1 if row["state"] == "failed" else 0
        if consecutive >= policy["stop_consecutive_provider_failures"]:
            return "stopped_repeated_provider_failures"
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    original_dir, output = args.original.resolve(), args.output.resolve()
    candidate = prepare(original_dir)
    _initial(candidate, output)
    frozen = verify(candidate, original_dir)
    if args.probe:
        result = asyncio.run(probe(candidate, frozen, output))
    elif args.execute:
        result = asyncio.run(execute(candidate, frozen, output))
    else:
        result = {"status": "frozen_no_model_calls", "freeze_sha256": candidate["freeze_sha256"],
                  "remaining_slots": len(candidate["indexes"]),
                  "known_original_model_usd": candidate["known_original_model_usd"],
                  "unknown_failure_reserved_usd": candidate["unknown_failure_reserved_usd"],
                  "probe_reserved_usd": candidate["probe_reserved_usd"],
                  "continuation_reserved_usd": candidate["continuation_reserved_usd"]}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
