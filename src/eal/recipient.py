"""Bounded model interaction over an already reviewed, launcher-bound task.

The provider sees an engineering question and a host-checked claim packet. It
may ask for the addressed explanation or write prose. The original question,
case, claim, source and final status remain in the trusted MCP host.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import time
from typing import Any

from jsonschema import Draft202012Validator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .providers import ModelResponse, ProviderError, TextProvider, response_cost
from .runtime import strict_json


_TOOLS = frozenset({"eal_bound_task", "eal_task_candidates", "eal_assess_bound_task",
                    "eal_explain_bound_task", "eal_finish_bound_task"})
_REQUIRED = _TOOLS - {"eal_task_candidates"}
_OPERATIONS = [
    {"operation": "answer", "description": "Write an explanation of the host-checked result; your text cannot change its status.",
     "input_schema": {"type": "object", "additionalProperties": False,
                      "properties": {"operation": {"const": "answer"},
                                     "text": {"type": "string", "minLength": 1, "maxLength": 16384}},
                      "required": ["operation", "text"]}},
    {"operation": "explain", "description": "Retrieve the addressed claim's argument and evidence trace once.",
     "input_schema": {"type": "object", "additionalProperties": False,
                      "properties": {"operation": {"const": "explain"}},
                      "required": ["operation"]}},
    {"operation": "stop", "description": "Abstain when the checked result is inadequate for the question.",
     "input_schema": {"type": "object", "additionalProperties": False,
                      "properties": {"operation": {"const": "stop"},
                                     "reason": {"type": "string", "minLength": 1, "maxLength": 1024}},
                      "required": ["operation", "reason"]}},
]


@dataclass(frozen=True)
class RecipientBudget:
    max_model_turns: int = 3
    max_repairs: int = 1
    max_tool_calls: int = 5
    max_total_tokens: int = 16_384
    max_output_tokens: int = 2048
    max_prompt_bytes: int = 65_536
    max_response_bytes: int = 16_384
    max_elapsed_seconds: float = 120.0
    max_model_cost_usd: float | None = None

    def __post_init__(self) -> None:
        for name in ("max_model_turns", "max_tool_calls", "max_total_tokens",
                     "max_output_tokens", "max_prompt_bytes", "max_response_bytes"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.max_tool_calls < 3:
            raise ValueError("The recipient needs discovery, assessment and finalisation calls")
        if type(self.max_repairs) is not int or self.max_repairs < 0:
            raise ValueError("max_repairs must be a non-negative integer")
        for name in ("max_elapsed_seconds", "max_model_cost_usd"):
            value = getattr(self, name)
            if value is None and name == "max_model_cost_usd":
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite")


class _Stop(Exception):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _usage(attempts: list[dict], identity: dict) -> dict:
    complete = all(a["input_tokens"] is not None and a["output_tokens"] is not None for a in attempts)
    prices = all(a["model_cost_usd"] is not None for a in attempts)
    input_tokens = sum(a["input_tokens"] or 0 for a in attempts)
    output_tokens = sum(a["output_tokens"] or 0 for a in attempts)
    known_cost = sum(a["model_cost_usd"] or 0 for a in attempts)
    return {"input_tokens": input_tokens if complete else None,
            "output_tokens": output_tokens if complete else None,
            "total_tokens": input_tokens + output_tokens if complete else None,
            "token_usage_complete": complete, "known_input_tokens": input_tokens,
            "known_output_tokens": output_tokens,
            "model_cost_usd": known_cost if prices else None,
            "known_model_cost_usd": known_cost,
            "model_cost_complete": prices,
            "cost_basis": "configured_token_rates",
            "tool_cost_usd": None, "total_cost_usd": None}


def _request(text: str) -> dict:
    value = strict_json(text)
    if not isinstance(value, dict) or not isinstance(value.get("operation"), str):
        raise ValueError("Return one JSON operation object")
    schema = next((entry["input_schema"] for entry in _OPERATIONS
                   if entry["operation"] == value["operation"]), None)
    if schema is None:
        raise ValueError("Unknown recipient operation")
    errors = list(Draft202012Validator(schema).iter_errors(value))
    if errors:
        raise ValueError("Recipient operation rejected: " + errors[0].message)
    return value


async def run_reviewed_recipient(question: str, provider: TextProvider,
                                 server: StdioServerParameters, *,
                                 budget: RecipientBudget = RecipientBudget(),
                                 interaction_mode: str = "text") -> dict[str, Any]:
    """Answer one exact reviewed task through a real recipient-only MCP server.

    The trusted launcher must pass the same original question to this function
    and its MCP server. The server's bound-task digest is compared before any
    assessment or model call. Model text can neither change the selected task
    nor supply an assessment ID. The final packet is retrieved after prose.
    """
    if not isinstance(question, str) or not question.strip() or not 1 <= len(question.encode("utf-8")) <= 4096:
        raise ValueError("question must contain one to 4096 UTF-8 bytes")
    if interaction_mode not in {"text", "native"}:
        raise ValueError("interaction_mode must be text or native")
    identity = provider.identity()
    _json(identity)
    native = interaction_mode == "native"
    report: dict[str, Any] = {
        "schema": "eal2-reviewed-recipient/1", "status": "incomplete", "stop_reason": "not_started",
        "interaction_mode": interaction_mode, "provider": identity, "question": question,
        "question_sha256": hashlib.sha256(question.encode("utf-8")).hexdigest(),
        "budget": asdict(budget), "attempts": [], "tool_calls": [], "repairs": 0,
        "budget_semantics": {"turns_tools_bytes_elapsed": "pre_call_limits",
                             "tokens_and_model_cost": "post_response_stop_thresholds_may_overshoot"},
        "bound_task": None, "candidates": None, "assessment": None,
        "explanation": None, "checked_answer": None, "recipient_output_unverified": None,
    }
    started = time.monotonic()
    replay_handles: list[str] = []

    def finish(reason: str) -> dict[str, Any]:
        report["stop_reason"] = reason
        report["usage"] = _usage(report["attempts"], identity)
        report["latency_seconds"] = time.monotonic() - started
        if "conversation" in report:
            report["conversation"] = [
                {key: value for key, value in message.items()
                 if key != "_responses_replay_handle"}
                for message in report["conversation"]]
        discard = getattr(provider, "discard_replay_handles", None)
        if callable(discard):
            discard(replay_handles)
        return report

    if native and (not identity.get("capabilities", {}).get("native_tools")
                   or not callable(getattr(provider, "complete_request", None))):
        return finish("native_tool_capability_unavailable")
    if budget.max_model_cost_usd is not None and not {
            "input_usd_per_million", "output_usd_per_million"
    } <= identity.get("pricing", {}).keys():
        return finish("cost_budget_unverifiable")

    try:
        async with asyncio.timeout(budget.max_elapsed_seconds):
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    hello = await session.initialize()
                    report["protocol_version"] = hello.protocolVersion
                    tools = (await session.list_tools()).tools
                    schemas = {tool.name: tool.inputSchema for tool in tools}
                    # A shared operator or legacy recipient endpoint can disclose
                    # source or bypass applicability. Refuse it before assessment.
                    if not _REQUIRED <= schemas.keys() or set(schemas) - _TOOLS:
                        raise _Stop("dedicated_reviewed_endpoint_required")
                    report["discovered_tools"] = sorted(schemas)

                    async def call(name: str, arguments: dict) -> dict:
                        if len(report["tool_calls"]) >= budget.max_tool_calls:
                            raise _Stop("tool_call_budget_exhausted")
                        if name not in schemas:
                            raise _Stop("required_mcp_operation_unavailable")
                        errors = list(Draft202012Validator(schemas[name]).iter_errors(arguments))
                        if errors:
                            raise _Stop("discovered_mcp_schema_rejected_host_request")
                        event = {"tool": name, "arguments": arguments, "status": "pending"}
                        report["tool_calls"].append(event)
                        began = time.monotonic()
                        try:
                            response = await session.call_tool(name, arguments=arguments)
                            value = response.structuredContent
                            if response.isError or not isinstance(value, dict):
                                event.update(status="error", is_error=bool(response.isError))
                                raise _Stop("reviewed_mcp_tool_failed")
                            event.update(status="ok", is_error=False, result=value)
                            return value
                        finally:
                            event["latency_seconds"] = time.monotonic() - began

                    bound = await call("eal_bound_task", {})
                    if (bound.get("question_sha256") != report["question_sha256"]
                            or not all(isinstance(bound.get(key), str) and bound[key]
                                       for key in ("task_id", "family_id", "artifact_id", "claim",
                                                   "review_contract_sha256"))):
                        raise _Stop("bound_question_or_review_mismatch")
                    report["bound_task"] = bound
                    # Preserve a finalisation call even if the model requests a trace.
                    if "eal_task_candidates" in schemas and budget.max_tool_calls >= 4:
                        try:
                            candidates = await call("eal_task_candidates", {})
                            if (candidates.get("meaning") != "suggestions_only"
                                    or not isinstance(candidates.get("candidates"), list)):
                                raise _Stop("candidate_contract_mismatch")
                            report["candidates"] = candidates
                        except _Stop as exc:
                            if str(exc) not in {"reviewed_mcp_tool_failed", "candidate_contract_mismatch"}:
                                raise
                            # Retrieval is advisory. An exact reviewed task can
                            # still be assessed when the suggestion index fails.
                            report["candidate_error"] = str(exc)
                    packet = await call("eal_assess_bound_task", {})
                    if (packet.get("artifact_id") != bound["artifact_id"]
                            or packet.get("claim") != bound["claim"]
                            or packet.get("verification") != "server_assessment"
                            or packet.get("status") not in {"supported", "contested", "unsupported", "out_of_scope"}
                            or not isinstance(packet.get("assessment_id"), str)
                            or not packet["assessment_id"]):
                        raise _Stop("bound_assessment_identity_mismatch")
                    report["assessment"] = packet
                    assessment_id = packet["assessment_id"]
                    system = ("Interpret a reviewed EAL/2 claim assessment for the original question. "
                              "The host owns the status; your prose remains unverified. "
                              "Return exactly one JSON object: answer with text, explain to inspect the "
                              "addressed trace, or stop with a reason. You cannot select another task, "
                              "claim, source, tool, context or assessment ID.")
                    messages: list[dict[str, Any]] = [
                        {"role": "system", "content": system},
                        {"role": "user", "content": _json({
                            "original_question": question, "reviewed_route": bound,
                            "candidate_suggestions": report["candidates"],
                            "checked_assessment": packet,
                            "operations": _OPERATIONS,
                        })},
                    ]
                    report["conversation"] = messages
                    explained = False
                    model_reason = "model_turn_budget_exhausted"
                    for turn in range(budget.max_model_turns):
                        usage = _usage(report["attempts"], identity)
                        if report["attempts"] and not usage["token_usage_complete"]:
                            model_reason = "token_usage_unavailable"
                            break
                        if usage["known_input_tokens"] + usage["known_output_tokens"] >= budget.max_total_tokens:
                            model_reason = "token_budget_exhausted"
                            break
                        if budget.max_model_cost_usd is not None:
                            if not usage["model_cost_complete"]:
                                model_reason = "cost_budget_unverifiable"
                                break
                            if usage["known_model_cost_usd"] >= budget.max_model_cost_usd:
                                model_reason = "model_cost_budget_exhausted"
                                break
                        prompt = _json(messages)
                        if len(prompt.encode("utf-8")) > budget.max_prompt_bytes:
                            model_reason = "prompt_byte_budget_exhausted"
                            break
                        output_limit = min(budget.max_output_tokens,
                                           budget.max_total_tokens - usage["known_input_tokens"] - usage["known_output_tokens"])
                        attempt = {"index": turn + 1, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                                   "prompt_bytes": len(prompt.encode("utf-8")), "max_output_tokens": output_limit,
                                   "status": "pending", "input_tokens": None, "output_tokens": None,
                                   "model_cost_usd": None}
                        report["attempts"].append(attempt)
                        began = time.monotonic()
                        response: ModelResponse | None = None
                        try:
                            if callable(getattr(provider, "complete_request", None)):
                                response = await provider.complete_request(messages.copy(), output_limit,
                                                                           operations=_OPERATIONS, native_tools=native)
                            else:
                                response = await provider.complete(messages.copy(), output_limit)
                            if not isinstance(response, ModelResponse):
                                raise ProviderError("Provider returned no model response")
                            attempt["status"] = "received"
                        except ProviderError as exc:
                            response = exc.response
                            attempt.update(status="provider_error", error_type="ProviderError")
                        except asyncio.CancelledError:
                            attempt.update(status="cancelled", error_type="CancelledError")
                            raise
                        except Exception as exc:
                            attempt.update(status="provider_error", error_type=type(exc).__name__)
                        finally:
                            attempt["latency_seconds"] = time.monotonic() - began
                            if response is not None:
                                replay_handle = response.metadata.get("responses_replay_handle")
                                if isinstance(replay_handle, str):
                                    replay_handles.append(replay_handle)
                                attempt.update(input_tokens=response.input_tokens,
                                               output_tokens=response.output_tokens,
                                               response_model=response.model,
                                               model_cost_usd=response_cost(response, identity),
                                               metadata={key: value for key, value in response.metadata.items()
                                                         if key != "responses_replay_handle"})
                                data = response.text.encode("utf-8")
                                attempt.update(response_sha256=hashlib.sha256(data).hexdigest(),
                                               response_bytes=len(data))
                                if len(data) <= budget.max_response_bytes:
                                    attempt["text"] = response.text
                                else:
                                    attempt.update(status="response_too_large", error_type="ResponseLimit")
                        if attempt["status"] != "received":
                            model_reason = attempt["status"]
                            break
                        usage = _usage(report["attempts"], identity)
                        if usage["total_tokens"] is not None and usage["total_tokens"] > budget.max_total_tokens:
                            model_reason = "token_budget_exhausted"
                            break
                        if budget.max_model_cost_usd is not None and (
                                not usage["model_cost_complete"] or
                                usage["known_model_cost_usd"] > budget.max_model_cost_usd):
                            model_reason = ("cost_budget_unverifiable" if not usage["model_cost_complete"]
                                            else "model_cost_budget_exhausted")
                            break
                        native_call = response.metadata.get("native_tool_call") if native else None
                        if native and not isinstance(native_call, dict):
                            model_reason = "native_response_missing_tool_call"
                            break
                        if native_call:
                            assistant = {"role": "assistant", "content": None,
                                         "tool_calls": [native_call]}
                        else:
                            assistant = {"role": "assistant", "content": response.text}
                        # Only a provider that issued this opaque handle can
                        # replay its raw reasoning and response items. Other
                        # providers receive ordinary API message dictionaries.
                        if "responses_replay_handle" in response.metadata:
                            assistant["_responses_replay_handle"] = response.metadata[
                                "responses_replay_handle"]
                        messages.append(assistant)
                        try:
                            request = _request(response.text)
                            if request["operation"] == "explain" and explained:
                                raise ValueError("Explanation was already supplied")
                        except (ValueError, UnicodeError) as exc:
                            report["repairs"] += 1
                            if report["repairs"] > budget.max_repairs:
                                model_reason = "repair_budget_exhausted"
                                break
                            feedback = {"is_error": True, "error": str(exc),
                                        "repairs_remaining": budget.max_repairs - report["repairs"]}
                            if native_call:
                                messages.append({"role": "tool", "tool_call_id": native_call["id"],
                                                 "content": _json(feedback)})
                            else:
                                messages.append({"role": "user", "content": _json({"host_feedback": feedback})})
                            continue
                        if request["operation"] == "stop":
                            report["model_stop_reason"] = request["reason"]
                            model_reason = "model_stopped"
                            break
                        if request["operation"] == "answer":
                            report["recipient_output_unverified"] = request["text"]
                            model_reason = "completed"
                            break
                        if budget.max_tool_calls - len(report["tool_calls"]) <= 1:
                            model_reason = "explanation_tool_budget_exhausted"
                            break
                        explanation = await call("eal_explain_bound_task", {"assessment_id": assessment_id})
                        if explanation.get("packet") != packet:
                            raise _Stop("addressed_explanation_mismatch")
                        report["explanation"] = explanation
                        explained = True
                        feedback = {"is_error": False, "operation": "explain", "result": explanation}
                        if native_call:
                            messages.append({"role": "tool", "tool_call_id": native_call["id"],
                                             "content": _json(feedback)})
                        else:
                            messages.append({"role": "user", "content": _json({"host_feedback": feedback})})

                    # Re-open the stored issue under the same bound task after
                    # the model turn; its prose is never the source of status.
                    checked = await call("eal_finish_bound_task", {"assessment_id": assessment_id})
                    if checked != packet:
                        raise _Stop("host_final_status_mismatch")
                    report["checked_answer"] = checked
                    report["status"] = "completed" if model_reason == "completed" else "incomplete"
                    return finish(model_reason)
    except asyncio.CancelledError:
        discard = getattr(provider, "discard_replay_handles", None)
        if callable(discard):
            discard(replay_handles)
        raise
    except TimeoutError:
        return finish("elapsed_time_budget_exhausted")
    except _Stop as exc:
        return finish(str(exc))
    except BaseExceptionGroup as exc:
        def leaves(group: BaseExceptionGroup) -> list[BaseException]:
            return [leaf for child in group.exceptions
                    for leaf in (leaves(child) if isinstance(child, BaseExceptionGroup) else [child])]

        failures = leaves(exc)
        if len(failures) == 1 and isinstance(failures[0], _Stop):
            return finish(str(failures[0]))
        if failures and all(isinstance(item, TimeoutError) for item in failures):
            return finish("elapsed_time_budget_exhausted")
        report["error_type"] = "ExceptionGroup"
        return finish("recipient_transport_failed")
    except Exception as exc:
        # Transport and provider adapters can include credentials in exception
        # text. Retain only a type on uncontrolled boundaries.
        report["error_type"] = type(exc).__name__
        return finish("recipient_transport_failed")
