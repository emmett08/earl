"""Responses transport and a durable conservative spending ledger."""
from __future__ import annotations

import json
import copy
import os
from pathlib import Path
import time
from typing import Protocol
import urllib.error
import urllib.request

from experiments.transfer_study.workspace import utc_now, write_json


class ExecutionStopped(RuntimeError):
    """Stop the run when credentials, model availability or money cannot support it."""


class Transport(Protocol):
    def send(self, payload: dict, timeout: int) -> dict: ...


class OpenAITransport:
    def __init__(self):
        self.key = os.environ.get("OPENAI_API_KEY")
        if not self.key:
            raise ExecutionStopped("OPENAI_API_KEY is absent; no live requests were sent")

    def send(self, payload: dict, timeout: int) -> dict:
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode(), method="POST",
            headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            # Never log authorization headers or echo arbitrary provider error bodies.
            if exc.code in (401, 403, 404, 429):
                raise ExecutionStopped(f"Provider HTTP {exc.code}; inspect access, model availability or quota") from exc
            raise RuntimeError(f"Provider HTTP {exc.code}") from exc


class BudgetedClient:
    """Record each attempted request before sending; failures retain their reservation."""

    def __init__(self, root: Path, plan: dict, transport: Transport):
        self.root, self.plan, self.transport = root, plan, transport
        self.records: list[dict] = []
        self.ledger = root / "calls.json"

    def request(self, profile: dict, messages: list[dict], tools: list[dict], session_id: str) -> dict:
        payload = {"model": profile["version"], "input": copy.deepcopy(messages), "store": False,
                   "max_output_tokens": self.plan["max_output_tokens"]}
        if profile["reasoning_effort"] is not None:
            payload["reasoning"] = {"effort": profile["reasoning_effort"]}
        if tools:
            payload.update(tools=tools, parallel_tool_calls=False)
        encoded = json.dumps(payload, ensure_ascii=False).encode()
        if len(encoded) > self.plan["max_request_bytes"]:
            raise ValueError("Request exceeds the declared byte limit")
        # UTF-8 bytes bound text token count conservatively; reserve another 4096
        # for API framing. Cached-input discounts are deliberately ignored.
        reserved = ((len(encoded) + 4096) * profile["input_per_million"] +
                    self.plan["max_output_tokens"] * profile["output_per_million"]) / 1e6
        if sum(row["charged_or_reserved_usd"] for row in self.records) + reserved > self.plan["budget_usd"]:
            raise ExecutionStopped("API budget exhausted before sending the next request")
        row = {"session_id": session_id, "started_at": utc_now().isoformat(),
               "request": payload, "reserved_usd": reserved, "charged_or_reserved_usd": reserved,
               "cost_estimate_usd": None, "status": "started"}
        self.records.append(row)
        write_json(self.ledger, self.records)
        start = time.monotonic()
        try:
            response = self.transport.send(payload, self.plan["request_timeout_seconds"])
            row["response"] = response
            usage = response.get("usage", {})
            if all(type(usage.get(key)) is int and usage[key] >= 0 for key in ("input_tokens", "output_tokens")):
                cost = (usage["input_tokens"] * profile["input_per_million"] +
                        usage["output_tokens"] * profile["output_per_million"]) / 1e6
                row.update(cost_estimate_usd=cost, charged_or_reserved_usd=cost)
                if cost > reserved:
                    raise ExecutionStopped("Provider usage exceeded the conservative reservation; stop and inspect billing")
            else:
                raise ValueError("Provider omitted complete usage; reservation retained")
            if response.get("model") != profile["version"]:
                raise ExecutionStopped("Provider reported a different model snapshot")
            if response.get("status") != "completed":
                raise ValueError(f"Provider result is {response.get('status')}; keep as an incomplete attempt")
            row["status"] = "completed"
            return response
        except Exception as exc:
            row["status"] = "failed"
            row["error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
            raise
        finally:
            row["elapsed_seconds"] = time.monotonic() - start
            write_json(self.ledger, self.records)
