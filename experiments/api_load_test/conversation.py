"""Explicit operation guidance without changing the evidence or model decision."""

from __future__ import annotations

from copy import deepcopy
import json

import jsonschema

from .materials import ARMS, finish_schema


SCOPE_FIELDS = ("service", "build_id", "run_id", "concurrent_clients")
DECISION_FIELDS = ("status", "failed_checks", "unknown_checks")
CHECKED_ARMS = frozenset({"eal_mcp", "plain_validator"})


class ConversationError(ValueError):
    """A model operation conflicts with the conversation contract."""

    def __init__(self, message: str, fields: tuple[str, ...] = ()):
        super().__init__(message)
        self.fields = fields


def _scope(case: dict) -> dict:
    return {key: case["target"]["input"][key] for key in SCOPE_FIELDS}


def _template(operation: str, arguments: dict, native_tools: bool) -> dict:
    if native_tools:
        return {"name": operation, "arguments": arguments}
    return {"operation": operation, **arguments}


def _answer_contract(packet: dict | None, case: dict, arm: str, native_tools: bool = False) -> dict:
    if arm not in ARMS:
        raise ValueError(f"Unknown experimental arm: {arm}")
    if packet is None:
        name = "assess_load_test" if arm == "eal_mcp" else "inspect_report"
        return {
            "instruction": ("Call the named function with its arguments. " if native_tools else
                            "Emit one JSON object with an explicit operation field. ") +
                           "Inspect a report before finishing. Choose report_id from the catalogue.",
            "operation_template": _template(name, {}, native_tools),
            "missing_fields": ["report_id"],
        }
    arguments = {"metrics": deepcopy(packet["metrics"])}
    missing = []
    if arm in CHECKED_ARMS:
        arguments.update({key: deepcopy(packet[key]) for key in DECISION_FIELDS})
    else:
        missing = list(DECISION_FIELDS)
    return {
        "instruction": ("Call the named function with its arguments; do not put operation in the arguments. "
                        if native_tools else "Emit one JSON object with an explicit operation field. ") + (
            "Supply the argument fields listed in missing_fields. "
            "They are absent from the template, not unknown measurement results. "
            "The host binds report_id and scope below; if supplied they must match. "
            "Explanation is optional. Keep failed_checks and unknown_checks disjoint."
        ),
        "bound_context": {"report_id": packet["report_id"], "scope": _scope(case)},
        "finish_template": _template("finish", arguments, native_tools),
        "missing_fields": missing,
    }


def prepare_packet(packet: dict, case: dict, arm: str, *, native_tools: bool = False) -> dict:
    """Add a final-answer template using only the information this arm supplies.

    Measurement-only arms receive no status or check sets. The source packet is
    left unchanged so the reference comparison still checks the actual tool.
    """
    if arm not in CHECKED_ARMS and any(key in packet for key in DECISION_FIELDS):
        raise ValueError("Measurement-only packet contains checked decision fields")
    prepared = deepcopy(packet)
    prepared["answer_contract"] = _answer_contract(packet, case, arm, native_tools)
    return prepared


def finish_answer(operation: dict, packet: dict | None, case: dict) -> dict:
    """Validate an explicit finish and bind its previously inspected context."""
    jsonschema.validate(operation, finish_schema())
    if packet is None:
        raise ConversationError("Inspect a report before finishing.", ("report_id",))
    expected = {"report_id": packet["report_id"], "scope": _scope(case)}
    conflicts = tuple(key for key, value in expected.items() if key in operation and operation[key] != value)
    if conflicts:
        raise ConversationError(
            "Supplied context conflicts with the most recently inspected report or requested scope.", conflicts)
    answer = deepcopy({key: value for key, value in operation.items() if key != "operation"})
    answer.update(expected)
    answer.setdefault("explanation", "")
    return answer


def repair_feedback(exc: Exception, advertised: list[dict], packet: dict | None,
                    case: dict, arm: str, operation: object = None, *, native_tools: bool = False) -> dict:
    """Explain an operation error without converting it into an evidence result."""
    fields = []
    if isinstance(exc, jsonschema.ValidationError):
        prefix = ".".join(str(item) for item in exc.absolute_path)
        if exc.validator == "required" and isinstance(exc.instance, dict):
            fields = [f"{prefix}.{key}" if prefix else key
                      for key in exc.validator_value if key not in exc.instance]
            message = "Missing required fields: " + ", ".join(fields) + "."
        else:
            fields = [prefix or "operation"]
            message = f"Invalid field {fields[0]}: {exc.message[:240]}"
    elif isinstance(exc, ConversationError):
        fields, message = list(exc.fields), str(exc)
    elif isinstance(exc, json.JSONDecodeError):
        message = "Return one valid JSON object, without Markdown or extra text."
    elif isinstance(operation, dict) and "operation" not in operation:
        fields = ["operation"]
        message = "Missing operation field. Use an explicit advertised operation; a decision object alone does not finish."
    elif isinstance(operation, dict) and operation.get("operation") not in {
            item["operation"] for item in advertised}:
        fields = ["operation"]
        message = "Unknown operation. Choose one of: " + ", ".join(item["operation"] for item in advertised) + "."
    else:
        message = str(exc)[:240] or "The operation does not match its advertised schema."
    return {
        "error": "operation_protocol",
        "message": message,
        "fields": fields,
        "evidence_changed": False,
        "instruction": (
            "This error concerns your operation, not the report or measurements. "
            "The previous evidence remains unchanged. Correct the operation; do not replace "
            "measured values with null or change check outcomes because of this error."
        ),
        "answer_contract": _answer_contract(packet, case, arm, native_tools),
    }
