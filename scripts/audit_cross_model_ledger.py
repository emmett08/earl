#!/usr/bin/env python3
"""Read-only forensic checks for one frozen developmental campaign ledger.

This is deliberately outside the campaign's frozen material set. It does not
alter, resume, score explanations, or submit model calls. The monetary values
are estimates from configured rates, not provider invoices.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path

import analyse_cross_model_campaign as legacy_analysis
from run_cross_model_campaign import _route, answer, digest, read_json, verify_freeze
from eal.providers import ModelResponse, response_cost


ROUTE_V2_SYSTEM = (
    "The host validated the earlier assessment request. Assess only the named claim using the "
    "host result. Reply with exactly one JSON object with two fields: claims (the claim ID mapped "
    "to supported, contested, unsupported, or out_of_scope) and explanation (one concise sentence). "
    "Use the host status as authoritative and explain only what the checked packet warrants. "
    "Do not return another operation request."
)


def _same_float(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-12)


def _cost_and_usage(response: dict | None, usage: dict | None, identity: dict) -> tuple[float | None, int, int]:
    if not isinstance(usage, dict):
        return None, 0, 0
    if not isinstance(response, dict) or not isinstance(response.get("metadata"), dict):
        raise ValueError("A priced call requires its retained model response and metadata")
    measured = ModelResponse(response["text"], usage["input_tokens"], usage["output_tokens"],
                             response["model"], response["metadata"])
    cost = response_cost(measured, identity)
    if cost is None or not _same_float(cost, usage["model_cost_usd"]):
        raise ValueError("Configured rate, tokens, and retained call cost disagree")
    return cost, measured.input_tokens, measured.output_tokens


def _routed_packet(second: dict, case: dict, first: dict, row: dict, routing_revision: str | None) -> None:
    messages = second["messages"]
    if len(messages) != len(case["messages"]) + 2:
        raise ValueError("Routed second prompt has an unexpected number of messages")
    marker = "Host assessment result (the status remains authoritative):\n"
    suffix = "\nReturn one JSON object with claims mapping the named claim to the checked status "
    content = messages[-1]["content"]
    if not content.startswith(marker) or suffix not in content:
        raise ValueError("Routed second prompt does not contain the prescribed host packet")
    packet = json.loads(content[len(marker):].split(suffix, 1)[0])
    # Reconstruct the legacy prompt from the frozen first turn, rather than
    # importing the runner's mutable second-turn builder. Later revisions may
    # correct that builder while the old ledger must remain independently
    # auditable under its original, conflicting system instruction.
    first_turn = list(case["messages"])
    if routing_revision == "skill-route-second-turn/2":
        first_turn[0] = {"role": "system", "content": ROUTE_V2_SYSTEM}
    elif routing_revision is not None:
        raise ValueError("Unrecognised versioned routing prompt")
    expected = [*first_turn, {"role": "assistant", "content": first["response"]["text"]},
                {"role": "user", "content": marker + json.dumps(packet, sort_keys=True, ensure_ascii=False)
                 + suffix + "and explanation as one concise sentence."}]
    if (packet.get("claim") != case["claim"] or packet.get("status") != case["host_status"]
            or packet.get("scope") != case["route_packet"]["scope"]
            or packet.get("assessment_id") != row.get("routed_assessment_id")
            or messages != expected):
        raise ValueError("Routed second prompt differs from its checked case and recorded assessment")


def validated_rows(frozen: dict, ledger: dict) -> list[dict]:
    """Validate scores under either immutable freeze schema without monkeypatching."""
    if frozen.get("schema") == "eal2-cross-model-route-v2-freeze/1":
        from run_cross_model_route_v2 import verify_freeze as verify_route_v2
        verify_route_v2(frozen)
        attempts = ledger.get("attempts")
        cases = frozen["cases"]
        if (ledger.get("schema") != "eal2-cross-model-ledger/1"
                or ledger.get("freeze_sha256") != frozen["freeze_sha256"]
                or not isinstance(attempts, list) or len(attempts) > len(cases)):
            raise ValueError("Route-v2 ledger differs from its frozen schedule")
        rows = []
        for index, row in enumerate(attempts):
            case = cases[index]
            if ((row.get("index"), row.get("case_id"), row.get("prompt_sha256")) !=
                    (index, case["case_id"], case["prompt_sha256"]) or row.get("retry_count") != 0):
                raise ValueError("Route-v2 attempt is not its scheduled, unretried prompt")
            if row["status"] == "completed":
                accepted = row.get("route_requested")
                if type(accepted) is not bool:
                    raise ValueError("Completed route lacks a validated host-request outcome")
                parsed = (answer(row["response"]["text"], case["claim"]) if accepted else
                          {"status": None, "explanation": None, "format_valid": False,
                           "error": row.get("route_reason")})
                status = case["host_status"] if accepted else None
                usage = row.get("usage")
                if (parsed != row.get("recipient") or status != row.get("accepted_status")
                        or row.get("exact_status_correct") != (status == case["expected"])
                        or row.get("false_support") != (status == "supported" and case["expected"] != "supported")
                        or not isinstance(usage, dict)
                        or any(type(usage.get(key)) is not int or usage[key] < 0
                               for key in ("input_tokens", "output_tokens", "cached_input_tokens"))
                        or isinstance(usage.get("model_cost_usd"), bool)
                        or not isinstance(usage.get("model_cost_usd"), (int, float))
                        or not math.isfinite(usage["model_cost_usd"]) or usage["model_cost_usd"] < 0):
                    raise ValueError("Route-v2 recipient, final score, or usage is inconsistent")
            rows.append({**case, "attempt": row})
        if ledger.get("status") == "complete" and len(attempts) != len(cases):
            raise ValueError("Complete route-v2 ledger is missing scheduled attempts")
        return rows
    verify_freeze(frozen)
    return legacy_analysis._audit(frozen, ledger)


def inspect(run_dir: Path) -> dict:
    frozen, ledger = read_json(run_dir / "freeze.json"), read_json(run_dir / "ledger.json")
    validated_rows(frozen, ledger)
    cases, attempts = frozen["cases"], ledger["attempts"]
    conditions = {item["id"] for item in frozen["plan"]["conditions"]}
    blocks: dict[tuple[str, str, int], Counter] = defaultdict(Counter)
    route_prefix_match = route_cases = 0
    for case in cases:
        blocks[(case["root_id"], case["state_id"], case["repetition"])][case["condition_id"]] += 1
        if case["arm"] == "skill_route":
            route_cases += 1
            content = case["messages"][1]["content"]
            brief = content.split("Task: ", 1)[1].split("\nCandidates:\n", 1)[0]
            candidates = json.loads(content.split("\nCandidates:\n", 1)[1])
            own = [item for item in candidates if item["artifact_id"] == case["root_id"]]
            route_prefix_match += int(len(own) == 1 and brief.startswith(own[0]["description"]))
    if any(set(counts) != conditions or any(n != 1 for n in counts.values()) for counts in blocks.values()):
        raise ValueError("Frozen schedule is not complete and paired within each root/state/repetition")

    known_cost = 0.0
    all_known_input = all_known_output = unknown_calls = 0
    known_seconds = 0.0
    route_failed_subcall_cost_hidden_from_analyser = 0.0
    recipient_consistency: dict[str, Counter] = defaultdict(Counter)
    for case, row in zip(cases, attempts):
        identity = frozen["provider_identities"][case["condition_id"]]
        expected_model = frozen["plan"].get("response_model_aliases", {}).get(
            case["condition_id"], identity["model"])
        if row["status"] == "completed" and row["response"]["model"] != expected_model:
            raise ValueError("Completed attempt returned a model outside the frozen identity")
        counts = recipient_consistency[case["condition_id"]]
        counts[row["status"]] += 1
        if row["status"] == "completed":
            recipient = row["recipient"]
            counts["valid_json"] += int(recipient["format_valid"])
            counts["malformed_or_declined"] += int(not recipient["format_valid"])
            counts["recipient_oracle_disagreement"] += int(
                recipient["format_valid"] and recipient["status"] != case["expected"])
            counts["recipient_false_support"] += int(
                recipient["status"] == "supported" and case["expected"] != "supported")
            counts["final_false_support"] += int(row["false_support"])
            if case["arm"] in {"eal_host", "equal_checker", "skill_route"}:
                counts["recipient_final_status_disagreement"] += int(
                    recipient["format_valid"] and recipient["status"] != row["accepted_status"])
            counts["oracle_matching_and_status_consistent_before_explanation_review"] += int(
                row["exact_status_correct"] and recipient["format_valid"]
                and recipient["status"] == row["accepted_status"])
        if case["arm"] == "skill_route":
            subcalls = row.get("calls", [])
            if subcalls and subcalls[0]["messages"] != case["messages"]:
                raise ValueError(f"Routed first prompt differs from freeze at {case['case_id']}")
            if len(subcalls) > 2:
                raise ValueError("Routed case exceeded two model calls")
            if row["status"] == "completed":
                accepted, reason = _route(subcalls[0]["response"]["text"], case)
                if (accepted != row.get("route_requested") or reason != row.get("route_reason")
                        or len(subcalls) != 1 + int(accepted)):
                    raise ValueError("Routed first response and recorded routing decision disagree")
            if len(subcalls) > 1:
                _routed_packet(subcalls[1], case, subcalls[0], row, frozen.get("routing_revision"))
            subcall_cost = 0.0
            for call in subcalls:
                if call.get("prompt_sha256") != digest(call["messages"]):
                    raise ValueError("Routed subcall prompt hash disagrees with its messages")
                if call.get("status") == "completed" and call["response"]["model"] != expected_model:
                    raise ValueError("Completed routed subcall used a different model")
                cost, input_tokens, output_tokens = _cost_and_usage(call.get("response"), call.get("usage"), identity)
                if cost is None:
                    unknown_calls += 1
                else:
                    subcall_cost += cost
                    all_known_input += input_tokens
                    all_known_output += output_tokens
                known_seconds += call.get("duration_seconds", 0)
            known_cost += subcall_cost
            if row["status"] == "completed" and not _same_float(subcall_cost, row["usage"]["model_cost_usd"]):
                raise ValueError("Completed route usage differs from its subcall accounting")
            if row["status"] == "failed" and row.get("usage") is None:
                route_failed_subcall_cost_hidden_from_analyser += subcall_cost
            if row["status"] == "pending" and not subcalls:
                unknown_calls += 1
        else:
            cost, input_tokens, output_tokens = _cost_and_usage(row.get("response"), row.get("usage"), identity)
            if cost is None:
                unknown_calls += 1
            else:
                known_cost += cost
                all_known_input += input_tokens
                all_known_output += output_tokens
            known_seconds += row.get("model_api_seconds", row.get("duration_seconds", 0))
    return {
        "schema": "eal2-cross-model-readonly-audit/1",
        "freeze_sha256": frozen["freeze_sha256"],
        "ledger_status": ledger["status"],
        "scheduled_cases": len(cases),
        "paired_blocks": len(blocks),
        "attempts_by_status": dict(Counter(row["status"] for row in attempts)),
        "unattempted_cases": len(cases) - len(attempts),
        "route_candidate_brief_prefix_matches": route_prefix_match,
        "route_scheduled_cases": route_cases,
        "recipient_status_consistency_by_condition": {
            condition["id"]: {
                "arm": condition["arm"], "model_class": condition["model_class"],
                "configured_model": frozen["provider_identities"][condition["id"]]["model"],
                **dict(recipient_consistency[condition["id"]]),
            } for condition in frozen["plan"]["conditions"]
        },
        "known_configured_rate_model_cost_usd_lower_bound": known_cost,
        "recorded_calls_with_unknown_usage": unknown_calls,
        "known_input_tokens_all_attempts": all_known_input,
        "known_output_tokens_all_attempts": all_known_output,
        "recorded_model_api_seconds_all_attempts": known_seconds,
        "failed_route_subcall_cost_missing_from_standard_analyser_usd":
            route_failed_subcall_cost_hidden_from_analyser,
        "limits": "No semantic review, invoice reconciliation, or inference; a pending or unpriced call may have billed.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    print(json.dumps(inspect(parser.parse_args().run_directory), indent=2, sort_keys=True))
