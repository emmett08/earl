"""Collect and store observations for the shared CLI/MCP reasoning service.

Tool binding and bounded acquisition live in tool_acquisition. Public helper
imports remain available here for existing service consumers.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .collection_scheduler import CollectionScheduler
from .store import RunStore, utc_now
from .tool_acquisition import (MAX_REQUEST_BYTES, ToolBinding, ToolRegistry, bounded_path, strict_json,
                               validate_envelope)


OBSERVATION_SCHEMA = "EAL/observation-record/1"
MAX_COLLECTION_CONTEXT_BYTES = 16 * 1024
MAX_COLLECTION_EVIDENCE = 128
MAX_COLLECTION_OUTPUT_BYTES = 128 * 1024 * 1024
MAX_COLLECTION_BYTES = 32 * 1024 * 1024


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
    return {"tool": tool.name, "tool_version": tool.version,
            "input": evidence.input, "context": dict(context)}


class EvidenceRuntime:
    def __init__(self, workspace: str | Path, registry: ToolRegistry, store: RunStore, *,
                 method_registry=None, scheduler: CollectionScheduler | None = None):
        from .methods import default_registry

        self.workspace = Path(workspace).resolve()
        self.registry = registry
        self.store = store
        self.method_registry = default_registry() if method_registry is None else method_registry
        self.scheduler = CollectionScheduler() if scheduler is None else scheduler

    def collect(self, program, context: Mapping[str, Any], evidence_ids: list[str] | None = None,
                *, registry: ToolRegistry | None = None) -> dict:
        from .evaluator import canonical_digest
        from .semantics import validate

        diagnostics = validate(program, registry=self.method_registry)
        if diagnostics:
            raise ValueError("Cannot collect evidence for an invalid program: " + "; ".join(d.message for d in diagnostics))
        if not isinstance(context, dict):
            raise ValueError("context must be a JSON object")
        canonical_digest(context)
        context_bytes = len(json.dumps(context, sort_keys=True, allow_nan=False).encode("utf-8"))
        if context_bytes > MAX_COLLECTION_CONTEXT_BYTES:
            raise ValueError(f"Collection context exceeds {MAX_COLLECTION_CONTEXT_BYTES} bytes")
        names = list(program.evidence) if evidence_ids is None else evidence_ids
        if (not isinstance(names, list) or any(not isinstance(name, str) for name in names)
                or len(set(names)) != len(names) or any(name not in program.evidence for name in names)):
            raise ValueError("evidence_ids must be unique declared evidence identifiers")
        if len(names) > MAX_COLLECTION_EVIDENCE:
            raise ValueError(f"Collection exceeds {MAX_COLLECTION_EVIDENCE} evidence requests")
        selected_registry = self.registry if registry is None else registry
        # Check the complete selected plan before its first effectful call.
        # A missing binding is still collected as a durable error observation.
        output_allowance = 0
        for name in names:
            declaration = program.evidence[name]
            version = program.tools[declaration.tool].version
            request = {"evidence_id": name, "environment": declaration.environment,
                       **acquisition_request(program, name, context)}
            request_bytes = len(json.dumps(request, sort_keys=True, allow_nan=False).encode("utf-8")) + 1
            if request_bytes > MAX_REQUEST_BYTES:
                raise ValueError(f"Tool request for {name!r} exceeds {MAX_REQUEST_BYTES} bytes")
            try:
                binding = selected_registry.binding_for(declaration.tool, version=version)
            except ValueError:
                continue
            if type(binding.max_output_bytes) is not int or not 1 <= binding.max_output_bytes <= MAX_COLLECTION_OUTPUT_BYTES:
                raise ValueError(f"Tool {declaration.tool!r} has an invalid output allowance")
            output_allowance += binding.max_output_bytes
            if output_allowance > MAX_COLLECTION_OUTPUT_BYTES:
                raise ValueError(f"Collection output allowance exceeds {MAX_COLLECTION_OUTPUT_BYTES} bytes")

        def parallel_safe(name: str) -> bool:
            declaration = program.evidence[name]
            try:
                return selected_registry.binding_for(
                    declaration.tool, version=program.tools[declaration.tool].version
                ).parallel_safe
            except ValueError:
                return False

        records = self.scheduler.run(
            names, parallel_safe,
            lambda name: self._collect_one(program, name, context, selected_registry),
        )
        collection = {"source_digest": program.source_digest, "context": dict(context), "records": records}
        if len(json.dumps(collection, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")) > MAX_COLLECTION_BYTES:
            raise ValueError(f"Collection exceeds {MAX_COLLECTION_BYTES} stored bytes")
        collection_id = self.store.put("collection", collection)
        return {"collection_id": collection_id, **collection}


    def _collect_one(self, program, name: str, context: dict, registry: ToolRegistry) -> dict:
        from .evaluator import canonical_digest, environment_fingerprint

        declaration = program.evidence[name]
        declared_tool = program.tools[declaration.tool]
        run_id = str(uuid4())
        started_at = utc_now()
        record = {
            "schema": OBSERVATION_SCHEMA,
            "evidence_id": name, "source_digest": program.source_digest,
            "tool": declaration.tool, "tool_version": declared_tool.version,
            "evidence_kind": declaration.kind,
            "environment": declaration.environment,
            "environment_fingerprint": environment_fingerprint(declaration.environment, context),
            "collected_at": started_at, "started_at": started_at, "run_id": run_id,
            "input_digest": canonical_digest(declaration.input), "input": declaration.input,
            "context": dict(context), "status": "error",
        }
        stdout, stderr = b"", b""
        try:
            binding = registry.binding_for(declaration.tool, version=declared_tool.version)
            record["tool_binding_digest"] = binding.binding_digest(self.store._binding_key, workspace=self.workspace)
            acquisition = acquisition_request(program, name, context)
            request = {"evidence_id": name, "environment": declaration.environment, **acquisition}
            record["request_digest"] = canonical_digest(request)
            record["acquisition_request"] = acquisition
            record["acquisition_request_digest"] = canonical_digest(acquisition)
            result = registry.acquire(binding, request, self.workspace, secret=self.store._binding_key)
            stdout, stderr = result.stdout, result.stderr
            record.update(result.metadata)
            # A collector that changed during the call cannot issue a current
            # observation under the identity checked before execution.
            if binding.binding_digest(self.store._binding_key, workspace=self.workspace) != record["tool_binding_digest"]:
                raise ValueError("Collector binding identity changed during acquisition")
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
    """Persist output digests and lengths without exposing raw process streams."""
    record["ingested_at"] = utc_now()
    record["stdout_digest"] = hashlib.sha256(stdout).hexdigest()
    record["stderr_digest"] = hashlib.sha256(stderr).hexdigest()
    record["stdout_bytes"] = len(stdout)
    record["stderr_bytes"] = len(stderr)
    store.put("observation", record, record_id=record["run_id"])


class ReasoningService:
    """One application path used by CLI, MCP and the text-model host."""

    def __init__(self, workspace: str | Path, registry_path: str | Path | None = None,
                 database_path: str | Path | None = None, *, method_registry=None,
                 scheduler: CollectionScheduler | None = None):
        from .methods import MethodRegistry, default_registry

        self.method_registry = default_registry() if method_registry is None else method_registry
        if not isinstance(self.method_registry, MethodRegistry):
            raise TypeError("method_registry must be a MethodRegistry")
        self.workspace = Path(workspace).resolve()
        self.registry_path = Path(registry_path).resolve() if registry_path else None
        registry = ToolRegistry.load(self.registry_path) if self.registry_path else ToolRegistry()
        self.store = RunStore(database_path or self.workspace / ".eal" / "runs.sqlite3")
        self.runtime = EvidenceRuntime(
            self.workspace, registry, self.store, method_registry=self.method_registry,
            scheduler=scheduler,
        )

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
                "new_collection_required": formatted != source}

    def collect(self, source: str, context: dict, evidence_ids: list[str] | None = None) -> dict:
        from .parser import parse

        registry = ToolRegistry.load(self.registry_path) if self.registry_path is not None else self.runtime.registry
        return self.runtime.collect(parse(source), context, evidence_ids, registry=registry)

    def plan(self, source: str, claim: str) -> dict:
        """List the complete acquisition closure for one declared claim."""
        from .parser import parse
        from .planning import EvidencePlanner
        from .semantics import validate

        program = parse(source)
        diagnostics = validate(program, registry=self.method_registry)
        if diagnostics:
            raise ValueError("Cannot plan invalid EAL source: " + "; ".join(
                item.message for item in diagnostics))
        plan = EvidencePlanner(program).plan(claim)
        closure = plan.closure
        return {
            "claim": claim, "source_digest": program.source_digest,
            "method_registry_fingerprint": self.method_registry.fingerprint,
            "evidence_ids": list(plan.evidence_ids), "estimated_calls": plan.estimated_calls,
            "calls": [dataclasses.asdict(call) for call in plan.calls],
            "dependencies": {
                "claims": [name for name in program.claims if name in closure.claims],
                "arguments": [name for name in program.arguments if name in closure.arguments],
                "reasoning": [name for name in program.reasoning if name in closure.reasoning],
                "assumptions": [name for name in program.assumptions if name in closure.assumptions],
                "objections": [name for name in program.objections if name in closure.objections],
            },
        }

    def collect_claim(self, source: str, context: dict, claim: str) -> dict:
        """Collect every support and attack route for a claim's declared graph."""
        plan = self.plan(source, claim)
        collection = self.collect(source, context, plan["evidence_ids"])
        return {**collection, "plan": plan}

    def packet(self, assessment_id: str, claim: str | None = None) -> dict:
        """Give a model a scoped result while keeping its full trace retrievable."""
        from .packets import AssessmentPacketBuilder

        assessment = self.explain(assessment_id)
        if assessment.get("method_registry_fingerprint") != self.method_registry.fingerprint:
            raise ValueError("Stored assessment method registry differs from the current packet contract")
        collection_id = assessment.get("collection_id")
        collection = ({"collection_id": collection_id,
                       **self.store.get(collection_id, kind="collection")}
                      if isinstance(collection_id, str) else None)
        return AssessmentPacketBuilder(method_registry=self.method_registry).build(
            assessment, claims=None if claim is None else [claim], collection=collection,
        )

    def current_binding_digests(self, program) -> dict[str, str | None]:
        """Resolve current operator configuration for each evidence declaration.

        Missing or changed configuration and an operator-pinned file mismatch
        invalidate a stored observation. Unpinned dependencies and physical
        data are outside this identity check.
        """
        registry = ToolRegistry.load(self.registry_path) if self.registry_path is not None else self.runtime.registry
        current = {}
        resolved: dict[tuple[str, str], str | None] = {}
        for name, evidence in program.evidence.items():
            tool = program.tools.get(evidence.tool)
            if tool is None:
                current[name] = None
                continue
            key = (tool.name, tool.version)
            if key not in resolved:
                try:
                    resolved[key] = registry.binding_for(
                        tool.name, version=tool.version).binding_digest(
                            self.store._binding_key, workspace=self.workspace)
                except ValueError:
                    resolved[key] = None
            current[name] = resolved[key]
        return current

    def current_execution_digests(self, program) -> dict[str, str | None]:
        """Check whether a command would inherit the same process environment.

        An inherited credential, kubeconfig or endpoint can change an
        observation's meaning while the operator TOML stays identical. A
        changed environment refuses explicit reuse of its old measurement.
        File imports do not spawn a process and have no execution environment.
        """
        registry = ToolRegistry.load(self.registry_path) if self.registry_path is not None else self.runtime.registry
        current: dict[str, str | None] = {}
        for name, evidence in program.evidence.items():
            tool = program.tools.get(evidence.tool)
            if tool is None:
                current[name] = None
                continue
            try:
                binding = registry.binding_for(tool.name, version=tool.version)
                current[name] = binding.process_environment_digest(self.store._binding_key)
            except ValueError:
                current[name] = None
        return current

    def reason(self, source: str, context: dict, collection_id: str | None = None, now: str | None = None) -> dict:
        from .collection_identity import CollectionIdentityValidator
        from .evaluator import evaluate
        from .parser import parse

        program = parse(source)
        if collection_id is not None and (not isinstance(collection_id, str) or not collection_id.strip()):
            raise ValueError("collection_id must be a nonempty string or null")
        collection = self.store.get(collection_id, kind="collection") if collection_id is not None else None
        records = ({} if collection is None else CollectionIdentityValidator().validate(
            collection, source_digest=program.source_digest, context=context))
        assessment = evaluate(program, records, now=utc_now() if now is None else now,
                              context=context, registry=self.method_registry,
                              binding_digests=self.current_binding_digests(program))
        assessment["collection_id"] = collection_id
        assessment["method_registry_fingerprint"] = self.method_registry.fingerprint
        assessment_id = self.store.put("assessment", assessment)
        return {"assessment_id": assessment_id, **assessment}

    def compile_aspic(self, source: str, context: dict, collection_id: str,
                      goal: str, now: str | None = None) -> dict:
        """Opt-in compilation of checked EAL routes into a bounded ASPIC+ snapshot.

        The ordinary ``reason`` operation retains EAL's authored dialectic.
        Compilation consumes the same operator-owned collection and current
        collector bindings; a client cannot supply a substitute theory.
        """
        from .aspic_compiler import compile_eal_aspic
        from .collection_identity import CollectionIdentityValidator
        from .parser import parse

        if not isinstance(collection_id, str) or not collection_id.strip():
            raise ValueError("compile_aspic requires a stored collection_id")
        program = parse(source)
        collection = self.store.get(collection_id, kind="collection")
        records = CollectionIdentityValidator().validate(
            collection, source_digest=program.source_digest, context=context)
        compiled = compile_eal_aspic(
            source, records, goal=goal,
            now=utc_now() if now is None else now, context=context,
            registry=self.method_registry,
            binding_digests=self.current_binding_digests(program),
        )
        return {"collection_id": collection_id, **compiled.to_dict()}

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
