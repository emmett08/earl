"""Fresh-session model command protocol and complete within-session transcripts."""

from __future__ import annotations

import json
import math
import subprocess
import time
from pathlib import Path
from typing import Any

from .workspace import StudyRun, read_json, utc_now, write_json


MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024


def _nonnegative(value: Any, label: str, *, integer: bool = False) -> None:
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or
            not math.isfinite(value) or value < 0 or (integer and type(value) is not int)):
        raise ValueError(f"{label} must be a non-negative {'integer' if integer else 'number'}")


class ModelGateway:
    """Call a configured model adapter without loading an earlier prompt session."""

    def __init__(self, run: StudyRun):
        self.run = run

    def invoke(self, session_id: str, prompt: str, *, context_path: Path | None = None) -> dict:
        packet = self.run.require_active(session_id)
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("A developer prompt is required")
        path = self.run.root / "calls" / f"{session_id}.json"
        history = read_json(path) if path.exists() else []
        if len(history) >= self.run.design.max_model_calls:
            raise ValueError("Session model-call budget exhausted, including failed attempts")
        completed = [call for call in history if "response" in call]
        if context_path is not None and completed:
            raise ValueError("EAL context is selected on the first model turn only")
        if completed:
            messages = list(completed[0]["request"]["messages"])
            for index, previous in enumerate(completed):
                if index:
                    messages.append({"role": "user", "content": previous["prompt"]})
                messages.append({"role": "assistant", "content": previous["response"]["content"]})
            messages.append({"role": "user", "content": prompt})
        elif context_path is not None:
            if packet["arm"] != "eal":
                raise ValueError("Registered EAL context belongs to an EAL session")
            candidate = Path(context_path).resolve()
            if not candidate.is_relative_to((self.run.root / "contexts").resolve()):
                raise ValueError("EAL context must be an artefact of this run")
            context = read_json(candidate)
            if context["session_id"] != session_id or context["prompt"] != prompt:
                raise ValueError("EAL context must match this session and prompt")
            messages = context["messages"]
        else:
            messages = [{"role": "user", "content": prompt}]
        model = self.run.design.models[packet["model_id"]]
        request = {"schema": "EAL/transfer-model-request/1",
                   "session_id": session_id, "model_id": model.identifier,
                   "model_version": model.version, "workspace": packet["workspace"],
                   "messages": messages}
        encoded = json.dumps(request, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(encoded) > MAX_REQUEST_BYTES:
            raise ValueError("Model request exceeds 1 MiB")
        start = time.monotonic()
        call = {"prompt": prompt, "request": request,
                "started_at": utc_now().isoformat(),
                "context_file": str(context_path) if context_path else None}
        try:
            result = subprocess.run(model.command, input=encoded, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    timeout=min(model.timeout_seconds, self.run.remaining_seconds(packet)),
                                    check=False)
            if result.returncode != 0:
                raise RuntimeError(f"Model adapter exited {result.returncode}: " +
                                   result.stderr[:4000].decode("utf-8", errors="replace"))
            if len(result.stdout) > MAX_RESPONSE_BYTES:
                raise ValueError("Model response exceeds 1 MiB")
            response = json.loads(result.stdout)
            self._validate_response(response, model.version)
            call["response"] = response
        except (OSError, subprocess.TimeoutExpired, RuntimeError, ValueError,
                json.JSONDecodeError) as exc:
            call["error"] = {"type": type(exc).__name__, "message": str(exc)[:4000]}
            raise
        finally:
            call["elapsed_seconds"] = time.monotonic() - start
            history.append(call)
            write_json(path, history)
        return call

    @staticmethod
    def _validate_response(response: Any, version: str) -> None:
        if (not isinstance(response, dict) or response.get("schema") != "EAL/transfer-model-response/1"
                or response.get("model_version") != version or
                not isinstance(response.get("content"), str)):
            raise ValueError("Model adapter returned an invalid or unpinned response")
        usage = response.get("usage")
        if not isinstance(usage, dict) or set(usage) != {"input_tokens", "output_tokens"}:
            raise ValueError("Model adapter must return both token counts")
        for key, value in usage.items():
            _nonnegative(value, key, integer=True)
        if "cost" in response:
            _nonnegative(response["cost"], "cost")
        if "tool_calls" in response:
            _nonnegative(response["tool_calls"], "tool_calls", integer=True)
        if "reported_model" in response and response["reported_model"] != version:
            raise ValueError("Provider reported a different model version")
