"""Strict, host-checked payloads for the optional EAL/MAS-coordination/1 study.

The MAS Protocol Lab wire envelope is a separate contract. Both study arms use
this payload validator; it neither transports packets nor implements EAL
reasoning. A task pins an explicit assessment time. For a live decision create a
new anchor and ask the EAL host for a new assessment rather than replaying an
old result under a new time.

The conversation is deliberately bounded: request A -> B, proposal B -> A,
then one review or objection A -> B. Actor identities come from the trusted
runner, not the payload or the wire envelope's sender spelling.
"""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass
from datetime import timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from eal.collection_identity import CollectionIdentityValidator
from eal.evaluator import canonical_digest
from eal.knowledge import EALKnowledgeBase
from eal.semantics import parse_time


PAYLOAD_SCHEMA = "EAL/MAS-coordination/1"
SCHEMA = json.loads(Path(__file__).with_name("schema.json").read_text())
Draft202012Validator.check_schema(SCHEMA)
_SCHEMA_VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


class ProtocolError(ValueError):
    """A malformed or unauthorised handoff; an EAL claim status is not an error."""


def _instant(value: str) -> str:
    return parse_time(value).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ScopeAnchor:
    """Trusted task scope, established before either worker starts."""

    task_id: str
    entry_id: str
    claim: str
    source_digest: str
    context_fingerprint: str
    method_registry_fingerprint: str
    assessed_at: str

    @property
    def scope(self) -> dict[str, str]:
        values = asdict(self)
        values.pop("task_id")
        return values


def make_anchor(kb: EALKnowledgeBase, *, task_id: str, entry_id: str,
                claim: str, assessed_at: str) -> ScopeAnchor:
    """Resolve a current registered claim and pin its host-produced identities."""
    entry = kb.catalogue.get(entry_id)
    if claim not in entry["claims"]:
        raise ProtocolError("Claim is not selected in the registered entry")
    anchor = ScopeAnchor(
        task_id=task_id, entry_id=entry_id, claim=claim,
        source_digest=entry["source_digest"],
        context_fingerprint=canonical_digest(entry["context"]),
        method_registry_fingerprint=entry["method_registry_fingerprint"],
        assessed_at=_instant(assessed_at),
    )
    # Apply discovery constraints even to values supplied by the trusted runner.
    _validate_shape(make_message(anchor, kind="assessment_request", message_id="anchor_check",
                                 sender="reviewer", recipient="assessor"))
    return anchor


def make_message(anchor: ScopeAnchor, *, kind: str, message_id: str,
                 sender: str, recipient: str, reply_to: str | None = None,
                 **body: Any) -> dict[str, Any]:
    """Construct a payload; validation remains mandatory before accepting it.

    Proposal body fields come from ``proposal_fields(registered_assessment)``.
    A review adds ``assessment_id`` and ``verdict`` (accepted/unresolved/rejected).
    An objection adds ``assessment_id``, ``target_kind``, ``target_id`` and
    ``reason``. Review verdicts and objection prose never change EAL status.
    """
    fixed = {
        "schema": PAYLOAD_SCHEMA, "kind": kind, "message_id": message_id,
        "task_id": anchor.task_id, "sender": sender, "recipient": recipient,
        "reply_to": reply_to, "scope": anchor.scope,
    }
    if fixed.keys() & body.keys():
        raise ProtocolError("Body cannot replace fixed coordination fields")
    return {**fixed, **copy.deepcopy(body)}


def proposal_fields(assessment: dict[str, Any]) -> dict[str, Any]:
    """Project a host result into references, leaving all packet floats local.

    The validator checks the references against the complete claim plan. If a
    bounded host packet omitted evidence identifiers this helper cannot invent
    them; the runner must retrieve the trusted complete collection first.
    """
    if assessment.get("schema") != "EAL/registered-assessment/1":
        raise ProtocolError("Proposal requires a registered assessment")
    return {
        "assessment_id": assessment["assessment_id"],
        "collection_id": assessment["collection_id"],
        "status": assessment["status"],
        "evidence_refs": {
            name: record["observation_id"]
            for name, record in assessment["packet"].get("evidence", {}).items()
        },
    }


def decode_payload(data: str) -> dict[str, Any]:
    """Decode JSON without duplicate fields, nonfinite values, or oversized input."""
    try:
        size = len(data.encode("utf-8")) if isinstance(data, str) else 32769
    except UnicodeError as exc:
        raise ProtocolError("Payload must contain valid UTF-8") from exc
    if size > 32768:
        raise ProtocolError("Payload must contain at most 32768 UTF-8 bytes")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ProtocolError("Payload contains a duplicate JSON field")
            result[key] = value
        return result

    def constant(_value):
        raise ProtocolError("Payload requires finite JSON")

    try:
        message = json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, RecursionError) as exc:
        raise ProtocolError("Payload is not strict JSON") from exc
    _validate_shape(message)
    return message


def _validate_shape(message: Any) -> None:
    try:
        encoded = json.dumps(message, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ProtocolError("Payload must contain bounded finite UTF-8 JSON") from exc
    if len(encoded) > 32768:
        raise ProtocolError("Payload exceeds 32768 UTF-8 bytes")
    if next(_SCHEMA_VALIDATOR.iter_errors(message), None) is not None:
        # Do not include arbitrary agent prose or host data in diagnostics.
        raise ProtocolError("Payload does not match EAL/MAS-coordination/1 discovery schema")


class Validator:
    """Validate host references and a single request/proposal/review conversation.

    Instantiate one validator per anchored task and feed it accepted messages
    in order. Invalid attempts do not consume a request or message identifier.
    Durable replay protection belongs to the study's retained runner ledger;
    this local validator must be reconstructed by replaying accepted messages.
    """

    def __init__(self, kb: EALKnowledgeBase, anchor: ScopeAnchor, *,
                 requester: str = "reviewer", responder: str = "assessor"):
        if requester == responder:
            raise ProtocolError("Task requester and responder must be distinct actors")
        self.kb = kb
        self.anchor = anchor
        self.requester = requester
        self.responder = responder
        self._messages: dict[str, dict[str, Any]] = {}
        self._answered: set[str] = set()
        self._check_anchor()

    def _check_anchor(self) -> dict[str, Any]:
        try:
            entry = self.kb.catalogue.get(self.anchor.entry_id, include_source=True)
        except (KeyError, ValueError) as exc:
            raise ProtocolError("Registered task scope is unavailable") from exc
        if entry["source_digest"] != self.anchor.source_digest:
            raise ProtocolError("Registered source revision changed after the task was anchored")
        if (entry["method_registry_fingerprint"] != self.anchor.method_registry_fingerprint
                or self.kb.service.method_registry.fingerprint != self.anchor.method_registry_fingerprint):
            raise ProtocolError("Method registry differs from the anchored contract")
        if canonical_digest(entry["context"]) != self.anchor.context_fingerprint:
            raise ProtocolError("Registered context differs from the anchored scope")
        if self.anchor.claim not in entry["claims"]:
            raise ProtocolError("Anchored claim is no longer selected")
        return entry

    def _reply(self, message: dict[str, Any]) -> dict[str, Any] | None:
        if message["kind"] == "assessment_request":
            if self._messages:
                raise ProtocolError("An anchored task admits one initial request")
            if message["sender"] != self.requester or message["recipient"] != self.responder:
                raise ProtocolError("Initial request differs from the authorised task actors")
            return None
        reply_to = message["reply_to"]
        previous = self._messages.get(reply_to)
        if previous is None:
            raise ProtocolError("Reply has no accepted prior message")
        required_kind = "assessment_request" if message["kind"] == "proposal" else "proposal"
        if previous["kind"] != required_kind:
            raise ProtocolError("Reply refers to the wrong message kind")
        if reply_to in self._answered:
            raise ProtocolError("Prior message already has an accepted reply")
        if (message["sender"] != previous["recipient"]
                or message["recipient"] != previous["sender"]):
            raise ProtocolError("Reply sender and recipient do not reverse the prior handoff")
        return previous

    def _assessment(self, message: dict[str, Any], entry: dict[str, Any],
                    previous: dict[str, Any] | None) -> dict[str, Any]:
        if previous is not None and previous["kind"] == "proposal":
            if message["assessment_id"] != previous["assessment_id"]:
                raise ProtocolError("Review or objection substituted the proposed assessment")
            refs = previous
        else:
            refs = message
        try:
            assessment = self.kb.service.store.get(message["assessment_id"], kind="assessment")
            collection = self.kb.service.store.get(refs["collection_id"], kind="collection")
        except KeyError as exc:
            raise ProtocolError("Assessment or collection reference is unknown") from exc
        for field in ("source_digest", "context_fingerprint", "method_registry_fingerprint"):
            if assessment.get(field) != self.anchor.scope[field]:
                raise ProtocolError("Assessment differs from the anchored scope")
        try:
            if _instant(assessment["assessed_at"]) != self.anchor.assessed_at:
                raise ProtocolError("Historical assessment does not match the anchored assessment time")
        except (KeyError, ValueError) as exc:
            raise ProtocolError("Assessment time differs from the anchored assessment time") from exc
        if assessment.get("collection_id") != refs["collection_id"]:
            raise ProtocolError("Collection reference differs from the assessment")
        result = assessment.get("claims", {}).get(self.anchor.claim)
        if not isinstance(result, dict) or result.get("status") != refs["status"]:
            raise ProtocolError("Proposed claim status differs from the trusted host result")
        try:
            records = CollectionIdentityValidator().validate(
                collection, source_digest=self.anchor.source_digest, context=entry["context"],
            )
            plan = self.kb.service.plan(entry["source"], self.anchor.claim)
            if set(refs["evidence_refs"]) != set(plan["evidence_ids"]):
                raise ProtocolError("Evidence references do not cover the complete claim plan")
            if set(records) != set(plan["evidence_ids"]):
                raise ProtocolError("Collection does not contain the complete claim plan")
            for name, observation_id in refs["evidence_refs"].items():
                record = records[name]
                if (record.get("run_id") != observation_id
                        or assessment.get("evidence", {}).get(name, {}).get("run_id") != observation_id):
                    raise ProtocolError("Evidence reference differs from the assessed observation")
                if self.kb.service.store.get(observation_id, kind="observation") != record:
                    raise ProtocolError("Collection observation differs from the durable host record")
        except (KeyError, ValueError) as exc:
            if isinstance(exc, ProtocolError):
                raise
            raise ProtocolError("Collection or evidence reference is invalid") from exc
        if message["kind"] == "objection":
            group = {
                "claim": "claims", "argument": "arguments", "assumption": "assumptions",
                "objection": "objections", "evidence": "evidence",
            }[message["target_kind"]]
            if message["target_id"] not in assessment.get(group, {}):
                raise ProtocolError("Objection target is absent from the trusted assessment")
            allowed = (set(plan["evidence_ids"]) if group == "evidence"
                       else set(plan["dependencies"].get(group, [])))
            if message["target_id"] not in allowed:
                raise ProtocolError("Objection target is outside the selected claim closure")
        try:
            return self.kb.service.packet(message["assessment_id"], self.anchor.claim)
        except (KeyError, ValueError) as exc:
            raise ProtocolError("Trusted assessment packet cannot be resolved") from exc

    def validate(self, message: dict[str, Any], *, actor: str) -> dict[str, Any] | None:
        """Accept a payload and return its trusted packet; requests return None."""
        _validate_shape(message)
        if actor not in (self.requester, self.responder):
            raise ProtocolError("Runner actor is not authorised for this task")
        if actor != message["sender"]:
            raise ProtocolError("Payload sender differs from the authenticated runner actor")
        if message["sender"] == message["recipient"]:
            raise ProtocolError("A handoff requires distinct actors")
        if message["message_id"] in self._messages:
            raise ProtocolError("Duplicate message identifier")
        if message["task_id"] != self.anchor.task_id or message["scope"] != self.anchor.scope:
            raise ProtocolError("Payload differs from the anchored task scope")
        entry = self._check_anchor()
        previous = self._reply(message)
        packet = (None if message["kind"] == "assessment_request"
                  else self._assessment(message, entry, previous))
        self._messages[message["message_id"]] = copy.deepcopy(message)
        if previous is not None:
            self._answered.add(message["reply_to"])
        return packet
