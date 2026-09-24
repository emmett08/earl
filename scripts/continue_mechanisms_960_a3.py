#!/usr/bin/env python3
"""Versioned A3 continuation over only original indices 468..959.

Both earlier ledgers and their failures are pinned and retained, never retried.
A separate metered connection probe precedes A3 calls. A dry freeze performs
no paid operation. This script is distinct from the immutable A2 runner.
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
import consolidate_mechanisms_960 as composite  # noqa: E402

SCHEMA = "eal2-mechanisms-960-a3-freeze/1"
LEDGER = "eal2-mechanisms-960-a3-ledger/1"
PROBE = "eal2-mechanisms-960-a3-separate-probe/1"
START = 468
EXPECTED_A2_LEDGER_FILE = "4f5714c777f9ec4cedaf84e2dc06981a0c2273be0e407c963c2cb446781ce550"
ACCEPTED_LENGTH_MODEL = "gpt-4.1-nano-2025-04-14"


def sources(original_dir: Path, a2_dir: Path) -> tuple[dict, dict, dict, dict]:
    """Revalidate exact immutable inputs, all 468 rows and separate A2 probe."""
    original_dir, a2_dir = original_dir.resolve(), a2_dir.resolve()
    summary, joined, unused_freeze, unused_probe, paths = composite.compose(original_dir, a2_dir)
    if (summary["attempted"] != START or summary["unattempted"] != 960-START
            or summary["input_file_sha256"]["continuation_ledger"] != EXPECTED_A2_LEDGER_FILE
            or summary["state_counts"] != {"completed": 461, "malformed": 2, "failed": 5}
            or summary["unknown_charge_attempt_indexes"] != [129, 138, 142, 377]):
        raise ValueError("A3 only applies to the exact terminal 468-attempt stop")
    a2_ledger = study.strict_json((a2_dir / "ledger.json").read_text(encoding="utf-8"))
    if (a2_ledger["status"] != "stopped_identity_usage_or_other_failure"
            or a2_ledger["attempts"][-1]["index"] != 467):
        raise ValueError("The A2 stop or final assigned index differs")
    last = a2_ledger["attempts"][-1]
    if (last["state"] != "failed" or last["error_kind"] != "ProviderError"
            or last["cost_usd"] is None or not isinstance(last["response"], dict)
            or last["response"].get("model") != ACCEPTED_LENGTH_MODEL
            or last["response"].get("metadata", {}).get("finish_reason") != "length"):
        raise ValueError("Metered length-limited final A2 response differs")
    frozen = study.strict_json((original_dir / "freeze.json").read_text(encoding="utf-8"))
    probe = study.strict_json((a2_dir / "probe.json").read_text(encoding="utf-8"))
    # Read-only composition already checked every prompt, score, usage and cost.
    for path, expected in paths:
        composite._again(path, expected)
    return frozen, summary, joined, probe


def prepare(original_dir: Path, a2_dir: Path) -> dict:
    frozen, summary, joined, a2_probe = sources(original_dir, a2_dir)
    indexes = list(range(START, 960))
    rates = frozen["provider_identity"].get("pricing", {})
    probe_reserve = ((512 + 4096) * rates["input_usd_per_million"]
                     + 16 * rates["output_usd_per_million"]) / 1e6
    original_rows, a2_rows = joined["attempts"][:132], joined["attempts"][132:]
    original_known = sum(row["cost_usd"] for row in original_rows if row["cost_usd"] is not None)
    a2_known = sum(row["cost_usd"] for row in a2_rows if row["cost_usd"] is not None)
    unknown_failure_reserve = sum(frozen["schedule"][i]["reserve_usd"]
                                  for i in summary["unknown_charge_attempt_indexes"])
    remaining_reserve = sum(frozen["schedule"][i]["reserve_usd"] for i in indexes)
    cap = frozen["plan"]["max_configured_model_cost_usd"]
    base = original_known + a2_known + a2_probe["cost_usd"] + unknown_failure_reserve
    if base + probe_reserve + remaining_reserve > cap:
        raise ValueError("Earlier costs, unknown reservations, two probes and remaining schedule exceed cap")
    result = {"schema": SCHEMA, "source_freeze_sha256": frozen["freeze_sha256"],
              "source_freeze_file_sha256": study.digest((original_dir / "freeze.json").read_bytes()),
              "source_terminal_ledger_file_sha256": summary["input_file_sha256"]["original_ledger"],
              "a2_freeze_sha256": composite.A2_SEMANTIC_FREEZE,
              "a2_freeze_file_sha256": summary["input_file_sha256"]["continuation_freeze"],
              "a2_terminal_ledger_file_sha256": summary["input_file_sha256"]["continuation_ledger"],
              "a2_probe_file_sha256": summary["input_file_sha256"]["separate_probe"],
              "composite_script_sha256": study.digest(Path(composite.__file__).read_bytes()),
              "script_sha256": study.digest(Path(__file__).read_bytes()),
              "indexes": indexes, "case_prompt_sha256": [frozen["schedule"][i]["prompt_sha256"] for i in indexes],
              "known_original_model_usd": original_known, "known_a2_model_usd": a2_known,
              "known_a2_probe_usd": a2_probe["cost_usd"],
              "prior_failed_indexes": [row["index"] for row in joined["attempts"] if row["state"] == "failed"],
              "prior_unknown_charge_indexes": summary["unknown_charge_attempt_indexes"],
              "unknown_failure_reserved_usd": unknown_failure_reserve,
              "probe_reserved_usd": probe_reserve, "continuation_reserved_usd": remaining_reserve,
              "configured_cap_usd": cap, "max_inflight": 2,
              "failure_policy": {
                  "no_retry": True,
                  "continue_after": ["response-less ProviderError, unknown actual charge reserved",
                                     "accepted-model metered ProviderError with finish_reason=length, known charge"],
                  "stop_consecutive_provider_failures": 3,
                  "stop_total_provider_failures": 8,
                  "threshold_scope": "new A3 attempts only; five prior failures retained separately",
                  "stop_immediately_after_batch": ["response_model_mismatch", "unknown_billed_usage",
                                                   "any other failure kind"],
                  "unknown_charge_reservation": "frozen per-case maximum for each failed slot"},
              "amendment": "A3: retain original and A2 failures (including metered length at 467) without retry; "
                           "send only original indices 468..959 at concurrency two. Continue after isolated "
                           "response-less ProviderError or metered accepted-model length, with A3-only thresholds."}
    result["freeze_sha256"] = study.digest(result)
    return result


def verify(continuation: dict, original_dir: Path, a2_dir: Path) -> dict:
    if continuation.get("schema") != SCHEMA:
        raise ValueError("Wrong continuation freeze schema")
    if study.digest({k: v for k, v in continuation.items() if k != "freeze_sha256"}) != continuation.get("freeze_sha256"):
        raise ValueError("Continuation freeze hash differs")
    if study.digest(Path(__file__).read_bytes()) != continuation["script_sha256"]:
        raise ValueError("Continuation runner changed after freeze")
    if study.digest(Path(composite.__file__).read_bytes()) != continuation["composite_script_sha256"]:
        raise ValueError("Pinned source validator changed after freeze")
    frozen, summary, joined, a2_probe = sources(original_dir, a2_dir)
    if (frozen["freeze_sha256"] != continuation["source_freeze_sha256"]
            or study.digest((original_dir / "freeze.json").read_bytes()) != continuation["source_freeze_file_sha256"]
            or summary["input_file_sha256"]["original_ledger"] != continuation["source_terminal_ledger_file_sha256"]
            or summary["input_file_sha256"]["continuation_freeze"] != continuation["a2_freeze_file_sha256"]
            or summary["input_file_sha256"]["continuation_ledger"] != continuation["a2_terminal_ledger_file_sha256"]
            or summary["input_file_sha256"]["separate_probe"] != continuation["a2_probe_file_sha256"]):
        raise ValueError("Source stopped campaign or A2 artifacts changed after A3 freeze")
    if (continuation["a2_freeze_sha256"] != composite.A2_SEMANTIC_FREEZE
            or continuation["prior_failed_indexes"] != [129,138,142,377,467]
            or continuation["prior_unknown_charge_indexes"] != [129,138,142,377]
            or continuation["max_inflight"] != 2
            or continuation["indexes"] != list(range(START, 960))
            or continuation["case_prompt_sha256"] !=
            [frozen["schedule"][i]["prompt_sha256"] for i in range(START, 960)]):
        raise ValueError("Continuation changed original order or prompts")
    if (continuation["known_original_model_usd"] !=
            sum(row["cost_usd"] for row in joined["attempts"][:132] if row["cost_usd"] is not None)
            or continuation["known_a2_model_usd"] !=
            sum(row["cost_usd"] for row in joined["attempts"][132:] if row["cost_usd"] is not None)
            or continuation["known_a2_probe_usd"] != a2_probe["cost_usd"]
            or continuation["unknown_failure_reserved_usd"] != sum(
                frozen["schedule"][i]["reserve_usd"] for i in [129,138,142,377])):
        raise ValueError("Prior charge and reservation accounting changed")
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
            or probe_result.get("cost_usd") is None or not isinstance(probe_result.get("response"), dict)):
        raise ValueError("Probe is incomplete, unbilled or belongs to another freeze")
    measured_probe = study.ModelResponse(**probe_result["response"])
    if (measured_probe.model not in frozen["plan"]["accepted_response_models"]
            or response_cost(measured_probe, frozen["provider_identity"]) != probe_result["cost_usd"]):
        raise ValueError("Probe model, usage or configured charge differs")
    provider = load_provider(study.local_file(ROOT, frozen["provider_file"]))
    if provider.identity() != frozen["provider_identity"]:
        raise ValueError("Provider changed since original freeze")
    if not os.environ.get("OPENAI_API_TOKEN"):
        raise ValueError("Configured credential is absent before continuation")
    rows = ledger["attempts"]
    if [row.get("index") for row in rows] != continuation["indexes"][:len(rows)]:
        raise ValueError("Continuation rows are not an exact frozen prefix")
    allowed=set(frozen["plan"]["accepted_response_models"])
    for row in rows:
        case = frozen["schedule"][row["index"]]
        composite._check_row(row, case, frozen["provider_identity"], allowed)
        if row["state"] == "failed" and not continuable_failure(row):
            raise ValueError("An earlier non-continuable failure must remain terminal")
    if failure_stop(rows, continuation["failure_policy"]):
        raise ValueError("Earlier failures crossed the frozen stop threshold; no further dispatch")
    spent = (continuation["known_original_model_usd"] + continuation["known_a2_model_usd"]
             + continuation["known_a2_probe_usd"] + continuation["unknown_failure_reserved_usd"])
    spent += probe_result["cost_usd"] + sum(
        row["cost_usd"] if row["cost_usd"] is not None else
        frozen["schedule"][row["index"]]["reserve_usd"] for row in rows)
    queued = continuation["indexes"][len(rows):]
    width = continuation["max_inflight"]
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
            "known_configured_cost_including_original_a2_and_probes_usd":
                 (continuation["known_original_model_usd"] + continuation["known_a2_model_usd"]
                  + continuation["known_a2_probe_usd"] + probe_result["cost_usd"] +
                  sum(row["cost_usd"] for row in rows if row["cost_usd"] is not None)),
            "unknown_failed_call_reserved_usd":
                 continuation["unknown_failure_reserved_usd"] +
                 sum(frozen["schedule"][row["index"]]["reserve_usd"] for row in rows
                     if row["cost_usd"] is None)}


def continuable_failure(row: dict) -> bool:
    """Two explicitly allowed ProviderError forms; both remain failed slots."""
    if row.get("state") != "failed" or row.get("error_kind") != "ProviderError":
        return False
    response = row.get("response")
    if response is None:
        return row.get("cost_usd") is None and row.get("usage") is None
    if (not isinstance(response, dict) or response.get("model") != ACCEPTED_LENGTH_MODEL
            or response.get("metadata", {}).get("finish_reason") != "length"
            or row.get("cost_usd") is None or row.get("usage") is None):
        return False
    choices = response["metadata"].get("response_choices")
    return (isinstance(choices, list) and len(choices) == 1
            and isinstance(choices[0], dict) and choices[0].get("finish_reason") == "length"
            and isinstance(choices[0].get("message"), dict)
            and choices[0]["message"].get("content") == response.get("text"))


def failure_stop(rows: list[dict], policy: dict) -> str | None:
    """Apply frozen A3-only thresholds after a complete two-slot batch."""
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("a2", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    original_dir, a2_dir, output = args.original.resolve(), args.a2.resolve(), args.output.resolve()
    if (output == original_dir or output == a2_dir
            or output.is_relative_to(original_dir) or output.is_relative_to(a2_dir)):
        raise ValueError("A3 output must be a separate directory outside immutable source ledgers")
    candidate = prepare(original_dir, a2_dir)
    _initial(candidate, output)
    frozen = verify(candidate, original_dir, a2_dir)
    if args.probe:
        result = asyncio.run(probe(candidate, frozen, output))
    elif args.execute:
        result = asyncio.run(execute(candidate, frozen, output))
    else:
        result = {"status": "frozen_no_model_calls", "freeze_sha256": candidate["freeze_sha256"],
                  "remaining_slots": len(candidate["indexes"]),
                  "known_original_model_usd": candidate["known_original_model_usd"],
                  "known_a2_model_usd": candidate["known_a2_model_usd"],
                  "known_a2_probe_usd": candidate["known_a2_probe_usd"],
                  "unknown_failure_reserved_usd": candidate["unknown_failure_reserved_usd"],
                  "probe_reserved_usd": candidate["probe_reserved_usd"],
                  "continuation_reserved_usd": candidate["continuation_reserved_usd"]}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
