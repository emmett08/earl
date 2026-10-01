"""Trusted tool bindings and bounded observation acquisition adapters.

The operator registry selects an adapter. EAL source supplies JSON input and
cannot choose executable paths or file locations. These adapters are not a
process sandbox.
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import math
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import time
import tomllib
from pathlib import Path
from typing import Any, Mapping

MAX_JSON_DEPTH = 128
MAX_REQUEST_BYTES = 1024 * 1024


def keyed_digest(secret: bytes, domain: bytes, value: Any) -> str:
    """Public configuration identity without an offline low-entropy value oracle."""
    from .evaluator import canonical_digest

    if not isinstance(secret, bytes) or len(secret) != 32:
        raise ValueError("A private 32-byte store key is required")
    if not isinstance(domain, bytes) or not domain:
        raise ValueError("A domain separator is required")
    # Frozen acquisition hash domain, independent of the authored source version.
    # Retain these bytes so EAL/3 can reuse compatible observation-record/1 data.
    return hmac.new(secret, b"EAL/2\0" + domain + b"\0" +
                    bytes.fromhex(canonical_digest(value)), hashlib.sha256).hexdigest()


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
    version: str
    argv: tuple[str, ...] = ()
    path: str | None = None
    timeout_seconds: float = 30.0
    max_output_bytes: int = 1024 * 1024
    env: Mapping[str, str] = dataclasses.field(default_factory=dict, repr=False)
    pinned_files: tuple[tuple[str, str], ...] = ()
    # The operator asserts this collector is read-only and independent of
    # other simultaneous acquisitions. Arbitrary commands default to serial.
    parallel_safe: bool = False
    # None preserves full host inheritance; an explicit list passes only the
    # named variables that exist, plus the operator's configured env overlay.
    inherit_env: tuple[str, ...] | None = None

    def effective_environment(self) -> dict[str, str]:
        if self.inherit_env is None:
            current = dict(os.environ)
        else:
            current = {name: os.environ[name] for name in self.inherit_env if name in os.environ}
        current.update(self.env)
        return current

    def process_environment_digest(self, secret: bytes, *,
                                   effective_env: Mapping[str, str] | None = None) -> str | None:
        """Identity of the effective command environment without exposing secrets."""
        if self.kind != "command":
            return None
        current = self.effective_environment() if effective_env is None else dict(effective_env)
        return keyed_digest(secret, b"process-environment", current)

    def binding_digest(self, secret: bytes, *, workspace: Path | None = None) -> str:
        """Keyed registry identity, checking each operator-pinned file's bytes."""
        if self.pinned_files and workspace is None:
            raise ValueError("Pinned collector files require a workspace")
        for name, expected in self.pinned_files:
            path = Path(name)
            path = path.resolve() if path.is_absolute() else bounded_path(workspace, name)
            try:
                descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                with os.fdopen(descriptor, "rb") as stream:
                    details = os.fstat(stream.fileno())
                    if not stat.S_ISREG(details.st_mode) or details.st_size > 16 * 1024 * 1024:
                        raise ValueError("Pinned collector file must be a regular file at most 16 MiB")
                    digest = hashlib.sha256(stream.read(16 * 1024 * 1024 + 1)).hexdigest()
            except OSError as exc:
                raise ValueError("Pinned collector file is inaccessible") from exc
            if digest != expected:
                raise ValueError("Pinned collector file identity differs from operator configuration")
        identity = {
            "name": self.name, "kind": self.kind,
            "version": self.version, "argv": list(self.argv),
            "path": self.path, "timeout_seconds": self.timeout_seconds,
            "max_output_bytes": self.max_output_bytes,
            "env": dict(self.env), "pinned_files": [{"path": path, "sha256": digest}
                                                     for path, digest in self.pinned_files]}
        # Scheduling is a host choice, not a property of a measurement.
        if self.inherit_env is not None:
            identity["inherit_env"] = sorted(self.inherit_env)
        return keyed_digest(secret, b"tool-binding", identity)


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
        allowed = {"kind", "version", "argv", "path", "timeout_seconds", "max_output_bytes", "env", "pinned_files", "parallel_safe", "inherit_env"}
        for name, raw in document.get("tools", {}).items():
            if not isinstance(raw, dict) or set(raw) - allowed:
                raise ValueError(f"Unknown registry settings for {name}")
            if raw.get("kind") not in _ADAPTERS:
                raise ValueError(f"{name}: kind must be command or json_file")
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
            parallel_safe = raw.get("parallel_safe", False)
            if type(parallel_safe) is not bool:
                raise ValueError(f"{name}: parallel_safe must be a boolean")
            inherited = raw.get("inherit_env")
            if inherited is not None:
                if (raw["kind"] != "command" or not isinstance(inherited, list)
                        or len(inherited) > 64 or any(
                            not isinstance(item, str)
                            or re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", item, re.ASCII) is None
                            for item in inherited)
                        or len(set(inherited)) != len(inherited)):
                    raise ValueError(f"{name}: inherit_env requires up to 64 distinct command environment variable names")
            pinned = raw.get("pinned_files", [])
            if (not isinstance(pinned, list) or len(pinned) > 32
                    or any(not isinstance(item, dict) or set(item) != {"path", "sha256"}
                           or not isinstance(item["path"], str) or not item["path"]
                           or not isinstance(item["sha256"], str)
                           or re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is None for item in pinned)
                    or len({item["path"] for item in pinned}) != len(pinned)):
                raise ValueError(f"{name}: pinned_files requires distinct paths and lowercase SHA-256 digests")
            if raw["kind"] != "command" and pinned:
                raise ValueError(f"{name}: only command bindings can pin executable files")
            bindings[name] = ToolBinding(
                name, raw["kind"], raw["version"], tuple(argv), raw.get("path"), float(timeout), limit, env,
                tuple((item["path"], item["sha256"]) for item in pinned), parallel_safe,
                None if inherited is None else tuple(inherited)
            )
        return cls(bindings)

    def binding_for(self, name: str, *, version: str) -> ToolBinding:
        binding = self.bindings.get(name)
        if binding is None:
            raise ValueError(f"Tool {name!r} is not in the operator registry")
        if binding.version != version:
            raise ValueError("Declared tool version differs from the operator registry")
        return binding

    def acquire(self, binding: ToolBinding, request: dict, workspace: Path,
                *, secret: bytes) -> AcquisitionResult:
        """Choose the trusted adapter selected by the operator's tool binding."""
        adapter = _ADAPTERS.get(binding.kind)
        if adapter is None:
            raise ValueError(f"Unsupported operator tool kind {binding.kind!r}")
        return adapter(binding, request, workspace, secret)


def _kill_process(process: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass


def _execute(binding: ToolBinding, request: dict, workspace: Path, secret: bytes) -> tuple[bytes, bytes, int, dict]:
    """Read bounded stdout/stderr without retaining unbounded subprocess output."""
    encoded_request = json.dumps(request, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n"
    if len(encoded_request) > MAX_REQUEST_BYTES:
        raise ValueError(f"Tool request exceeds {MAX_REQUEST_BYTES} bytes")
    effective_env = binding.effective_environment()
    # Arguments may themselves contain credentials. The keyed binding digest
    # identifies the configured command without copying argv into a record.
    metadata = {"process_environment_digest": binding.process_environment_digest(
        secret, effective_env=effective_env)}
    if os.name != "posix":
        raise RuntimeError("The bounded command adapter currently requires a POSIX host")
    process = subprocess.Popen(
        binding.argv, cwd=workspace, env=effective_env, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, start_new_session=True,
    )
    stdout, stderr = bytearray(), bytearray()
    deadline = time.monotonic() + binding.timeout_seconds
    failure = None
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


def _acquire_command(binding: ToolBinding, request: dict, workspace: Path, secret: bytes) -> AcquisitionResult:
    stdout, stderr, returncode, metadata = _execute(binding, request, workspace, secret)
    if metadata.get("execution_error"):
        error = ValueError(metadata["execution_error"])
    elif returncode != 0:
        error = ValueError(f"Tool exited with status {returncode}")
    else:
        error = None
    return AcquisitionResult(stdout, stderr, metadata, error)


def _acquire_json_file(binding: ToolBinding, request: dict, workspace: Path, secret: bytes) -> AcquisitionResult:
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
