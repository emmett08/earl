"""Versioned case and acquisition contracts for the workflow study."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from eal.tool_acquisition import ToolRegistry, validate_envelope


SCHEMA = "eal2-ci-prospective-case/1"
TRACE_SCHEMA = "eal2-ci-prospective-tool-trace/1"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return sha256(value if type(value) is bytes else canonical(value)).hexdigest()


def timestamp(value: str) -> datetime:
    if type(value) is not str:
        raise ValueError("A timestamp requires ISO-8601 text")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() is None:
        raise ValueError("A timestamp needs an explicit UTC offset")
    return result.astimezone(timezone.utc)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Case:
    id: str
    family_id: str
    task: str
    scope: dict[str, Any]
    decision_cut: str
    reference_id: str
    allowed: dict[str, tuple[dict[str, Any], ...]]
    # Operator-owned grant: possible EAL evidence names/environment declarations.
    evidence_grants: dict[str, dict[str, str]]

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Case":
        expected = {"schema", "id", "family_id", "task", "scope", "decision_cut",
                    "reference_id", "allowed", "evidence_grants"}
        if type(raw) is not dict or set(raw) != expected or raw["schema"] != SCHEMA:
            raise ValueError("Unknown or malformed versioned case")
        for key in ("id", "family_id", "task", "reference_id"):
            if type(raw[key]) is not str or not raw[key]:
                raise ValueError(f"Case needs {key}")
        if type(raw["scope"]) is not dict or not raw["scope"]:
            raise ValueError("Case requires a typed, nonempty scope")
        timestamp(raw["decision_cut"])
        allowed = raw["allowed"]
        if type(allowed) is not dict or not allowed or any(
            type(name) is not str or not name or type(inputs) is not list or not inputs
            or any(type(item) is not dict for item in inputs) for name, inputs in allowed.items()
        ):
            raise ValueError("Case needs finite tool input allowlists")
        grants = raw["evidence_grants"]
        if type(grants) is not dict or not grants or any(
            type(name) is not str or type(value) is not dict
            or set(value) != {"tool", "environment"}
            or value["tool"] not in allowed or any(type(v) is not str or not v for v in value.values())
            for name, value in grants.items()
        ):
            raise ValueError("Case needs reviewed EAL evidence declarations")
        canonical(raw)
        return cls(raw["id"], raw["family_id"], raw["task"], raw["scope"],
                   raw["decision_cut"], raw["reference_id"],
                   {key: tuple(items) for key, items in allowed.items()}, grants)

    def as_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "id": self.id, "family_id": self.family_id,
                "task": self.task, "scope": self.scope, "decision_cut": self.decision_cut,
                "reference_id": self.reference_id,
                "allowed": {key: list(items) for key, items in self.allowed.items()},
                "evidence_grants": self.evidence_grants}


class ToolGateway:
    """Use the same trusted EAL registry commands for prose arm acquisitions.

    E/J instead call `eal_collect` over MCP, which uses this registry directly.
    Selection is restricted to case-specific exact JSON inputs before execution.
    """

    def __init__(self, workspace: Path, registry_path: Path):
        self.workspace = Path(workspace).resolve()
        self.registry_path = Path(registry_path).resolve()
        self.registry = ToolRegistry.load(self.registry_path)

    def catalogue(self, case: Case) -> list[dict[str, Any]]:
        return [{"tool_id": name, "version": self.registry.bindings[name].version,
                 "mode": self.registry.bindings[name].mode,
                 "allowed_inputs": list(inputs)}
                for name, inputs in sorted(case.allowed.items())]

    def authorise(self, case: Case, tool_id: str, arguments: Any) -> None:
        if tool_id not in case.allowed or not any(canonical(arguments) == canonical(item)
                                                  for item in case.allowed[tool_id]):
            raise ValueError("Tool request is outside the reviewed case input allowlist")
        binding = self.registry.bindings.get(tool_id)
        if binding is None or binding.kind != "command":
            raise ValueError("Study tool requires a reviewed command binding")

    def authorise_source(self, case: Case, source: str, claim: str) -> None:
        from eal.parser import parse
        program = parse(source)
        if program.patterns or program.applications:
            raise ValueError("This study version compares direct declarations only")
        if claim not in program.claims:
            raise ValueError("The authored claim is absent")
        if not program.evidence:
            raise ValueError("The authored source has no reviewed acquisition")
        for name, evidence in program.evidence.items():
            grant = case.evidence_grants.get(name)
            if (grant is None or grant != {"tool": evidence.tool,
                                          "environment": evidence.environment}):
                raise ValueError("EAL evidence identifier or environment lacks a case grant")
            tool = program.tools.get(evidence.tool)
            binding = self.registry.bindings.get(evidence.tool)
            if tool is None or binding is None or (tool.version, tool.mode) != (binding.version, binding.mode):
                raise ValueError("EAL tool version/mode differs from the reviewed registry")
            self.authorise(case, evidence.tool, evidence.input)
        for environment in program.environments.values():
            # EAL predicates still receive semantic validation in MCP; this
            # gate prevents an unrelated model-authored context from collecting.
            if environment.name not in {grant["environment"] for grant in case.evidence_grants.values()}:
                raise ValueError("EAL environment lacks a case grant")

    def capture(self, case: Case, tool_id: str, arguments: dict[str, Any]) -> dict:
        started = now()
        trace: dict[str, Any] = {"schema": TRACE_SCHEMA, "case_id": case.id,
                                 "family_id": case.family_id, "tool_id": tool_id,
                                 "arguments": arguments, "started_at": started,
                                 "status": "error", "error": None}
        try:
            self.authorise(case, tool_id, arguments)
            binding = self.registry.bindings[tool_id]
            names = [name for name, grant in case.evidence_grants.items()
                     if grant["tool"] == tool_id]
            if len(names) != 1:
                raise ValueError("Prose acquisition needs one reviewed evidence binding")
            evidence_id = names[0]
            request = {"evidence_id": evidence_id,
                       "environment": case.evidence_grants[evidence_id]["environment"],
                       "tool": tool_id, "tool_version": binding.version,
                       "mode": binding.mode, "input": arguments, "context": case.scope}
            result = self.registry.acquire(binding, request, self.workspace)
            trace.update(tool_version=binding.version, mode=binding.mode,
                         execution=result.metadata,
                         stdout_sha256=digest(result.stdout), stderr_sha256=digest(result.stderr))
            if result.error is not None:
                raise ValueError(f"Collector failed ({type(result.error).__name__})")
            envelope = validate_envelope(result.stdout, file_import=False, context=case.scope,
                                         acquisition={key: request[key] for key in
                                                      ("tool", "tool_version", "mode", "input", "context")})
            observed = envelope.get("observed_at", now())
            if timestamp(observed) > timestamp(case.decision_cut):
                raise ValueError("Tool observation postdates the case decision cut")
            trace.update(status="ok", observed_at=observed, value=envelope["value"],
                         value_sha256=digest(envelope["value"]),
                         details=envelope.get("details", {}))
        except (ValueError, KeyError, TypeError, OSError) as exc:
            trace["error"] = {"type": type(exc).__name__,
                              "message": str(exc) if type(exc) is ValueError
                              else "Tool execution failed"}
        trace["finished_at"] = now()
        return trace
