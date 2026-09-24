#!/usr/bin/env python3
"""Developmental, paired EAL/2 and JSON reviewed-route model experiment.

The frozen cross-model-delivery corpus predates this adapter. Its nine base
states and tamper states are exposed, synthetic and await independent review.
``preflight`` makes no provider calls. ``run`` requires explicit model, rates,
call and cost limits and never persists an API credential.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import random
import shutil
import sys
import tempfile
import time
import tomllib
from pathlib import Path
from typing import Any

from mcp import StdioServerParameters

from eal.applicability import TaskApplicabilityRegistry, review_applicability_digest
from eal.artifacts import ArtifactRegistry
from eal.families import FamilyRegistry, Parameter, review_binding_digest
from eal.providers import ChatCompletionsProvider, ModelResponse, ProviderError, TextProvider
from eal.recipient import RecipientBudget, run_reviewed_recipient
from eal.responses_provider import ResponsesProvider
from eal.routing import TaskFamilyHost
from eal.runtime import ReasoningService, strict_json


REPO = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
CORPUS = REPO / "benchmarks" / "experiments" / "cross-model-delivery"
MANIFEST = CORPUS / "manifest.json"
GRAPH_DIR = REPO / "benchmarks" / "equal_checker_graphs"
REVIEW_LABEL = "fixture_author_only_no_independent_review"
REVIEW_TIME = "2026-09-24T12:00:00Z"
DESCRIPTIONS = {
    "release_provenance": ("Pinned release build and staged digest", ["release", "digest", "stage", "build"]),
    "thermal_soak": ("Thermal soak logged preconditions", ["thermal", "soak", "calibration", "dwell"]),
    "network_failover": ("Network failover test and alert challenge", ["network", "failover", "alert", "trace"]),
}
SCHEMA = "eal2-reviewed-json-developmental/1"
# A missing required observation is a recipient refusal under the current
# claim-scope gate, even when the old raw interpreter/checker had a status.
EXPECTED_REFUSALS = {
    ("thermal_soak", "stale_qualifying"),
    ("thermal_soak", "future_timestamp"),
    ("network_failover", "stale_alert"),
    ("network_failover", "stale_answer"),
}
REASONS = {
    "release_provenance": {"matching_stage": "matching_digest", "digest_mismatch": "digest_mismatch",
                           "matching_repull": "matching_digest", "wrong_build_revision": "wrong_revision"},
    "thermal_soak": {"recent_qualifying": "qualifying_soak", "stale_qualifying": "stale_record",
                     "fresh_repeat": "qualifying_soak", "future_timestamp": "future_record"},
    "network_failover": {"qualifying_test": "qualifying_test", "buffer_challenge": "active_alert",
                         "separate_trace": "trace_answers_alert", "unrelated_trace": "unrelated_trace",
                         "stale_alert": "stale_alert", "stale_answer": "stale_answer"},
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def material_hashes() -> dict[str, str]:
    """All executable semantics and synthetic inputs consumed by this pilot."""
    paths = {REPO / "pyproject.toml", REPO / "benchmarks" / "equal_checker.py",
             HERE / "run.py", HERE / "json_checker.py"}
    for directory, pattern in ((REPO / "src" / "eal", "*.py"),
                               (REPO / "grammar", "*.g4"), (CORPUS, "*"),
                               (GRAPH_DIR, "*.json")):
        if directory.exists():
            paths.update(path for path in directory.rglob(pattern)
                         if path.is_file() and "__pycache__" not in path.parts
                         and path.suffix in {".json", ".toml", ".eal", ".py", ".md", ".g4"})
    return {str(path.relative_to(REPO)): digest(path) for path in sorted(paths)}


def runtime_versions() -> dict[str, str]:
    versions = {"python": platform.python_version()}
    for name in ("mcp", "httpx", "jsonschema", "antlr4-python3-runtime"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not_installed"
    return versions


def _toml(value: Any) -> str:
    """Bounded generated TOML values; source material never becomes a key."""
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{key} = {_toml(item)}" for key, item in value.items()) + " }"
    raise TypeError(f"Unsupported generated TOML value {type(value).__name__}")


def corpus() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (manifest.get("schema") != "eal2-cross-model-delivery/1"
            or manifest.get("cohort_status") != "developmental_unreviewed"
            or {root["id"] for root in manifest["roots"]} != set(DESCRIPTIONS)):
        raise ValueError("The frozen developmental corpus changed its contract")
    for root in manifest["roots"]:
        if (root["id"] not in DESCRIPTIONS or not root["brief"]
                or not root["states"] or not root["context"]):
            raise ValueError("Corpus root is incomplete")
    return manifest


def _tools(root: dict, state: dict) -> dict:
    registry = tomllib.loads((CORPUS / state["registry"]).read_text(encoding="utf-8"))
    result = {}
    for name, settings in registry["tools"].items():
        if name in result or settings["kind"] != "json_file":
            raise ValueError("Study requires a unique JSON-file evidence tool")
        result[name] = {**settings, "path": f"roots/{root['id']}/{settings['path']}"}
    return result


def records(root: dict, state: dict) -> dict[str, dict]:
    """Load independent JSON observation envelopes named in the frozen state."""
    result = {}
    for name, relative in state["checker_evidence"].items():
        path = (CORPUS / relative).resolve()
        if not path.is_relative_to(CORPUS.resolve()):
            raise ValueError("Observation path escaped the frozen corpus")
        result[name] = json.loads(path.read_text(encoding="utf-8"))
    return result


def prepare(workspace: Path, roots: list[dict], selected: dict, state: dict) -> tuple[TaskFamilyHost, dict]:
    """Pin three EAL sources and one per-root finite reviewed case in a fresh run."""
    workspace.mkdir(parents=True, exist_ok=True)
    shutil.copytree(CORPUS / "roots", workspace / "roots")
    tools: dict[str, dict] = {}
    for root in roots:
        active = state if root["id"] == selected["id"] else root["states"][0]
        for name, binding in _tools(root, active).items():
            if name in tools:
                raise ValueError("Evidence tool names collide across roots")
            tools[name] = binding
    tool_lines = []
    for name, binding in sorted(tools.items()):
        tool_lines.extend([f"[tools.{name}]"] + [f"{key} = {_toml(value)}"
                                                    for key, value in binding.items()] + [""])
    (workspace / "tools.toml").write_text("\n".join(tool_lines), encoding="utf-8")
    service = ReasoningService(workspace, workspace / "tools.toml", workspace / "runs.sqlite3")
    artifact_lines = []
    for root in roots:
        source = CORPUS / root["source"]
        artifact_lines.extend([f"[artifacts.{root['id']}]",
                               f"path = {_toml(root['source'])}",
                               f"sha256 = {_toml(digest(source))}",
                               f"method_registry_fingerprint = {_toml(service.method_registry.fingerprint)}",
                               f"claims = {_toml([root['claim']])}",
                               f"context = {_toml(root['context'])}",
                               f"now = {_toml(root['now'])}", ""])
    (workspace / "artifacts.toml").write_text("\n".join(artifact_lines), encoding="utf-8")
    artifacts = ArtifactRegistry.load(service, workspace / "artifacts.toml")
    family_lines = ['schema = "eal2-task-families/1"', ""]
    for root in roots:
        family_id = root["id"]
        context = root["context"]
        parameters = {name: Parameter("string", (value,)) for name, value in context.items()}
        paths = {name: name for name in context}
        case_digest = review_binding_digest(family_id, parameters, paths, context,
                                            family_id, artifacts.definitions[family_id],
                                            [root["claim"]])
        description, terms = DESCRIPTIONS[family_id]
        family_lines.extend([f"[families.{family_id}]", f"description = {_toml(description)}",
                             f"terms = {_toml(terms)}", f"context_paths = {_toml(paths)}", ""])
        for name, value in context.items():
            family_lines.extend([f"[families.{family_id}.parameters.{name}]",
                                 'type = "string"', f"values = {_toml([value])}", ""])
        family_lines.extend([f"[[families.{family_id}.cases]]",
                             f"bindings = {_toml(context)}", f"artifact_id = {_toml(family_id)}",
                             f"claims = {_toml([root['claim']])}",
                             f"reviewed_by = {_toml(REVIEW_LABEL)}",
                             f"reviewed_at = {_toml(REVIEW_TIME)}",
                             f"review_contract_sha256 = {_toml(case_digest)}", ""])
    (workspace / "families.toml").write_text("\n".join(family_lines), encoding="utf-8")
    families = FamilyRegistry.load(artifacts, workspace / "families.toml")
    task_lines = ['schema = "eal2-task-applicability/1"', ""]
    for root in roots:
        family_id = root["id"]
        reviewed_digest = review_applicability_digest(
            families, family_id, root["brief"], family_id, root["context"], root["claim"])
        task_lines.extend([f"[tasks.{family_id}]", f"question = {_toml(root['brief'])}",
                           f"family_id = {_toml(family_id)}",
                           f"bindings = {_toml(root['context'])}",
                           f"claim = {_toml(root['claim'])}",
                           f"reviewed_by = {_toml(REVIEW_LABEL)}",
                           f"reviewed_at = {_toml(REVIEW_TIME)}",
                           f"review_contract_sha256 = {_toml(reviewed_digest)}", ""])
    (workspace / "tasks.toml").write_text("\n".join(task_lines), encoding="utf-8")
    applicability = TaskApplicabilityRegistry.load(families, workspace / "tasks.toml")
    task_ids = set(DESCRIPTIONS)
    host = TaskFamilyHost(families, principal="developmental_study_caller",
                          authorised_families=task_ids,
                          authorised_claims={root["id"]: {root["claim"]} for root in roots},
                          applicability=applicability, task_text=selected["brief"],
                          authorised_tasks=task_ids)
    return host, {"source_sha256": {root["id"]: digest(CORPUS / root["source"]) for root in roots},
                  "method_registry_fingerprint": service.method_registry.fingerprint,
                  "family_catalogue_sha256": digest(workspace / "families.toml"),
                  "task_catalogue_sha256": digest(workspace / "tasks.toml")}


def _json_checker(root: dict):
    # The comparator imports the independently authored graph; it does not
    # parse EAL source or copy an EAL assessment.
    from json_checker import JsonReviewedChecker
    return JsonReviewedChecker.from_root(
        root, trusted_question=root["brief"],
        authorised_tasks={root["id"]}, authorised_families={root["id"]},
        authorised_artifacts={root["id"]}, authorised_claims={root["claim"]},
    )


def assess_pair(root: dict, state: dict, roots: list[dict]) -> dict:
    with tempfile.TemporaryDirectory(prefix="eal2-reviewed-") as temporary:
        host, provenance = prepare(Path(temporary), roots, root, state)
        eal_start = time.perf_counter()
        try:
            eal_packet = host.assess_bound_task()
            eal_status = eal_packet["status"]
            if host.finish_bound_task(eal_packet["assessment_id"]) != eal_packet:
                raise AssertionError("EAL finish changed the issued packet")
            eal_reason = eal_packet.get("decisive")
            eal_error = None
        except ValueError as exc:
            if not str(exc).startswith("Claim assessment unresolved: required evidence"):
                raise
            eal_packet, eal_status, eal_reason, eal_error = None, "refused", None, str(exc)
        eal_elapsed = time.perf_counter() - eal_start
        json_start = time.perf_counter()
        comparison = _json_checker(root).assess_bound(records(root, state), root["now"])
        json_elapsed = time.perf_counter() - json_start
        if comparison["status"] not in {"supported", "contested", "unsupported", "refused"}:
            raise AssertionError("JSON comparator returned an unknown status")
        matched = comparison["status"] == eal_status
        expected_recipient = ("refused" if (root["id"], state["id"]) in EXPECTED_REFUSALS
                              else state["expected"])
        return {"root": root["id"], "state": state["id"], "reference_raw_status": state["expected"],
                "expected_recipient_status": expected_recipient,
                "recipient_reference_match": eal_status == comparison["status"] == expected_recipient,
                "original_raw_label_match": eal_status == comparison["status"] == state["expected"],
                "review_status": state["review"]["status"],
                "eal": {"status": eal_status, "packet": eal_packet,
                        "reason": eal_reason, "refusal": eal_error, "elapsed_ms": eal_elapsed * 1000},
                "json": {"status": comparison["status"], "packet": comparison,
                         "reason": comparison.get("reason", comparison.get("trace")),
                         "elapsed_ms": json_elapsed * 1000},
                "parity": matched, "provenance": provenance}


def preflight(*, include_tamper: bool = True) -> dict:
    manifest = corpus()
    roots = manifest["roots"]
    pairs = []
    for root in roots:
        for state in [*root["states"], *(root.get("tamper", []) if include_tamper else [])]:
            pairs.append(assess_pair(root, state, roots))
    return {"schema": SCHEMA, "phase": "offline_preflight", "status": "developmental_unreviewed",
            "manifest_sha256": digest(MANIFEST),
            "equal_checker_sha256": digest(REPO / "benchmarks" / "equal_checker.py"),
            "graph_sha256": {root["id"]: digest(GRAPH_DIR / f"{root['id']}.json") for root in roots},
            "pairs": pairs, "parity": sum(row["parity"] for row in pairs),
            "recipient_reference_match": sum(row["recipient_reference_match"] for row in pairs),
            "original_raw_label_match": sum(row["original_raw_label_match"] for row in pairs),
            "total": len(pairs),
            "passed": all(row["parity"] and row["recipient_reference_match"] for row in pairs),
            "interpretation": "Synthetic fixture-author integration parity and explicitly amended recipient refusal states only. Original raw labels remain visible and differ in four stale/future states. No model or independent human outcome is measured."}


def _message_json(text: str, required: set[str]) -> dict:
    data = strict_json(text)
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError("Model response does not have exactly the required JSON fields")
    return data


def _tool_prompt(question: str) -> list[dict[str, str]]:
    return [{"role": "system", "content": "You are a recipient of one bound reviewed engineering task. Request the checked tool result. Return only one JSON object: {\"operation\":\"assess_bound_task\"}. You cannot replace the original question, source, claim or bindings."},
            {"role": "user", "content": question}]


def _delivery_prompt(question: str, packet: dict) -> list[dict[str, str]]:
    return [{"role": "system", "content": "Report the checked status and identify the decisive record pattern. Return only JSON with exactly three fields: status (supported, contested, unsupported or refused), reason_code (one of matching_digest, digest_mismatch, wrong_revision, qualifying_soak, stale_record, future_record, qualifying_test, active_alert, trace_answers_alert, unrelated_trace, stale_alert, stale_answer), and records_only (true). A refused check has no certified claim status: the reason_code describes the record defect. Limit the conclusion to submitted records."},
            {"role": "user", "content": json.dumps({"question": question, "checked_result": packet},
                                                       sort_keys=True, ensure_ascii=False)}]


def _raw_prompt(question: str, source: Any, records_for_state: dict) -> list[dict[str, str]]:
    return [{"role": "system", "content": "Judge the bounded engineering claim from the submitted records. Return JSON with exactly three fields: status (supported, contested or unsupported), reason_code (one of matching_digest, digest_mismatch, wrong_revision, qualifying_soak, stale_record, future_record, qualifying_test, active_alert, trace_answers_alert, unrelated_trace, stale_alert, stale_answer), and records_only (true). Do not assume physical verification beyond the records."},
            {"role": "user", "content": json.dumps({"question": question, "argument": source,
                                                       "observations": records_for_state},
                                                       sort_keys=True, ensure_ascii=False)}]


class BoundedCalls:
    def __init__(self, provider: TextProvider, *, max_calls: int, max_cost_usd: float,
                 input_usd_per_million: float, output_usd_per_million: float,
                 max_output_tokens: int, journal: Path | None = None,
                 frozen_materials: dict[str, str] | None = None):
        self.provider = provider
        self.max_calls = max_calls
        self.max_cost_usd = max_cost_usd
        self.input_rate = input_usd_per_million
        self.output_rate = output_usd_per_million
        self.max_output_tokens = max_output_tokens
        self.calls = 0
        self.cost_usd = 0.0
        self.journal = journal
        self.actual_model: str | None = None
        self.stopped = False
        self.frozen_materials = frozen_materials
        # Private provider result retains opaque Responses replay state. Never
        # put its handle or encrypted reasoning items in the attempt ledger.
        self.last_response: ModelResponse | None = None

    def _write(self, event: dict) -> None:
        if self.journal is None:
            return
        with self.journal.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _discard_response_handle(self, response: ModelResponse | None) -> None:
        if response is None:
            return
        discard = getattr(self.provider, "discard_replay_handles", None)
        handle = response.metadata.get("responses_replay_handle")
        if callable(discard) and isinstance(handle, str):
            discard([handle])

    async def complete(self, messages: list[dict[str, Any]],
                       max_output_tokens: int | None = None, *,
                       operations: list[dict] | None = None,
                       native_tools: bool = False) -> dict:
        self.last_response = None
        if self.frozen_materials is not None and material_hashes() != self.frozen_materials:
            self.stopped = True
            self._write({"phase": "material_drift", "before_call": self.calls + 1})
            raise RuntimeError("Frozen study materials changed; no next provider call was attempted")
        if self.calls >= self.max_calls:
            self.stopped = True
            raise RuntimeError("Local provider-call cap reached")
        # Conservative pre-call reservation. This is an operator stop rule,
        # not an API billing guarantee; actual usage can exceed the estimate.
        output_limit = self.max_output_tokens if max_output_tokens is None else max_output_tokens
        if not 1 <= output_limit <= self.max_output_tokens:
            raise ValueError("Requested output exceeds the shared provider limit")
        serialized = json.dumps(messages, ensure_ascii=False).encode("utf-8")
        public_messages = [{key: value for key, value in message.items()
                            if key != "_responses_replay_handle"} for message in messages]
        reservation = (len(serialized) * self.input_rate
                       + output_limit * self.output_rate) / 1_000_000
        if self.cost_usd + reservation > self.max_cost_usd:
            self.stopped = True
            raise RuntimeError("Local estimated cost cap prevents the next provider call")
        self.calls += 1
        call_id = self.calls
        self._write({"phase": "before", "call": call_id, "messages": public_messages,
                     "prompt_sha256": hashlib.sha256(serialized).hexdigest(),
                     "max_output_tokens": output_limit,
                     "native_tools": native_tools,
                     "operations": None if operations is None else
                     [item["operation"] for item in operations],
                     "estimated_reservation_usd": reservation})
        started = time.perf_counter()
        try:
            if operations is not None and callable(getattr(self.provider, "complete_request", None)):
                response = await self.provider.complete_request(
                    messages, output_limit, operations=operations, native_tools=native_tools)
            else:
                response = await self.provider.complete(messages, output_limit)
        except ProviderError as exc:
            partial = exc.response
            if (partial is not None and partial.input_tokens is not None
                    and partial.output_tokens is not None):
                self.cost_usd += (partial.input_tokens * self.input_rate
                                  + partial.output_tokens * self.output_rate) / 1_000_000
            else:
                self.cost_usd += reservation
            self.stopped = True
            self._write({"phase": "after", "call": call_id, "error": str(exc),
                         "cumulative_estimated_cost_usd": self.cost_usd,
                         "provider_response": None if partial is None else
                         {"input_tokens": partial.input_tokens,
                          "output_tokens": partial.output_tokens,
                          "model": partial.model,
                          "text": partial.text,
                          "metadata": {key: value for key, value in partial.metadata.items()
                                       if key != "responses_replay_handle"}}})
            self._discard_response_handle(partial)
            raise RuntimeError("Provider failed; run stopped after retaining the attempt") from exc
        except Exception as exc:
            self.cost_usd += reservation
            self.stopped = True
            self._write({"phase": "after", "call": call_id,
                         "error_type": type(exc).__name__, "usage": "unknown"})
            raise RuntimeError("Unexpected provider failure; usage unknown and run stopped") from exc
        input_tokens, output_tokens = response.input_tokens, response.output_tokens
        self.last_response = response
        if input_tokens is not None and output_tokens is not None:
            self.cost_usd += (input_tokens * self.input_rate
                              + output_tokens * self.output_rate) / 1_000_000
        else:
            self.cost_usd += reservation
        record = {"text": response.text, "usage": {"input_tokens": input_tokens,
                "output_tokens": output_tokens, "model": response.model,
                "cached_input_tokens": response.metadata.get("cached_input_tokens"),
                "reasoning_tokens": response.metadata.get("reasoning_tokens"),
                "response_id": response.metadata.get("id"),
                "finish_reason": response.metadata.get("finish_reason")},
                "elapsed_ms": (time.perf_counter() - started) * 1000,
                "prompt_sha256": hashlib.sha256(serialized).hexdigest(),
                "prompt_bytes": len(serialized)}
        self._write({"phase": "after", "call": call_id, "record": record,
                     "cumulative_estimated_cost_usd": self.cost_usd})
        if input_tokens is None or output_tokens is None:
            self.stopped = True
            self._discard_response_handle(response)
            self.last_response = None
            raise RuntimeError("Provider omitted token usage; run stopped after retaining the attempt")
        if response.model is None:
            self.stopped = True
            self._discard_response_handle(response)
            self.last_response = None
            raise RuntimeError("Provider omitted actual model identity; run stopped after retaining the attempt")
        if self.actual_model is None:
            self.actual_model = response.model
        elif self.actual_model != response.model:
            self.stopped = True
            self._discard_response_handle(response)
            self.last_response = None
            raise RuntimeError("Provider model identity changed; run stopped after retaining the attempt")
        if operations is None:
            self._discard_response_handle(response)
        return record


class RecipientProvider:
    """Apply the shared call ledger/cap to the real recipient MCP model turn."""

    def __init__(self, calls: BoundedCalls):
        self.calls = calls

    def identity(self) -> dict:
        return {**self.calls.provider.identity(),
                "pricing": {"input_usd_per_million": self.calls.input_rate,
                            "cached_input_usd_per_million": self.calls.input_rate,
                            "output_usd_per_million": self.calls.output_rate}}

    async def complete(self, messages: list[dict[str, str]], max_output_tokens: int) -> ModelResponse:
        await self.calls.complete(messages, max_output_tokens, operations=[])
        assert self.calls.last_response is not None
        return self.calls.last_response

    async def complete_request(self, messages: list[dict[str, Any]], max_output_tokens: int, *,
                               operations: list[dict], native_tools: bool = False) -> ModelResponse:
        await self.calls.complete(messages, max_output_tokens,
                                  operations=operations, native_tools=native_tools)
        assert self.calls.last_response is not None
        return self.calls.last_response

    def discard_replay_handles(self, handles: list[str]) -> None:
        discard = getattr(self.calls.provider, "discard_replay_handles", None)
        if callable(discard):
            discard(handles)


async def real_recipient(root: dict, state: dict, roots: list[dict], calls: BoundedCalls) -> dict:
    """Exercise the real dedicated MCP endpoint with a trusted question file."""
    with tempfile.TemporaryDirectory(prefix="eal2-real-recipient-") as temporary:
        workspace = Path(temporary)
        prepare(workspace, roots, root, state)
        question = workspace / "trusted_question.txt"
        question.write_text(root["brief"], encoding="utf-8")
        argv = ["-m", "eal.server", "--workspace", str(workspace),
                "--registry", str(workspace / "tools.toml"),
                "--database", str(workspace / "runs.sqlite3"),
                "--artifacts", str(workspace / "artifacts.toml"),
                "--families", str(workspace / "families.toml"),
                "--tasks", str(workspace / "tasks.toml"),
                "--recipient-task-file", str(question),
                "--recipient-only", "--recipient-principal", "developmental_study_caller"]
        for item in roots:
            argv.extend(["--recipient-family-grant", item["id"],
                         "--recipient-task-grant", item["id"],
                         "--recipient-grant", f"{item['id']}:{item['claim']}"])
        env = {**os.environ, "PYTHONPATH": str(REPO / "src") + os.pathsep
               + os.environ.get("PYTHONPATH", "")}
        server = StdioServerParameters(command=sys.executable, args=argv, env=env)
        report = await run_reviewed_recipient(
            root["brief"], RecipientProvider(calls), server,
            budget=RecipientBudget(max_model_turns=2, max_repairs=0,
                                   max_tool_calls=5, max_output_tokens=calls.max_output_tokens,
                                   max_model_cost_usd=calls.max_cost_usd,
                                   max_elapsed_seconds=90),
        )
        checked = report.get("checked_answer")
        expected_refusal = (root["id"], state["id"]) in EXPECTED_REFUSALS
        report["expected_recipient_refusal"] = expected_refusal
        report["refusal_as_expected"] = (
            expected_refusal and report["assessment"] is None and
            report["checked_answer"] is None and not report["attempts"] and
            report["stop_reason"] == "reviewed_mcp_tool_failed")
        report["status_match_offline"] = (None if expected_refusal else
                                          isinstance(checked, dict) and
                                          checked.get("status") == state["expected"])
        return report


async def run_live(*, model: str, max_calls: int, max_cost_usd: float,
                   input_rate: float, output_rate: float, max_output_tokens: int,
                   api_key_env: str, seed: int, states_per_root: int,
                   raw_arms: bool = True, real_recipient_arm: bool = True,
                   reasoning_effort: str = "none",
                   provider_api: str = "responses",
                   journal: Path | None = None,
                   frozen_materials: dict[str, str] | None = None,
                   provider: TextProvider | None = None) -> dict:
    if provider is None and not os.environ.get(api_key_env):
        raise RuntimeError(f"{api_key_env} is absent; no provider call was attempted")
    if not 1 <= states_per_root <= 3:
        raise ValueError("The developmental pilot selects one to three base states per root")
    if (max_calls < 1 or max_output_tokens < 32
            or any(not math.isfinite(rate) or rate < 0 for rate in (max_cost_usd, input_rate, output_rate))):
        raise ValueError("Call, output and estimated cost settings must be finite and bounded")
    offline = preflight(include_tamper=True)
    if not offline["passed"]:
        raise RuntimeError("Offline EAL/JSON parity failed; model run blocked")
    frozen_materials = frozen_materials or material_hashes()
    if material_hashes() != frozen_materials:
        raise RuntimeError("Frozen study materials changed before the first provider call")
    if provider_api not in {"responses", "chat_completions"}:
        raise ValueError("provider_api must be responses or chat_completions")
    provider_type = ResponsesProvider if provider_api == "responses" else ChatCompletionsProvider
    provider = provider or provider_type(model=model, api_key_env=api_key_env,
                                         timeout_seconds=90, sampling={},
                                         pricing={"input_usd_per_million": input_rate,
                                                  "output_usd_per_million": output_rate},
                                         capabilities={"reasoning_effort": reasoning_effort})
    budget = BoundedCalls(provider, max_calls=max_calls, max_cost_usd=max_cost_usd,
                          input_usd_per_million=input_rate,
                          output_usd_per_million=output_rate,
                          max_output_tokens=max_output_tokens, journal=journal,
                          frozen_materials=frozen_materials)
    rng = random.Random(seed)
    # Exact root/state indices prevent duplicate names in future corpus changes.
    chosen = {(root["id"], state["id"]) for root in corpus()["roots"]
              for state in root["states"][:states_per_root]}
    selected = [pair for pair in offline["pairs"] if (pair["root"], pair["state"]) in chosen]
    rng.shuffle(selected)
    results = []
    root_map = {root["id"]: root for root in corpus()["roots"]}
    for pair in selected:
        root = root_map[pair["root"]]
        state = next(state for state in root["states"] if state["id"] == pair["state"])
        record = records(root, state)
        row = {"root": root["id"], "state": state["id"],
               "reference_raw_status": pair["reference_raw_status"],
               "system_status": {arm: pair[arm]["status"] for arm in ("eal", "json")}}
        try:
            plan = await budget.complete(_tool_prompt(root["brief"]))
        except RuntimeError as exc:
            row["stop_reason"] = str(exc)
            results.append(row)
            break
        row["bound_tool_request"] = plan
        try:
            operation = _message_json(plan["text"], {"operation"})["operation"]
            row["bound_tool_adherence"] = operation == "assess_bound_task"
        except (KeyError, ValueError, TypeError):
            row["bound_tool_adherence"] = False
        # Conditional delivery and raw-notation probes run regardless of this
        # diagnostic planning response. Assessment is launcher-bound.
        arm_order = ["eal", "json"]
        rng.shuffle(arm_order)
        row["arm_order"] = arm_order[:]
        row["delivery"] = {}
        for arm in arm_order:
            packet = {"task_id": root["id"], "claim": root["claim"],
                      "scope": root["context"], "status": pair[arm]["status"],
                      "observations": record}
            prompt = _delivery_prompt(root["brief"], packet)
            try:
                response = await budget.complete(prompt)
            except RuntimeError as exc:
                row["stop_reason"] = str(exc)
                break
            entry = {"response": response,
                     "packet_bytes": len(json.dumps(packet, ensure_ascii=False).encode("utf-8"))}
            try:
                answer = _message_json(response["text"], {"status", "reason_code", "records_only"})
                entry["answer"] = answer
                entry["status_fidelity"] = answer["status"] == pair[arm]["status"]
                entry["reason_fidelity"] = answer["reason_code"] == REASONS[root["id"]][state["id"]]
                entry["scope_assertion"] = answer["records_only"] is True
            except (KeyError, ValueError, TypeError):
                entry.update(answer=None, status_fidelity=False, reason_fidelity=False,
                             scope_assertion=False)
            row["delivery"][arm] = entry
        if row.get("stop_reason"):
            results.append(row)
            break
        if raw_arms:
            raw_order = ["raw_eal", "raw_json"]
            rng.shuffle(raw_order)
            row["raw_order"] = raw_order[:]
            row["raw"] = {}
            from benchmarks.equal_checker import graph_for_root
            for arm in raw_order:
                representation = ((CORPUS / root["source"]).read_text(encoding="utf-8")
                                  if arm == "raw_eal" else json.dumps(
                                      graph_for_root(root["id"], GRAPH_DIR),
                                      indent=2, sort_keys=True, ensure_ascii=False))
                try:
                    response = await budget.complete(_raw_prompt(root["brief"], representation, record))
                except RuntimeError as exc:
                    row["stop_reason"] = str(exc)
                    break
                entry = {"response": response}
                try:
                    answer = _message_json(response["text"], {"status", "reason_code", "records_only"})
                    entry["answer"] = answer
                    entry["status_correct"] = answer["status"] == pair["reference_raw_status"]
                    entry["reason_correct"] = answer["reason_code"] == REASONS[root["id"]][state["id"]]
                    entry["scope_assertion"] = answer["records_only"] is True
                except (KeyError, ValueError, TypeError):
                    entry.update(answer=None, status_correct=False, reason_correct=False,
                                 scope_assertion=False)
                row["raw"][arm] = entry
        if real_recipient_arm and not row.get("stop_reason"):
            row["real_recipient"] = await real_recipient(root, state, corpus()["roots"], budget)
            if budget.stopped:
                row["stop_reason"] = "Shared provider budget or model identity stopped"
        results.append(row)
        if row.get("stop_reason"):
            break
    stopped = any("stop_reason" in row for row in results)
    return {"schema": SCHEMA, "phase": "developmental_live_pilot", "model_requested": model,
            "provider_identity": provider.identity(), "seed": seed,
            "provider_api": provider_api,
            "reasoning_effort": reasoning_effort,
            "runtime_versions": runtime_versions(),
            "states_per_root": states_per_root, "raw_arms": raw_arms,
            "real_recipient_arm": real_recipient_arm,
            "actual_provider_calls": budget.calls,
            "estimated_model_cost_usd": budget.cost_usd, "cost_limit_usd": max_cost_usd,
            "cost_basis": "undiscounted_configured_input_and_output_rates; cached token discounts and failed-call invoices unverified",
            "offline_manifest_sha256": offline["manifest_sha256"],
            "material_sha256": frozen_materials,
            "offline_parity": {"passed": offline["passed"], "pairs": offline["total"]},
            "results": results, "status": "stopped_partial" if stopped else "developmental_unreviewed",
            "reason_reference": REASONS,
            "interpretation": "System status parity, bound tool request adherence, recipient status fidelity, fixture-author reason categories and raw notation correctness are distinct. A true records_only field is a model assertion, not independently verified prose scope. These exposed synthetic tasks do not establish transfer or human reasoning benefit."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("preflight", help="Offline, unbilled parity and route audit")
    check.add_argument("--output", type=Path, required=True)
    live = sub.add_parser("run", help="Bounded, explicitly charged provider pilot")
    live.add_argument("--model", required=True)
    live.add_argument("--provider-api", choices=("responses", "chat_completions"),
                      default="responses")
    live.add_argument("--api-key-env", default="OPENAI_API_KEY")
    live.add_argument("--max-calls", type=int, required=True)
    live.add_argument("--max-cost-usd", type=float, required=True)
    live.add_argument("--input-usd-per-million", type=float, required=True)
    live.add_argument("--output-usd-per-million", type=float, required=True)
    live.add_argument("--max-output-tokens", type=int, default=256)
    live.add_argument("--reasoning-effort", choices=("none", "low", "medium"), default="none")
    live.add_argument("--states-per-root", type=int, default=2)
    live.add_argument("--seed", type=int, default=67453)
    live.add_argument("--no-raw-arms", action="store_true")
    live.add_argument("--no-real-recipient-arm", action="store_true")
    live.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "preflight":
        report = preflight()
    else:
        if not os.environ.get(args.api_key_env):
            raise SystemExit(f"{args.api_key_env} is absent; no provider call was attempted")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        freeze = args.output.with_suffix(args.output.suffix + ".freeze.json")
        journal = args.output.with_suffix(args.output.suffix + ".attempts.jsonl")
        if any(path.exists() for path in (args.output, freeze, journal)):
            raise SystemExit("Refusing to overwrite a retained pilot, freeze or attempt ledger")
        frozen = {"schema": SCHEMA, "model": args.model,
                  "provider_api": args.provider_api,
                  "runtime_versions": runtime_versions(),
                  "source_manifest_sha256": digest(MANIFEST),
                  "source_sha256": {root["id"]: digest(CORPUS / root["source"])
                                    for root in corpus()["roots"]},
                  "graph_sha256": {root_id: digest(GRAPH_DIR / f"{root_id}.json")
                                   for root_id in DESCRIPTIONS},
                  "reason_reference": REASONS, "seed": args.seed,
                  "reasoning_effort": args.reasoning_effort,
                  "states_per_root": args.states_per_root,
                  "raw_arms": not args.no_raw_arms,
                  "real_recipient_arm": not args.no_real_recipient_arm,
                  "max_calls": args.max_calls, "max_cost_usd": args.max_cost_usd,
                  "input_usd_per_million": args.input_usd_per_million,
                  "output_usd_per_million": args.output_usd_per_million,
                  "max_output_tokens": args.max_output_tokens,
                  "material_sha256": material_hashes(),
                  "planned_calls": 3 * args.states_per_root * (
                      3 + (2 if not args.no_raw_arms else 0)
                      + (2 if not args.no_real_recipient_arm else 0))}
        if args.max_calls < frozen["planned_calls"]:
            raise SystemExit("Call limit is below the fixed complete-pilot schedule")
        freeze.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report = asyncio.run(run_live(model=args.model, api_key_env=args.api_key_env,
                                      max_calls=args.max_calls, max_cost_usd=args.max_cost_usd,
                                      input_rate=args.input_usd_per_million,
                                      output_rate=args.output_usd_per_million,
                                      max_output_tokens=args.max_output_tokens,
                                      states_per_root=args.states_per_root, seed=args.seed,
                                      raw_arms=not args.no_raw_arms,
                                      real_recipient_arm=not args.no_real_recipient_arm,
                                      reasoning_effort=args.reasoning_effort,
                                      provider_api=args.provider_api, journal=journal,
                                      frozen_materials=frozen["material_sha256"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                           encoding="utf-8")
    print(json.dumps({"phase": report["phase"], "status": report["status"],
                      "output": str(args.output), "passed": report.get("passed"),
                      "provider_calls": report.get("actual_provider_calls")}, sort_keys=True))
    return 0 if report.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
