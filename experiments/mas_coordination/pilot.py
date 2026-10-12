"""Prepare, record and inspect bounded host-assisted coordination trials.

This CLI does not launch models. A trusted host records actual external turns;
model-generated text never changes anchors, executables, fixtures, or scoring.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import math
from pathlib import Path

from eal.api_load_methods import registry
from eal.knowledge import EALKnowledgeBase

from .cases import CLAIMS, prepare_case, preseed, score_response
from .mcp_snapshots import checked_packets
from .protocol import ScopeAnchor, Validator, make_anchor, make_message, proposal_fields
from .transport import LabTransport


PLAN = Path(__file__).with_name("plan.json")


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def read(path: Path):
    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON field: {key}")
            result[key] = value
        return result

    def finite_constant(value):
        raise ValueError(f"Nonfinite JSON number: {value}")

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_fields,
                      parse_constant=finite_constant)


def received_payloads(bus, run_id: str, actor: str, expected: list[dict], receipt_path: Path) -> list[dict]:
    """Relay only the exact addressed canonical payloads returned by receive.

    The supplied runtime returns delivery records wrapping each canonical
    envelope with sequence/redelivery metadata. Retain those raw receipts and
    relay only verified payloads to their intended recipient.
    """
    received = bus.receive(run_id, actor)
    write(receipt_path, received)
    if not isinstance(received, list):
        raise ValueError("Protocol receive did not return a message list")
    payloads = []
    for delivery in received:
        if (not isinstance(delivery, dict)
                or set(delivery) != {"message", "sequence", "redelivered"}
                or type(delivery["sequence"]) is not int or delivery["sequence"] <= 0
                or type(delivery["redelivered"]) is not bool):
            raise ValueError("Protocol receive returned invalid delivery metadata")
        envelope = delivery["message"]
        if (not isinstance(envelope, dict)
                or set(envelope) != {"message_id", "run_id", "sender", "recipient", "version", "kind", "payload"}
                or envelope.get("run_id") != run_id
                or envelope.get("recipient") != actor or not isinstance(envelope.get("payload"), dict)):
            raise ValueError("Protocol receive returned a wrongly addressed envelope")
        if (envelope["version"] != "1" or any(envelope[key] != envelope["payload"].get(key)
                                               for key in ("message_id", "sender", "recipient", "kind"))):
            raise ValueError("Protocol envelope metadata differs from its canonical payload")
        payloads.append(envelope["payload"])
    wanted = {message["message_id"]: message for message in expected}
    actual = {message.get("message_id"): message for message in payloads}
    if len(actual) != len(payloads) or actual != wanted:
        raise ValueError("Protocol receive differs from the exact expected payloads")
    return [actual[message["message_id"]] for message in expected]


def prepare(output: Path, arms: list[str], runtime: Path | None):
    plan = read(PLAN)
    if not arms or len(set(arms)) != len(arms) or not set(arms) <= set(plan["arms"]):
        raise ValueError("Select distinct declared pilot arms")
    if "eal_protocol" in arms:
        if runtime is None:
            raise ValueError("The protocol arm requires --runtime with a built MAS Protocol Lab source directory")
        binary = runtime / "rust-protocol/target/release/mas-protocol-codec"
        if not binary.is_file():
            raise FileNotFoundError(f"Build the MAS Protocol Lab codec first: {binary}")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("Use a new empty output directory; retained runs are immutable")
    output.mkdir(parents=True, exist_ok=True)
    write(output / "plan.json", plan)
    runs = []
    for task_index, item in enumerate(plan["case_order"], start=1):
        task_id = f"task{task_index:03d}"
        for arm in item["arms"]:
            if arm not in arms:
                continue
            run_id = f"{task_id}-{arm}"
            run = output / run_id
            case = prepare_case(item["case_id"], run / "workspace")
            assessments = preseed(case)
            packets, mcp = asyncio.run(checked_packets(case.knowledge, assessments))
            task = copy.deepcopy(case.task)
            task.pop("case_id", None)
            task["task_id"] = task_id
            anchors = {claim: make_anchor(case.knowledge, task_id=task_id, entry_id=case.entry_id,
                                          claim=claim, assessed_at=case.assessed_at) for claim in CLAIMS}
            requests = [make_message(anchors[claim], kind="assessment_request", message_id=f"request-{index}",
                                     sender="reviewer", recipient="assessor") for index, claim in enumerate(CLAIMS)]
            templates = [make_message(anchors[claim], kind="proposal", message_id=f"proposal-{index}",
                                      sender="assessor", recipient="reviewer", reply_to=requests[index]["message_id"],
                                      **proposal_fields(assessments[claim])) for index, claim in enumerate(CLAIMS)]
            state = {
                "run_id": run_id, "arm": arm, "case_id": item["case_id"],
                "runtime": None if runtime is None else str(runtime.resolve()),
                "task": task, "anchors": {claim: {"task_id": anchors[claim].task_id, **anchors[claim].scope} for claim in CLAIMS},
                "assessments": assessments, "requests": requests, "accepted_messages": requests,
                "execution_mode": "host_assisted", "executions": [], "rejections": [], "delivery": "pending",
                "native_model_tokens": None, "native_model_cost_usd": None,
                "coordinator_contributions": ["Authored initial assessment requests", "Prepared trusted historical EAL snapshots", "Retrieved identical packets through actual MCP"],
                "mcp": mcp,
                "received_by_actor": {"assessor": requests}, "transport_events": [],
                "collected_count": sum(row["collected_count"] for row in assessments.values()),
                "reused_count": sum(row["reused_count"] for row in assessments.values()),
                "implementation": {str(file.relative_to(Path(__file__).parents[2])): hashlib.sha256(file.read_bytes()).hexdigest()
                                   for file in Path(__file__).parent.glob("*.py")},
            }
            for claim, anchor in anchors.items():
                Validator(case.knowledge, anchor).validate(requests[CLAIMS.index(claim)], actor="reviewer")
            if arm == "eal_protocol":
                bus = LabTransport(runtime, run / "mailbox.sqlite")
                bus.create(run_id, "assessor", "reviewer")
                for request in requests:
                    bus.send(run_id, request, actor="reviewer")
                state["received_by_actor"]["assessor"] = received_payloads(
                    bus, run_id, "assessor", requests, run / "assessor-receipt.json")
                state["transport_events"].append({"operation": "receive", "actor": "assessor",
                                                  "message_ids": [row["message_id"] for row in requests]})
                state["coordinator_contributions"].append("Relayed canonical runtime receive payloads only to their intended role")
            write(run / "state.json", state)
            write(run / "assessor-context.json", {
                "role": "assessor", "task": task, "received_messages": state["received_by_actor"]["assessor"],
                "trusted_snapshots": packets, "proposal_templates": templates,
                "instructions": "Inspect the addressed requests and host snapshots. Return one proposal per claim using these exact trusted identities; do not broaden scope or change host status. Output one JSON object with proposals (array) and consumed_message_ids (array). No answer key or other run workspace is available to this role.",
            })
            runs.append(run_id)
    write(output / "manifest.json", {"schema": "EAL/mas-coordination-run/1", "plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
                                     "prepared_runs": runs, "unrun_arms": sorted(set(plan["arms"]) - set(arms)),
                                     "no_improvement_claim": True})
    return {"output": str(output), "prepared_runs": runs}


def replay(run: Path, state: dict):
    kb = EALKnowledgeBase(run / "workspace", run / "workspace/tools.toml", method_registry=registry())
    validators = {claim: Validator(kb, ScopeAnchor(**value)) for claim, value in state["anchors"].items()}
    for message in state["accepted_messages"]:
        validators[message["scope"]["claim"]].validate(message, actor=message["sender"])
    return kb, validators


def record(run: Path, actor: str, response: Path, execution_id: str, elapsed: float | None = None,
           *, execution_mode: str):
    state = read(run / "state.json")
    if actor not in {"assessor", "reviewer"}:
        raise ValueError("Unknown role")
    if execution_mode not in {"actual_host_agent", "software_test"}:
        raise ValueError("Execution mode must explicitly identify actual_host_agent or software_test")
    if not isinstance(execution_id, str) or not execution_id.strip():
        raise ValueError("Execution identity must be nonempty")
    if elapsed is not None and (type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0):
        raise ValueError("Elapsed time must be a measured finite nonnegative number or absent")
    if any(row["execution_id"] == execution_id for row in state["executions"]):
        raise ValueError("Execution identity already recorded")
    if any(row["actor"] == actor for row in state["executions"]):
        raise ValueError("First-attempt pilot is frozen; use a new declared pilot for additional turns")
    if actor == "reviewer" and not any(row["actor"] == "assessor" for row in state["executions"]):
        raise ValueError("Record the assessor first attempt before executing the reviewer")
    _, validators = replay(run, state)
    body_key = "proposals" if actor == "assessor" else "reviews"
    value = None
    raw = None
    messages = []
    consumed = []
    errors = []
    packets = {}
    received = state.get("received_by_actor", {}).get(actor, [])
    expected = [row["message_id"] for row in received]
    admission = "rejected"
    consumption_valid = False
    try:
        raw = response.read_bytes()
        value = read(response)
        fields = {body_key, "consumed_message_ids"} | ({"answer"} if actor == "reviewer" else set())
        if not isinstance(value, dict) or set(value) != fields:
            raise ValueError(f"Response fields must be exactly {sorted(fields)}")
        consumed = value["consumed_message_ids"]
        if (not isinstance(consumed, list) or any(not isinstance(item, str) for item in consumed)
                or sorted(consumed) != sorted(expected)):
            raise ValueError("Recipient did not attest inspection of exactly the addressed messages")
        consumption_valid = True
        messages = value[body_key]
        count = len(CLAIMS) if actor == "assessor" or state["delivery"] == "accepted" else 0
        if not isinstance(messages, list) or len(messages) != count:
            raise ValueError(f"Return exactly {count} {body_key}")
        if any(not isinstance(message, dict) or not isinstance(message.get("scope"), dict) for message in messages):
            raise ValueError("Messages must be objects with scoped claim identities")
        if count and {message["scope"].get("claim") for message in messages} != set(CLAIMS):
            raise ValueError("Exactly one message for each selected claim is required")
        if actor == "assessor":
            registered_context = state["assessments"][CLAIMS[0]]["packet"]["context_fingerprint"]
            from eal.evaluator import canonical_digest
            wanted = {key: state["task"]["requested_scope"][key] for key in ("service", "build_id", "dataset")}
            if canonical_digest(wanted) != registered_context:
                raise ValueError("Task target context differs from the registered assessment context; cross-build handoff rejected")
        for message in messages:
            if message.get("kind") != ("proposal" if actor == "assessor" else "review"):
                raise ValueError("Message kind does not match the executed role")
            packet = validators[message["scope"]["claim"]].validate(message, actor=actor)
            packets[message["scope"]["claim"]] = packet
        admission = "accepted"
    except OSError as exc:
        admission = "unknown"
        errors.append(f"Response unavailable: {type(exc).__name__}")
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        errors.append(str(exc))
    if errors:
        state["rejections"].append({"actor": actor, "execution_id": execution_id,
                                    "diagnosis": "; ".join(errors), "outcome": admission})
    if admission == "accepted":
        # Domain admission is all-or-nothing. The separate runtime may persist
        # some sends before another fails; never call that durable bus atomicity.
        state["accepted_messages"].extend(messages)
    execution = {"actor": actor, "execution_id": execution_id, "execution_mode": execution_mode,
                 "elapsed_seconds": elapsed, "response_sha256": None if raw is None else hashlib.sha256(raw).hexdigest(),
                 "first_attempt_outcome": admission,
                 "consumed_message_ids": consumed, "admission_errors": errors,
                 "model_tokens": None, "model_cost_usd": None,
                 "execution_identity_provenance": "Trusted host assertion; the recorder does not verify external execution"}
    state["executions"].append(execution)
    write(run / f"{actor}-response.json", value)
    if raw is not None:
        (run / f"{actor}-response.raw.json").write_bytes(raw)
    transport = {"status": "not_applicable", "sent_message_ids": [], "acknowledged_message_ids": [], "errors": []}
    if state["arm"] == "eal_protocol" and consumption_valid:
        transport["status"] = "complete"
        try:
            bus = LabTransport(state["runtime"], run / "mailbox.sqlite")
            for message_id in consumed:
                bus.acknowledge(state["run_id"], message_id, actor)
                transport["acknowledged_message_ids"].append(message_id)
            if admission == "accepted":
                for message in messages:
                    bus.send(state["run_id"], message, actor=actor)
                    transport["sent_message_ids"].append(message["message_id"])
        except (OSError, ValueError, RuntimeError) as exc:
            transport["status"] = "partial" if transport["sent_message_ids"] else "failed"
            transport["errors"].append(str(exc))
    execution["durable_transport"] = transport
    if actor == "assessor":
        state["admission"] = admission
        state["delivery"] = ("rejected" if admission == "rejected" else "unresolved"
                             if admission == "unknown" or transport["errors"] else "accepted")
        addressed = messages if state["delivery"] == "accepted" else []
        if state["arm"] == "eal_protocol" and state["delivery"] == "accepted":
            try:
                addressed = received_payloads(bus, state["run_id"], "reviewer", messages,
                                             run / "reviewer-receipt.json")
                state["transport_events"].append({"operation": "receive", "actor": "reviewer",
                                                  "message_ids": [row["message_id"] for row in addressed]})
            except (OSError, ValueError, RuntimeError) as exc:
                transport["errors"].append(str(exc))
                transport["status"] = "persisted_but_not_relayed"
                state["delivery"] = "unresolved"
                addressed = []
        state["received_by_actor"]["reviewer"] = addressed
        reviews = [make_message(ScopeAnchor(**state["anchors"][claim]), kind="review", message_id=f"review-{index}",
                                sender="reviewer", recipient="assessor", reply_to=message["message_id"],
                                assessment_id=message["assessment_id"], verdict="accepted")
                   for index, (claim, message) in enumerate(zip(CLAIMS, sorted(addressed, key=lambda row: CLAIMS.index(row["scope"]["claim"]))))]
        write(run / "reviewer-context.json", {
            "role": "reviewer", "task": state["task"], "delivery": state["delivery"], "diagnoses": errors + transport["errors"],
            "received_messages": addressed, "trusted_packets": packets if addressed else {},
            "review_templates": reviews,
            "instructions": "Inspect addressed messages and host-checked packets. Produce the canonical scoped answer in task.answer_contract. Return one JSON object with answer, reviews (use exact templates; empty after rejected handoff), and consumed_message_ids. Preserve stale/unassessed versus measured failure and the synthetic qualification. Read no other run files.",
        })
    else:
        # A correctly reported unassessed target after rejected delivery needs no review reply.
        answer = value.get("answer") if isinstance(value, dict) else None
        state["score"] = score_response(state["case_id"], answer, delivery=state["delivery"])
        state["score"]["response_admitted"] = admission == "accepted"
    write(run / "state.json", state)
    return {"recorded": execution, "delivery": state["delivery"], "score": state.get("score")}


def report(output: Path):
    manifest = read(output / "manifest.json")
    rows = []
    for name in manifest["prepared_runs"]:
        state = read(output / name / "state.json")
        rows.append({key: state.get(key) for key in ("run_id", "case_id", "arm", "admission", "delivery", "score", "executions", "rejections", "collected_count", "reused_count")})
    result = {"schema": "EAL/mas-coordination-pilot-report/1", "manifest": manifest, "runs": rows,
              "conclusion": "Descriptive feasibility pilot only; no demonstrated output or cost improvement.",
              "limitations": ["Internally synthetic tasks", "One trial per case/arm", "Native model tokens and cost unavailable", "Model/time/output ceilings requested but not enforceable by this recording CLI", "Execution modes and external IDs are host assertions, not inferred from role labels", "Domain admission is atomic per response; runtime sends and acknowledgements are separate durable operations", "Shared-file isolation and answer-key blinding are instructions, not filesystem access controls"]}
    write(output / "report.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    setup = commands.add_parser("prepare")
    setup.add_argument("--output", type=Path, required=True)
    setup.add_argument("--arms", nargs="+", choices=["mcp_json", "eal_protocol"], default=["mcp_json", "eal_protocol"])
    setup.add_argument("--runtime", type=Path)
    save = commands.add_parser("record")
    save.add_argument("--run", type=Path, required=True)
    save.add_argument("--actor", choices=["assessor", "reviewer"], required=True)
    save.add_argument("--response", type=Path, required=True)
    save.add_argument("--execution-id", required=True)
    save.add_argument("--execution-mode", choices=["actual_host_agent", "software_test"], required=True)
    save.add_argument("--elapsed", type=float)
    inspect = commands.add_parser("report")
    inspect.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.operation == "prepare":
        result = prepare(args.output.resolve(), args.arms, args.runtime)
    elif args.operation == "record":
        result = record(args.run.resolve(), args.actor, args.response, args.execution_id, args.elapsed,
                        execution_mode=args.execution_mode)
    else:
        result = report(args.output.resolve())
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
