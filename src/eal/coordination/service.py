"""Reusable, single-host assessor/reviewer coordination over registered MCP.

External worker execution and assessment are reserved before effects. A
reservation without a committed receipt is never automatically repeated.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from functools import wraps
from uuid import uuid4

from filelock import FileLock

from eal.evaluator import canonical_digest
from eal.store import utc_now
from .bus import envelope, open_bus
from .contracts import ServerSpec, TaskSpec, json_object, make_finding
from .gateway import MCPGateway
from .ledger import canonical_json
from .profiles import check_task, pin_task, validate_answer
from .state import State

MESSAGE_SCHEMA = "EAL/MAS-coordination/3"
MODES = {"actual_host_agent", "provider", "software_test"}
DEFAULT_BUDGETS = {"max_worker_calls": 2, "max_gateway_calls_per_role": 4,
                   "max_mcp_calls_per_role": 64, "max_messages": 8, "max_bytes": 65536,
                   "max_worker_output_bytes": 65536, "wall_seconds": 900,
                   "worker_seconds": 180}


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
    if type(value) is not dict:
        raise ValueError("Worker response must be one JSON object")
    canonical_json(value)
    return value


def lifecycle(operation):
    @wraps(operation)
    def locked(self, *args, **kwargs):
        with self._lifecycle:
            return operation(self, *args, **kwargs)
    return locked


class Coordinator:
    """Open an existing frozen run; use ``start`` to create a new run."""
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        if not (self.directory / "coordination.sqlite").is_file():
            raise FileNotFoundError("No coordinator state; start a new run first")
        self.state = State(self.directory / "coordination.sqlite")
        self.config = self.state.config()
        self.server = ServerSpec.from_dict(self.config["server"])
        self.anchor = self.config["anchor"]
        self.task = TaskSpec.from_dict(self.anchor["task"])
        self.bus = open_bus(self.directory, self.config)
        self._lifecycle = FileLock(self.directory / "lifecycle.lock", timeout=30)

    @classmethod
    def start(cls, directory, server, task, *, budgets=None, transport=None):
        directory = Path(directory).resolve()
        if directory.exists() and any(directory.iterdir()):
            raise FileExistsError("Use an empty directory; existing runs are immutable")
        server = ServerSpec.from_dict(server) if type(server) is dict else server
        task = TaskSpec.from_dict(task) if type(task) is dict else task
        if not isinstance(server, ServerSpec) or not isinstance(task, TaskSpec):
            raise ValueError("Typed server and task specifications are required")
        selected = dict(DEFAULT_BUDGETS)
        if budgets is not None:
            if type(budgets) is not dict or set(budgets) - set(selected):
                raise ValueError("Unknown coordination budget")
            selected.update(budgets)
        if any(type(value) is not int or value < 1 for value in selected.values()):
            raise ValueError("Budgets require positive integers")
        if (selected["max_worker_calls"] > 2 or selected["max_messages"] > 100
                or selected["max_bytes"] > 1048576 or selected["max_worker_output_bytes"] > 1048576
                or selected["wall_seconds"] > 3600 or selected["worker_seconds"] > selected["wall_seconds"]
                or selected["max_gateway_calls_per_role"] > 64 or selected["max_mcp_calls_per_role"] > 256):
            raise ValueError("Budgets exceed the single-host coordinator profile")
        selected_transport = {"kind": "json"} if transport is None else dict(transport)
        if selected_transport == {"kind": "json"}:
            pass
        elif set(selected_transport) == {"kind", "runtime"} and selected_transport["kind"] == "lab":
            selected_transport["runtime"] = str(Path(selected_transport["runtime"]).resolve())
        else:
            raise ValueError("Transport must be JSON or an explicitly installed Lab runtime")
        anchor = pin_task(server, task)
        directory.mkdir(parents=True, exist_ok=True)
        state = State(directory / "coordination.sqlite")
        state.initialize({"schema": "EAL/coordination-run/1", "run_id": "coord-" + uuid4().hex,
                          "server": server.to_dict(), "anchor": anchor, "budgets": selected,
                          "transport": selected_transport, "created_at": utc_now(),
                          "deadline": int(time.time()) + selected["wall_seconds"]})
        value = cls(directory)
        value.state.event("started", {"task_digest": anchor["task_digest"]})
        value.resume()
        return value

    def _active(self):
        if self.state.cancelled():
            raise ValueError("Run was cancelled")
        if time.time() >= self.config["deadline"]:
            raise ValueError("Run wall-clock budget exhausted")

    def _ensure_bus(self):
        if any(event["kind"] == "bus_initialized" for event in self.state.events()):
            return
        b = self.config["budgets"]
        self.bus.create(self.config["run_id"], "assessor", "reviewer",
                        max_messages=b["max_messages"], max_bytes=b["max_bytes"],
                        max_calls=b["max_worker_calls"])
        self.state.event("bus_initialized", {})

    def _request(self):
        return {"schema": MESSAGE_SCHEMA, "kind": "request", "message_id": "request",
                "task_id": self.task.task_id, "task_digest": self.anchor["task_digest"],
                "sender": "reviewer", "recipient": "assessor", "reply_to": None, "attempt": 0}

    def _incoming(self, role):
        if role == "assessor":
            return [self._request()]
        assessor = self.state.effect("worker:assessor")
        if not assessor or assessor["status"] != "committed" or not assessor["result"]["accepted"]:
            raise ValueError("No accepted assessor handoff is ready")
        return assessor["outbox"]

    def _receive(self, role, expected):
        wrappers = self.bus.receive(self.config["run_id"], role)
        if type(wrappers) is not list or len(wrappers) != len(expected):
            raise ValueError("Addressed delivery differs from the expected handoff")
        received = []
        for wrapper, payload in zip(wrappers, expected):
            if (type(wrapper) is not dict or set(wrapper) != {"message", "sequence", "redelivered"}
                    or type(wrapper["sequence"]) is not int or wrapper["sequence"] < 1
                    or type(wrapper["redelivered"]) is not bool
                    or canonical_json(wrapper["message"]) != canonical_json(envelope(self.config["run_id"], payload))):
                raise ValueError("Canonical delivery envelope or receipt metadata differs")
            received.append(wrapper["message"]["payload"])
        self.state.event("received", {"role": role, "receipts": wrappers})
        return received

    @lifecycle
    def resume(self):
        """Resume committed publication/ACK only; never relaunch an unknown effect."""
        self._ensure_bus()
        initial = self.state.reserve_effect("initial", self._request())
        if initial["status"] != "committed":
            # This is a deterministic coordinator contribution, not a worker.
            self.state.complete_effect("initial", {"message": self._request()}, [self._request()])
        # Transport accounting is deterministic. Reconcile its reservation
        # without granting permission to repeat an uncertain worker execution.
        transport_calls = {row["id"]: row for row in self.bus.status(self.config["run_id"])["calls"]}
        for role in ("assessor", "reviewer"):
            effect = self.state.effect("worker:" + role)
            if effect:
                call_id = effect["payload"]["call_id"]
                existing = transport_calls.get(call_id)
                if existing is None:
                    self.bus.reserve(self.config["run_id"], role, call_id)
                    transport_calls[call_id] = {"id": call_id, "actor": role, "state": "reserved", "evidence": None}
                elif existing["actor"] != role:
                    raise ValueError("Transport reservation belongs to another role")
        def send(message):
            return self.bus.send(self.config["run_id"], message, actor=message["sender"])
        def ack(key):
            if key.startswith("worker:"):
                effect = self.state.effect(key)
                for incoming in effect["payload"]["context"]["received_messages"]:
                    self.bus.acknowledge(self.config["run_id"], incoming["message_id"], effect["payload"]["role"])
        self.state.drain_outbox(send, ack)
        # Finish is not idempotent in Lab; reconcile its durable state first.
        calls = transport_calls
        for role in ("assessor", "reviewer"):
            effect = self.state.effect("worker:" + role)
            if not effect or effect["status"] != "committed":
                continue
            result = effect["result"]
            call_id = effect["payload"]["call_id"]
            evidence = {"execution_id": result["execution_id"], "execution_mode": result["execution_mode"],
                        "response_digest": result["raw_digest"], "outcome": result["outcome"],
                        "tokens": None, "cost_usd": None}
            prior = calls.get(call_id)
            if prior is None:
                raise ValueError("Committed worker has no prelaunch transport reservation")
            if prior["state"] == "recorded":
                if prior["evidence"] != evidence:
                    raise ValueError("Transport completion evidence differs from the committed worker")
            else:
                self.bus.finish(self.config["run_id"], role, call_id, evidence)
            if not any(event["kind"] == "transport_finished" and event["data"]["call_id"] == call_id for event in self.state.events()):
                self.state.event("transport_finished", {"call_id": call_id})
        return self.status()

    @lifecycle
    def reserve_worker(self, role, *, execution_mode="actual_host_agent"):
        if role not in {"assessor", "reviewer"} or execution_mode not in MODES:
            raise ValueError("Unknown worker role or execution mode")
        self._active()
        prior = self.state.effect("worker:" + role)
        if prior:
            if prior["payload"]["execution_mode"] != execution_mode:
                raise ValueError("A frozen worker execution mode cannot change")
            return {"new": False, "state": prior["status"], "call_id": prior["payload"]["call_id"],
                    "context": prior["payload"]["context"]}
        self.resume()
        incoming = self._receive(role, self._incoming(role))
        worker_count = sum(effect["key"].startswith("worker:") for effect in self.state.effects())
        if worker_count >= self.config["budgets"]["max_worker_calls"]:
            raise ValueError("Worker call budget exhausted")
        call_id = self.config["run_id"] + ":" + role
        context = {"schema": "EAL/coordination-worker-context/1", "role": role, "call_id": call_id,
                   "task": self.anchor, "received_messages": incoming,
                   "gateway": {"argv": [sys.executable, "-m", "eal.coordination.cli",
                                        "query" if role == "assessor" else "lookup", "--run", str(self.directory),
                                        "--call-id", call_id]},
                   "response_schema": str(Path(__file__).with_name("response-schema.json")),
                   "instructions": ("Inspect your addressed messages. Request a finding using the gateway argv and author an outcome or disposition with its exact trusted references. Return message and consumed_message_ids."
                                    if role == "assessor" else
                                    "Inspect your addressed handoff. Retrieve its finding by adding --finding-id to the gateway argv. Independently author the scoped answer, preserving every claim status, assessment ID and assessment time. Return answer and consumed_message_ids."),
                   "qualifications": "EAL status is conditional on the registered argument. Unsupported is not proof of the opposite. Authored prose and measurements are not independently certified by registration."}
        payload = {"role": role, "call_id": call_id, "execution_mode": execution_mode, "context": context}
        reserved = self.state.reserve_effect("worker:" + role, payload)
        if reserved["status"] != "new":
            return {"new": False, "state": reserved["status"], "call_id": call_id, "context": context}
        self.bus.reserve(self.config["run_id"], role, call_id)
        self.state.event("worker_reserved", {"role": role, "call_id": call_id, "execution_mode": execution_mode})
        return {"new": True, "state": "reserved", "call_id": call_id, "context": context}

    def _worker(self, call_id, role=None):
        for actor in ("assessor", "reviewer"):
            effect = self.state.effect("worker:" + actor)
            if effect and effect["payload"]["call_id"] == call_id:
                if role and actor != role:
                    raise ValueError("Operation is unavailable to this worker role")
                return actor, effect
        raise ValueError("No prelaunch worker reservation matches this call")

    def _gateway(self, call_id, role, operation):
        self._active()
        _, worker = self._worker(call_id, role)
        if worker["status"] == "committed":
            raise ValueError("The worker's first response has already been recorded")
        self.state.reserve_call(role, "gateway", operation, self.config["budgets"]["max_gateway_calls_per_role"])
        def before_call(name, arguments, exposure):
            self._active()
            self.state.reserve_call(role, "mcp", name, self.config["budgets"]["max_mcp_calls_per_role"])
        return MCPGateway(self.server, self.anchor, on_call=before_call)

    def _unknown(self, gateway=None):
        finding = make_finding(self.anchor, {"ok": False, "code": "effect_outcome_unknown",
                               "detail": "Assessment effect has no committed complete receipt; automatic reexecution is disabled"},
                               calls=[] if gateway is None else gateway.calls)
        finding["collected_count"] = finding["reused_count"] = None
        finding["finding_id"] = "finding_" + canonical_digest({k: v for k, v in finding.items() if k != "finding_id"})
        return finding

    def query(self, call_id):
        gateway = self._gateway(call_id, "assessor", "query")
        reservation = self.state.reserve_effect("assessment", {"task_digest": self.anchor["task_digest"]})
        if reservation["status"] == "committed":
            current = check_task(self.server, self.anchor)
            finding = reservation["result"] if current == reservation["result"]["check"] else make_finding(self.anchor, current)
        elif reservation["status"] == "unknown":
            finding = self._unknown()
        else:
            try:
                finding = gateway.assess()
            except Exception as error:
                self.state.event("assessment_interrupted", {"error_type": type(error).__name__, "calls": gateway.calls})
                finding = self._unknown(gateway)
            else:
                self.state.complete_effect("assessment", finding, [])
        self.state.issue(finding)
        self.state.event("query", {"call_id": call_id, "finding_id": finding["finding_id"]})
        return finding

    def _issued(self, identity):
        finding = self.state.finding(identity)
        if finding["finding_id"] != "finding_" + canonical_digest({k: v for k, v in finding.items() if k != "finding_id"}):
            raise ValueError("Issued finding content identity differs")
        if finding["task_digest"] != self.anchor["task_digest"]:
            raise ValueError("Finding belongs to another task")
        current = check_task(self.server, self.anchor)
        if finding["check"]["code"] != "effect_outcome_unknown" and current != finding["check"]:
            raise ValueError("Task correspondence changed since finding issuance")
        return finding

    def lookup(self, call_id, finding_id):
        gateway = self._gateway(call_id, "reviewer", "lookup")
        finding = self._issued(finding_id)
        if finding["check"]["code"] != "effect_outcome_unknown":
            finding = gateway.lookup(finding)
        self.state.event("lookup", {"call_id": call_id, "finding_id": finding_id, "calls": gateway.calls})
        return finding

    def _admit(self, role, call_id, context, value):
        fields = {"message", "consumed_message_ids"} if role == "assessor" else {"answer", "consumed_message_ids"}
        if set(value) != fields or value["consumed_message_ids"] != [m["message_id"] for m in context["received_messages"]]:
            raise ValueError("Response fields or consumed message identities differ")
        operation = "query" if role == "assessor" else "lookup"
        if role == "assessor":
            message = value["message"]
            if type(message) is not dict:
                raise ValueError("Handoff must be an object")
            common = {"schema", "kind", "message_id", "task_id", "task_digest", "sender", "recipient", "reply_to", "attempt", "finding_id"}
            extra = {"assessment_refs"} if message.get("kind") == "outcome" else {"code", "outcome"}
            if set(message) != common | extra or message.get("kind") not in {"outcome", "disposition"}:
                raise ValueError("Handoff differs from the closed coordination message contract")
            if (message["schema"], message["task_id"], message["task_digest"], message["sender"], message["recipient"], message["reply_to"], message["attempt"]) != (MESSAGE_SCHEMA, self.task.task_id, self.anchor["task_digest"], "assessor", "reviewer", "request", 0) or type(message["attempt"]) is not int:
                raise ValueError("Handoff replaced a trusted task identity")
            if (type(message["message_id"]) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}", message["message_id"]) or message["message_id"] == "request"):
                raise ValueError("Reply requires a distinct bounded message identity")
            identity = message["finding_id"]
        else:
            if type(value["answer"]) is not dict:
                raise ValueError("Answer must be an object")
            identity = value["answer"].get("finding_id")
        if not any(e["kind"] == operation and e["data"]["call_id"] == call_id and e["data"]["finding_id"] == identity for e in self.state.events()):
            raise ValueError("Worker must request its referenced finding through its role gateway")
        finding = self._issued(identity)
        if role == "assessor":
            if finding["check"]["ok"]:
                refs = {claim: row["assessment_id"] for claim, row in finding["assessments"].items()}
                if message["kind"] != "outcome" or message["assessment_refs"] != refs:
                    raise ValueError("Outcome must retain every actual assessment reference")
            elif (message["kind"] != "disposition" or message["code"] != finding["check"]["code"]
                  or message["outcome"] != ("incomplete" if finding["check"]["code"] in {"evidence_unavailable", "effect_outcome_unknown"} else "rejected")):
                raise ValueError("Unassessed task requires its matching typed disposition")
            return [message]
        received_id = context["received_messages"][0]["finding_id"]
        if identity != received_id:
            raise ValueError("Reviewer substituted the addressed finding")
        diagnostics = validate_answer(self.anchor, finding, value["answer"])
        if diagnostics:
            raise ValueError(canonical_json(diagnostics))
        return []

    @lifecycle
    def record(self, call_id, raw_response, execution_id, *, execution_mode, response=None, evidence=None):
        """Atomically retain exact bytes, admission and outbox before publication."""
        role, worker = self._worker(call_id)
        if type(raw_response) is not bytes or type(execution_id) is not str or not execution_id.strip() or len(execution_id) > 512:
            raise ValueError("Exact response bytes and a bounded actual execution identity are required")
        if execution_mode != worker["payload"]["execution_mode"]:
            raise ValueError("Execution mode differs from the prelaunch reservation")
        digest = hashlib.sha256(raw_response).hexdigest()
        if worker["status"] == "committed":
            prior = worker["result"]
            if prior["raw_digest"] != digest or prior["execution_id"] != execution_id:
                raise ValueError("First response cannot be replaced or repaired")
            self.resume()
            return prior
        result = {"execution_id": execution_id, "execution_mode": execution_mode,
                  "raw_base64": base64.b64encode(raw_response).decode("ascii"), "raw_digest": digest,
                  "evidence": {}, "accepted": False,
                  "outcome": "rejected", "diagnostics": [], "response": None}
        outbox = []
        try:
            result["evidence"] = {} if evidence is None else json_object(evidence, "execution evidence")
            self._active()
            if len(raw_response) > self.config["budgets"]["max_worker_output_bytes"]:
                raise ValueError("Worker response exceeds output budget")
            decoded = strict_json(raw_response)
            wrapped = set(decoded) == {"response", "execution"}
            if wrapped:
                from .workers import _receipt
                if execution_mode == "software_test":
                    raise ValueError("Software mode requires a direct response, without a live receipt")
                receipt = _receipt(decoded["execution"], call_id)
                if receipt["execution_id"] != execution_id:
                    raise ValueError("External execution receipt differs from the recorded identity")
            parsed = decoded["response"] if wrapped else decoded
            if response is not None and canonical_json(response) != canonical_json(parsed):
                raise ValueError("Parsed worker response differs from its exact retained bytes")
            if type(parsed) is not dict:
                raise ValueError("Worker frame must be an object")
            if execution_mode == "provider" and not wrapped:
                raise ValueError("Provider execution needs its matching external receipt")
            for prior in self.state.effects():
                if prior["key"].startswith("worker:") and prior["status"] == "committed" and prior["result"]["execution_id"] == execution_id:
                    raise ValueError("Separate worker roles require distinct execution identities")
            result["response"] = parsed
            outbox = self._admit(role, call_id, worker["payload"]["context"], parsed)
            result.update(accepted=True, outcome="accepted")
        except Exception as error:
            result["diagnostics"] = [{"code": "response_rejected", "detail": str(error)}]
        self.state.complete_effect("worker:" + role, result, outbox)
        self.state.event("worker_recorded", {"call_id": call_id, "execution_id": execution_id, "outcome": result["outcome"]})
        self.resume()
        return result

    def run(self, worker):
        """Run each role once in a fresh command context; retain interruptions."""
        from .workers import WorkerInterrupted
        if worker.max_output_bytes > self.config["budgets"]["max_worker_output_bytes"]:
            raise ValueError("Worker output limit exceeds the run's frozen budget")
        self.resume()
        for role in ("assessor", "reviewer"):
            existing = self.state.effect("worker:" + role)
            if existing:
                if existing["status"] != "committed" or not existing["result"]["accepted"]:
                    return self.status()
                continue
            reservation = self.reserve_worker(role, execution_mode=worker.execution_mode)
            if not reservation["new"]:
                return self.status()
            remaining = min(self.config["budgets"]["worker_seconds"],
                            max(1, int(self.config["deadline"] - time.time())))
            try:
                output = worker.execute(reservation["context"], reservation["call_id"], remaining,
                                        should_stop=self.state.cancelled)
            except WorkerInterrupted as error:
                result = {"execution_id": error.execution_id, "execution_mode": error.execution_mode,
                          "raw_base64": base64.b64encode(error.raw_response).decode("ascii"),
                          "raw_digest": hashlib.sha256(error.raw_response).hexdigest(), "evidence": error.evidence,
                          "accepted": False, "outcome": "interrupted", "diagnostics": [{"code": error.reason}], "response": None}
                self.state.complete_effect("worker:" + role, result, [])
                self.state.event("worker_interrupted", {"call_id": reservation["call_id"], "reason": error.reason})
                self.resume()
                return self.status()
            self.record(reservation["call_id"], output.raw_response, output.execution_id,
                        execution_mode=output.execution_mode, response=output.response, evidence=output.evidence)
            if not self.state.effect("worker:" + role)["result"]["accepted"]:
                return self.status()
        return self.status()

    def cancel(self):
        self.state.cancel()
        return self.status()

    def status(self):
        workers = {role: self.state.effect("worker:" + role) for role in ("assessor", "reviewer")}
        answer = None
        if self.state.cancelled():
            status = "cancelled"
        elif any(w and w["status"] == "committed" and not w["result"]["accepted"] for w in workers.values()):
            status = "failed"
        elif workers["reviewer"] and workers["reviewer"]["status"] == "committed":
            answer = workers["reviewer"]["result"]["response"]["answer"]
            status = "completed" if answer["conclusion"] == "assessed" else "completed_unassessed"
        elif time.time() >= self.config["deadline"]:
            status = "expired"
        elif any(w and w["status"] == "unknown" for w in workers.values()):
            status = "awaiting_worker_result"
        else:
            status = "ready_reviewer" if workers["assessor"] else "ready_assessor"
        committed = [w for w in workers.values() if w and w["status"] == "committed"]
        initial = self.state.effect("initial")
        if initial and not initial["acknowledged"] and status not in {"cancelled", "expired"}:
            status = "delivery_pending"
        if committed and status not in {"cancelled", "expired"}:
            finished = {event["data"]["call_id"] for event in self.state.events() if event["kind"] == "transport_finished"}
            if any(not w["acknowledged"] or w["payload"]["call_id"] not in finished for w in committed):
                status = "delivery_pending"
        return {"schema": "EAL/coordination-status/1", "run_id": self.config["run_id"], "status": status,
                "task_digest": self.anchor["task_digest"], "deadline": self.config["deadline"],
                "workers": {role: None if not w else {"state": w["status"], "call_id": w["payload"]["call_id"],
                            "execution_mode": w["payload"]["execution_mode"],
                            "execution_id": None if w["result"] is None else w["result"]["execution_id"],
                            "outcome": None if w["result"] is None else w["result"]["outcome"]} for role, w in workers.items()},
                "answer": answer, "calls": self.state.calls()}

    def export(self, path):
        value = {"schema": "EAL/coordination-export/1", "config": self.config,
                 "status": self.status(), "effects": self.state.effects(), "events": self.state.events(),
                 "transport": self.bus.status(self.config["run_id"]),
                 "limits": ["Trusted local host; shared filesystem permissions are not role isolation",
                            "Worker external execution receipts are host assertions, not authenticated provider receipts",
                            "Assessment times belong to individual MCP results; replay does not establish a current decision"]}
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        return value
