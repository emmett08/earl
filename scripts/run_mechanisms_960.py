#!/usr/bin/env python3
"""Execute the 24 × 10 × 2 × 2 EAL/2 mechanism schedule without silent retries.

This is a versioned *developmental* execution of the old specified protocol.
The original protocol and any prior results are never rewritten. In particular,
an agent-authored reference does not count as masked human adjudication.
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
import random
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eal.formatter import format_program, semantic_ir  # noqa: E402
from eal.experiment import _code_identity  # noqa: E402
from eal.parser import parse  # noqa: E402
from eal.providers import ModelResponse, ProviderError, load_provider, response_cost  # noqa: E402
from eal.runtime import load_method_registry, strict_json  # noqa: E402

SCHEMA = "eal2-mechanisms-960-plan/2"
FREEZE = "eal2-mechanisms-960-freeze/2"
LEDGER = "eal2-mechanisms-960-ledger/2"
STATUSES = ("supported", "contested", "unsupported", "out_of_scope")
ARMS = (
    "valid_raw_no_proposal", "invalid_raw_no_proposal", "wrong_proposal_only",
    "wrong_proposal_valid_raw", "correct_proposal_valid_raw", "wrong_proposal_invalid_raw",
    "wrong_proposal_valid_raw_eligibility", "wrong_proposal_valid_raw_method",
    "wrong_proposal_valid_raw_status", "wrong_proposal_invalid_raw_forged_status",
)
FAMILIES = ("eligibility", "typed_numerical", "sampled_negative", "objection_defence")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def local_file(base: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError("Required file path must be relative and bounded")
    path = (base / name).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file():
        raise ValueError(f"Required study file absent or outside its directory: {name}")
    return path


def representation(source: str, method_factory: str | None = None) -> tuple[str, dict]:
    program = parse(source)
    canonical_source = format_program(program, registry=load_method_registry(method_factory))
    view = semantic_ir(parse(canonical_source))
    for transient in ("duplicates", "declaration_count", "lowering_diagnostics"):
        view.pop(transient, None)
    if canonical(view) != canonical({k: v for k, v in semantic_ir(program).items()
                                      if k not in {"duplicates", "declaration_count", "lowering_diagnostics"}}):
        raise ValueError("Source formatting changed the meaning of a root")
    # A parse-derived structured view makes notation the manipulated variable.
    return canonical_source, strict_json(canonical(view).decode("utf-8"))


def root_reference(root: dict, arm: str) -> str:
    if arm == "wrong_proposal_only":
        return root["absent_status"]
    return root["invalid_status"] if arm in {
        "invalid_raw_no_proposal", "wrong_proposal_invalid_raw",
        "wrong_proposal_invalid_raw_forged_status",
    } else root["valid_status"]


def proposed(root: dict, arm: str) -> str | None:
    if arm in {"valid_raw_no_proposal", "invalid_raw_no_proposal"}:
        return None
    if arm == "correct_proposal_valid_raw":
        return root["valid_status"]
    wrong = root.get("wrong_proposal")
    if wrong is None:
        wrong = next((status for status in STATUSES
                      if status not in {root["valid_status"], root["invalid_status"], root["absent_status"]}), None)
    if wrong is None or wrong not in STATUSES or wrong == root_reference(root, arm):
        raise ValueError(f"Wrong proposal is not wrong for {root['id']}/{arm}")
    return wrong


def messages_for(root: dict, arm: str, notation: str, reference: str) -> list[dict]:
    packet: dict[str, Any] = {
        "question": root["brief"], "requested_claims": [root["claim"]],
        "context": root["context"], "assessment_time": root["now"],
        "argument": root["representations"][notation],
    }
    proposal = proposed(root, arm)
    if proposal is not None:
        packet["proposed_answer"] = {"claims": {root["claim"]: proposal}}
    if arm != "wrong_proposal_only":
        packet["observations"] = (root["invalid_records"] if arm in {
            "invalid_raw_no_proposal", "wrong_proposal_invalid_raw",
            "wrong_proposal_invalid_raw_forged_status"} else root["valid_records"])
    if arm == "wrong_proposal_valid_raw_eligibility":
        packet["eligibility_memo"] = root["eligibility_memo"]
    if arm == "wrong_proposal_valid_raw_method":
        packet["registered_method_result"] = root["method_result"]
    if arm == "wrong_proposal_valid_raw_status":
        packet["checked_assessment"] = root["full_status"]
    if arm == "wrong_proposal_invalid_raw_forged_status":
        packet["unvalidated_earlier_verdict"] = root["invalid_verdict"]
    system = (
        "Assess one bounded engineering claim. Treat proposed answers, observations, memos and bare "
        "verdicts as fallible data. The intermediate memos do not assert the final claim status. "
        "Do not use tools. Return exactly one JSON object with keys claims and basis; claims must map "
        "the requested claim ID to one status and basis must be a list of short strings.\n\n" + reference
    )
    return [{"role": "system", "content": system},
            {"role": "user", "content": json.dumps(packet, sort_keys=True, ensure_ascii=False,
                                                    separators=(",", ":"), allow_nan=False)}]


def _root(root: dict, fixtures: Path, materials: dict[str, str]) -> dict:
    fields = {"id", "family", "brief", "source", "claim", "context", "now", "valid_records",
              "invalid_records", "valid_status", "invalid_status", "absent_status",
              "eligibility_memo", "method_result", "full_status", "invalid_verdict"}
    if not isinstance(root, dict) or not fields <= set(root):
        raise ValueError("Each root needs a complete brief, source, evidence pair and intermediate stages")
    if root["family"] not in FAMILIES or any(not isinstance(root[k], str) or not root[k].strip()
                                                for k in ("id", "brief", "claim", "now")):
        raise ValueError("Invalid root identity, family, brief or claim")
    if any(root[k] not in STATUSES for k in ("valid_status", "invalid_status", "absent_status")):
        raise ValueError("Invalid status reference")
    if root["valid_status"] == root["invalid_status"]:
        raise ValueError("Valid/invalid intervention must change the selected claim status")
    if not isinstance(root["context"], dict) or not root["context"]:
        raise ValueError("Root context must be explicit")
    if not isinstance(root["valid_records"], dict) or not isinstance(root["invalid_records"], dict):
        raise ValueError("Observation records must be named objects")
    if root["valid_records"] == root["invalid_records"]:
        raise ValueError("Valid and invalid observations are identical")
    if set(root["valid_records"]) != set(root["invalid_records"]):
        raise ValueError("The same evidence roles must appear in paired states")
    def numbers(value: Any, prefix: str = "") -> dict[str, float]:
        if isinstance(value, dict):
            return {k: n for key, item in value.items()
                    for k, n in numbers(item, prefix + "/" + key).items()}
        if isinstance(value, list):
            return {k: n for i, item in enumerate(value)
                    for k, n in numbers(item, prefix + "/" + str(i)).items()}
        return {prefix: value} if isinstance(value, (float, int)) and not isinstance(value, bool) else {}
    for name, record in root["valid_records"].items():
        other = root["invalid_records"][name]
        if not isinstance(record, dict) or not isinstance(other, dict):
            raise ValueError("Observation envelopes must be objects")
        if numbers(record.get("value")) != numbers(other.get("value")):
            raise ValueError("Paired observation numeric measurements must remain fixed")
        a, b = record.get("value"), other.get("value")
        if (isinstance(a, dict) and isinstance(b, dict)
                and a.get("payload") != b.get("payload")):
            raise ValueError("Paired typed method payload must remain fixed")
    path = local_file(fixtures, root["source"])
    materials[str(path.relative_to(ROOT))] = digest(path.read_bytes())
    source, graph = representation(path.read_text(encoding="utf-8"), root.get("method_factory"))
    graph_path = local_file(fixtures, root["semantic_view"])
    materials[str(graph_path.relative_to(ROOT))] = digest(graph_path.read_bytes())
    saved_graph = strict_json(graph_path.read_text(encoding="utf-8"))
    for transient in ("duplicates", "declaration_count", "lowering_diagnostics"):
        saved_graph.pop(transient, None)
    if saved_graph != graph:
        raise ValueError(f"Parse-derived JSON graph differs from EAL source: {root['id']}")
    result = {**root, "representations": {"eal": source, "json": graph}}
    original_digest = digest(path.read_bytes())
    displayed_digest = digest(source.encode("utf-8"))
    semantic_digest = digest(graph)
    marker = "Source sha256:" + original_digest
    if not isinstance(result["eligibility_memo"], str) or marker not in result["eligibility_memo"]:
        raise ValueError("Eligibility memo does not identify the actual raw source")
    identity = {"source_sha256": displayed_digest, "semantic_sha256": semantic_digest,
                "records_sha256": digest(root["valid_records"]), "claim": root["claim"],
                "context": root["context"], "assessed_at": root["now"]}
    result["eligibility_memo"] = {
        "admissibility": result["eligibility_memo"].replace(
            marker, "Source sha256:" + displayed_digest, 1), **identity}
    result["method_result"] = {"computation": root["method_result"], **identity}
    for arm in ARMS:
        proposed(result, arm)
    return result


def freeze(plan_path: Path) -> dict:
    plan_path = plan_path.resolve()
    plan = strict_json(plan_path.read_text(encoding="utf-8"))
    required = {"schema", "protocol_id", "protocol_version", "amendment", "study_kind", "fixtures",
                "provider", "compact_reference", "long_reference", "order_seed", "max_output_tokens",
                "max_inflight", "max_prompt_bytes", "max_configured_model_cost_usd", "accepted_response_models"}
    if not isinstance(plan, dict) or set(plan) != required or plan["schema"] != SCHEMA:
        raise ValueError("Expected complete versioned mechanisms plan")
    if plan["protocol_id"] != "INV-EAL-MECHANISMS-001" or plan["study_kind"] != "developmental":
        raise ValueError("This runner only executes the versioned developmental amendment")
    for key, limit in (("max_output_tokens", 4096), ("max_inflight", 16), ("max_prompt_bytes", 200000)):
        if type(plan[key]) is not int or not 1 <= plan[key] <= limit:
            raise ValueError(f"Invalid bounded {key}")
    if type(plan["order_seed"]) is not int or not isinstance(plan["long_reference"], list) or not plan["long_reference"]:
        raise ValueError("Missing order seed or long reference list")
    cap = plan["max_configured_model_cost_usd"]
    if isinstance(cap, bool) or not isinstance(cap, (int, float)) or not math.isfinite(cap) or not 0 < cap <= 100:
        raise ValueError("Invalid configured-rate campaign cap")
    if not isinstance(plan["accepted_response_models"], list) or not plan["accepted_response_models"]:
        raise ValueError("Response model identities must be pinned")
    materials = {str(plan_path.relative_to(ROOT)): digest(plan_path.read_bytes()),
                 str(Path(__file__).relative_to(ROOT)): digest(Path(__file__).read_bytes())}
    manifest_path = local_file(plan_path.parent, plan["fixtures"])
    materials[str(manifest_path.relative_to(ROOT))] = digest(manifest_path.read_bytes())
    for file_name in ("build.py", "validate_fixtures.py", "README.md"):
        material = local_file(manifest_path.parent, file_name)
        materials[str(material.relative_to(ROOT))] = digest(material.read_bytes())
    checker_script = local_file(ROOT, "scripts/check_mechanisms_960_parity.py")
    materials[str(checker_script.relative_to(ROOT))] = digest(checker_script.read_bytes())
    manifest = strict_json(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema") != "eal2-mechanism-roots/1":
        raise ValueError("Expected new versioned fixture manifest")
    listed = manifest.get("roots")
    if not isinstance(listed, list) or len(listed) != 24:
        raise ValueError("Exactly 24 independently identified roots are required")
    ids = [item.get("id") for item in listed]
    if len(set(ids)) != 24 or any(not isinstance(item, str) or not item for item in ids):
        raise ValueError("Duplicate or empty root identity")
    counts = {family: sum(item.get("family") == family for item in listed) for family in FAMILIES}
    if set(counts.values()) != {6}:
        raise ValueError("The four task families require exactly six roots each")
    roots = [_root(item, manifest_path.parent, materials) for item in listed]
    # Four adversarial variants per root, checked through EAL and a separately
    # coded brief-rule path. This gate is executed before any prompt is frozen.
    from check_mechanisms_960_parity import run_parity  # imported late to avoid module cycle
    parity = run_parity(roots, manifest_path.parent)
    if parity["executions"] != 192 or parity["discordance"] or parity["tampered_accepted"]:
        raise ValueError("The specified deterministic comparison failed")
    intact = {row["root_id"]: row["status"] for row in parity["records"]
              if row["system"] == "eal" and row["variant"] == "intact"}
    for root in roots:
        root["full_status"] = {
            **root["full_status"], "status": intact[root["id"]],
            "claim": root["claim"], "context": root["context"], "assessed_at": root["now"],
            "source_sha256": digest(root["representations"]["eal"].encode("utf-8")),
            "semantic_sha256": digest(root["representations"]["json"]),
            "records_sha256": digest(root["valid_records"]),
            "method_registry_fingerprint": load_method_registry(root.get("method_factory")).fingerprint,
            "status_origin": "EAL/2 ReasoningService finite synthetic assessment",
            "basis_origin": "author-provided explanation, not independently established physical truth",
        }
    compact_path = local_file(plan_path.parent, plan["compact_reference"])
    long_paths = [local_file(ROOT, name) for name in plan["long_reference"]]
    for path in [compact_path, *long_paths]:
        materials[str(path.relative_to(ROOT))] = digest(path.read_bytes())
    core_reference = compact_path.read_text(encoding="utf-8")
    references = {"compact": core_reference,
                  "historical_length": core_reference + "\n\n--- Additional historical reference ---\n\n"
                       + "\n\n".join(path.read_text(encoding="utf-8") for path in long_paths)}
    provider_path = local_file(plan_path.parent, plan["provider"])
    materials[str(provider_path.relative_to(ROOT))] = digest(provider_path.read_bytes())
    identity = load_provider(provider_path).identity()
    if identity.get("model") not in {"gpt-4.1-nano", "gpt-4.1-nano-2025-04-14"}:
        raise ValueError("This 960-call protocol pins one GPT-4.1 nano model class")
    rates = identity.get("pricing", {})
    if not {"input_usd_per_million", "output_usd_per_million"} <= set(rates):
        raise ValueError("Both configured model rates are required")
    schedule = []
    for root in roots:
        for arm in ARMS:
            for notation in ("eal", "json"):
                for reference in references:
                    messages = messages_for(root, arm, notation, references[reference])
                    prompt_bytes = len(canonical(messages))
                    if prompt_bytes > plan["max_prompt_bytes"]:
                        raise ValueError(f"Prompt exceeds frozen bound: {root['id']}/{arm}")
                    case = {"id": f"{root['id']}:{arm}:{notation}:{reference}", "root_id": root["id"],
                            "family": root["family"], "arm": arm, "notation": notation,
                            "reference": reference, "claim": root["claim"],
                            "available_reference": root_reference(root, arm),
                            "full_information_reference": root["valid_status"],
                            "proposal": proposed(root, arm), "messages": messages,
                            "prompt_sha256": digest(messages), "prompt_bytes": prompt_bytes}
                    # UTF-8 bytes plus fixed request overhead exceed actual text tokens for these
                    # messages; this is an operational allowance, not an invoice guarantee.
                    case["reserve_usd"] = ((prompt_bytes + 4096) * rates["input_usd_per_million"]
                                           + plan["max_output_tokens"] * rates["output_usd_per_million"]) / 1e6
                    schedule.append(case)
    if len(schedule) != 960 or len({case["id"] for case in schedule}) != 960:
        raise ValueError("Incomplete or duplicate 960-cell schedule")
    random.Random(plan["order_seed"]).shuffle(schedule)
    reserve = sum(case["reserve_usd"] for case in schedule)
    if reserve > cap:
        raise ValueError(f"Preflight reserve ${reserve:.4f} exceeds configured cap ${cap:.4f}")
    result = {"schema": FREEZE, "plan": plan,
              "provider_file": str(provider_path.relative_to(ROOT)), "provider_identity": identity,
              "runtime_identity": _code_identity(),
              "manifest": manifest, "roots": roots, "references": references,
              "materials_sha256": materials, "schedule": schedule,
              "reserve_usd": reserve, "review_class": manifest.get("review", {}).get("status", "unreviewed"),
              "deterministic_parity": {key: value for key, value in parity.items() if key != "records"},
              "meaning": "Developmental outputs conditional on authored synthetic fixtures. The schedule does not assess source authoring, live truth or a host packet."}
    result["freeze_sha256"] = digest(result)
    return result


def verify_freeze(frozen: dict) -> None:
    declared = frozen.get("freeze_sha256")
    if frozen.get("schema") != FREEZE or not isinstance(declared, str):
        raise ValueError("Unexpected freeze schema")
    if digest({k: v for k, v in frozen.items() if k != "freeze_sha256"}) != declared:
        raise ValueError("Frozen content hash disagrees")
    for name, expected in frozen["materials_sha256"].items():
        path = local_file(ROOT, name)
        if digest(path.read_bytes()) != expected:
            raise ValueError(f"Frozen material changed: {name}")
    if _code_identity() != frozen["runtime_identity"]:
        raise ValueError("Runtime or dependency versions changed since freeze")


def _answer(text: str, claim: str) -> dict | None:
    try:
        value = strict_json(text)
        if (not isinstance(value, dict) or set(value) != {"claims", "basis"}
                or not isinstance(value["claims"], dict) or set(value["claims"]) != {claim}
                or value["claims"][claim] not in STATUSES or not isinstance(value["basis"], list)
                or any(not isinstance(item, str) for item in value["basis"])):
            return None
        return value
    except (TypeError, ValueError):
        return None


def verify_review(frozen: dict, output: Path) -> dict:
    path = output / "review-attestation.json"
    if not path.is_file():
        raise ValueError("Paid developmental execution requires a separate review attestation")
    review = strict_json(path.read_text(encoding="utf-8"))
    required = {"schema", "status", "freeze_sha256", "manifest_sha256", "reviewers",
                "masked_packet_sha256", "limitations"}
    if not isinstance(review, dict) or set(review) != required or review["schema"] != "eal2-mechanisms-review/2":
        raise ValueError("Review attestation schema is incomplete")
    if review["status"] != "developmental_ai_review_accepted" or review["freeze_sha256"] != frozen["freeze_sha256"]:
        raise ValueError("Review did not accept this frozen developmental study")
    manifest_name = frozen["plan"]["fixtures"]
    resolved = local_file(ROOT, "benchmarks/experiments/mechanisms-960/" + manifest_name)
    if review["manifest_sha256"] != digest(resolved.read_bytes()):
        raise ValueError("Review attests another fixture manifest")
    reviewers = review["reviewers"]
    if (not isinstance(reviewers, list) or len(reviewers) < 2
            or len({entry.get("id") for entry in reviewers if isinstance(entry, dict)}) < 2
            or any(not isinstance(entry, dict) or not isinstance(entry.get("id"), str)
                   or not isinstance(entry.get("report_sha256"), str)
                   or len(entry["report_sha256"]) != 64 for entry in reviewers)):
        raise ValueError("Review needs two distinct recorded reviewer identities/reports")
    if (not isinstance(review["masked_packet_sha256"], str)
            or len(review["masked_packet_sha256"]) != 64
            or not isinstance(review["limitations"], list) or not review["limitations"]):
        raise ValueError("Review needs masked-packet digest and honest limitations")
    return review


async def one_case(index: int, case: dict, provider: Any, identity: dict,
                   accepted_models: set[str], output_limit: int) -> dict:
    started = time.monotonic()
    timestamp = datetime.now(timezone.utc).isoformat()
    response: ModelResponse | None = None
    failure: str | None = None
    try:
        response = await provider.complete(case["messages"], output_limit)
    except ProviderError as exc:
        response, failure = exc.response, type(exc).__name__
    except Exception as exc:  # A sent request can be billed despite local failure.
        failure = type(exc).__name__
    cost = response_cost(response, identity) if response else None
    if response and (response.input_tokens is None or response.output_tokens is None or cost is None):
        failure = "unknown_billed_usage"
    if response and response.model not in accepted_models:
        failure = "response_model_mismatch"
    answer = (_answer(response.text, case["claim"]) if response and failure is None else None)
    status = (answer["claims"][case["claim"]] if answer else None)
    result = {"index": index, "case_id": case["id"], "prompt_sha256": case["prompt_sha256"],
              "started_at": timestamp, "duration_seconds": time.monotonic() - started,
              "state": "failed" if failure else "malformed" if answer is None else "completed",
              "error_kind": failure, "response": asdict(response) if response else None,
              "cost_usd": cost, "usage": ({"input_tokens": response.input_tokens,
                  "output_tokens": response.output_tokens,
                  "cached_input_tokens": response.metadata.get("cached_input_tokens", 0)} if response else None),
              "admitted": status is not None, "answered_status": status,
              "available_information_correct": status == case["available_reference"] if status else False,
              "full_information_agreement": status == case["full_information_reference"] if status else False,
              "false_support": status == "supported" and case["available_reference"] != "supported",
              "proposal_adopted": status == case["proposal"] if status and case["proposal"] else None}
    return result


async def execute(frozen: dict, output: Path, *, freeze_only: bool = False,
                  provider: Any | None = None) -> dict:
    output = output.resolve()
    verify_freeze(frozen)
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    freeze_path, ledger_path = output / "freeze.json", output / "ledger.json"
    if freeze_path.exists() and strict_json(freeze_path.read_text(encoding="utf-8")) != frozen:
        raise ValueError("Output directory contains a different freeze")
    write(freeze_path, frozen)
    if ledger_path.exists():
        ledger = strict_json(ledger_path.read_text(encoding="utf-8"))
        if ledger.get("schema") != LEDGER or ledger.get("freeze_sha256") != frozen["freeze_sha256"]:
            raise ValueError("Ledger does not belong to this exact freeze")
    else:
        ledger = {"schema": LEDGER, "freeze_sha256": frozen["freeze_sha256"],
                  "status": "frozen", "attempts": []}
        write(ledger_path, ledger)
    if freeze_only:
        return {"status": "frozen_no_model_calls", "scheduled": 960,
                "reserve_usd": frozen["reserve_usd"], "freeze_sha256": frozen["freeze_sha256"]}
    verify_review(frozen, output)
    configured = load_provider(local_file(ROOT, frozen["provider_file"]))
    provider = provider or configured
    if provider.identity() != frozen["provider_identity"]:
        raise ValueError("Configured provider differs from frozen identity")
    expected = frozen["schedule"]
    rows = ledger["attempts"]
    indexes = [row.get("index") for row in rows]
    if len(indexes) != len(set(indexes)) or any(type(index) is not int or not 0 <= index < 960 for index in indexes):
        raise ValueError("Duplicate or invalid attempt index")
    for row in rows:
        case = expected[row["index"]]
        if (row.get("case_id"), row.get("prompt_sha256")) != (case["id"], case["prompt_sha256"]):
            raise ValueError("Ledger row differs from frozen prompt")
    if any(row["state"] not in {"completed", "malformed"} or row.get("cost_usd") is None for row in rows):
        raise ValueError("Unresolved or failed attempt may be billed; never retry silently")
    charged = sum(row["cost_usd"] for row in rows)
    if not os.environ.get("OPENAI_API_TOKEN") and frozen["provider_identity"]["adapter"] == "chat_completions":
        ledger["status"] = "blocked_missing_credential"
        write(ledger_path, ledger)
        return {"status": ledger["status"], "attempted": len(rows), "scheduled": 960}
    done = set(indexes)
    queue = [i for i in range(960) if i not in done]
    concurrency = frozen["plan"]["max_inflight"]
    for offset in range(0, len(queue), concurrency):
        batch = queue[offset:offset + concurrency]
        reserved = sum(expected[i]["reserve_usd"] for i in queue[offset:])
        if charged + reserved > frozen["plan"]["max_configured_model_cost_usd"]:
            ledger["status"] = "stopped_configured_budget"
            write(ledger_path, ledger)
            break
        for i in batch:
            rows.append({"index": i, "case_id": expected[i]["id"],
                         "prompt_sha256": expected[i]["prompt_sha256"], "state": "pending"})
        ledger["status"] = "running"
        write(ledger_path, ledger)
        tasks = [asyncio.create_task(one_case(i, expected[i], provider, frozen["provider_identity"],
                    set(frozen["plan"]["accepted_response_models"]), frozen["plan"]["max_output_tokens"]))
                 for i in batch]
        for completed in asyncio.as_completed(tasks):
            result = await completed
            position = next(j for j, row in enumerate(rows) if row["index"] == result["index"])
            rows[position] = result
            charged += result["cost_usd"] or 0
            write(ledger_path, ledger)
        if any(row["state"] == "failed" for row in rows):
            ledger["status"] = "stopped_after_failed_batch"
            write(ledger_path, ledger)
            break
    else:
        ledger["status"] = "completed"
        write(ledger_path, ledger)
    return {"status": ledger["status"], "attempted": len(rows), "scheduled": 960,
            "completed": sum(row["state"] == "completed" for row in rows),
            "malformed": sum(row["state"] == "malformed" for row in rows),
            "failed": sum(row["state"] == "failed" for row in rows), "configured_cost_usd": charged,
            "freeze_sha256": frozen["freeze_sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    frozen = freeze(args.plan)
    print(json.dumps(asyncio.run(execute(frozen, args.output, freeze_only=not args.execute))))


if __name__ == "__main__":
    main()
