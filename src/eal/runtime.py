"""Real, bounded tool execution and the shared CLI/MCP reasoning service.

The language names tools. Only the operator's TOML registry binds those names to
executables. Source input is JSON data on stdin; it is never evaluated as shell.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
import selectors
import signal
import subprocess
import time
import tomllib
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .store import RunStore, utc_now


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

    value = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid_constant, parse_float=finite_float)
    try:
        # JSON escapes can encode lone UTF-16 surrogates which cannot be stored
        # or hashed as UTF-8. Reject these before adding values to run records.
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except UnicodeError as exc:
        raise ValueError("JSON strings must contain valid Unicode scalar values") from exc
    return value


def bounded_path(workspace: Path, name: str) -> Path:
    """Resolve symlinks and refuse traversal outside the configured workspace."""
    path = (workspace / name).resolve()
    if not path.is_relative_to(workspace.resolve()):
        raise ValueError(f"Path is outside the workspace: {name}")
    return path


def load_method_registry(factory: str | None = None):
    """Load a trusted host factory; EAL source cannot select Python code.

    A factory is configured by the process operator as ``package.module:name``
    and returns an immutable MethodRegistry. Importing it executes trusted
    application code, just as starting a custom MCP server does.
    """
    from importlib import import_module
    import re

    from .methods import MethodRegistry, default_registry

    if factory is None:
        return default_registry()
    if not isinstance(factory, str) or not re.fullmatch(
        r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*", factory, flags=re.ASCII
    ):
        raise ValueError("Method factory must have the form package.module:function")
    module_name, function_name = factory.split(":")
    try:
        build = getattr(import_module(module_name), function_name)
    except (ImportError, AttributeError) as exc:
        raise ValueError(f"Cannot load configured method factory {factory!r}") from exc
    if not callable(build):
        raise ValueError("The configured method factory is not callable")
    registry = build()
    if not isinstance(registry, MethodRegistry):
        raise ValueError("The configured method factory must return a MethodRegistry")
    return registry


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
            if raw.get("kind") not in {"command", "json_file"}:
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


def _timestamp(value: Any) -> str:
    from .semantics import parse_time

    if not isinstance(value, str):
        raise ValueError("observed_at must be an ISO-8601 timestamp with a timezone")
    parse_time(value)
    return value


class EvidenceRuntime:
    def __init__(self, workspace: str | Path, registry: ToolRegistry, store: RunStore, *, method_registry=None):
        from .methods import default_registry

        self.workspace = Path(workspace).resolve()
        self.registry = registry
        self.store = store
        self.method_registry = default_registry() if method_registry is None else method_registry

    def collect(self, program, context: Mapping[str, Any], evidence_ids: list[str] | None = None) -> dict:
        from .evaluator import canonical_digest, environment_fingerprint
        from .semantics import validate

        diagnostics = validate(program, registry=self.method_registry)
        if diagnostics:
            raise ValueError("Cannot collect evidence for an invalid program: " + "; ".join(d.message for d in diagnostics))
        if not isinstance(context, dict):
            raise ValueError("context must be a JSON object")
        canonical_digest(context)
        names = list(program.evidence) if evidence_ids is None else evidence_ids
        if len(set(names)) != len(names) or any(name not in program.evidence for name in names):
            raise ValueError("evidence_ids must be unique declared evidence identifiers")
        records = {}
        for name in names:
            declaration = program.evidence[name]
            declared_tool = program.tools[declaration.tool]
            run_id = str(uuid4())
            started_at = utc_now()
            record = {
                "evidence_id": name, "source_digest": program.source_digest,
                "tool": declaration.tool, "tool_version": declared_tool.version, "mode": declared_tool.mode,
                "evidence_kind": declaration.kind,
                "environment": declaration.environment,
                "environment_fingerprint": environment_fingerprint(declaration.environment, context),
                "collected_at": started_at, "started_at": started_at, "run_id": run_id,
                "input_digest": canonical_digest(declaration.input), "input": declaration.input,
                "context": dict(context), "status": "error",
            }
            stdout, stderr = b"", b""
            try:
                binding = self.registry.bindings.get(declaration.tool)
                if binding is None:
                    raise ValueError(f"Tool {declaration.tool!r} is not in the operator registry")
                if binding.version != declared_tool.version or binding.mode != declared_tool.mode:
                    raise ValueError("Declared tool version/mode differs from the operator registry")
                request = {"evidence_id": name, "input": declaration.input, "environment": declaration.environment, "context": dict(context)}
                record["request_digest"] = canonical_digest(request)
                if binding.kind == "command":
                    stdout, stderr, returncode, metadata = _execute(binding, request, self.workspace)
                    record.update(metadata)
                    if metadata.get("execution_error"):
                        raise ValueError(metadata["execution_error"])
                    if returncode != 0:
                        raise ValueError(f"Tool exited with status {returncode}")
                else:
                    path = bounded_path(self.workspace, binding.path)
                    record["file"] = str(path.relative_to(self.workspace))
                    with path.open("rb") as stream:
                        stdout = stream.read(binding.max_output_bytes + 1)
                    if len(stdout) > binding.max_output_bytes:
                        stdout = stdout[:binding.max_output_bytes]
                        record["output_truncated"] = True
                        raise ValueError("output_limit")
                envelope = strict_json(stdout.decode("utf-8"))
                if not isinstance(envelope, dict) or "value" not in envelope or set(envelope) - {"value", "observed_at", "context", "details"}:
                    raise ValueError("Tool output must be an object with value and optional observed_at, context, details")
                if binding.kind == "json_file" and not {"observed_at", "context"} <= set(envelope):
                    raise ValueError("File observations require observed_at and context; import must preserve their age and scope")
                if "context" in envelope:
                    if not isinstance(envelope["context"], dict) or canonical_digest(envelope["context"]) != canonical_digest(context):
                        raise ValueError("Observation context differs from the requested context")
                record["collected_at"] = _timestamp(envelope["observed_at"]) if "observed_at" in envelope else utc_now()
                record["value"] = envelope["value"]
                record["data_digest"] = canonical_digest(envelope["value"])
                if "details" in envelope:
                    record["details"] = envelope["details"]
                record["status"] = "ok"
            except (ValueError, TypeError, OSError, UnicodeError, OverflowError, RuntimeError) as exc:
                record["error"] = {"type": type(exc).__name__, "message": str(exc)}
            record["ingested_at"] = utc_now()
            record["stdout_digest"] = hashlib.sha256(stdout).hexdigest()
            record["stderr_digest"] = hashlib.sha256(stderr).hexdigest()
            record["stdout_bytes"] = len(stdout)
            record["stderr_bytes"] = len(stderr)
            record["stderr"] = stderr.decode("utf-8", errors="replace")
            # Error output is retained for diagnosis, bounded by registry limits.
            if record["status"] == "error":
                record["stdout"] = stdout.decode("utf-8", errors="replace")
            self.store.put("observation", record, record_id=run_id)
            records[name] = record
        collection = {"source_digest": program.source_digest, "context": dict(context), "records": records}
        collection_id = self.store.put("collection", collection)
        return {"collection_id": collection_id, **collection}


class ReasoningService:
    """One application path used by CLI, MCP and the text-model host."""

    def __init__(self, workspace: str | Path, registry_path: str | Path | None = None, database_path: str | Path | None = None, *, method_registry=None):
        from .methods import MethodRegistry, default_registry

        self.method_registry = default_registry() if method_registry is None else method_registry
        if not isinstance(self.method_registry, MethodRegistry):
            raise TypeError("method_registry must be a MethodRegistry")
        self.workspace = Path(workspace).resolve()
        registry = ToolRegistry.load(registry_path) if registry_path else ToolRegistry()
        self.store = RunStore(database_path or self.workspace / ".eal" / "runs.sqlite3")
        self.runtime = EvidenceRuntime(self.workspace, registry, self.store, method_registry=self.method_registry)

    def validate(self, source: str) -> dict:
        from .parser import parse
        from .semantics import validate

        try:
            program = parse(source)
        except ValueError as exc:
            return {"valid": False, "diagnostics": [{"code": "syntax", "message": str(exc)}]}
        diagnostics = validate(program, registry=self.method_registry)
        return {"valid": not diagnostics, "source_digest": program.source_digest,
                "method_registry_fingerprint": self.method_registry.fingerprint,
                "diagnostics": [dataclasses.asdict(d) for d in diagnostics]}

    def describe(self) -> dict:
        from .discovery import describe_language

        return describe_language(registry=self.method_registry)

    def format(self, source: str) -> dict:
        from .formatter import format_source
        from .parser import parse

        formatted = format_source(source, registry=self.method_registry)
        return {"source": formatted, "source_digest": parse(formatted).source_digest,
                "observation_recollection_required": formatted != source}

    def collect(self, source: str, context: dict, evidence_ids: list[str] | None = None) -> dict:
        from .parser import parse

        return self.runtime.collect(parse(source), context, evidence_ids)

    def reason(self, source: str, context: dict, collection_id: str | None = None, now: str | None = None) -> dict:
        from .evaluator import evaluate
        from .parser import parse

        program = parse(source)
        collection = self.store.get(collection_id, kind="collection") if collection_id else {"records": {}}
        assessment = evaluate(program, collection["records"], now=now or utc_now(), context=context, registry=self.method_registry)
        assessment["method_registry_fingerprint"] = self.method_registry.fingerprint
        assessment_id = self.store.put("assessment", assessment)
        return {"assessment_id": assessment_id, **assessment}

    def explain(self, assessment_id: str, claim: str | None = None) -> dict:
        assessment = self.store.get(assessment_id, kind="assessment")
        if claim is None:
            return {"assessment_id": assessment_id, **assessment}
        if claim not in assessment["claims"]:
            raise ValueError(f"Unknown claim {claim!r}")
        return {
            "assessment_id": assessment_id, "claim": claim, "result": assessment["claims"][claim],
            "assessed_at": assessment["assessed_at"], "source_digest": assessment["source_digest"],
            "method_registry_fingerprint": assessment.get("method_registry_fingerprint"),
            **{key: assessment[key] for key in ("arguments", "evidence", "assumptions", "reasoning", "objections")},
        }
