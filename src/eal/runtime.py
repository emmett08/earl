"""Collect and store observations for the shared CLI/MCP reasoning service.

Tool binding and bounded acquisition live in tool_acquisition. Public helper
imports remain available here for existing service consumers.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .store import RunStore, utc_now
from .tool_acquisition import (ToolBinding, ToolRegistry, bounded_path, strict_json,
                               validate_envelope)


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


def _timestamp(value: Any) -> str:
    from .semantics import parse_time

    if not isinstance(value, str):
        raise ValueError("observed_at must be an ISO-8601 timestamp with a timezone")
    parse_time(value)
    return value


def acquisition_request(program, evidence_id: str, context: Mapping[str, Any]) -> dict:
    """Identify acquisition independently of local argument/declaration names.

    The collection separately binds the observation to exact source bytes and
    its evidence declaration. This identity checks correspondence, not whether
    a producer genuinely measured the supplied value.
    """
    evidence = program.evidence[evidence_id]
    tool = program.tools[evidence.tool]
    return {"tool": tool.name, "tool_version": tool.version, "mode": tool.mode,
            "input": evidence.input, "context": dict(context)}


class EvidenceRuntime:
    def __init__(self, workspace: str | Path, registry: ToolRegistry, store: RunStore, *, method_registry=None):
        from .methods import default_registry

        self.workspace = Path(workspace).resolve()
        self.registry = registry
        self.store = store
        self.method_registry = default_registry() if method_registry is None else method_registry

    def collect(self, program, context: Mapping[str, Any], evidence_ids: list[str] | None = None) -> dict:
        from .evaluator import canonical_digest
        from .semantics import validate

        diagnostics = validate(program, registry=self.method_registry)
        if diagnostics:
            raise ValueError("Cannot collect evidence for an invalid program: " + "; ".join(d.message for d in diagnostics))
        if not isinstance(context, dict):
            raise ValueError("context must be a JSON object")
        canonical_digest(context)
        names = list(program.evidence) if evidence_ids is None else evidence_ids
        if (not isinstance(names, list) or any(not isinstance(name, str) for name in names)
                or len(set(names)) != len(names) or any(name not in program.evidence for name in names)):
            raise ValueError("evidence_ids must be unique declared evidence identifiers")
        records = {}
        for name in names:
            records[name] = self._collect_one(program, name, context)
        collection = {"source_digest": program.source_digest, "context": dict(context), "records": records}
        collection_id = self.store.put("collection", collection)
        return {"collection_id": collection_id, **collection}


    def _collect_one(self, program, name: str, context: dict) -> dict:
        from .evaluator import canonical_digest, environment_fingerprint

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
            binding = self.registry.binding_for(declaration.tool,
                                                version=declared_tool.version, mode=declared_tool.mode)
            acquisition = acquisition_request(program, name, context)
            request = {"evidence_id": name, "environment": declaration.environment, **acquisition}
            record["request_digest"] = canonical_digest(request)
            record["acquisition_request"] = acquisition
            record["acquisition_request_digest"] = canonical_digest(acquisition)
            result = self.registry.acquire(binding, request, self.workspace)
            stdout, stderr = result.stdout, result.stderr
            record.update(result.metadata)
            if result.error is not None:
                raise result.error
            envelope = validate_envelope(stdout, file_import=binding.kind == "json_file",
                                         context=context, acquisition=acquisition)
            record["collected_at"] = _timestamp(envelope["observed_at"]) if "observed_at" in envelope else utc_now()
            record["value"] = envelope["value"]
            record["data_digest"] = canonical_digest(envelope["value"])
            if "details" in envelope:
                record["details"] = envelope["details"]
            record["status"] = "ok"
        except (ValueError, TypeError, OSError, UnicodeError, OverflowError, RuntimeError) as exc:
            record["error"] = {"type": type(exc).__name__, "message": str(exc)}
        _store_observation(self.store, record, stdout, stderr)
        return record


def _store_observation(store: RunStore, record: dict, stdout: bytes, stderr: bytes) -> None:
    """Persist success or failure with the same bounded raw-output accounting."""
    record["ingested_at"] = utc_now()
    record["stdout_digest"] = hashlib.sha256(stdout).hexdigest()
    record["stderr_digest"] = hashlib.sha256(stderr).hexdigest()
    record["stdout_bytes"] = len(stdout)
    record["stderr_bytes"] = len(stderr)
    record["stderr"] = stderr.decode("utf-8", errors="replace")
    if record["status"] == "error":
        record["stdout"] = stdout.decode("utf-8", errors="replace")
    store.put("observation", record, record_id=record["run_id"])


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
        if collection_id is not None and (not isinstance(collection_id, str) or not collection_id.strip()):
            raise ValueError("collection_id must be a nonempty string or null")
        collection = self.store.get(collection_id, kind="collection") if collection_id is not None else {"records": {}}
        assessment = evaluate(program, collection["records"], now=utc_now() if now is None else now, context=context, registry=self.method_registry)
        assessment["collection_id"] = collection_id
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
