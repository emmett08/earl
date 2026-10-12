"""Run software-only task-correspondence and effect-recovery comparisons.

This experiment launches no models and fabricates no worker answers. Duplicate
requests execute the actual registered Python EAL host at a fixed teaching time;
other recovery episodes use an explicitly synthetic, counted effect. Faults are
injected Python interruptions, not process-kill or power-loss tests. Lab episodes
use the supplied CLI, Rust codec and SQLite mailbox, without a substitute parser.
"""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from typing import Any

from eal.evaluator import canonical_digest

from .cases import CLAIMS, MET_CLAIM, OBSERVED_AT, SOURCE_SCOPE, prepare_case
from .effect_ledger import EffectLedger, canonical_json
from .protocol import Validator, make_anchor, make_message, proposal_fields
from .task_contract import TaskContract, check_candidate
from .transport import LabTransport


ARMS = ("plain_retry", "durable_json", "durable_lab")
BUDGETS = {"maximum_effect_invocations": 3, "maximum_handler_deliveries": 3,
           "maximum_send_attempts": 8, "maximum_ack_attempts": 8,
           "maximum_unique_messages": 8, "maximum_message_bytes": 65536,
           "wall_seconds": 3600}
EPISODES = (
    {"id": "no_fault", "effect_mode": "synthetic_counted_effect", "fault": None},
    {"id": "duplicate_request", "effect_mode": "actual_eal_python_host", "fault": None},
    {"id": "commit_before_publish", "effect_mode": "synthetic_counted_effect", "fault": "after_commit"},
    {"id": "send_receipt_lost", "effect_mode": "synthetic_counted_effect", "fault": "after_send"},
    {"id": "ack_confirmation_lost", "effect_mode": "synthetic_counted_effect", "fault": "after_ack"},
    {"id": "interrupted_effect", "effect_mode": "synthetic_counted_effect", "fault": "after_effect_before_commit"},
)
RUN = "episode"
KEY = "episode/assessor/request"


def save(path: Path, value: Any):
    """Persist experiment evidence; policies never read this journal for recovery."""
    encoded = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def frozen_plan() -> dict:
    return {
        "schema": "EAL/mas-coordination-operational-plan/1",
        "execution_mode": "software_fault_injection", "native_model_calls": 0,
        "arms": list(ARMS), "budgets_per_episode_arm": dict(BUDGETS),
        "correspondence_cases": ["nominal", "changed_run", "changed_clients", "changed_build"],
        "fault_schedules": [
            {**episode, "fault_on_handler_attempt": 0 if episode["fault"] else None,
             "handler_schedule": "Three identical deliveries received before ACK" if episode["id"] == "duplicate_request"
             else "One initial delivery; after an injected interruption poll the actual pending inbox once and resume committed outbox if present"}
            for episode in EPISODES
        ],
        "same_in_all_arms": ["Logical input and stable reply identity", "Logical effect and fixed ceilings",
                            "Transport identity/content collision checks", "Reply content omits invocation counters",
                            "Independent evidence journal; it is unavailable to recovery policy"],
        "contrast": "plain_retry and durable_json share a JSON mailbox; only durable policies use EffectLedger. durable_lab uses the same ledger over the actual Lab mailbox.",
        "duplicate_effect": "One selected actual EAL kb.assess invocation per effect start. Every persisted assessment is retained; stable replies carry qualified semantic status, not varying assessment IDs or final worker answers.",
        "resource_policy": "Retain incomplete EAL results and exceptions. Do not raise the method's unchanged five-second startup limit, replace the effect, or silently rerun a failed episode.",
        "scope": "Internal synthetic software fixtures; no native reasoning, MCP invocation, total-cost or wire-syntax improvement claim.",
    }


class JsonMailbox:
    """Durable JSON control with the same stable-ID dedup and ACK prerequisites.

    Only the small mailbox operations needed by this experiment are implemented.
    Plain retry uses this same backend, without the effect/outbox ledger.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, config TEXT NOT NULL)")
            db.execute("""CREATE TABLE IF NOT EXISTS messages(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                message_id TEXT NOT NULL, sender TEXT NOT NULL, recipient TEXT NOT NULL,
                content TEXT NOT NULL, bytes INTEGER NOT NULL,
                received INTEGER NOT NULL DEFAULT 0, acked INTEGER NOT NULL DEFAULT 0,
                UNIQUE(run_id, message_id))""")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous = FULL")
        return db

    @contextmanager
    def transaction(self):
        with closing(self.connect()) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def create(self, run_id, *participants, max_messages=8, max_bytes=65536, max_calls=3):
        config = {"agents": list(participants), "max_messages": max_messages,
                  "max_bytes": max_bytes, "max_calls": max_calls}
        with self.transaction() as db:
            old = db.execute("SELECT config FROM runs WHERE id = ?", (run_id,)).fetchone()
            if old and old["config"] != canonical_json(config):
                raise ValueError("Frozen mailbox configuration differs")
            if not old:
                db.execute("INSERT INTO runs VALUES (?, ?)", (run_id, canonical_json(config)))

    @staticmethod
    def config(db, run_id):
        row = db.execute("SELECT config FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown JSON mailbox run")
        return json.loads(row["config"])

    def send(self, run_id, payload, *, actor):
        if (not isinstance(payload, dict) or not isinstance(payload.get("message_id"), str)
                or not payload["message_id"] or payload.get("sender") != actor):
            raise ValueError("Invalid message identity or authenticated sender")
        envelope = {"run_id": run_id, "version": "1", "payload": payload,
                    **{key: payload[key] for key in ("message_id", "sender", "recipient", "kind")}}
        content = canonical_json(envelope)
        size = len(content.encode("utf-8"))
        with self.transaction() as db:
            config = self.config(db, run_id)
            if actor not in config["agents"] or payload["recipient"] not in config["agents"]:
                raise ValueError("Unregistered JSON mailbox actor")
            old = db.execute("SELECT sequence, content FROM messages WHERE run_id = ? AND message_id = ?",
                             (run_id, payload["message_id"])).fetchone()
            if old:
                if old["content"] != content:
                    raise ValueError("Message identity reused with different content")
                return {"accepted": True, "duplicate": True, "sequence": old["sequence"]}
            usage = db.execute("SELECT COUNT(*) AS messages, COALESCE(SUM(bytes), 0) AS bytes FROM messages WHERE run_id = ?",
                               (run_id,)).fetchone()
            if usage["messages"] >= config["max_messages"] or usage["bytes"] + size > config["max_bytes"]:
                raise ValueError("JSON mailbox communication budget exhausted")
            row = db.execute("INSERT INTO messages(run_id, message_id, sender, recipient, content, bytes) VALUES (?, ?, ?, ?, ?, ?)",
                             (run_id, payload["message_id"], actor, payload["recipient"], content, size))
            return {"accepted": True, "duplicate": False, "sequence": row.lastrowid}

    def receive(self, run_id, recipient):
        with self.transaction() as db:
            if recipient not in self.config(db, run_id)["agents"]:
                raise ValueError("Unregistered JSON mailbox recipient")
            rows = db.execute("SELECT * FROM messages WHERE run_id = ? AND recipient = ? AND acked = 0 ORDER BY sequence",
                              (run_id, recipient)).fetchall()
            db.executemany("UPDATE messages SET received = 1 WHERE sequence = ?", [(row["sequence"],) for row in rows])
            return [{"message": json.loads(row["content"]), "sequence": row["sequence"],
                     "redelivered": bool(row["received"])} for row in rows]

    def acknowledge(self, run_id, message_id, recipient):
        with self.transaction() as db:
            self.config(db, run_id)
            row = db.execute("SELECT * FROM messages WHERE run_id = ? AND message_id = ?", (run_id, message_id)).fetchone()
            if row is None or row["recipient"] != recipient or not row["received"]:
                raise ValueError("JSON message must be received by its addressed actor before ACK")
            db.execute("UPDATE messages SET acked = 1 WHERE sequence = ?", (row["sequence"],))
            return {"acknowledged": True, "message_id": message_id}

    def status(self, run_id):
        with closing(self.connect()) as db:
            config = self.config(db, run_id)
            rows = db.execute("SELECT message_id AS id, sender, recipient, received, acked, bytes FROM messages WHERE run_id = ? ORDER BY sequence",
                              (run_id,)).fetchall()
            return {"config": config, "usage": {"messages": len(rows), "bytes": sum(row["bytes"] for row in rows)},
                    "messages": [dict(row) for row in rows]}


def assessment_complete(assessment: dict) -> bool:
    """Separate unusable computation from a successfully computed negative result."""
    packet = assessment.get("packet", {})
    arguments = packet.get("arguments", {})
    return bool(arguments) and all(row.get("method_result", {}).get("status") == "supported"
                                   for row in arguments.values()) and all(
        row.get("status") == "available" for row in packet.get("evidence", {}).values())


class SimulatedInterruption(Exception):
    pass


class ResourceIncomplete(RuntimeError):
    pass


class Episode:
    def __init__(self, directory: Path, spec: dict, arm: str, runtime: Path):
        self.directory, self.spec, self.arm, self.runtime = directory, dict(spec), arm, runtime
        self.directory.mkdir(parents=True, exist_ok=False)
        self.started = time.monotonic()
        self.events = []
        self.attempt = 0
        self.safe_unknown = False
        self.local_confirmed = False
        self.case = None
        self.input = {"schema": "EAL/MAS-operational-request/1", "message_id": "request",
                      "sender": "reviewer", "recipient": "assessor", "kind": "assessment_request",
                      "operation": {"entry_id": "load_test", "claim": MET_CLAIM,
                                    "requested_scope": dict(SOURCE_SCOPE), "assessed_at": OBSERVED_AT,
                                    "effect_mode": spec["effect_mode"]}}
        self.event("episode_started", arm=arm, input_digest=canonical_digest(self.input))

    def event(self, operation, **fields):
        self.events.append({"sequence": len(self.events) + 1, "operation": operation, **fields})
        save(self.directory / "events.json", self.events)

    def count(self, operation):
        return sum(row["operation"] == operation for row in self.events)

    def budget(self, operation, maximum):
        if self.count(operation) >= BUDGETS[maximum] or time.monotonic() - self.started >= BUDGETS["wall_seconds"]:
            raise ResourceIncomplete("Predeclared operational budget exhausted: " + operation)

    def transport(self):
        return LabTransport(self.runtime, self.directory / "mailbox.sqlite") if self.arm == "durable_lab" else JsonMailbox(self.directory / "mailbox.sqlite")

    def fault(self, point):
        if self.attempt == 0 and self.spec["fault"] == point:
            self.event("fault_injected", point=point, fault_mode="Python interruption")
            raise SimulatedInterruption(point)

    def effect(self):
        self.budget("effect_started", "maximum_effect_invocations")
        self.event("effect_started", effect_mode=self.spec["effect_mode"])
        ordinal = self.count("effect_started")
        if self.spec["effect_mode"] == "actual_eal_python_host":
            if self.case is None:
                self.case = prepare_case("nominal", self.directory / "workspace")
            self.event("eal_assessment_called", entry_id=self.case.entry_id, claim=MET_CLAIM,
                       assessed_at=self.case.assessed_at)
            assessment = self.case.knowledge.assess(self.case.entry_id, MET_CLAIM, now=self.case.assessed_at)
            save(self.directory / f"assessment-{ordinal:03d}.json", assessment)
            self.event("eal_assessment_returned", assessment_id=assessment["assessment_id"],
                       collected_count=assessment["collected_count"], reused_count=assessment["reused_count"],
                       complete=assessment_complete(assessment))
            if not assessment_complete(assessment):
                raise ResourceIncomplete("Actual EAL assessment returned unusable or incomplete computation; retained without retry")
            # Stable semantic receipt: assessment UUIDs remain in separate evidence.
            summary = {"claim": MET_CLAIM, "status": assessment["status"],
                       "source_digest": assessment["source_digest"], "assessed_at": assessment["assessed_at"],
                       "scope": dict(SOURCE_SCOPE), "production_supported": False}
            result = {"raw_assessment": assessment, "admission": "accepted", "summary": summary}
        else:
            summary = {"synthetic": True, "operation_digest": canonical_digest(self.input["operation"]),
                       "value": "counted deterministic software effect"}
            result = {"raw_response": canonical_json(summary), "admission": "accepted", "summary": summary}
        save(self.directory / f"effect-{ordinal:03d}.json", result)
        self.event("effect_returned", effect_result_file=f"effect-{ordinal:03d}.json")
        return result

    @staticmethod
    def reply(result):
        return {"schema": "EAL/MAS-operational-receipt/1", "message_id": "reply",
                "kind": "proposal", "sender": "assessor", "recipient": "reviewer",
                "reply_to": "request", "summary": result["summary"]}

    def send(self, message):
        self.budget("send_attempted", "maximum_send_attempts")
        self.event("send_attempted", message_id=message["message_id"])
        result = self.transport().send(RUN, message, actor="assessor")
        self.event("remote_send_returned", duplicate=result["duplicate"], message_id=message["message_id"])
        self.fault("after_send")
        self.event("send_confirmed", message_id=message["message_id"])
        return result

    def ack(self, key):
        if key != KEY:
            raise ValueError("ACK belongs to another logical request")
        self.budget("ack_attempted", "maximum_ack_attempts")
        self.event("ack_attempted", message_id="request")
        result = self.transport().acknowledge(RUN, "request", "assessor")
        self.event("remote_ack_returned", message_id="request")
        self.fault("after_ack")
        self.local_confirmed = True
        self.event("ack_confirmed", message_id="request")
        return result

    def handle(self, payload):
        if payload != self.input:
            raise ValueError("Controlled inbound identity or payload changed")
        self.budget("handler_delivery", "maximum_handler_deliveries")
        self.event("handler_delivery", attempt=self.attempt)
        if self.arm == "plain_retry":
            result = self.effect()
            self.fault("after_effect_before_commit")
            self.event("result_checkpointed_without_outbox", result_is_recoverable=False)
            self.fault("after_commit")
            self.send(self.reply(result))
            self.ack(KEY)
        else:
            ledger = EffectLedger(self.directory / "effects.sqlite")
            reserved = ledger.reserve_effect(KEY, payload)
            self.event("effect_reservation", status=reserved["status"], diagnosis=reserved["diagnosis"])
            if reserved["status"] == "unknown":
                self.safe_unknown = True
                self.event("effect_outcome_unknown", automatic_reexecution=False)
                return
            if reserved["status"] == "new":
                result = self.effect()
                self.fault("after_effect_before_commit")
                ledger.complete_effect(KEY, result, [self.reply(result)])
                self.event("effect_committed")
                self.fault("after_commit")
            else:
                self.event("committed_effect_replayed", external_effect_reexecuted=False)
            ledger.drain_outbox(self.send, self.ack)

    def run(self):
        errors = []
        try:
            bus = self.transport()
            bus.create(RUN, "reviewer", "assessor", max_messages=BUDGETS["maximum_unique_messages"],
                       max_bytes=BUDGETS["maximum_message_bytes"], max_calls=BUDGETS["maximum_effect_invocations"])
            bus.send(RUN, self.input, actor="reviewer")
            queued = []
            # All arms receive the same explicit concurrent duplicate schedule.
            repetitions = 3 if self.spec["id"] == "duplicate_request" else 1
            for _ in range(repetitions):
                receipt = bus.receive(RUN, "assessor")
                self.event("inbound_received", redelivered=receipt[0]["redelivered"])
                queued.append(receipt[0]["message"]["payload"])
            interrupted = False
            for self.attempt, payload in enumerate(queued):
                try:
                    self.handle(payload)
                except SimulatedInterruption as exc:
                    interrupted = True
                    self.event("interruption_retained", point=str(exc))
            if interrupted:
                self.attempt = 1
                self.event("recovery_started", method="New transport and ledger objects")
                receipt = self.transport().receive(RUN, "assessor")
                self.event("recovery_inbox_polled", pending_count=len(receipt))
                if receipt:
                    self.handle(receipt[0]["message"]["payload"])
                elif self.arm != "plain_retry":
                    EffectLedger(self.directory / "effects.sqlite").drain_outbox(self.send, self.ack)
                else:
                    self.event("no_pending_inbound", automatic_reexecution=False)
        except Exception as exc:
            errors.append({"type": type(exc).__name__, "detail": str(exc)})
            self.event("episode_incomplete", error=errors[-1], automatic_retry=False)
        mailbox = None
        replies = []
        try:
            mailbox = self.transport().status(RUN)
            replies = self.transport().receive(RUN, "reviewer")
            save(self.directory / "reviewer-receipts.json", replies)
        except Exception as exc:
            errors.append({"type": type(exc).__name__, "detail": str(exc), "stage": "final_mailbox_inspection"})
        received = [row["message"]["payload"] for row in replies]
        acknowledged = bool(mailbox and next((row["acked"] for row in mailbox["messages"] if row["id"] == "request"), False))
        returned = [row for row in self.events if row["operation"] == "eal_assessment_returned"]
        receipts_complete = len(returned) == self.count("eal_assessment_called")
        recorded_collected = sum(row["collected_count"] for row in returned)
        recorded_reused = sum(row["reused_count"] for row in returned)
        delivered = bool(received) and acknowledged
        outcome = "incomplete" if errors else "effect_outcome_unknown" if self.safe_unknown else "delivered" if delivered else "delivery_pending"
        row = {"episode_id": self.spec["id"], "arm": self.arm, "effect_mode": self.spec["effect_mode"],
               "execution_mode": "software_fault_injection", "outcome": outcome, "errors": errors,
               "logical_effect_invocations": self.count("effect_started"),
               "eal_assessment_calls": self.count("eal_assessment_called"),
               "collection_receipts_complete": receipts_complete,
               "collected_count": recorded_collected if receipts_complete else None,
               "reused_count": recorded_reused if receipts_complete else None,
               "recorded_collected_count": recorded_collected, "recorded_reused_count": recorded_reused,
               "handler_deliveries": self.count("handler_delivery"), "send_attempts": self.count("send_attempted"),
               "ack_attempts": self.count("ack_attempted"), "unique_replies": len(received),
               "input_acknowledged": acknowledged, "local_completion_confirmed": self.local_confirmed,
               "recovered_delivery": delivered if self.spec["fault"] else None,
               "safe_unknown": self.safe_unknown,
               "automatic_reexecution_after_unknown": self.spec["fault"] == "after_effect_before_commit" and self.count("effect_started") > 1,
               "mailbox_usage": mailbox["usage"] if mailbox else None,
               "qualified_reply_summaries": [message["summary"] for message in received],
               "budgets": dict(BUDGETS), "event_trace": "events.json", "final_worker_answers": None}
        save(self.directory / "result.json", row)
        return row


def run_episode(directory: Path, episode_id: str, arm: str, runtime: Path | None = None):
    if arm not in ARMS:
        raise ValueError("Unknown operational arm")
    spec = next((row for row in EPISODES if row["id"] == episode_id), None)
    if spec is None:
        raise ValueError("Unknown operational episode")
    return Episode(Path(directory), spec, arm, Path(runtime or "/workspace/mas-protocol-lab")).run()


def run_correspondence(directory: Path):
    """Compare admission gates using actual original-source EAL assessments."""
    directory.mkdir(parents=True, exist_ok=False)
    case = prepare_case("nominal", directory / "workspace")
    assessments, errors = {}, []
    for claim in CLAIMS:
        try:
            assessments[claim] = case.knowledge.assess(case.entry_id, claim, now=case.assessed_at)
            if not assessment_complete(assessments[claim]):
                errors.append({"claim": claim, "detail": "Actual assessment computation incomplete or unavailable"})
        except Exception as exc:
            errors.append({"claim": claim, "type": type(exc).__name__, "detail": str(exc)})
    save(directory / "source-assessments.json", assessments)
    rows = []
    for name, change in [("nominal", {}), ("changed_run", {"run_id": "demo-load-002"}),
                         ("changed_clients", {"concurrent_clients": 20}), ("changed_build", {"build_id": "demo-build-43"})]:
        task = json.loads(json.dumps(case.task))
        task["requested_scope"].update(change)
        contract = TaskContract.from_case(replace(case, task=task), task_id="operational-" + name)
        checked = check_candidate(case.knowledge, contract, case.entry_id)
        legacy = None
        if set(assessments) == set(CLAIMS):
            # Mirror /1's reference validation and context-only task gate.
            try:
                for index, claim in enumerate(CLAIMS):
                    anchor = make_anchor(case.knowledge, task_id=contract.task_id, entry_id=case.entry_id,
                                         claim=claim, assessed_at=case.assessed_at)
                    validator = Validator(case.knowledge, anchor)
                    request = make_message(anchor, kind="assessment_request", message_id=f"request-{index}",
                                           sender="reviewer", recipient="assessor")
                    validator.validate(request, actor="reviewer")
                    validator.validate(make_message(anchor, kind="proposal", message_id=f"proposal-{index}",
                                                     sender="assessor", recipient="reviewer", reply_to=request["message_id"],
                                                     **proposal_fields(assessments[claim])), actor="assessor")
                wanted = {key: task["requested_scope"][key] for key in ("service", "build_id", "dataset")}
                legacy = canonical_digest(wanted) == assessments[CLAIMS[0]]["packet"]["context_fingerprint"]
            except Exception as exc:
                errors.append({"case": name, "type": type(exc).__name__, "detail": str(exc)})
        corresponds = task["requested_scope"] == SOURCE_SCOPE
        rows.append({"case_id": name, "requested_scope": task["requested_scope"],
                     "candidate_source_scope": dict(SOURCE_SCOPE), "task_contract": contract.to_dict(),
                     "legacy_context_only_admitted": legacy, "v2_candidate_check": checked.to_dict(),
                     "legacy_false_admission": legacy is True and not corresponds,
                     "v2_false_admission": checked.ok and not corresponds,
                     "final_worker_answers": None})
    result = {"execution_mode": "actual_eal_python_host_and_software_admission_checks",
              "eal_assessment_calls": len(CLAIMS), "errors": errors,
              "outcome": "incomplete" if errors else "complete", "cases": rows,
              "assessment_artifact": "source-assessments.json", "actual_mcp_calls": 0}
    save(directory / "result.json", result)
    return result


def run(output: Path, runtime: Path | None = None):
    output = Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("Use a new empty output directory; preserve all prior outcomes")
    output.mkdir(parents=True, exist_ok=True)
    plan = frozen_plan()
    save(output / "plan.json", plan)
    try:
        correspondence = run_correspondence(output / "correspondence")
    except Exception as exc:
        correspondence = {"outcome": "incomplete", "eal_assessment_calls": None,
                          "errors": [{"type": type(exc).__name__, "detail": str(exc)}],
                          "cases": [{"case_id": name, "execution_state": "not_run_or_unknown", "final_worker_answers": None}
                                    for name in plan["correspondence_cases"]]}
        save(output / "correspondence/result.json", correspondence)
    rows = []
    for spec in EPISODES:
        for arm in ARMS:
            row = run_episode(output / (spec["id"] + "-" + arm), spec["id"], arm, runtime)
            row["artifact_directory"] = spec["id"] + "-" + arm
            rows.append(row)
    summary = {}
    for arm in ARMS:
        selected = [row for row in rows if row["arm"] == arm]
        summary[arm] = {"scheduled_episodes": len(EPISODES), "retained_episodes": len(selected),
                        "delivered": sum(row["outcome"] == "delivered" for row in selected),
                        "safe_unknown": sum(row["outcome"] == "effect_outcome_unknown" for row in selected),
                        "incomplete": sum(row["outcome"] == "incomplete" for row in selected),
                        "logical_effect_invocations": sum(row["logical_effect_invocations"] for row in selected),
                        "eal_assessment_calls": sum(row["eal_assessment_calls"] for row in selected)}
    report = {"schema": "EAL/mas-coordination-operational-report/1",
              "created_at": datetime.now(timezone.utc).isoformat(), "execution_mode": "software_fault_injection",
              "outcome": "incomplete" if correspondence["outcome"] == "incomplete" or any(row["outcome"] == "incomplete" for row in rows) else "complete",
              "plan_digest": canonical_digest(plan), "correspondence": correspondence,
              "summary": summary, "episodes": rows, "native_model_calls": 0, "actual_mcp_calls": 0,
              "model_tokens": None, "model_cost_usd": None,
              "limitations": ["Internal synthetic fixtures and explicit fault schedules",
                              "No native model outputs or fabricated final answers",
                              "Actual Python EAL calls are not MCP calls",
                              "Interrupted external effects are unresolved, not successfully completed",
                              "Observation reuse and logical effect-call reduction are separate measurements",
                              "Stable semantic receipts omit per-assessment UUIDs; complete actual assessments are retained separately",
                              "Wall budget checked at operation boundaries; existing EAL method limits unchanged",
                              "Wire syntax is not credited for effects also achieved by the durable JSON control",
                              "No token, USD, development-cost or general capability improvement measured"],
              "implementation_sha256": {str(path.relative_to(Path(__file__).parents[2])): hashlib.sha256(path.read_bytes()).hexdigest()
                                         for path in (Path(__file__), Path(__file__).with_name("effect_ledger.py"), Path(__file__).with_name("task_contract.py"))}}
    save(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--runtime", type=Path, default=Path("/workspace/mas-protocol-lab"))
    args = parser.parse_args()
    result = run(args.output, args.runtime)
    print(json.dumps({"output": str(args.output.resolve()), "summary": result["summary"],
                      "correspondence_outcome": result["correspondence"]["outcome"],
                      "outcome": result["outcome"]}, indent=2, allow_nan=False))
    if result["outcome"] == "incomplete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
