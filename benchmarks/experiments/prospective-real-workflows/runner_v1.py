"""Versioned, prospective four-arm runner; no cases or results ship with it.

The study runner accepts only an externally signed stage bundle for actual
pilot/retrospective/shadow work. `smoke` is deliberately ineligible for study
analysis and permits local fixture tests. No model controls a grant or a write.
"""

from __future__ import annotations

import asyncio
import copy
from dataclasses import asdict, dataclass
import hashlib
from importlib.metadata import version
import inspect
import json
from pathlib import Path
import random
import sys
import tempfile
import time
from typing import Any, Callable, Mapping, Protocol

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.equal_checker import evaluate as evaluate_graph  # noqa: E402
from eal.evaluator import canonical_digest, environment_fingerprint  # noqa: E402
from eal.methods import default_registry  # noqa: E402
from eal.parser import parse  # noqa: E402
from eal.providers import ModelResponse, ProviderError, response_cost  # noqa: E402
from eal.runtime import ReasoningService, strict_json  # noqa: E402

from gateway_v1 import (GitObjectReader, HTTPSJSONReader, ReadOnlyGateway,
                        canonical, digest, now, timestamp)  # noqa: E402
from ledger_v1 import AttemptLedger  # noqa: E402
from receipts_v1 import verify_stage  # noqa: E402


SCHEMA = "eal2-real-workflow-runner/1"
CASE_SCHEMA = "eal2-real-workflow-case/1"
ARMS = ("P", "T", "E", "J")
STATUSES = {"supported", "contested", "unsupported", "out_of_scope", "indeterminate"}


class AttemptError(ValueError):
    pass


@dataclass(frozen=True)
class Case:
    id: str
    family_id: str
    principal: str
    decision_cut: str
    brief: str
    scope: dict[str, Any]
    formal_query: dict[str, Any]
    reference_id: str
    fixed_calls: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if (not self.id or not self.family_id or not self.principal or not self.brief
                or not isinstance(self.scope, dict) or not self.scope
                or not isinstance(self.formal_query, dict) or not self.formal_query
                or not isinstance(self.reference_id, str) or not self.reference_id):
            raise ValueError("Case needs identity, principal, brief, query, reference and scope")
        timestamp(self.decision_cut)
        if any(not isinstance(call, dict) or set(call) != {"tool_id", "arguments"}
               or not isinstance(call["tool_id"], str) or not isinstance(call["arguments"], dict)
               for call in self.fixed_calls):
            raise ValueError("Fixed captures need exact tool IDs and argument objects")
        canonical(self.as_dict())

    def as_dict(self) -> dict:
        return {"schema": CASE_SCHEMA, "id": self.id, "family_id": self.family_id,
                "principal": self.principal, "decision_cut": self.decision_cut,
                "brief": self.brief, "scope": self.scope, "formal_query": self.formal_query,
                "reference_id": self.reference_id, "fixed_calls": list(self.fixed_calls)}


@dataclass(frozen=True)
class Limits:
    max_calls: int = 2
    max_tools: int = 3
    max_prompt_bytes: int = 64_000
    max_output_tokens: int = 2048
    max_response_bytes: int = 128_000
    max_cost_usd: float = 5.0
    max_wall_seconds: float = 90.0

    def __post_init__(self) -> None:
        if (not 1 <= self.max_calls <= 4 or not 0 <= self.max_tools <= 16
                or not 1024 <= self.max_prompt_bytes <= 256_000
                or not 1 <= self.max_output_tokens <= 8192
                or not 1024 <= self.max_response_bytes <= 1_000_000
                or not 0 < self.max_cost_usd <= 100
                or not 1 <= self.max_wall_seconds <= 3600):
            raise ValueError("Invalid finite study limits")


class Provider(Protocol):
    def identity(self) -> dict: ...
    async def complete(self, messages: list[dict[str, str]], max_output_tokens: int) -> ModelResponse: ...


class ArmPolicy(Protocol):
    id: str
    def system_prompt(self) -> str: ...
    def finalise(self, answer: Mapping, traces: list[dict], case: Case) -> dict: ...


class ProsePolicy:
    id = "P"

    def system_prompt(self) -> str:
        return ("Assess the engineering claim. Identify sources, exact query and scope, objections, "
                "uncertainty and an appropriate action. Return JSON with status, explanation and recommendation. "
                "Use the common read-only catalogue for evidence; do not assume records were obtained.")

    def finalise(self, answer: Mapping, traces: list[dict], case: Case) -> dict:
        status = answer.get("status")
        if status not in STATUSES:
            raise AttemptError("Prose response lacks a common decision status")
        return {"authoritative_status": status, "checked_status": None,
                "explanation": answer.get("explanation"),
                "recommendation": answer.get("recommendation"), "host_result": None}


class ToulminPolicy(ProsePolicy):
    id = "T"

    def system_prompt(self) -> str:
        return ("Assess the engineering claim. Give one line each for Claim, Grounds, Warrant, "
                "Backing, Qualifier and Rebuttal. Return JSON with status, explanation and recommendation, "
                "including those six fields. Use the common read-only catalogue and exact query/scope.")

    def finalise(self, answer: Mapping, traces: list[dict], case: Case) -> dict:
        for key in ("claim", "grounds", "warrant", "backing", "qualifier", "rebuttal"):
            if not isinstance(answer.get(key), str):
                raise AttemptError(f"Toulmin response lacks {key}")
        return super().finalise(answer, traces, case)


def _matching_trace(traces: list[dict], tool: str, version: str, mode: str,
                    input_data: Any, case: Case) -> dict | None:
    candidates = [trace for trace in traces if trace.get("tool_id") == tool
                  and trace.get("tool_version") == version and trace.get("mode") == mode
                  and trace.get("arguments") == input_data]
    if len(candidates) > 1:
        raise AttemptError("Ambiguous repeated acquisition for one declared evidence")
    if not candidates:
        return None
    trace = candidates[0]
    if (trace.get("schema") != "eal2-real-tool-trace/1"
            or trace.get("case_id") != case.id
            or trace.get("case_family_id") != case.family_id
            or trace.get("principal") != case.principal
            or trace.get("decision_cut") != case.decision_cut):
        raise AttemptError("Tool trace has the wrong case identity or decision cut")
    if trace.get("status") == "ok":
        if (trace.get("value_sha256") != digest(trace.get("value"))
                or timestamp(trace.get("observed_at")) > timestamp(case.decision_cut)):
            raise AttemptError("Tool trace digest or observation time is invalid")
    return trace


class EAL2Host:
    """Use the installed EAL/2 ReasoningService with gateway-captured records."""

    def check(self, source: str, claim: str, traces: list[dict], case: Case) -> dict:
        with tempfile.TemporaryDirectory(prefix="eal-study-assess-") as temporary:
            service = ReasoningService(temporary, database_path=Path(temporary) / "runs.sqlite3")
            validation = service.validate(source)
            if not validation["valid"]:
                raise AttemptError("Invalid EAL/2 source: " + json.dumps(validation["diagnostics"]))
            program = parse(source)
            if claim not in program.claims:
                raise AttemptError("Authored claim selection is absent from the source")
            records: dict[str, dict] = {}
            for name, evidence in program.evidence.items():
                tool = program.tools[evidence.tool]
                trace = _matching_trace(traces, tool.name, tool.version, tool.mode,
                                        evidence.input, case)
                if trace is None or trace["status"] != "ok":
                    continue
                records[name] = {
                    "evidence_id": name, "source_digest": program.source_digest,
                    "tool": tool.name, "tool_version": tool.version, "mode": tool.mode,
                    "evidence_kind": evidence.kind, "environment": evidence.environment,
                    "environment_fingerprint": environment_fingerprint(evidence.environment, case.scope),
                    "input_digest": canonical_digest(evidence.input),
                    "run_id": digest(trace), "status": "ok",
                    "collected_at": trace["observed_at"], "value": trace["value"],
                    "data_digest": canonical_digest(trace["value"]),
                }
            collection_id = service.store.put("collection", {
                "source_digest": program.source_digest, "context": case.scope, "records": records})
            result = service.reason(source, case.scope, collection_id=collection_id, now=case.decision_cut)
            return {"status": result["claims"][claim]["status"],
                    "source_digest": program.source_digest,
                    "method_registry_fingerprint": result["method_registry_fingerprint"],
                    "assessment": {key: value for key, value in result.items()
                                   if key not in {"assessment_id", "collection_id"}}}


class EALPolicy:
    id = "E"

    def __init__(self, host: EAL2Host | None = None):
        self.host = host or EAL2Host()

    def system_prompt(self) -> str:
        return ("Select an argument family and author EAL/2 source for the engineering claim, "
                "its exact query and scope, evidence and live objections. Return JSON with source, "
                "claim (the authored claim name), explanation and recommendation. The host checks "
                "the final status; your status text cannot replace it.")

    def finalise(self, answer: Mapping, traces: list[dict], case: Case) -> dict:
        source, claim = answer.get("source"), answer.get("claim")
        if not isinstance(source, str) or not isinstance(claim, str):
            raise AttemptError("EAL/2 source authoring or claim selection failed")
        checked = self.host.check(source, claim, traces, case)
        return {"authoritative_status": checked["status"], "checked_status": checked["status"],
                "explanation": answer.get("explanation"),
                "recommendation": answer.get("recommendation"), "host_result": checked}


class GenericGraphHost:
    """Invoke the repository's independent JSON argument graph checker."""

    def check(self, graph: Mapping, traces: list[dict], case: Case) -> dict:
        evidence = {}
        for name, contract in graph.get("evidence", {}).items():
            trace = _matching_trace(traces, name, contract["tool_version"],
                                    contract["mode"], contract.get("input", {}), case)
            if trace is None or trace["status"] != "ok":
                continue
            evidence[name] = {"context": case.scope, "observed_at": trace["observed_at"],
                              "request": {"context": case.scope, "tool": name,
                                          "tool_version": trace["tool_version"],
                                          "mode": trace["mode"], "input": trace["arguments"]},
                              "value": trace["value"]}
        result = evaluate_graph(graph, evidence, case.decision_cut)
        return result.as_dict()


class GenericPolicy:
    id = "J"

    def __init__(self, host: GenericGraphHost | None = None):
        self.host = host or GenericGraphHost()

    def system_prompt(self) -> str:
        return ("Select and author a generic JSON argument graph for the claim, exact query, scope, "
                "evidence, alternative routes and objections. Return JSON with graph, explanation and "
                "recommendation. The independent checker owns the final status.")

    def finalise(self, answer: Mapping, traces: list[dict], case: Case) -> dict:
        graph = answer.get("graph")
        if not isinstance(graph, dict):
            raise AttemptError("JSON argument graph authoring failed")
        checked = self.host.check(graph, traces, case)
        return {"authoritative_status": checked["status"], "checked_status": checked["status"],
                "explanation": answer.get("explanation"),
                "recommendation": answer.get("recommendation"), "host_result": checked}


def default_policies() -> dict[str, ArmPolicy]:
    return {policy.id: policy for policy in
            (ProsePolicy(), ToulminPolicy(), EALPolicy(), GenericPolicy())}


def policy_manifest(policies: Mapping[str, ArmPolicy]) -> dict:
    """Pin injected implementations and their state to a signed parity review."""
    if set(policies) != set(ARMS):
        raise AttemptError("Real stage requires one policy per core arm")

    def implementation(value: object, *, exclude_host: bool = False) -> dict:
        source = inspect.getsourcefile(type(value))
        if not source or not Path(source).is_file():
            raise AttemptError("Policy/checker has no reviewable implementation file")
        state = {key: item for key, item in vars(value).items() if key != "host"} if exclude_host else vars(value)
        try:
            state_digest = digest(state)
        except (TypeError, ValueError, UnicodeError) as exc:
            raise AttemptError("Policy/checker configuration is not finite JSON") from exc
        return {"class": f"{type(value).__module__}.{type(value).__qualname__}",
                "source_sha256": digest(Path(source).read_bytes()),
                "configuration_sha256": state_digest}

    source_files = [*sorted((ROOT / "src/eal").rglob("*.py")),
                    ROOT / "benchmarks/equal_checker.py", ROOT / "pyproject.toml",
                    *sorted((ROOT / "benchmarks/experiments/prospective-real-workflows").glob("*_v1.py"))]
    files = {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in source_files}
    arms = []
    for arm in ARMS:
        policy = policies[arm]
        if policy.id != arm or not callable(getattr(policy, "finalise", None)):
            raise AttemptError("Injected arm identity or finaliser differs from the required arm")
        host = getattr(policy, "host", None)
        if arm in {"E", "J"} and (host is None or not callable(getattr(host, "check", None))):
            raise AttemptError("Checked arm has no reviewable host implementation")
        arms.append({"id": arm, "implementation": implementation(policy, exclude_host=True),
                     "system_prompt_sha256": digest(policy.system_prompt().encode("utf-8")),
                     "checker": implementation(host) if arm in {"E", "J"} else None})
    return {"schema": "eal2-real-arm-parity/1", "arms": arms, "source_sha256": files,
        "dependency_versions": {name: version(name) for name in
                                ("antlr4-python3-runtime", "cryptography", "httpx")},
        "method_registry_fingerprint": default_registry().fingerprint}


def authorise_stage(*, stage: str, case: Case, model_id: str, gateway: ReadOnlyGateway,
                    actual_policies: Mapping[str, ArmPolicy],
                    receipt_bundle: Mapping, receipt_root: Path,
                    trust_roster: Mapping, plan_path: Path,
                    limits: Limits = Limits(), acquisition: str = "fixed_capture",
                    repetition: int = 0, seed: int = 0) -> dict:
    plan = plan_path.read_bytes()
    execution_plan = strict_json(plan.decode("utf-8"))
    expected_status = {"feasibility_pilot": "pilot_ready",
                       "retrospective_execution": "retrospective_ready",
                       "prospective_shadow": "shadow_ready"}.get(stage)
    if (not isinstance(execution_plan, dict)
            or execution_plan.get("schema") != "eal2-real-workflow-execution-plan/1"
            or execution_plan.get("investigation_id") != "INV-EAL-REAL-001"
            or execution_plan.get("stage") != stage
            or execution_plan.get("status") != expected_status
            or execution_plan.get("supersedes_spec_sha256") != digest(
                (Path(__file__).with_name("plan.json")).read_bytes())):
        raise AttemptError("A separately versioned ready execution plan must supersede the pending specification")
    assignment = {"case_id": case.id, "model_id": model_id, "acquisition": acquisition,
                  "repetition": repetition, "seed": seed}
    if (execution_plan.get("limits") != asdict(limits)
            or not isinstance(execution_plan.get("schedule"), list)
            or execution_plan["schedule"].count(assignment) != 1):
        raise AttemptError("Runtime limits or assignment differ from the signed execution plan")
    if stage in {"retrospective_execution", "prospective_shadow"}:
        analysis = execution_plan.get("analysis", {})
        for key in ("family_count_confirmatory", "practical_gain_margin",
                    "false_support_margin", "minimum_decision_coverage"):
            if analysis.get(key) is None:
                raise AttemptError("Frozen analysis margins and family count are missing")
    details = verify_stage(stage=stage, bundle=receipt_bundle, root=receipt_root,
                           trust_roster=trust_roster, plan_bytes=plan)
    if stage in {"retrospective_execution", "prospective_shadow"}:
        schedule = receipt_bundle["artifacts"]["frozen_schedule_sha256"]
        signed_schedule = strict_json((receipt_root / schedule["path"]).read_text(encoding="utf-8"))
        if (signed_schedule.get("schema") != "eal2-real-schedule/1"
                or signed_schedule.get("entries") != execution_plan["schedule"]):
            raise AttemptError("Runtime assignment schedule differs from the signed frozen schedule")
    manifest = receipt_bundle["artifacts"]["independent_case_manifest_sha256"]
    cases = strict_json((receipt_root / manifest["path"]).read_text(encoding="utf-8"))
    if not isinstance(cases, dict) or cases.get("schema") != "eal2-real-case-manifest/1":
        raise AttemptError("Signed case manifest has an unknown schema")
    if (cases.get("stage") != stage or sum(entry == case.as_dict() for entry in cases.get("cases", [])) != 1):
        raise AttemptError("Case is absent or duplicated in signed independent manifest")
    reference = receipt_bundle["artifacts"]["reference_review_sha256"]
    review = strict_json((receipt_root / reference["path"]).read_text(encoding="utf-8"))
    if (not isinstance(review, dict) or review.get("schema") != "eal2-real-reference-review/1"
            or not isinstance(review.get("entries"), list)):
        raise AttemptError("Signed reference review has an unknown schema")
    matches = [entry for entry in review["entries"] if isinstance(entry, dict)
               and entry.get("case_id") == case.id]
    if (len(matches) != 1 or matches[0].get("reference_id") != case.reference_id
            or matches[0].get("case_sha256") != digest(case.as_dict())):
        raise AttemptError("Signed reference review does not bind this exact case and reference")
    allowlist = receipt_bundle["artifacts"]["tool_allowlist_and_isolation_sha256"]
    signed_tools = strict_json((receipt_root / allowlist["path"]).read_text(encoding="utf-8"))
    if not isinstance(signed_tools, dict) or signed_tools.get("schema") != "eal2-real-tool-allowlist/1":
        raise AttemptError("Signed tool allowlist has an unknown schema")
    if signed_tools.get("grants") != gateway.signed_spec()["grants"]:
        raise AttemptError("Runtime grants differ from the signed tool allowlist")
    if not isinstance(signed_tools.get("operator_isolation"), dict) or not signed_tools["operator_isolation"]:
        raise AttemptError("Signed allowlist omits the operator isolation declaration")
    parity = receipt_bundle["artifacts"]["prompt_and_method_parity_sha256"]
    signed_parity = strict_json((receipt_root / parity["path"]).read_text(encoding="utf-8"))
    if signed_parity != policy_manifest(actual_policies):
        raise AttemptError("Runtime arms, prompts or checker versions differ from signed parity review")
    models = receipt_bundle["artifacts"]["model_snapshot_manifest_sha256"]
    model_manifest = strict_json((receipt_root / models["path"]).read_text(encoding="utf-8"))
    if model_manifest.get("schema") != "eal2-real-model-matrix/1":
        raise AttemptError("Signed model matrix has an unknown schema")
    matches = [item for item in model_manifest.get("models", []) if item.get("id") == model_id]
    if (len(matches) != 1 or not isinstance(matches[0].get("identity_sha256"), str)
            or len(matches[0]["identity_sha256"]) != 64
            or not isinstance(matches[0].get("resolved_model"), str)):
        raise AttemptError("Model is absent from the signed snapshot matrix")
    details["model_identity_sha256"] = matches[0]["identity_sha256"]
    details["resolved_model"] = matches[0]["resolved_model"]
    return details


class ProspectiveRunner:
    def __init__(self, *, gateway: ReadOnlyGateway, provider_factory: Callable[[str], Provider],
                 ledger: AttemptLedger, limits: Limits, policies: Mapping[str, ArmPolicy] | None = None):
        self.gateway, self.provider_factory, self.ledger, self.limits = gateway, provider_factory, ledger, limits
        self.policies = dict(default_policies() if policies is None else policies)
        if set(self.policies) != set(ARMS) or any(key != policy.id for key, policy in self.policies.items()):
            raise ValueError("Injected policies must implement exactly P/T/E/J")

    async def run_case(self, *, case: Case, model_id: str, stage: str,
                       acquisition: str, repetition: int = 0, seed: int = 0,
                       receipt_bundle: Mapping | None = None, receipt_root: Path | None = None,
                       trust_roster: Mapping | None = None, plan_path: Path | None = None) -> list[dict]:
        if acquisition not in {"fixed_capture", "selected_acquisition"}:
            raise ValueError("Acquisition comparisons must be separate")
        if stage != "smoke":
            expected = {"git_object": GitObjectReader, "https_json_get": HTTPSJSONReader}
            if (set(self.gateway.readers) != set(expected)
                    or any(type(self.gateway.readers[name]) is not cls for name, cls in expected.items())):
                raise AttemptError("Real study stages require the reviewed built-in reader implementations")
            if any(value is None for value in (receipt_bundle, receipt_root, trust_roster, plan_path)):
                raise AttemptError("Signed external stage prerequisites are required before calls")
            receipt = authorise_stage(stage=stage, case=case, model_id=model_id,
                                      gateway=self.gateway, actual_policies=self.policies,
                                      receipt_bundle=receipt_bundle, receipt_root=receipt_root,
                                      trust_roster=trust_roster, plan_path=plan_path,
                                      limits=self.limits, acquisition=acquisition,
                                      repetition=repetition, seed=seed)
        else:
            receipt = {"ineligible_fixture": True}
            if any(grant.adapter != "git_object" for grant in self.gateway.grants.values()):
                raise AttemptError("Smoke fixtures may execute only local pinned Git reads")
        if type(repetition) is not int or repetition < 0:
            raise ValueError("Repetition must be a nonnegative integer")
        order = list(ARMS)
        random.Random(digest({"seed": seed, "case": case.id, "model": model_id,
                              "repetition": repetition, "acquisition": acquisition})).shuffle(order)
        assignments = []
        starts = []
        for arm in order:
            assignment = {"stage": stage, "case_id": case.id, "family_id": case.family_id,
                          "model_id": model_id, "arm": arm, "repetition": repetition,
                          "acquisition": acquisition, "runner_schema": SCHEMA}
            attempt_id = digest(assignment)
            starts.append({"kind": "start", "attempt_id": attempt_id,
                           "assigned_at": now(), "assignment": assignment,
                           "randomisation_seed": seed, "arm_order": order,
                           "limits": asdict(self.limits),
                           "case_sha256": digest(case.as_dict()), "stage_receipts": receipt})
            assignments.append((attempt_id, arm))
        self.ledger.reserve_block(starts)
        capture: list[dict] = []
        if acquisition == "fixed_capture":
            # Execute once; all four arms receive identical bytes, identity,
            # and failure traces. A failed fixed call stays in all four rows.
            for call in case.fixed_calls:
                capture.append(self.gateway.capture(
                    case_id=case.id, family_id=case.family_id, principal=case.principal,
                    decision_cut=case.decision_cut, stage=stage,
                    tool_id=call["tool_id"], arguments=call["arguments"]))
        results = []
        for attempt_id, arm in assignments:
            result = await self._one(copy.deepcopy(case), model_id, stage,
                                     acquisition, arm, capture, receipt)
            self.ledger.append({"kind": "outcome", "attempt_id": attempt_id,
                                "finished_at": now(), "result": result})
            results.append({"attempt_id": attempt_id, "arm": arm, **result})
        return results

    async def _one(self, case: Case, model_id: str, stage: str, acquisition: str,
                   arm: str, capture: list[dict], receipt: dict) -> dict:
        policy = self.policies[arm]
        traces = strict_json(canonical(capture).decode("utf-8"))
        calls: list[dict] = []
        start = time.monotonic()
        outcome = {"status": "failed", "error": None, "tool_traces": traces,
                   "model_calls": calls, "raw_answer": None, "authoritative": None,
                   "elapsed_seconds": None, "simulated_fixture": stage == "smoke",
                   "tool_cost_usd": None, "human_review_minutes": None}
        try:
            provider = self.provider_factory(model_id)  # Fresh provider/session per assigned arm.
            identity = provider.identity()
            if stage != "smoke" and digest(identity) != receipt.get("model_identity_sha256"):
                raise AttemptError("Provider identity drifted after the signed gate")
            outcome["model_identity"] = {key: identity[key] for key in
                                         ("provider", "adapter", "model", "sampling", "pricing",
                                          "measurement_kind", "capabilities", "command_digest") if key in identity}
            if identity.get("measurement_kind") == "interface_only" and stage != "smoke":
                raise AttemptError("Interface-only provider cannot supply a model trial")
            if not {"input_usd_per_million", "output_usd_per_million"} <= identity.get("pricing", {}).keys():
                raise AttemptError("Model pricing is required before a bounded call")
            catalogue = self.gateway.catalogue(case.principal, case.id)
            common = {"question": case.brief, "scope": case.scope,
                      "formal_query": case.formal_query,
                      "decision_cut": case.decision_cut, "tools": catalogue,
                      "acquisition": acquisition}
            if acquisition == "selected_acquisition":
                if self.limits.max_calls < 2:
                    raise AttemptError("Selected acquisition requires two bounded model calls")
                selected = await self._complete(provider, identity, calls, policy.system_prompt(),
                                                {**common, "task": "Select read-only tool calls as JSON {calls:[{tool_id,arguments}]}.",
                                                 "max_tools": self.limits.max_tools}, start,
                                                receipt.get("resolved_model"))
                requested = strict_json(selected)
                proposals = requested.get("calls") if isinstance(requested, dict) else None
                if (not isinstance(proposals, list) or len(proposals) > self.limits.max_tools
                        or any(not isinstance(call, dict) or set(call) != {"tool_id", "arguments"}
                               for call in proposals)):
                    raise AttemptError("Model tool-selection response is invalid or exceeds the equal limit")
                for call in proposals:
                    traces.append(self.gateway.capture(
                        case_id=case.id, family_id=case.family_id, principal=case.principal,
                        decision_cut=case.decision_cut, stage=stage,
                        tool_id=call["tool_id"], arguments=call["arguments"]))
            answer_text = await self._complete(provider, identity, calls, policy.system_prompt(),
                                               {**common, "task": "Give the final arm response as a JSON object.",
                                                "records": traces}, start, receipt.get("resolved_model"))
            outcome["raw_answer"] = answer_text
            answer = strict_json(answer_text)
            if not isinstance(answer, dict):
                raise AttemptError("Final response is not a JSON object")
            authoritative = policy.finalise(answer, traces, case)
            outcome.update(status="completed", authoritative=authoritative,
                           case_claim_correspondence="requires_independent_adjudication",
                           reference_id=case.reference_id)
        except Exception as exc:
            outcome["error"] = {"type": type(exc).__name__,
                                "message": str(exc) if isinstance(exc, (AttemptError, ValueError))
                                else "Attempt failed; inspect the retained call and trace identities"}
            if isinstance(exc, ProviderError) and isinstance(exc.response, ModelResponse):
                failure_usage = {"input_tokens": exc.response.input_tokens,
                                 "output_tokens": exc.response.output_tokens,
                                 "model": exc.response.model,
                                 "cached_input_tokens": exc.response.metadata.get("cached_input_tokens"),
                                 "cost_usd": response_cost(exc.response, locals().get("identity", {}))}
                if calls:
                    calls[-1]["provider_failure_usage"] = failure_usage
                else:
                    calls.append({"provider_failure_usage": failure_usage})
        outcome["elapsed_seconds"] = time.monotonic() - start
        return outcome

    async def _complete(self, provider: Provider, identity: dict, calls: list[dict],
                        system: str, payload: dict, start: float,
                        expected_model: str | None) -> str:
        if len(calls) >= self.limits.max_calls:
            raise AttemptError("Model call ceiling reached")
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": canonical(payload).decode("utf-8")}]
        if len(canonical(messages)) > self.limits.max_prompt_bytes:
            raise AttemptError("Prompt byte ceiling reached")
        if time.monotonic() - start >= self.limits.max_wall_seconds:
            raise AttemptError("Attempt wall-time ceiling reached")
        prior_tokens = sum(row.get("output_tokens") or 0 for row in calls)
        remaining = self.limits.max_output_tokens - prior_tokens
        if remaining <= 0:
            raise AttemptError("Output token ceiling reached")
        row: dict[str, Any] = {"messages": messages, "requested_output_tokens": remaining,
                               "started_at": now(), "response": None, "error": None}
        calls.append(row)
        try:
            response = await asyncio.wait_for(provider.complete(messages, remaining),
                                              self.limits.max_wall_seconds - (time.monotonic() - start))
            if not isinstance(response, ModelResponse):
                raise AttemptError("Provider returned an invalid response object")
            row.update(input_tokens=response.input_tokens, output_tokens=response.output_tokens,
                       resolved_model=response.model,
                       metadata={key: response.metadata[key] for key in
                                 ("cached_input_tokens", "request_id", "finish_reason")
                                 if key in response.metadata},
                       cost_usd=response_cost(response, identity))
            response_bytes = response.text.encode("utf-8")
            if len(response_bytes) > self.limits.max_response_bytes:
                row.update(response_bytes=len(response_bytes), response_sha256=digest(response_bytes))
                raise AttemptError("Provider response exceeded the byte ceiling")
            row["response"] = response.text
            if expected_model is not None and response.model != expected_model:
                raise AttemptError("Resolved model differs from the signed snapshot")
            if response.output_tokens is None or row["cost_usd"] is None:
                raise AttemptError("Provider usage or configured price is unavailable")
            if response.output_tokens > remaining:
                raise AttemptError("Provider exceeded output token ceiling")
            if sum(item.get("cost_usd") or 0 for item in calls) > self.limits.max_cost_usd:
                raise AttemptError("Model cost ceiling exceeded")
            return response.text
        except Exception as exc:
            row["error"] = type(exc).__name__
            raise
        finally:
            row["finished_at"] = now()
