"""Frozen, source-linked finite-state decisions after v4 coding sequences.

The agent sees the same state, action menu and argument propositions in P1
and P2. P2 additionally sees the EAL/2 notation for those propositions.
Neither packet reveals the action oracle. Each fresh probe is separate from
the mutable coding lineage; its state is a labelled public synthetic fixture.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

if __package__:
    from . import packets
else:
    import packets


HERE = Path(__file__).resolve().parent
CASES = HERE / "decision_cases" / "cases.json"
EAL = HERE / "decision-premise.eal"
SYSTEMS = {"fulfilment", "entitlement", "reservation"}
CASE_IDS = {"clean", "defeated"}
ALLOWED = {
    "fulfilment": ("RECONCILE_COMPLETE", "HOLD_UNRESOLVED"),
    "entitlement": ("RETRY_SAME_KEY", "RECONCILE_NO_REISSUE"),
    "reservation": ("MOVE_CURRENT_BUNDLE", "REJECT_NO_EFFECT"),
}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _case(source: Path, system: str, case_id: str,
          evidence_schema: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
    if system not in SYSTEMS or case_id not in CASE_IDS or not isinstance(evidence_schema, dict):
        raise ValueError("unknown decision system/case or invalid evidence schema")
    root = HERE / "decision_cases" / system / case_id
    if source.resolve() != (root / "source").resolve() or source.is_symlink():
        raise ValueError("decision source must be the registered host-only case fixture")
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    if cases.get("schema") != "architecture-v4-decision-cases/1":
        raise ValueError("wrong decision-case manifest schema")
    definition = cases["systems"][system][case_id]
    if evidence_schema and evidence_schema != definition.get("evidence_schema"):
        raise ValueError("decision evidence schema differs from registered case")
    manifest = packets._source_manifest(source)
    if manifest["tree_sha256"] != definition["source_tree_sha256"]:
        raise ValueError("decision case source differs from its frozen identity")
    state_path = root / "state.json"
    raw = state_path.read_bytes()
    if _digest(raw) != definition["state_sha256"]:
        raise ValueError("decision state differs from its frozen identity")
    state = json.loads(raw)
    if (state.get("schema") != "architecture-v4-decision-state/1" or
            state.get("system") != system or state.get("case_id") != case_id):
        raise ValueError("decision state identity differs")
    brief_path = HERE.parent / "systems" / system / "features" / "D.md"
    if _digest(brief_path.read_bytes()) != definition["brief_sha256"]:
        raise ValueError("public D brief differs from frozen case identity")
    return definition, state, manifest["tree_sha256"]


def _derive(system: str, state: dict[str, Any]) -> tuple[bool, bool, str, str]:
    """Typed finite-state predicate, with an independent action decision."""
    if system == "fulfilment":
        request, provider = state.get("request"), state.get("provider")
        if (not isinstance(request, dict) or not isinstance(provider, dict)
                or not isinstance(request.get("key"), str)
                or not request["key"] or provider.get("status") not in {"applied", "unknown"}
                or provider.get("key") != request["key"]):
            raise ValueError("invalid refund-status case record")
        eligible = request.get("same_request") is True
        if not eligible:
            raise ValueError("decision probe requires the same stable request")
        effects = provider.get("recorded_refunds")
        if not isinstance(effects, list) or any(not isinstance(item, dict)
                                               or item.get("key") != request["key"]
                                               for item in effects):
            raise ValueError("malformed refund effect record")
        if provider["status"] == "applied" and len(effects) != 1:
            raise ValueError("applied status requires exactly one recorded refund in this case")
        blocker = provider["status"] == "unknown"
        oracle = "HOLD_UNRESOLVED" if blocker else "RECONCILE_COMPLETE"
        explanation = ("The same stable return request is eligible for reconciliation. "
                       "An unknown provider status challenges completion; no new refund or final event follows until status resolves."
                       if blocker else
                       "The same stable request has a recorded applied refund. Complete the remaining transitions with its original key, without another refund.")
        return eligible, blocker, oracle, explanation
    if system == "entitlement":
        request, lookup = state.get("request"), state.get("lookup")
        if (not isinstance(request, dict) or not isinstance(lookup, list)
                or not all(isinstance(request.get(key), str) and request[key]
                           for key in ("account_id", "user_id", "request_id"))
                or state.get("timeout_phase") not in {"before_effect", "after_effect"}):
            raise ValueError("invalid issuer-status case record")
        if len(lookup) > 1 or any(not isinstance(receipt, dict)
                                  or receipt.get("account_id") != request["account_id"]
                                  or receipt.get("request_id") != request["request_id"]
                                  or receipt.get("user_id") != request["user_id"]
                                  or not isinstance(receipt.get("token_id"), str)
                                  for receipt in lookup):
            raise ValueError("invalid same-key issuer lookup record")
        if state["timeout_phase"] == "before_effect" and lookup:
            raise ValueError("pre-effect timeout cannot have a matching committed receipt")
        if state["timeout_phase"] == "after_effect" and len(lookup) != 1:
            raise ValueError("after-effect fixture requires one matching receipt")
        eligible, blocker = True, bool(lookup)
        oracle = "RECONCILE_NO_REISSUE" if blocker else "RETRY_SAME_KEY"
        explanation = ("The stable request can be retried after a known pre-effect timeout and an empty authoritative lookup."
                       if not blocker else
                       "A matching committed receipt challenges retry. Return or record it without another issue call.")
        return eligible, blocker, oracle, explanation
    request, current = state.get("request"), state.get("current_bookings")
    if (not isinstance(request, dict) or not isinstance(current, list)
            or not all(isinstance(request.get(key), str) and request[key]
                       for key in ("customer_id", "bundle_request_id", "move_request_id"))
            or not isinstance(request.get("own_booking_ids"), list)
            or not request["own_booking_ids"]
            or not all(isinstance(value, str) and value for value in request["own_booking_ids"])
            or len(set(request["own_booking_ids"])) != len(request["own_booking_ids"])
            or type(request.get("new_start")) is not int
            or type(request.get("new_end")) is not int
            or request["new_start"] >= request["new_end"]):
        raise ValueError("invalid current-calendar case record")
    if any(not isinstance(row, dict) or not isinstance(row.get("booking_id"), str)
           or not isinstance(row.get("room_id"), str)
           or type(row.get("start")) is not int or type(row.get("end")) is not int
           or type(row.get("active")) is not bool
           or not isinstance(row.get("customer_id"), str) for row in current):
        raise ValueError("malformed current booking row")
    own = set(request["own_booking_ids"])
    matches = [row for row in current if row["booking_id"] in own]
    if len(matches) != len(own) or any(not row["active"] or row["customer_id"] != request["customer_id"]
                                      for row in matches):
        raise ValueError("probe requires currently active owned bundle bookings")
    target_rooms = {row["room_id"] for row in matches}
    blocker = any(row["booking_id"] not in own and row["active"]
                  and row["room_id"] in target_rooms
                  and request["new_start"] < row["end"]
                  and row["start"] < request["new_end"] for row in current)
    eligible = True
    oracle = "REJECT_NO_EFFECT" if blocker else "MOVE_CURRENT_BUNDLE"
    explanation = ("The current active booking index contains another reservation that overlaps the requested destination. "
                   "The older bundle receipt does not cancel that conflict."
                   if blocker else
                   "The current active index has no other-booking conflict after excluding exactly the owned bundle IDs; a move may proceed.")
    return eligible, blocker, oracle, explanation


def _formal(eligible: bool, blocker: bool, context: dict[str, Any]) -> dict[str, Any]:
    from eal.aspic_compiler import compile_eal_aspic
    from eal.evaluator import canonical_digest, evaluate
    from eal.parser import parse

    source = EAL.read_text(encoding="utf-8")
    program = parse(source)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    binding = _digest(_canonical({"case_probe_sha256": _digest(Path(__file__).read_bytes()),
                                   "source_tree_sha256": context["source_tree_sha256"]}))
    value = {"eligible": eligible, "blocker": blocker}
    records = {name: packets._record(program, name, value, context, now, binding)
               for name in program.evidence}
    authored = evaluate(program, records, now=now, context=context)
    if authored["valid"] is not True:
        raise ValueError("decision EAL source failed validation")
    compiled = compile_eal_aspic(source, records, goal="provisional_action",
                                 now=now, context=context).to_dict()
    if compiled["claim_status"] != authored["claims"]["provisional_action"]["status"]:
        raise ValueError("decision EAL and ASPIC+ statuses disagree")
    return {"status": compiled["claim_status"],
            "grounded_status": compiled["formal"]["grounded_status"],
            "routes": [{"id": name, "status": row["status"]}
                       for name, row in sorted(compiled["routes"].items())],
            "objections": [{"id": name, "status": row["status"]}
                           for name, row in sorted(authored["objections"].items())],
            "defeats": [{"kind": row["kind"], "attacker": row["attacker"],
                         "target": row["target"], "subargument": row["subargument"]}
                        for row in compiled["formal"]["defeats"]],
            "evidence_availability": {name: {"available": row["available"],
                                             "issues": row["availability_issues"]}
                                      for name, row in sorted(compiled["source_map"]["evidence"].items())},
            "eal_source_sha256": program.source_digest,
            "snapshot_digest": compiled["snapshot_digest"],
            "evidence_record_digest": canonical_digest(records),
            "evaluated_at": now}


def generate(source: Path, system: str, case_id: str, arm: str,
             evidence_schema: dict[str, Any]) -> dict[str, Any]:
    """Return one arm's read-only decision prompt and a host-only action oracle."""
    if arm not in {"P0", "P1", "P2"}:
        raise ValueError("unknown decision-probe arm")
    definition, state, source_sha = _case(Path(source), system, case_id, evidence_schema)
    eligible, blocker, expected, explanation = _derive(system, state)
    if expected != definition["expected_action"] or tuple(definition["allowed_actions"]) != ALLOWED[system]:
        raise ValueError("independent finite-state action differs from frozen oracle")
    context = {"study": "architecture-extension-v4-decision-probe",
               "system": system, "case_id": case_id,
               "source_tree_sha256": source_sha,
               "state_sha256": definition["state_sha256"]}
    expected_status = "contested" if blocker else "supported"
    formal = _formal(eligible, blocker, context) if arm != "P0" else None
    if formal is not None and formal["status"] != expected_status:
        raise ValueError("formal decision premise differs from typed state")
    argument_content = ({key: formal[key] for key in (
        "status", "grounded_status", "routes", "objections",
        "defeats", "evidence_availability")} if formal is not None else {})
    visible_state = {key: value for key, value in state.items() if key != "case_id"}
    shared = {"system": system,
              "source_tree_sha256": source_sha,
              "state_sha256": definition["state_sha256"],
              "brief_sha256": definition["brief_sha256"],
              "state": visible_state, "guidance": definition["guidance"],
              "provisional_action": definition["provisional_action"],
              "plain_conclusion": explanation,
              "status": expected_status,
              "argument_content": argument_content,
              "allowed_actions": list(ALLOWED[system])}
    digest = _digest(_canonical(shared))
    common_view = {key: value for key, value in shared.items() if key != "argument_content"}
    common = json.dumps(common_view, ensure_ascii=False, sort_keys=True,
                        separators=(",", ":"))
    instruction = ('\nChoose exactly one allowed action for the stated current state. '
                   'Return only one JSON object on the final line with exactly the key "action"; '
                   'for example {"action":"ACTION_NAME"}. Do not edit files.\n')
    if arm == "P0":
        unassisted = dict(shared)
        for key in ("plain_conclusion", "status", "argument_content", "guidance", "provisional_action"):
            unassisted.pop(key)
        prompt = json.dumps(unassisted, indent=2, ensure_ascii=False, sort_keys=True) + instruction
    elif arm == "P1":
        assert formal is not None
        plain = ("eligible_request requires a matching stable request in this finite state. "
                 "blocking_state requires the explicitly recorded defeating condition. "
                 "eligible_route supports provisional_action using the first observation; "
                 "defeating_condition targets that route when the second is available. "
                 "Both observations are case_probe version 1 inspections in the public_case "
                 "environment, with a 3600-second freshness bound. state_inspection uses "
                 "structured/1 reasoning and says eligibility is conditional on the "
                 "absence of a defeating observation. Unavailable evidence does not assert "
                 "the opposite state. The current scoped claim and grounded result are "
                 "shown above. This source-linked synthetic case is a decision exercise, "
                 "not verified production behaviour.")
        prompt = common + "\n" + packets.inference_status_text(formal, formal["status"]) + "\n" + plain + instruction
    else:
        assert formal is not None
        prompt = (common + "\n" + packets.inference_status_text(formal, formal["status"]) + "\n"
                  + packets.formal_excerpt(EAL) + instruction)
    result = {"schema": "architecture-v4-decision-packet/1", "system": system,
              "case_id": case_id, "arm": arm, "prompt_text": prompt,
              "expected_action": expected, "allowed_actions": list(ALLOWED[system]),
              "shared_material_digest": digest, "source_tree_sha256": source_sha,
              "state_sha256": definition["state_sha256"],
              "facts": visible_state, "guidance": definition["guidance"],
              "status": expected_status, "selected_action": expected,
              "argument_content": shared["argument_content"],
              "evidence_provenance": ({key: formal[key] for key in (
                  "eal_source_sha256", "snapshot_digest", "evidence_record_digest", "evaluated_at")}
                  if formal is not None else None)}
    if arm == "P2":
        result["formal"] = formal
    if packets._source_manifest(Path(source))["tree_sha256"] != source_sha:
        raise ValueError("decision source changed during observation")
    return result


def score(response_text: str, expected_action: str,
          allowed_actions: list[str] | tuple[str, ...] | None = None) -> dict[str, Any]:
    """Strictly grade a retained final action; malformed output stays invalid."""
    if not isinstance(response_text, str) or not isinstance(expected_action, str):
        raise ValueError("decision response and expected action must be text")
    allowed = set(allowed_actions or {action for actions in ALLOWED.values() for action in actions})
    if expected_action not in allowed:
        raise ValueError("expected action is outside the declared menu")
    lines = [line.strip() for line in response_text.splitlines() if line.strip()]
    candidate = lines[-1] if lines else ""
    try:
        decision = json.loads(candidate)
    except json.JSONDecodeError:
        return {"status": "invalid", "selected_action": None, "correct": False,
                "reason": "final nonempty line is not JSON"}
    if not isinstance(decision, dict) or set(decision) != {"action"} or decision["action"] not in allowed:
        return {"status": "invalid", "selected_action": None, "correct": False,
                "reason": "decision is not exactly one allowed action"}
    selected = decision["action"]
    return {"status": "correct" if selected == expected_action else "incorrect",
            "selected_action": selected, "correct": selected == expected_action,
            "reason": "exact action enum match" if selected == expected_action else "different allowed action"}
