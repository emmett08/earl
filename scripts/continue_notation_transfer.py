#!/usr/bin/env python3
"""Document and continue a frozen diagnostic after a measured length failure.

This is an operational amendment, not a new experiment or a retry. The original
runner, freeze, prompts, schedule, output limit, rates and scoring stay fixed.
Every truncated response remains a failed primary outcome. Only a provider
failure with a retained length response, exact model and fully known cost may
be passed. Network failures, unknown usage and uncertain attempts stop the run.

First review the immutable sidecar without making requests::

    python scripts/continue_notation_transfer.py --output RUN_DIR \
        --approve-failure trial-00029:SHA256

Then add --execute, or execute the already prepared sidecar without repeating
the approval. All original costs count against the original campaign threshold.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time

import notation_transfer_experiment as study
from eal.providers import ModelResponse, ProviderError, provider_from_config, response_cost


SCHEMA = "EAL/notation-transfer-continuation/1"
POLICY = {
    "eligible_failure": "provider_error with retained single assistant choice and finish_reason length",
    "required_identity": "response model exactly equals frozen model",
    "required_usage": "known input/output counts and consistent cached/reasoning counts; saved cost equals recomputed cost",
    "existing_failures": "explicit trial ID and original byte SHA256 approval required",
    "later_length_failures": "retain failed primary outcome, charge known cost, record SHA256 and advance once",
    "other_failures": "stop; never retry existing or uncertain attempts",
    "experiment_changes": "none: original schedule, prompts, output cap, rates and scoring retained",
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_freeze(output):
    path = output / "freeze.json"
    if not path.is_file():
        raise ValueError("Continuation requires the original existing freeze")
    frozen = study.strict_json(path.read_text())
    core = {key: value for key, value in frozen.items() if key != "freeze_digest"}
    if study.digest(core) != frozen.get("freeze_digest"):
        raise ValueError("Freeze digest does not match its contents")
    if sha256(study.__file__) != frozen.get("script_sha256"):
        raise ValueError("Original runner changed since freezing")
    if study._code_identity()["source_digest"] != frozen["runtime"]["source_digest"]:
        raise ValueError("Original runtime changed since freezing")
    if frozen.get("scoring_schema") != study.SCORING_SCHEMA:
        raise ValueError("Frozen scoring schema does not match original runner")
    ids = [row["trial_id"] for row in frozen["schedule"]]
    if len(ids) != len(set(ids)) or any(Path(name).name != name for name in ids):
        raise ValueError("Invalid frozen schedule IDs")
    return frozen


def _existing(output, frozen):
    """Read a contiguous prefix; do not silently skip files outside the schedule."""
    schedule = frozen["schedule"]
    expected_paths = {row["trial_id"] + ".json" for row in schedule}
    if any(path.name not in expected_paths for path in (output / "trials").glob("*.json")):
        raise ValueError("Unexpected trial file outside frozen schedule")
    records = []
    gap = False
    for row in schedule:
        path = output / "trials" / (row["trial_id"] + ".json")
        if not path.exists():
            gap = True
            continue
        if gap:
            raise ValueError("Existing trials are not a contiguous schedule prefix")
        record = study.strict_json(path.read_text())
        if any(record.get(key) != value for key, value in row.items()):
            raise ValueError("Stored trial does not match frozen schedule")
        if record.get("freeze_digest") != frozen["freeze_digest"]:
            raise ValueError("Stored trial belongs to a different freeze")
        if record.get("state") == "attempt_started":
            # It may have been charged. No sidecar or operator flag permits retry.
            records.append(record)
            continue
        messages = study.messages_for(frozen["tasks"][row["task_id"]], row["condition"],
                                      row["repetition"], frozen["common_reference"])
        if study.digest(messages) != row["messages_digest"] or record.get("messages") != messages:
            raise ValueError("Stored trial prompt differs from frozen prompt")
        if record.get("scoring_schema") != study.SCORING_SCHEMA:
            raise ValueError("Stored trial has an unexpected scoring schema")
        records.append(record)
    return records


def _known_cost(record, frozen):
    """Validate measurements independently of the saved model-match/cost flags."""
    if record.get("state") == "attempt_started":
        raise ValueError("Unresolved attempt must not be retried")
    if record.get("state") not in {"responded", "malformed_response", "provider_error"}:
        raise ValueError("Unknown recorded outcome state")
    try:
        response = ModelResponse(**record["response"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Unknown response usage") from exc
    if response.model != frozen["provider_identity"]["model"] or record.get("response_model_matches") is not True:
        raise ValueError("Response model is unverified")
    if response.input_tokens is None or response.output_tokens is None:
        raise ValueError("Unknown response usage")
    cached = response.metadata.get("cached_input_tokens")
    # Cache-sensitive rates require an explicit count; absence is not evidence of zero.
    if "cached_input_usd_per_million" in frozen["provider_identity"].get("pricing", {}) and cached is None:
        raise ValueError("Unknown cached input usage")
    if cached is not None and (type(cached) is not int or not 0 <= cached <= response.input_tokens):
        raise ValueError("Inconsistent cached input usage")
    reasoning = response.metadata.get("reasoning_tokens")
    if reasoning is not None and (type(reasoning) is not int or not 0 <= reasoning <= response.output_tokens):
        raise ValueError("Inconsistent reasoning token usage")
    cost = response_cost(response, frozen["provider_identity"])
    saved = record.get("cost_usd")
    if cost is None or isinstance(saved, bool) or not isinstance(saved, (float, int)) or not math.isfinite(saved) or saved != cost:
        raise ValueError("Unknown or inconsistent recorded cost")
    return cost


def _length_failure(record, frozen):
    cost = _known_cost(record, frozen)
    metadata = record["response"]["metadata"]
    choices = metadata.get("response_choices")
    if (record["state"] != "provider_error" or metadata.get("finish_reason") != "length"
            or not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict)
            or choices[0].get("finish_reason") != "length"):
        raise ValueError("Provider error is not a retained length failure")
    message = choices[0].get("message")
    if (not isinstance(message, dict) or message.get("role") != "assistant"
            or not isinstance(message.get("content"), str)
            or message.get("tool_calls") or message.get("function_call") or message.get("refusal")):
        raise ValueError("Length response is not a plain assistant text completion")
    if record["score"].get("correct") or record["available_information_score"].get("correct"):
        raise ValueError("Length failure must remain a failed primary outcome")
    return cost


def _entry(output, record):
    return {"trial_id": record["trial_id"],
            "sha256": sha256(output / "trials" / (record["trial_id"] + ".json")),
            "state": record["state"], "cost_usd": record.get("cost_usd")}


def prepare(output, approved_failures):
    """Author the operational amendment before calls, binding every prior byte."""
    output = Path(output)
    frozen = _load_freeze(output)
    sidecar = output / "continuation.json"
    if sidecar.exists():
        metadata = _validate_sidecar(output, frozen)
        if approved_failures and approved_failures != metadata["approved_existing_failures"]:
            raise ValueError("Approval differs from immutable continuation sidecar")
        return metadata
    records = _existing(output, frozen)
    if not records:
        raise ValueError("Continuation requires an existing failed attempt")
    failures = {r["trial_id"]: sha256(output / "trials" / (r["trial_id"] + ".json"))
                for r in records if r.get("state") == "provider_error"}
    if not failures or failures != approved_failures:
        raise ValueError("Exact trial ID and byte SHA256 approval required for all existing failures")
    charged = 0.0
    for record in records:
        charged += _length_failure(record, frozen) if record["state"] == "provider_error" else _known_cost(record, frozen)
    if records[-1]["state"] != "provider_error":
        raise ValueError("Initial continuation must follow the recorded failure")
    metadata = {
        "schema": SCHEMA, "created_at": datetime.now(timezone.utc).isoformat(),
        "original_freeze_sha256": sha256(output / "freeze.json"),
        "original_freeze_digest": frozen["freeze_digest"],
        "original_runner_sha256": frozen["script_sha256"],
        "continuation_runner_sha256": sha256(__file__),
        "scoring_schema": study.SCORING_SCHEMA,
        "policy": POLICY,
        "approved_existing_failures": approved_failures,
        "original_records": [_entry(output, record) for record in records],
        "original_known_cost_usd": charged,
        "max_campaign_model_cost_usd": frozen["plan"]["max_campaign_model_cost_usd"],
        "remaining_schedule_ids": [row["trial_id"] for row in frozen["schedule"][len(records):]],
    }
    metadata["continuation_digest"] = study.digest(metadata)
    study.write(sidecar, metadata)
    return metadata


def _validate_sidecar(output, frozen):
    metadata = study.strict_json((output / "continuation.json").read_text())
    core = {key: value for key, value in metadata.items() if key != "continuation_digest"}
    if study.digest(core) != metadata.get("continuation_digest"):
        raise ValueError("Continuation sidecar digest mismatch")
    expected = {"schema": SCHEMA, "original_freeze_sha256": sha256(output / "freeze.json"),
                "original_freeze_digest": frozen["freeze_digest"],
                "original_runner_sha256": frozen["script_sha256"],
                "continuation_runner_sha256": sha256(__file__), "scoring_schema": study.SCORING_SCHEMA,
                "policy": POLICY,
                "max_campaign_model_cost_usd": frozen["plan"]["max_campaign_model_cost_usd"]}
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError("Continuation binding changed")
    entries = metadata["original_records"]
    if [entry["trial_id"] for entry in entries] != [row["trial_id"] for row in frozen["schedule"][:len(entries)]]:
        raise ValueError("Original record manifest does not match frozen schedule")
    if metadata["remaining_schedule_ids"] != [row["trial_id"] for row in frozen["schedule"][len(entries):]]:
        raise ValueError("Continuation changed the remaining schedule")
    for entry in entries:
        if sha256(output / "trials" / (entry["trial_id"] + ".json")) != entry["sha256"]:
            raise ValueError("Original trial bytes changed after continuation preparation")
    return metadata


def _record_outcome(record, response, task, row, frozen):
    """Apply exactly the frozen runner's response contract and two scores."""
    cost = response_cost(response, frozen["provider_identity"]) if response else None
    record.update(response=asdict(response) if response else None, cost_usd=cost,
                  response_model_matches=(response.model == frozen["provider_identity"]["model"]) if response else None)
    final = None
    if response and record["state"] == "responded":
        try:
            decoded = study.strict_json(response.text)
            if not isinstance(decoded, dict) or set(decoded) != {"claims", "basis"} or not isinstance(decoded["basis"], list):
                raise ValueError("Response must contain claims and basis")
            if not isinstance(decoded["claims"], dict) or set(decoded["claims"]) != set(task["expected"]) or any(s not in study.STATUSES for s in decoded["claims"].values()):
                raise ValueError("Wrong claim identifiers or status labels")
            final = decoded
        except (ValueError, TypeError):
            record["state"] = "malformed_response"
    scored_report = {"final": final, "status": "completed" if final is not None else "incomplete"}
    record["scoring_schema"] = study.SCORING_SCHEMA
    record["score"] = study.score_answer(task["expected"], scored_report)
    available_expected = task["available_information_references"][row["condition"]["information"]]
    record["available_information_score"] = study.score_answer(available_expected, scored_report)
    proposed = study.candidate_answer(task["expected"], row["condition"]["candidate_quality"], row["repetition"])
    record["proposal_correct_given_available_information"] = (
        all(proposed[name] == status for name, status in available_expected.items()) if proposed is not None else None)


def _finish(output, frozen, metadata, records, reason, uncertain=0):
    completed = [record for record in records if record["state"] != "attempt_started"]
    summary = study.summarise(completed, len(frozen["schedule"]), uncertain)
    status = {"status": reason, **summary, "live_results": bool(completed),
              "continuation_digest": metadata["continuation_digest"]}
    added = [record for record in completed if record["trial_id"] in metadata["remaining_schedule_ids"]]
    skipped = []
    for record in completed:
        if record["state"] == "provider_error":
            try:
                _length_failure(record, frozen)
            except ValueError:
                continue
            skipped.append(_entry(output, record))
    journal = {
        "schema": "EAL/notation-transfer-continuation-status/1", "status": reason,
        "continuation_digest": metadata["continuation_digest"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "completed_output_range": {"first": added[0]["trial_id"], "last": added[-1]["trial_id"], "count": len(added)} if added else None,
        "completed_records": [_entry(output, record) for record in added],
        "retained_length_failures": skipped,
        "known_cost_usd": sum(record["cost_usd"] or 0 for record in completed),
        "uncertain_attempts": uncertain,
    }
    study.write(output / "continuation-status.json", journal)
    study.write(output / "report.json", summary)
    study.write(output / "execution-status.json", status)
    return status


async def execute(output, approved_failures=None):
    output = Path(output)
    frozen = _load_freeze(output)
    metadata = prepare(output, approved_failures or {})
    records = _existing(output, frozen)
    charged = 0.0
    for record in records:
        if record["state"] == "attempt_started":
            return _finish(output, frozen, metadata, records, "unresolved_attempt_not_retried", 1)
        try:
            cost = _known_cost(record, frozen)
            if record["state"] == "provider_error":
                _length_failure(record, frozen)
                approved = metadata["approved_existing_failures"].get(record["trial_id"])
                if record["trial_id"] not in metadata["remaining_schedule_ids"] and approved != _entry(output, record)["sha256"]:
                    raise ValueError("Prior failure is not approved")
            charged += cost
        except ValueError:
            return _finish(output, frozen, metadata, records, "prior_provider_failure_not_retried")
    # Audit every existing outcome before obtaining a provider or a credential.
    if len(records) == len(frozen["schedule"]):
        return _finish(output, frozen, metadata, records, "completed")
    provider = provider_from_config(frozen["provider_configuration"])
    if provider.identity() != frozen["provider_identity"]:
        return _finish(output, frozen, metadata, records, "provider_identity_changed")
    credential = frozen["provider_configuration"].get("api_key_env", "OPENAI_API_KEY")
    if frozen["provider_identity"]["adapter"] == "chat_completions" and credential and not os.getenv(credential):
        return _finish(output, frozen, metadata, records, "blocked_before_execution")
    reason = "completed"
    for row in frozen["schedule"][len(records):]:
        task = frozen["tasks"][row["task_id"]]
        messages = study.messages_for(task, row["condition"], row["repetition"], frozen["common_reference"])
        if study.digest(messages) != row["messages_digest"]:
            raise ValueError("Prompt drift")
        rates = frozen["provider_identity"].get("pricing", {})
        if not {"input_usd_per_million", "output_usd_per_million"} <= rates.keys():
            reason = "pricing_unavailable"
            break
        # This is the original runner's unchanged conservative pre-call bound.
        byte_bound = len(json.dumps(messages, ensure_ascii=False).encode()) + 2048
        allowance = (byte_bound * rates["input_usd_per_million"] + frozen["plan"]["max_output_tokens"] * rates["output_usd_per_million"]) / 1e6
        if charged + allowance > frozen["plan"]["max_campaign_model_cost_usd"]:
            reason = "cost_threshold"
            break
        target = output / "trials" / (row["trial_id"] + ".json")
        record = {**row, "freeze_digest": frozen["freeze_digest"], "state": "attempt_started",
                  "started_at": datetime.now(timezone.utc).isoformat(), "messages": messages,
                  "continuation_digest": metadata["continuation_digest"]}
        # Exclusive creation prevents a second process from repeating this attempt.
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x") as stream:
            json.dump(record, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
        response = None
        started = time.monotonic()
        try:
            response = await provider.complete(messages, frozen["plan"]["max_output_tokens"])
            record["state"] = "responded"
        except ProviderError as exc:
            response = exc.response
            record["state"] = "provider_error"
            record["error"] = type(exc).__name__
        record["latency_seconds"] = time.monotonic() - started
        _record_outcome(record, response, task, row, frozen)
        study.write(target, record)
        records.append(record)
        if not record["response_model_matches"]:
            reason = "response_model_unverified"
        else:
            try:
                charged += _known_cost(record, frozen)
                if record["state"] == "provider_error":
                    _length_failure(record, frozen)
            except ValueError:
                reason = "provider_failure_or_unknown_usage"
        # Persist the decision and retained failure hash before any later call.
        intermediate = "running" if reason == "completed" and len(records) < len(frozen["schedule"]) else reason
        _finish(output, frozen, metadata, records, intermediate)
        if reason != "completed":
            break
    return _finish(output, frozen, metadata, records, reason)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approve-failure", action="append", default=[], metavar="TRIAL_ID:SHA256")
    parser.add_argument("--execute", action="store_true", help="Continue with actual configured model requests")
    args = parser.parse_args()
    approvals = {}
    for value in args.approve_failure:
        trial_id, separator, checksum = value.partition(":")
        if not separator or len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum) or trial_id in approvals:
            parser.error("--approve-failure requires a unique TRIAL_ID:lowercase_SHA256")
        approvals[trial_id] = checksum
    if args.execute:
        result = asyncio.run(execute(args.output, approvals))
    else:
        metadata = prepare(args.output, approvals)
        result = {"status": "continuation_prepared_no_model_calls", "continuation_digest": metadata["continuation_digest"],
                  "remaining_trials": len(metadata["remaining_schedule_ids"]),
                  "original_known_cost_usd": metadata["original_known_cost_usd"]}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
