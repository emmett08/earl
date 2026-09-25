"""Trusted tool bindings and bounded observation acquisition adapters.

The operator registry selects an adapter. EAL source supplies JSON input and
cannot choose executable paths or file locations. These adapters are not a
process sandbox.
"""

from __future__ import annotations

import dataclasses
import math
import json
import os
import selectors
import signal
import stat
import subprocess
import time
import tomllib
from pathlib import Path
from typing import Any, Mapping

MAX_JSON_DEPTH = 128


def strict_json(text: str) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key {key!r}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"Non-finite JSON value {value}")

    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"Non-finite JSON value {value}")
        return parsed

    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid_constant, parse_float=finite_float)
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            if isinstance(item, (dict, list)):
                if depth >= MAX_JSON_DEPTH:
                    raise ValueError(f"JSON nesting exceeds {MAX_JSON_DEPTH} container levels")
                children = item.values() if isinstance(item, dict) else item
                pending.extend((child, depth + 1) for child in children)
        # JSON escapes can encode lone UTF-16 surrogates which cannot be stored
        # or hashed as UTF-8. Reject these before adding values to run records.
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except UnicodeError as exc:
        raise ValueError("JSON strings must contain valid Unicode scalar values") from exc
    except RecursionError as exc:
        raise ValueError("JSON nesting exceeds decoder resources") from exc
    return value


def bounded_path(workspace: Path, name: str) -> Path:
    """Resolve symlinks and refuse traversal outside the configured workspace."""
    path = (workspace / name).resolve()
    if not path.is_relative_to(workspace.resolve()):
        raise ValueError(f"Path is outside the workspace: {name}")
    return path


@dataclasses.dataclass(frozen=True)
class ToolBinding:
    name: str
    kind: str
    mode: str
    version: str
    argv: tuple[str, ...] = ()
    path: str | None = None
    timeout_seconds: float = 30.0
    max_output_bytes: int = 1024 * 1024
    env: Mapping[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class AcquisitionResult:
    stdout: bytes = b""
    stderr: bytes = b""
    metadata: Mapping[str, Any] = dataclasses.field(default_factory=dict)
    error: Exception | None = None


class ToolRegistry:
    def __init__(self, bindings: Mapping[str, ToolBinding] | None = None):
        self.bindings = dict(bindings or {})

    @classmethod
    def load(cls, path: str | Path) -> "ToolRegistry":
        with Path(path).open("rb") as stream:
            document = tomllib.load(stream)
        if set(document) - {"tools"} or not isinstance(document.get("tools", {}), dict):
            raise ValueError("The registry must contain only a [tools] table")
        bindings = {}
        allowed = {"kind", "mode", "version", "argv", "path", "timeout_seconds", "max_output_bytes", "env"}
        for name, raw in document.get("tools", {}).items():
            if not isinstance(raw, dict) or set(raw) - allowed:
                raise ValueError(f"Unknown registry settings for {name}")
            if raw.get("kind") not in _ADAPTERS:
                raise ValueError(f"{name}: kind must be command or json_file")
            if raw.get("mode") not in {"deterministic", "nondeterministic"}:
                raise ValueError(f"{name}: mode must be deterministic or nondeterministic")
            if not isinstance(raw.get("version"), str) or not raw["version"]:
                raise ValueError(f"{name}: a nonempty version is required")
            argv = raw.get("argv", [])
            if not isinstance(argv, list) or not all(isinstance(arg, str) and arg for arg in argv):
                raise ValueError(f"{name}: argv must contain nonempty strings")
            if raw["kind"] == "command" and (not argv or "path" in raw):
                raise ValueError(f"{name}: command requires argv and does not use path")
            if raw["kind"] == "json_file" and (not isinstance(raw.get("path"), str) or not raw["path"] or argv):
                raise ValueError(f"{name}: json_file requires a path and does not use argv")
            timeout = raw.get("timeout_seconds", 30.0)
            if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
                raise ValueError(f"{name}: timeout_seconds must be finite, positive and at most 3600")
            limit = raw.get("max_output_bytes", 1024 * 1024)
            if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 16 * 1024 * 1024:
                raise ValueError(f"{name}: max_output_bytes must be an integer from 1 through 16777216")
            env = raw.get("env", {})
            if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
                raise ValueError(f"{name}: env must map strings to strings")
            bindings[name] = ToolBinding(
                name, raw["kind"], raw["mode"], raw["version"], tuple(argv), raw.get("path"), float(timeout), limit, env
            )
        return cls(bindings)

    def binding_for(self, name: str, *, version: str, mode: str) -> ToolBinding:
        binding = self.bindings.get(name)
        if binding is None:
            raise ValueError(f"Tool {name!r} is not in the operator registry")
        if binding.version != version or binding.mode != mode:
            raise ValueError("Declared tool version/mode differs from the operator registry")
        return binding

    def acquire(self, binding: ToolBinding, request: dict, workspace: Path) -> AcquisitionResult:
        """Choose the trusted adapter selected by the operator's tool binding."""
        adapter = _ADAPTERS.get(binding.kind)
        if adapter is None:
            raise ValueError(f"Unsupported operator tool kind {binding.kind!r}")
        return adapter(binding, request, workspace)


def _kill_process(process: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass


def _execute(binding: ToolBinding, request: dict, workspace: Path) -> tuple[bytes, bytes, int, dict]:
    """Read bounded stdout/stderr without retaining unbounded subprocess output."""
    from .evaluator import canonical_digest

    effective_env = dict(os.environ)
    effective_env.update(binding.env)
    metadata = {"process_environment_digest": canonical_digest(effective_env), "argv": list(binding.argv)}
    if os.name != "posix":
        raise RuntimeError("The bounded command adapter currently requires a POSIX host")
    process = subprocess.Popen(
        binding.argv, cwd=workspace, env=effective_env, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, start_new_session=True,
    )
    stdout, stderr = bytearray(), bytearray()
    deadline = time.monotonic() + binding.timeout_seconds
    failure = None
    encoded_request = json.dumps(request, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n"
    # Nonblocking stdin matters: an adapter may never consume a large request.
    try:
        with selectors.DefaultSelector() as selector:
            for stream, label in ((process.stdout, "stdout"), (process.stderr, "stderr"), (process.stdin, "stdin")):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_WRITE if label == "stdin" else selectors.EVENT_READ, label)
            remaining_input = memoryview(encoded_request)
            while selector.get_map():
                if time.monotonic() >= deadline:
                    failure = "timeout"
                    break
                events = selector.select(min(0.1, max(0, deadline - time.monotonic())))
                for key, _ in events:
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
                    remaining = binding.max_output_bytes - len(stdout) - len(stderr)
                    target.extend(chunk[:max(0, remaining)])
                    if len(chunk) > remaining:
                        failure = "output_limit"
                        break
                if failure:
                    break
        if failure:
            _kill_process(process)
        try:
            returncode = process.wait(timeout=max(0.01, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            failure = "timeout"
            _kill_process(process)
            returncode = process.wait(timeout=5)
    except BaseException:
        _kill_process(process)
        process.wait(timeout=5)
        raise
    finally:
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream and not stream.closed:
                stream.close()
    metadata.update({"returncode": returncode, "output_truncated": failure == "output_limit"})
    if failure:
        metadata["execution_error"] = failure
    return bytes(stdout), bytes(stderr), returncode, metadata


def _acquire_command(binding: ToolBinding, request: dict, workspace: Path) -> AcquisitionResult:
    stdout, stderr, returncode, metadata = _execute(binding, request, workspace)
    if metadata.get("execution_error"):
        error = ValueError(metadata["execution_error"])
    elif returncode != 0:
        error = ValueError(f"Tool exited with status {returncode}")
    else:
        error = None
    return AcquisitionResult(stdout, stderr, metadata, error)


def _acquire_json_file(binding: ToolBinding, request: dict, workspace: Path) -> AcquisitionResult:
    path = bounded_path(workspace, binding.path)
    metadata = {"file": str(path.relative_to(workspace))}
    # A FIFO or device can block indefinitely before a bounded read begins.
    # File imports only accept regular files.
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("File observations require a regular file")
            stdout = stream.read(binding.max_output_bytes + 1)
    except (OSError, ValueError) as exc:
        return AcquisitionResult(metadata=metadata, error=exc)
    if len(stdout) > binding.max_output_bytes:
        metadata["output_truncated"] = True
        return AcquisitionResult(stdout[:binding.max_output_bytes], metadata=metadata,
                                 error=ValueError("output_limit"))
    return AcquisitionResult(stdout, metadata=metadata)


_ADAPTERS = {"command": _acquire_command, "json_file": _acquire_json_file}


def validate_envelope(stdout: bytes, *, file_import: bool, context: dict,
                      acquisition: dict) -> dict:
    """Check observation shape and the declared acquisition identity."""
    from .evaluator import canonical_digest

    envelope = strict_json(stdout.decode("utf-8"))
    if not isinstance(envelope, dict) or "value" not in envelope or set(envelope) - {"value", "observed_at", "context", "request", "details"}:
        raise ValueError("Tool output must be an object with value and optional observed_at, context, request, details")
    if file_import and not {"observed_at", "context", "request"} <= set(envelope):
        raise ValueError("File observations require observed_at and context and request; import must preserve age, scope and acquisition identity")
    if "request" in envelope:
        if not isinstance(envelope["request"], dict) or canonical_digest(envelope["request"]) != canonical_digest(acquisition):
            raise ValueError("Observation request differs from the declared acquisition request")
    if "context" in envelope:
        if not isinstance(envelope["context"], dict) or canonical_digest(envelope["context"]) != canonical_digest(context):
            raise ValueError("Observation context differs from the requested context")
    return envelope

