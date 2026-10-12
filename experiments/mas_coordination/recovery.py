"""Interactive, checked EAL handoffs with durable effect/outbox recovery.

Workers request findings through this trusted gateway. No computed assessment,
completed proposal or final answer is placed in an initial worker context.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

from jsonschema import Draft202012Validator
from eal.api_load_methods import registry
from eal.evaluator import canonical_digest
from eal.knowledge import EALKnowledgeBase

from .cases import prepare_case, CLAIMS
from .effect_ledger import EffectLedger, canonical_json
from .mcp_snapshots import checked_packets
from .pilot import read, received_payloads
from .task_contract import TaskContract, CandidateCheck, check_candidate, validate_answer
from .transport import LabTransport


ROOT = Path(__file__).parent
SCHEMA = json.loads((ROOT / "recovery-schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA)


class DeliveryInterrupted(RuntimeError):
    """A semantically admitted, persisted outcome is awaiting safe publication."""


def metadata(run: Path):
    connection = sqlite3.connect(run / "gateway.sqlite", timeout=30)
    connection.execute("CREATE TABLE IF NOT EXISTS issued(id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
    connection.execute("CREATE TABLE IF NOT EXISTS gateway_calls(id INTEGER PRIMARY KEY, actor TEXT, operation TEXT, outcome TEXT, finding_id TEXT)")
    connection.commit()
    return connection


def begin_call(run: Path, actor: str, operation: str):
    db = metadata(run)
    try:
        db.execute("BEGIN IMMEDIATE")
        count = db.execute("SELECT count(*) FROM gateway_calls WHERE actor=?", (actor,)).fetchone()[0]
        if count >= 4:
            raise ValueError("Gateway invocation budget exhausted")
        identity = db.execute("INSERT INTO gateway_calls(actor,operation,outcome) VALUES(?,?,'started')", (actor, operation)).lastrowid
        db.commit()
        return identity
    finally:
        db.close()


def end_call(run: Path, identity: int, outcome: str, finding_id: str | None):
    db = metadata(run)
    try:
        db.execute("UPDATE gateway_calls SET outcome=?,finding_id=? WHERE id=?", (outcome, finding_id, identity))
        db.commit()
    finally:
        db.close()


def issue(run: Path, finding: dict):
    db = metadata(run)
    encoded = canonical_json(finding)
    try:
        db.execute("BEGIN IMMEDIATE")
        prior = db.execute("SELECT payload FROM issued WHERE id=?", (finding["finding_id"],)).fetchone()
        if prior is not None and prior[0] != encoded:
            raise ValueError("Immutable gateway-issued finding collision")
        db.execute("INSERT OR IGNORE INTO issued(id,payload) VALUES(?,?)", (finding["finding_id"], encoded))
        db.commit()
    finally:
        db.close()


def save(path: Path, value):
    """Atomic file replacement for views; durable effects live in SQLite."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def components(run: Path):
    state = read(run / "state.json")
    contract = TaskContract.from_dict(state["contract"])
    kb = EALKnowledgeBase(run / "workspace", run / "workspace/tools.toml", method_registry=registry())
    return state, contract, kb


def prepare(output: Path, runtime: Path):
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Preserve existing trials; use a fresh output directory")
    if not (runtime / "rust-protocol/target/release/mas-protocol-codec").is_file():
        raise FileNotFoundError("Build the supplied Lab runtime first")
    output.mkdir(parents=True, exist_ok=True)
    plan = read(ROOT / "recovery-plan.json")
    save(output / "plan.json", plan)
    runs = []
    for number, item in enumerate(plan["native_cases"], start=1):
        for arm in item["arms"]:
            name = f"task{number + 500}-{arm}"
            run = output / name
            case = prepare_case("measured_failure" if number == 1 else "nominal", run / "workspace")
            if number == 1:
                # A fresh 3% teaching variant, not the earlier 2% trial bytes.
                report_path = case.workspace / "report.json"
                before = report_path.read_bytes()
                report = json.loads(before)
                next(row for row in report["requests"] if 200 <= row["status_code"] < 300)["status_code"] = 0
                after = (json.dumps(report, indent=2) + "\n").encode()
                source = case.source_path.read_text().replace(hashlib.sha256(before).hexdigest(), hashlib.sha256(after).hexdigest())
                report_path.write_bytes(after)
                case.source_path.write_text(source)
            else:
                task = copy.deepcopy(case.task)
                task["requested_scope"]["run_id"] = "demo-load-002"
                task["requested_scope"]["concurrent_clients"] = 20
                case = replace(case, task=task)
            contract = TaskContract.from_case(case, task_id=f"task{number + 500}")
            request = {"schema": "EAL/MAS-coordination/2", "kind": "request", "message_id": "request",
                       "task_id": contract.task_id, "task_digest": contract.task_digest,
                       "sender": "reviewer", "recipient": "assessor", "reply_to": None, "attempt": 0,
                       "candidate_entry_id": contract.entry_id}
            VALIDATOR.validate(request)
            state = {"run_id": name, "case_id": item["id"], "arm": arm, "contract": contract.to_dict(),
                     "runtime": str(runtime.resolve()), "request": request, "executions": [], "gateway_calls": [],
                     "received": {"assessor": [request]}, "message": None, "score": None}
            if arm == "checked_protocol":
                bus = LabTransport(runtime, run / "mailbox.sqlite")
                bus.create(name, "assessor", "reviewer")
                bus.send(name, request, actor="reviewer")
                received_payloads(bus, name, "assessor", [request], run / "assessor-receipt.json")
            save(run / "state.json", state)
            save(run / "assessor-context.json", {"role": "assessor", "contract": contract.to_dict(),
                 "received_messages": [request], "gateway": f"{sys.executable} -m experiments.mas_coordination.recovery query --run {run.resolve()}",
                 "payload_schema": str(ROOT / "recovery-schema.json"),
                 "instructions": "Request a finding through the gateway. Author one outcome or disposition message to the reviewer, referring to its finding_id and trusted assessment_refs. Inspect the initial request and preserve every task identity. No proposal template or assessment is supplied here."})
            runs.append(name)
    save(output / "manifest.json", {"runs": runs, "plan_digest": canonical_digest(plan), "mode": "host_assisted",
         "implementation_digest": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in ROOT.iterdir() if path.is_file() and path.suffix in {".py", ".json"}},
         "semantic_definitions_digest": canonical_digest(contract.to_dict()["semantic_definitions"])})
    return {"runs": runs, "output": str(output)}


def _query(run: Path):
    state, contract, kb = components(run)
    key = "query:" + contract.task_digest
    ledger = EffectLedger(run / "effects.sqlite") if state["arm"] == "checked_protocol" else None
    reservation = ledger.reserve_effect(key, {"operation": "assess", "task_digest": contract.task_digest}) if ledger else {"status": "new"}
    if reservation["status"] == "unknown":
        current = check_candidate(kb, contract, contract.entry_id)
        check = CandidateCheck(False, "effect_outcome_unknown", "External effect was reserved but its outcome is not durably recorded; no automatic reexecution is authorized", current.task_digest, current.entry_id, current.source_digest, current.context_fingerprint, current.method_registry_fingerprint)
        identity = {"task_digest": contract.task_digest, "check": check.to_dict(), "assessment_refs": {}}
        finding = {"finding_id": "finding_" + canonical_digest(identity), **identity, "assessments": {}, "packets": {},
                   "mcp": {"calls": [], "reason": "effect_outcome_unknown"}, "collected_count": None, "reused_count": None}
        repeated = True
    elif reservation["status"] == "committed":
        finding = reservation["result"]
        current = check_candidate(kb, contract, contract.entry_id)
        if current.to_dict() != finding["check"]:
            identity = {"task_digest": contract.task_digest, "check": current.to_dict(), "assessment_refs": {}}
            finding = {"finding_id": "finding_" + canonical_digest(identity), **identity, "assessments": {}, "packets": {},
                       "mcp": {"calls": [], "reason": current.code}, "collected_count": 0, "reused_count": 0}
        repeated = True
    else:
        check = check_candidate(kb, contract, contract.entry_id)
        assessments = {claim: kb.assess(contract.entry_id, claim, now=contract.assessed_at) for claim in contract.claims} if check.ok else {}
        packets, trace = asyncio.run(checked_packets(kb, assessments)) if assessments else ({}, {"calls": [], "reason": check.code})
        refs = {claim: result["assessment_id"] for claim, result in assessments.items()}
        identity = {"task_digest": contract.task_digest, "check": check.to_dict(), "assessment_refs": refs}
        finding = {"finding_id": "finding_" + canonical_digest(identity), **identity, "assessments": assessments,
                   "packets": packets, "mcp": trace,
                   "collected_count": sum(row["collected_count"] for row in assessments.values()),
                   "reused_count": sum(row["reused_count"] for row in assessments.values())}
        if ledger:
            ledger.complete_effect(key, finding, [])
        repeated = False
    path = run / "findings" / (finding["finding_id"] + ".json")
    if path.exists() and read(path) != finding:
        raise ValueError("Immutable finding identity collision")
    issue(run, finding)
    save(path, finding)
    state["gateway_calls"].append({"operation": "assess", "finding_id": finding["finding_id"], "cached": repeated})
    save(run / "state.json", state)
    return finding


def query(run: Path):
    identity = begin_call(run, "assessor", "query")
    try:
        result = _query(run)
    except Exception:
        end_call(run, identity, "failed", None)
        raise
    end_call(run, identity, "succeeded", result["finding_id"])
    return result


def lookup(run: Path, finding_id: str, *, track: bool = False):
    identity = begin_call(run, "reviewer", "lookup") if track else None
    try:
        result = _lookup(run, finding_id)
    except Exception:
        if identity is not None: end_call(run, identity, "failed", finding_id)
        raise
    if identity is not None: end_call(run, identity, "succeeded", finding_id)
    return result


def _lookup(run: Path, finding_id: str):
    if not finding_id.startswith("finding_") or len(finding_id) != 72 or any(c not in "0123456789abcdef" for c in finding_id[8:]):
        raise ValueError("Finding identifier must be a bounded content identity")
    state, contract, kb = components(run)
    finding = read(run / "findings" / (finding_id + ".json"))
    db = metadata(run)
    try:
        issued = db.execute("SELECT payload FROM issued WHERE id=?", (finding_id,)).fetchone()
        if issued is None or issued[0] != canonical_json(finding):
            raise ValueError("Finding is not an immutable gateway-issued result")
    finally:
        db.close()
    identity = {key: finding[key] for key in ("task_digest", "check", "assessment_refs")}
    if finding_id != "finding_" + canonical_digest(identity) or finding["task_digest"] != contract.task_digest:
        raise ValueError("Finding is not bound to this task")
    original = CandidateCheck.from_dict(finding["check"])
    current = check_candidate(kb, contract, contract.entry_id)
    if original.code != "effect_outcome_unknown" and current.to_dict() != original.to_dict():
        raise ValueError("Candidate correspondence changed after this finding was recorded")
    for claim, assessment in finding["assessments"].items():
        # File views never replace the underlying EAL store as the authority.
        packet = kb.service.packet(assessment["assessment_id"], claim)
        if (packet != assessment["packet"] or packet != finding["packets"][claim]
                or finding["assessment_refs"].get(claim) != assessment["assessment_id"]):
            raise ValueError("Finding substituted a persisted EAL assessment or packet")
        stored = kb.service.store.get(assessment["assessment_id"], kind="assessment")
        if stored["assessed_at"] != contract.assessed_at or stored["source_digest"] != contract.source_digest:
            raise ValueError("Finding references a different EAL time or revision")
    return finding


def _record(run: Path, actor: str, response: Path, execution_id: str, *, execution_mode: str, fault: str | None = None):
    state, contract, kb = components(run)
    if actor not in {"assessor", "reviewer"} or not execution_id.strip():
        raise ValueError("Trusted actor and actual external execution identity are required")
    value = read(response)
    fields = {"message", "consumed_message_ids"} if actor == "assessor" else {"answer", "consumed_message_ids"}
    if set(value) != fields or value["consumed_message_ids"] != [row["message_id"] for row in state["received"][actor]]:
        raise ValueError("Response fields or actual inspected message identities differ from the declared role")
    existing = next((row for row in state["executions"] if row["actor"] == actor), None)
    if existing:
        if existing["execution_id"] != execution_id or existing["response_digest"] != canonical_digest(value):
            raise ValueError("First attempt is immutable; cannot replace or repair this role")
        if actor == "assessor" and state.get("received", {}).get("reviewer"):
            return {"execution_id": execution_id, "actor": actor, "score": state["score"], "replayed": True}
        if actor == "reviewer" and state.get("reviewer_acked"):
            return {"execution_id": execution_id, "actor": actor, "score": state["score"], "replayed": True}
    else:
        state["executions"].append({"actor": actor, "execution_id": execution_id, "response_digest": canonical_digest(value),
                                    "execution_mode": execution_mode, "tokens": None, "usd_cost": None})
    save(run / (actor + "-response.json"), value)
    if actor == "assessor":
        message = value["message"]
        VALIDATOR.validate(message)
        if message["message_id"] == state["request"]["message_id"]:
            raise ValueError("Reply identity collides with the incoming request")
        if (message["sender"], message["recipient"], message["reply_to"], message["task_digest"], message["task_id"], message["attempt"]) != ("assessor", "reviewer", "request", contract.task_digest, contract.task_id, 0):
            raise ValueError("Handoff replaced trusted identities or exceeded the first-attempt budget")
        finding = lookup(run, message["finding_id"])
        check = CandidateCheck.from_dict(finding["check"])
        if check.ok:
            if message["kind"] != "outcome" or message["assessment_refs"] != finding["assessment_refs"]:
                raise ValueError("Outcome must reference the complete actual host assessments")
        elif (message["kind"] != "disposition" or message["code"] != check.code
              or message["outcome"] != ("incomplete" if check.code in {"evidence_unavailable", "effect_outcome_unknown"} else "rejected")):
            raise ValueError("Unassessed target needs a matching typed disposition, not an assessment status")
        state["message"] = message
        # Persist raw response and admission before any publication/ACK.
        save(run / "state.json", state)
        if state["arm"] == "checked_protocol":
            ledger = EffectLedger(run / "handoffs.sqlite")
            key = "request"
            reservation = ledger.reserve_effect(key, state["request"])
            if reservation["status"] == "unknown" and not existing:
                raise RuntimeError("effect_outcome_unknown: a handoff reservation requires reconciliation")
            ledger.complete_effect(key, {"execution_id": execution_id, "response_digest": canonical_digest(value)}, [message])
            bus = LabTransport(state["runtime"], run / "mailbox.sqlite")
            def send(row):
                result = bus.send(state["run_id"], row, actor="assessor")
                if fault == "after_send":
                    raise RuntimeError("Injected interruption after remote send; resume committed outbox")
                return result
            try:
                ledger.drain_outbox(send, lambda key: bus.acknowledge(state["run_id"], key, "assessor"))
                received = received_payloads(bus, state["run_id"], "reviewer", [message], run / "reviewer-receipt.json")
            except Exception as exc:
                raise DeliveryInterrupted("Persisted handoff delivery is interrupted; resume the same artifact") from exc
        else:
            received = [message]
        state["received"]["reviewer"] = received
        save(run / "reviewer-context.json", {"role": "reviewer", "contract": contract.to_dict(), "received_messages": received,
             "gateway": f"{sys.executable} -m experiments.mas_coordination.recovery lookup --run {run.resolve()} --finding-id <received finding_id>",
             "answer_fields": ["statuses", "scope", "assessed_at", "conclusion", "production_supported"],
             "instructions": "Inspect your addressed handoff, retrieve that finding through the gateway, and author the scoped answer using the contract's explicit definitions. No final answer or review template is supplied."})
    else:
        finding = lookup(run, state["message"]["finding_id"])
        check = CandidateCheck.from_dict(finding["check"])
        errors = validate_answer(contract, check, finding["assessments"] or None, value["answer"])
        state["score"] = {"correct": not errors, "diagnostics": errors}
        save(run / "state.json", state)
        if state["arm"] == "checked_protocol":
            bus = LabTransport(state["runtime"], run / "mailbox.sqlite")
            try:
                bus.acknowledge(state["run_id"], state["message"]["message_id"], "reviewer")
            except Exception as exc:
                raise DeliveryInterrupted("Persisted reviewer result is awaiting acknowledgement") from exc
        state["reviewer_acked"] = True
    save(run / "state.json", state)
    return {"execution_id": execution_id, "actor": actor, "score": state["score"]}


def record(run: Path, actor: str, response: Path, execution_id: str, *, execution_mode: str, fault: str | None = None):
    state, _, _ = components(run)
    if (actor not in {"assessor", "reviewer"} or not execution_id.strip()
            or execution_mode not in {"actual_host_agent", "software_test"}):
        raise ValueError("Trusted actor and execution identity are required")
    raw = response.read_bytes() if response.exists() else b""
    digest = hashlib.sha256(raw).hexdigest()
    attempts = state.setdefault("attempts", {})
    prior = attempts.get(actor)
    if prior and (prior["execution_id"] != execution_id or prior["raw_digest"] != digest):
        raise ValueError("Cannot replace an already retained first attempt")
    if prior and prior["outcome"] == "rejected":
        return prior
    attempts[actor] = {"execution_id": execution_id, "raw_digest": digest, "outcome": "pending"}
    # Preserve malformed UTF-8 exactly as well as a readable diagnostic view.
    (run / (actor + "-attempt.bin")).write_bytes(raw)
    save(run / (actor + "-attempt.raw"), {"raw_utf8": raw.decode("utf-8", errors="replace")})
    save(run / "state.json", state)
    try:
        result = _record(run, actor, response, execution_id, execution_mode=execution_mode, fault=fault)
    except Exception as exc:
        state, _, _ = components(run)
        state["attempts"][actor]["outcome"] = "delivery_interrupted" if isinstance(exc, DeliveryInterrupted) else "rejected"
        state["attempts"][actor]["diagnosis"] = str(exc)
        save(run / "state.json", state)
        raise
    state, _, _ = components(run)
    state["attempts"][actor]["outcome"] = "recorded"
    save(run / "state.json", state)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    setup = commands.add_parser("prepare")
    setup.add_argument("--output", required=True, type=Path)
    setup.add_argument("--runtime", type=Path, default=Path("/workspace/mas-protocol-lab"))
    for name in ["query", "lookup", "record"]:
        command = commands.add_parser(name)
        command.add_argument("--run", required=True, type=Path)
        if name == "lookup": command.add_argument("--finding-id", required=True)
        if name == "record":
            command.add_argument("--actor", choices=["assessor", "reviewer"], required=True)
            command.add_argument("--response", required=True, type=Path)
            command.add_argument("--execution-id", required=True)
            command.add_argument("--execution-mode", required=True, choices=["actual_host_agent", "software_test"])
            command.add_argument("--fault", choices=["after_send"])
    args = parser.parse_args()
    if args.operation == "prepare": result = prepare(args.output.resolve(), args.runtime)
    elif args.operation == "query": result = query(args.run.resolve())
    elif args.operation == "lookup": result = lookup(args.run.resolve(), args.finding_id, track=True)
    else: result = record(args.run.resolve(), args.actor, args.response, args.execution_id, execution_mode=args.execution_mode, fault=args.fault)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__": main()
