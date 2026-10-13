"""Bounded operator-configured commands for one independent worker execution.

Every invocation owns a fresh process group.  The coordinator must reserve its
call before invoking this adapter and durably retain the returned bytes before
admitting the response.  A command receipt is an operator assertion: accepting
one does not independently authenticate a provider or establish that a model
ran.  This adapter never retries an interrupted command.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import selectors
import subprocess
import time
from typing import Any

from ..command_process import supervised_command


_MODES = {"software_test", "provider", "actual_host_agent"}
_MAX_CONTEXT_BYTES = 4 * 1024 * 1024
_MAX_OUTPUT_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class WorkerResult:
    execution_id: str
    execution_mode: str
    raw_response: bytes
    evidence: dict[str, Any]
    response: dict[str, Any]


class WorkerInterrupted(RuntimeError):
    """Retain bounded partial output even when no response can be admitted."""

    def __init__(self, reason: str, *, execution_id: str, execution_mode: str,
                 raw_response: bytes, evidence: dict[str, Any]):
        # Exception text deliberately excludes argv, environment and stderr.
        super().__init__(f"Worker command failed: {reason}")
        self.reason = reason
        self.execution_id = execution_id
        self.execution_mode = execution_mode
        self.raw_response = raw_response
        self.evidence = evidence


def _strict_object(raw: bytes) -> dict[str, Any]:
    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("Nonfinite JSON number")

    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("Nonfinite JSON number")
        return result

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_fields,
                       parse_constant=reject_constant, parse_float=finite_float)
    if not isinstance(value, dict):
        raise ValueError("Worker response must be an object")
    return value


def _receipt(value: Any, call_id: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"execution_id", "model", "usage"}:
        raise ValueError("Live execution requires an external execution receipt")
    execution_id = value["execution_id"]
    if (not isinstance(execution_id, str) or not execution_id or len(execution_id) > 512
            or any(ord(character) < 32 for character in execution_id)
            or execution_id == call_id or execution_id.startswith("command:")):
        raise ValueError("Live execution requires an external execution identity")
    model = value["model"]
    if model is not None and (not isinstance(model, str) or not model or len(model) > 256
                              or any(ord(character) < 32 for character in model)):
        raise ValueError("Invalid model identity")
    usage = value["usage"]
    if usage is not None and (
        not isinstance(usage, dict)
        or set(usage) - {"input_tokens", "output_tokens", "total_tokens"}
        or any(type(count) is not int or count < 0 for count in usage.values())
    ):
        raise ValueError("Invalid usage receipt")
    return value


class CommandWorker:
    """Run a trusted argv without a shell or inherited environment secrets.

    Context is one JSON object on stdin; stdout is one final JSON object.  In
    software_test mode that object is the response itself.  Live modes require
    {"response": <object>, "execution": {"execution_id": <external id>,
    "model": <string or null>, "usage": <token counts or null>}}.  Supplied
    environment values are never copied into execution evidence.
    """

    def __init__(self, argv: Sequence[str], *, execution_mode: str,
                 timeout_seconds: int, max_output_bytes: int,
                 environment: Mapping[str, str] | None = None,
                 workspace: Path | str | None = None):
        if isinstance(argv, (str, bytes)) or not isinstance(argv, Sequence) or not argv:
            raise ValueError("argv must be a nonempty sequence of strings")
        if any(not isinstance(argument, str) or not argument or "\0" in argument
               for argument in argv):
            raise ValueError("argv must contain nonempty strings without NUL")
        if not isinstance(execution_mode, str) or execution_mode not in _MODES:
            raise ValueError("Unknown worker execution mode")
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 3600:
            raise ValueError("timeout_seconds must be an integer from 1 through 3600")
        if type(max_output_bytes) is not int or not 1 <= max_output_bytes <= _MAX_OUTPUT_BYTES:
            raise ValueError("max_output_bytes must be an integer from 1 through 16777216")
        if environment is not None and (
            not isinstance(environment, Mapping)
            or any(not isinstance(name, str) or not name or "=" in name or "\0" in name
                   or not isinstance(value, str) or "\0" in value
                   for name, value in environment.items())
        ):
            raise ValueError("environment must map valid variable names to string values")
        location = Path.cwd() if workspace is None else Path(workspace)
        location = location.resolve()
        if not location.is_dir():
            raise ValueError("Worker workspace must be an existing directory")
        self.argv = tuple(argv)
        self.execution_mode = execution_mode
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        self.environment = dict(environment or {})
        self.workspace = location

    def execute(self, context: dict[str, Any], call_id: str, remaining_seconds: int,
                *, should_stop: Callable[[], bool] | None = None) -> WorkerResult:
        if not isinstance(context, dict):
            raise ValueError("Worker context must be an object")
        if not isinstance(call_id, str) or re.fullmatch(r"[A-Za-z0-9_.:/-]{1,256}", call_id) is None:
            raise ValueError("call_id must be a bounded identifier")
        if type(remaining_seconds) is not int or remaining_seconds < 1:
            raise ValueError("remaining_seconds must be a positive integer")
        if should_stop is not None and not callable(should_stop):
            raise ValueError("should_stop must be callable")
        if os.name != "posix":
            raise RuntimeError("Command workers require a POSIX host")
        encoded = json.dumps(context, allow_nan=False, sort_keys=True,
                             ensure_ascii=False).encode("utf-8") + b"\n"
        if len(encoded) > _MAX_CONTEXT_BYTES:
            raise ValueError("Worker context exceeds its byte limit")
        started = time.monotonic()
        timeout = min(self.timeout_seconds, remaining_seconds)
        stdout, stderr = bytearray(), bytearray()
        evidence: dict[str, Any] = {
            "call_id": call_id, "supervisor_pid": None, "returncode": None,
            "model": None, "usage": None, "receipt_verification": None,
        }
        execution_id = f"command:{call_id}"
        failure = None
        try:
            if should_stop is not None and should_stop():
                failure = "cancelled"
        except Exception:
            failure = "supervisor_failure"
        if failure is None:
            try:
                with supervised_command(self.argv, workspace=self.workspace,
                                        environ=self.environment, timeout=timeout) as command:
                    process = command.process
                    evidence["supervisor_pid"] = process.pid
                    execution_id = f"command:{call_id}:{process.pid}"
                    deadline = started + timeout
                    try:
                        with selectors.DefaultSelector() as selector:
                            for stream, label in ((process.stdin, "stdin"),
                                                  (process.stdout, "stdout"),
                                                  (process.stderr, "stderr")):
                                os.set_blocking(stream.fileno(), False)
                                selector.register(stream, selectors.EVENT_WRITE if label == "stdin"
                                                  else selectors.EVENT_READ, label)
                            remaining_input = memoryview(encoded)
                            while selector.get_map():
                                if should_stop is not None and should_stop():
                                    failure = "cancelled"
                                    break
                                if time.monotonic() >= deadline:
                                    failure = "timeout"
                                    break
                                for key, _ in selector.select(min(0.05, max(0, deadline - time.monotonic()))):
                                    if key.data == "stdin":
                                        try:
                                            written = os.write(key.fd, remaining_input[:65536])
                                            remaining_input = remaining_input[written:]
                                        except BrokenPipeError:
                                            remaining_input = remaining_input[:0]
                                        if not remaining_input:
                                            selector.unregister(key.fileobj)
                                            key.fileobj.close()
                                        continue
                                    chunk = os.read(key.fd, 65536)
                                    if not chunk:
                                        selector.unregister(key.fileobj)
                                        key.fileobj.close()
                                        continue
                                    target = stdout if key.data == "stdout" else stderr
                                    available = self.max_output_bytes - len(stdout) - len(stderr)
                                    target.extend(chunk[:max(0, available)])
                                    if len(chunk) > available:
                                        failure = "output_limit"
                                        break
                                if failure:
                                    break
                        if failure:
                            process.terminate()
                        try:
                            process.wait(timeout=max(0.01, deadline - time.monotonic()))
                        except subprocess.TimeoutExpired:
                            failure = failure or "timeout"
                            process.terminate()
                            process.wait(timeout=5)
                        status = command.collector_status()
                        evidence["returncode"] = status.returncode
                        if status.timed_out:
                            failure = failure or "timeout"
                    except BaseException:
                        # The ownership pipe also cancels the collector if this
                        # application dies; never release it with live children.
                        if process.poll() is None:
                            process.terminate()
                        process.wait(timeout=5)
                        raise
            except OSError:
                # OS error strings may include credential-bearing argv paths.
                failure = failure or "start_failure"
            except Exception:
                # Supervisor errors and cancellation callbacks can carry
                # private inputs in their messages. Retain only their category.
                failure = failure or "supervisor_failure"
        evidence.update({
            "elapsed_ms": max(0, int((time.monotonic() - started) * 1000)),
            "stdout_bytes": len(stdout), "stderr_bytes": len(stderr),
            "output_truncated": failure == "output_limit",
        })
        if self.execution_mode == "software_test":
            diagnostic = bytes(stderr).decode("utf-8", errors="replace")
            for value in sorted(set(self.environment.values()), key=len, reverse=True):
                if value:
                    diagnostic = diagnostic.replace(value, "[redacted]")
            evidence["stderr"] = diagnostic[:min(4096, self.max_output_bytes)]
        # Live stderr is deliberately omitted: providers can emit credentials.
        raw = bytes(stdout)
        if failure is None and evidence["returncode"] != 0:
            failure = "nonzero_exit"
        response = None
        if failure is None:
            try:
                parsed = _strict_object(raw)
                if self.execution_mode == "software_test":
                    response = parsed
                else:
                    if set(parsed) != {"response", "execution"} or not isinstance(parsed["response"], dict):
                        raise ValueError("Live response requires a receipt envelope")
                    receipt = _receipt(parsed["execution"], call_id)
                    execution_id = receipt["execution_id"]
                    response = parsed["response"]
                    evidence.update({"model": receipt["model"], "usage": receipt["usage"],
                                     "external_execution_receipt": receipt,
                                     "receipt_verification": "operator_command_assertion"})
            except (ValueError, UnicodeError, RecursionError):
                failure = "invalid_response"
        if failure:
            evidence["execution_error"] = failure
            raise WorkerInterrupted(failure, execution_id=execution_id,
                                    execution_mode=self.execution_mode,
                                    raw_response=raw, evidence=evidence)
        return WorkerResult(execution_id, self.execution_mode, raw, evidence, response)
