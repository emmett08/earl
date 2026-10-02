"""Responses transport and a durable conservative spending ledger."""
from __future__ import annotations

import json
import copy
import os
from pathlib import Path
import time
import threading
from typing import Protocol
import urllib.error
import urllib.request

from experiments.transfer_study.workspace import utc_now
from .answers import response_format
from .journal import AttemptJournal


from .execution import ExecutionStopped, ExecutionControl


class ProviderResponseError(ValueError):
    """Retain text from a matched response that cannot continue model interaction."""

    def __init__(self, message: str, response: dict, *, attempt_status: str = 'failed',
                 stop_collection: bool = False):
        super().__init__(message)
        self.response = response
        self.attempt_status = attempt_status
        self.stop_collection = stop_collection


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

    def __init__(self, root: Path, plan: dict, transport: Transport, *, control: ExecutionControl | None = None):
        self.root, self.plan, self.transport = root, plan, transport
        self.journal = AttemptJournal(root)
        self.journal.prepare_append()
        self.records: list[dict] = self.journal.read()
        self.control = control
        self._lock = threading.RLock()
        self._spent = sum(row["charged_or_reserved_usd"] for row in self.records)

    def finish(self) -> None:
        with self._lock:
            self.journal.finish(self.records)

    def receipts(self, session_id: str, after: int = 0) -> list[int]:
        with self._lock:
            return [r["attempt"] for r in self.records[after:] if r["session_id"] == session_id]

    def request(self, profile: dict, messages: list[dict], tools: list[dict], session_id: str, *,
                response_mode: str | None = None) -> dict:
        payload = {"model": profile["version"], "input": copy.deepcopy(messages), "store": False,
                   "max_output_tokens": self.plan["max_output_tokens"]}
        if profile["reasoning_effort"] is not None:
            payload["reasoning"] = {"effort": profile["reasoning_effort"]}
            payload["include"] = ["reasoning.encrypted_content"]
        mode = response_mode or self.plan['response_mode']
        structured = response_format(mode).provider_format
        if structured is not None:
            if not profile.get('supports_structured_output', False):
                raise ValueError('Selected provider/model does not declare schema-output support')
            payload['text'] = {'format': structured}
        if tools:
            payload.update(tools=tools, parallel_tool_calls=False)
        encoded = json.dumps(payload, ensure_ascii=False).encode()
        if len(encoded) > self.plan["max_request_bytes"]:
            raise ValueError("Request exceeds the declared byte limit")
        # UTF-8 bytes bound text token count conservatively; reserve another 4096
        # for API framing. Cached-input discounts are deliberately ignored.
        reserved = ((len(encoded) + 4096) * profile["input_per_million"] +
                    self.plan["max_output_tokens"] * profile["output_per_million"]) / 1e6
        with self._lock:
            timeout = min(self.plan["request_timeout_seconds"], self.control.remaining()) if self.control else self.plan["request_timeout_seconds"]
            if self._spent + reserved > self.plan["budget_usd"]:
                raise ExecutionStopped("API budget exhausted before sending the next request")
            row = {"attempt": len(self.records), "session_id": session_id, "started_at": utc_now().isoformat(),
                   "request": payload, "reserved_usd": reserved, "charged_or_reserved_usd": reserved,
                   "cost_estimate_usd": None, "status": "started"}
            self.records.append(row)
            self._spent += reserved
            self.journal.append({"event": "started", **row})
        start = time.monotonic()
        try:
            response = self.transport.send(payload, timeout)
            row["response"] = response
            if not isinstance(response, dict):
                raise ValueError('Provider response is not an object')
            row['provider_status'] = response.get('status')
            usage = response.get("usage", {})
            usage_valid = isinstance(usage, dict) and all(
                type(usage.get(key)) is int and usage[key] >= 0 for key in ("input_tokens", "output_tokens"))
            if usage_valid:
                cost = (usage["input_tokens"] * profile["input_per_million"] +
                        usage["output_tokens"] * profile["output_per_million"]) / 1e6
                with self._lock:
                    self._spent += cost - row["charged_or_reserved_usd"]
                    row.update(cost_estimate_usd=cost, charged_or_reserved_usd=cost)
                if cost > reserved:
                    raise ExecutionStopped("Provider usage exceeded the conservative reservation; stop and inspect billing")
            if response.get("model") != profile["version"]:
                raise ExecutionStopped("Provider reported a different model snapshot")
            if not usage_valid:
                raise ProviderResponseError("Provider omitted complete usage; reservation retained", response,
                                            stop_collection=True)
            if response.get("status") != "completed":
                raise ProviderResponseError(f"Provider result is {response.get('status')}; retain any answer text",
                                            response, attempt_status='incomplete')
            output = response.get('output')
            if not isinstance(output, list) or any(not isinstance(item, dict) for item in output):
                raise ProviderResponseError('Provider output must be a list of objects', response)
            row["status"] = "completed"
            return response
        except Exception as exc:
            if self.control and (isinstance(exc, ExecutionStopped) or
                                 isinstance(exc, ProviderResponseError) and exc.stop_collection):
                self.control.stop(str(exc))
            row["status"] = exc.attempt_status if isinstance(exc, ProviderResponseError) else "failed"
            row["error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
            raise
        finally:
            row["elapsed_seconds"] = time.monotonic() - start
            with self._lock:
                self.journal.append({"event": "finished", **{k: v for k, v in row.items() if k != "request"}})
