"""One-attempt, four-arm prospective runner for reviewed GitHub workflow cases.

There are no enrolled or scored cases in this package. Real stages require an
externally reviewed ready execution plan and signed receipts; the bundled study
specification remains `specified_not_ready`.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
import inspect
import json
from pathlib import Path
import random
import sys
import time
from typing import Any, Callable, Mapping, Protocol

PROJECT = Path(__file__).resolve().parents[2]
if str(PROJECT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT / "src"))
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

from eal.providers import ModelResponse, ProviderError, load_provider, response_cost  # noqa: E402
from eal.runtime import strict_json  # noqa: E402

from json_frontend_v1 import compile_json, frontend_contract  # noqa: E402
from ledger_v1 import AttemptLedger  # noqa: E402
from mcp_host_v1 import MCPHost  # noqa: E402
from preflight_v1 import preflight  # noqa: E402
from protocol_v1 import Case, ToolGateway, canonical, digest, now  # noqa: E402


SCHEMA = "eal2-ci-prospective-runner/1"
ARMS = ("P", "T", "J", "E")
STATUSES = {"supported", "contested", "unsupported", "out_of_scope", "indeterminate"}
TOULMIN = ("claim", "grounds", "warrant", "backing", "qualifier", "rebuttal")
PHASE_INSTRUCTIONS = {
    "select_and_author": {
        "P": "First response only: select permitted read-only evidence. Return exactly one JSON object {\"calls\":[{\"tool_id\":\"...\",\"arguments\":{...}}]}. Do not state a decision yet.",
        "T": "First response only: select permitted read-only evidence. Return exactly one JSON object {\"calls\":[{\"tool_id\":\"...\",\"arguments\":{...}}]}. Do not state a decision yet.",
        "E": "First response only: author valid EAL/2 source using direct declarations and select one authored claim. Return exactly one JSON object {\"source\":\"...\",\"claim\":\"...\"}. The host will run actual MCP validation, collection, reasoning and explanation before your final answer.",
        "J": "First response only: author the versioned eal2-ci-json-frontend/1 typed declaration object and select one claim. Return exactly one JSON object {\"program\":{...},\"claim\":\"...\"}. This JSON compiles to the same EAL/2 typed program and runs through the same MCP host.",
    },
    "communicate_decision": {
        "P": "Final response only: use the returned tool records to give one JSON object with status, recommendation and explanation prose. Status must be supported, contested, unsupported, out_of_scope or indeterminate.",
        "T": "Final response only: give one JSON object with status, recommendation, explanation and six one-line strings: claim, grounds, warrant, backing, qualifier, rebuttal.",
        "E": "Final response only: use the checked MCP result to give one JSON object with recommendation and explanation; optional status text is untrusted. The application will show the host-owned checked status.",
        "J": "Final response only: use the checked MCP result to give one JSON object with recommendation and explanation; optional status text is untrusted. The application will show the host-owned checked status.",
    },
}


class AttemptError(ValueError):
    pass


@dataclass(frozen=True)
class Limits:
    max_model_calls: int = 2
    max_tool_calls: int = 3
    max_prompt_bytes: int = 64_000
    max_response_bytes: int = 128_000
    max_output_tokens: int = 4096
    max_wall_seconds: float = 120
    max_cost_usd: float = 5

    def __post_init__(self):
        if (self.max_model_calls != 2 or type(self.max_tool_calls) is not int
                or not 1 <= self.max_tool_calls <= 12 or not 1024 <= self.max_prompt_bytes <= 256_000
                or not 1024 <= self.max_response_bytes <= 1_000_000
                or not 128 <= self.max_output_tokens <= 16384
                or not 1 <= self.max_wall_seconds <= 3600 or not 0 < self.max_cost_usd <= 100):
            raise ValueError("Invalid finite study limits")


class Provider(Protocol):
    def identity(self) -> dict: ...
    async def complete(self, messages: list[dict[str, str]], max_output_tokens: int) -> ModelResponse: ...


@dataclass(frozen=True)
class Prepared:
    calls: tuple[dict[str, Any], ...] = ()
    source: str | None = None
    claim: str | None = None
    semantic_ir: dict | None = None


class ArmPolicy(Protocol):
    id: str
    prompt: str
    def prepare(self, answer: dict, case: Case, gateway: ToolGateway, max_tools: int) -> Prepared: ...
    def finalise(self, answer: dict, host: dict | None) -> dict: ...


class ProsePolicy:
    id = "P"

    def __init__(self, prompt: str):
        self.prompt = prompt

    def prepare(self, answer: dict, case: Case, gateway: ToolGateway, max_tools: int) -> Prepared:
        calls = answer.get("calls")
        if (type(calls) is not list or not 1 <= len(calls) <= max_tools
                or any(type(call) is not dict or set(call) != {"tool_id", "arguments"}
                       or type(call["tool_id"]) is not str for call in calls)):
            raise AttemptError("Model did not select bounded read-only calls")
        for call in calls:
            gateway.authorise(case, call["tool_id"], call["arguments"])
        return Prepared(calls=tuple(calls))

    def finalise(self, answer: dict, host: dict | None) -> dict:
        if (answer.get("status") not in STATUSES
                or type(answer.get("recommendation")) is not str
                or type(answer.get("explanation")) is not str):
            raise AttemptError("Prose answer lacks status, recommendation or explanation")
        return {"authoritative_status": answer["status"], "checked_status": None,
                "recommendation": answer["recommendation"],
                "explanation": answer["explanation"]}


class ToulminPolicy(ProsePolicy):
    id = "T"

    def finalise(self, answer: dict, host: dict | None) -> dict:
        if any(type(answer.get(key)) is not str or "\n" in answer[key] for key in TOULMIN):
            raise AttemptError("Toulmin response lacks six one-line fields")
        return {**super().finalise(answer, host),
                "toulmin": {key: answer[key] for key in TOULMIN}}


class EALPolicy:
    id = "E"

    def __init__(self, prompt: str):
        self.prompt = prompt

    def prepare(self, answer: dict, case: Case, gateway: ToolGateway, max_tools: int) -> Prepared:
        source, claim = answer.get("source"), answer.get("claim")
        if type(source) is not str or type(claim) is not str:
            raise AttemptError("EAL source authoring or claim selection failed")
        gateway.authorise_source(case, source, claim)
        from eal.parser import parse
        if len(parse(source).evidence) > max_tools:
            raise AttemptError("EAL source exceeds the equal tool-call limit")
        return Prepared(source=source, claim=claim)

    def finalise(self, answer: dict, host: dict | None) -> dict:
        if host is None:
            raise AttemptError("EAL host packet is absent")
        if type(answer.get("recommendation")) is not str or type(answer.get("explanation")) is not str:
            raise AttemptError("EAL response lacks a recommendation or explanation")
        return {"authoritative_status": host["status"], "checked_status": host["status"],
                "recommendation": answer["recommendation"],
                "explanation": answer["explanation"],
                "raw_model_status": answer.get("status")}


class JSONPolicy(EALPolicy):
    id = "J"

    def prepare(self, answer: dict, case: Case, gateway: ToolGateway, max_tools: int) -> Prepared:
        if type(answer.get("program")) is not dict or type(answer.get("claim")) is not str:
            raise AttemptError("JSON typed program or claim selection failed")
        source, meaning = compile_json(answer["program"])
        gateway.authorise_source(case, source, answer["claim"])
        from eal.parser import parse
        if len(parse(source).evidence) > max_tools:
            raise AttemptError("JSON source exceeds the equal tool-call limit")
        return Prepared(source=source, claim=answer["claim"], semantic_ir=meaning)


def default_policies(study_dir: Path) -> dict[str, ArmPolicy]:
    classes = {"P": ProsePolicy, "T": ToulminPolicy, "J": JSONPolicy, "E": EALPolicy}
    return {key: cls((study_dir / "arms" / f"{key}.md").read_text(encoding="utf-8"))
            for key, cls in classes.items()}


def policy_manifest(policies: Mapping[str, ArmPolicy]) -> dict:
    if set(policies) != set(ARMS) or any(policies[key].id != key for key in ARMS):
        raise AttemptError("Four injected P/T/J/E policies are mandatory")
    files = [Path(__file__), Path(__file__).with_name("json_frontend_v1.py"),
             Path(__file__).with_name("mcp_host_v1.py")]
    arms = []
    for key in ARMS:
        policy = policies[key]
        path = inspect.getsourcefile(type(policy))
        if path is None or not Path(path).is_file() or not callable(getattr(policy, "prepare", None)):
            raise AttemptError("Injected policy has no reviewable implementation")
        try:
            state = digest(vars(policy))
        except (ValueError, TypeError):
            raise AttemptError("Injected policy state needs finite JSON") from None
        arms.append({"id": key, "class": f"{type(policy).__module__}.{type(policy).__qualname__}",
                     "source_sha256": digest(Path(path).read_bytes()),
                     "state_sha256": state,
                     "prompt_sha256": digest(policy.prompt.encode("utf-8"))})
    from eal.discovery import describe_language
    eal_source = PROJECT / "src" / "eal"
    package_files = {str(path.relative_to(PROJECT)): digest(path.read_bytes())
                     for path in sorted(eal_source.rglob("*.py"))} if eal_source.is_dir() else {}
    return {"schema": "eal2-ci-arm-parity/1", "arms": arms,
            "mcp_language_contract_sha256": digest(describe_language()),
            "json_frontend_contract_sha256": digest(frontend_contract()),
            "backend_source_sha256": package_files,
            "host_files": {path.name: digest(path.read_bytes()) for path in files}}


class ProspectiveRunner:
    def __init__(self, *, gateway: ToolGateway, provider_factory: Callable[[str], Provider],
                 ledger: AttemptLedger, policies: Mapping[str, ArmPolicy],
                 limits: Limits = Limits(), host: MCPHost | None = None):
        policy_manifest(policies)
        self.gateway, self.provider_factory, self.ledger = gateway, provider_factory, ledger
        self.policies, self.limits = dict(policies), limits
        self.host = host or MCPHost(gateway)

    async def run_case(self, *, case: Case, model_id: str, stage: str,
                       repetition: int = 0, seed: int = 0,
                       study_path: Path | None = None, execution_path: Path | None = None,
                       bundle_path: Path | None = None, receipt_root: Path | None = None,
                       trust_roster: Mapping | None = None) -> list[dict]:
        if type(repetition) is not int or repetition < 0 or type(seed) is not int:
            raise ValueError("Repetition and seed must be integers")
        if stage not in {"smoke", "pilot", "retrospective", "prospective_shadow"}:
            raise ValueError("Unknown study stage")
        assignment = {"stage": stage, "case_id": case.id, "model_id": model_id,
                      "repetition": repetition, "seed": seed, "acquisition": "selected_acquisition"}
        provider = self.provider_factory(model_id)
        identity = provider.identity()
        if stage != "smoke":
            if any(value is None for value in (study_path, execution_path, bundle_path,
                                               receipt_root, trust_roster)):
                raise AttemptError("Reviewed ready stage and signed receipts are required")
            receipt = preflight(stage=stage, case=case, model_id=model_id, assignment=assignment,
                                study_path=study_path, execution_path=execution_path,
                                bundle_path=bundle_path, receipt_root=receipt_root,
                                trust_roster=trust_roster,
                                arm_manifest=policy_manifest(self.policies),
                                registry_sha256=digest(self.gateway.registry_path.read_bytes()),
                                tool_manifest=self.gateway.catalogue(case),
                                provider_identity=identity)
            if identity.get("measurement_kind") == "interface_only":
                raise AttemptError("An interface-only provider is ineligible for a real model trial")
        else:
            receipt = {"ineligible_synthetic_smoke": True}
        order = list(ARMS)
        random.Random(digest({"assignment": assignment})).shuffle(order)
        starts = []
        attempts = []
        for arm in order:
            unit = {key: value for key, value in assignment.items() if key != "seed"}
            unit.update(arm=arm, schema=SCHEMA)
            attempt_id = digest(unit)
            starts.append({"kind": "start", "attempt_id": attempt_id,
                           "assigned_at": now(), "assignment": unit,
                           "seed": seed, "order": order, "case_sha256": digest(case.as_dict()),
                           "model_identity_sha256": digest(identity),
                           "limits": asdict(self.limits), "stage_receipts": receipt})
            attempts.append((attempt_id, arm))
        self.ledger.reserve_block(starts)
        outcomes = []
        for attempt_id, arm in attempts:
            # A new provider/session per arm; the frozen identity must remain.
            result = await self._one(case, model_id, arm, digest(identity), stage)
            self.ledger.append({"kind": "outcome", "attempt_id": attempt_id,
                                "finished_at": now(), "result": result})
            outcomes.append({"attempt_id": attempt_id, "arm": arm, **result})
        return outcomes

    async def _one(self, case: Case, model_id: str, arm: str, identity_digest: str, stage: str) -> dict:
        start = time.monotonic()
        model_calls: list[dict] = []
        traces: list[dict] = []
        checked = None
        result = {"status": "failed", "error": None, "model_calls": model_calls,
                  "tool_traces": traces, "host_result": None,
                  "raw_answer": None, "authoritative": None,
                  "reference_id": case.reference_id,
                  "ineligible_synthetic_smoke": stage == "smoke"}
        try:
            provider = self.provider_factory(model_id)
            identity = provider.identity()
            if digest(identity) != identity_digest:
                raise AttemptError("Provider identity drifted after preflight")
            policy = self.policies[arm]
            common = {"task": case.task, "scope": case.scope,
                      "decision_cut": case.decision_cut,
                      "read_only_tools": self.gateway.catalogue(case)}
            if arm in {"E", "J"}:
                discovery_packet = await self.host.describe()
                discovery = discovery_packet["description"]
                result["mcp_discovery"] = discovery_packet["receipt"]
                from eal.discovery import describe_language
                if digest(discovery) != digest(describe_language()):
                    raise AttemptError("MCP language contract differs from the frozen package")
                common["eal_language_contract"] = discovery
                if arm == "J":
                    common["json_frontend_contract"] = frontend_contract()
            first = await self._complete(provider, identity, model_calls,
                                         policy.prompt + "\n\n" + PHASE_INSTRUCTIONS["select_and_author"][arm],
                                         {**common, "phase": "select_and_author",
                                          "max_tool_calls": self.limits.max_tool_calls}, start)
            proposal = strict_json(first)
            if type(proposal) is not dict:
                raise AttemptError("Initial authoring response is not a JSON object")
            prepared = policy.prepare(proposal, case, self.gateway, self.limits.max_tool_calls)
            if arm in {"E", "J"}:
                assert prepared.source is not None and prepared.claim is not None
                checked = await self.host.check(prepared.source, prepared.claim, case)
                checked["mcp_calls"].insert(0, result["mcp_discovery"])
                result["host_result"] = checked
                records = checked["collection"].get("records", {})
                traces.extend({"evidence_id": name, **record} for name, record in records.items())
                evidence_prompt = {"checked_assessment": checked["assessment"],
                                   "checked_explanation": checked["explanation"],
                                   "tool_records": records}
            else:
                for call in prepared.calls:
                    traces.append(self.gateway.capture(case, call["tool_id"], call["arguments"]))
                evidence_prompt = {"tool_records": traces}
            second = await self._complete(provider, identity, model_calls,
                                          policy.prompt + "\n\n" + PHASE_INSTRUCTIONS["communicate_decision"][arm],
                                          {**common, "phase": "communicate_decision",
                                           "evidence": evidence_prompt}, start)
            result["raw_answer"] = second
            answer = strict_json(second)
            if type(answer) is not dict:
                raise AttemptError("Final response is not a JSON object")
            authoritative = policy.finalise(answer, checked)
            result.update(status="completed", authoritative=authoritative,
                          claim_correspondence="requires_masked_adjudication")
        except Exception as exc:
            if arm in {"E", "J"} and getattr(exc, "mcp_calls", None) is not None:
                result["host_result"] = {"mcp_calls": [
                    *([result["mcp_discovery"]] if "mcp_discovery" in result else []),
                    *exc.mcp_calls], "failed": True}
            result["error"] = {"type": type(exc).__name__,
                               "message": str(exc)[:1000] if type(exc) in
                               (AttemptError, ValueError) else "Attempt failed; inspect retained traces"}
            if isinstance(exc, ProviderError) and isinstance(exc.response, ModelResponse):
                model_calls.append({"provider_failure_usage": {
                    "input_tokens": exc.response.input_tokens,
                    "output_tokens": exc.response.output_tokens,
                    "model": exc.response.model}})
        result["elapsed_seconds"] = time.monotonic() - start
        return result

    async def _complete(self, provider: Provider, identity: dict, calls: list[dict],
                        system: str, payload: dict, started: float) -> str:
        if len(calls) >= self.limits.max_model_calls:
            raise AttemptError("Model call ceiling reached")
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": canonical(payload).decode("utf-8")}]
        if len(canonical(messages)) > self.limits.max_prompt_bytes:
            raise AttemptError("Prompt byte ceiling reached")
        remaining_tokens = self.limits.max_output_tokens - sum(
            item.get("output_tokens") or 0 for item in calls)
        remaining_seconds = self.limits.max_wall_seconds - (time.monotonic() - started)
        if remaining_tokens <= 0 or remaining_seconds <= 0:
            raise AttemptError("Attempt resource ceiling reached")
        row: dict[str, Any] = {"messages": messages, "started_at": now(),
                               "requested_output_tokens": remaining_tokens}
        calls.append(row)
        try:
            response = await asyncio.wait_for(provider.complete(messages, remaining_tokens),
                                              timeout=remaining_seconds)
            if not isinstance(response, ModelResponse):
                raise AttemptError("Provider returned no valid model response")
            row.update(response=response.text, input_tokens=response.input_tokens,
                       output_tokens=response.output_tokens, resolved_model=response.model,
                       metadata={key: response.metadata[key] for key in
                                 ("request_id", "finish_reason", "cached_input_tokens")
                                 if key in response.metadata},
                       cost_usd=response_cost(response, identity))
            if response.model != identity.get("model"):
                raise AttemptError("Resolved model differs from pinned snapshot")
            if (len(response.text.encode("utf-8")) > self.limits.max_response_bytes
                    or response.output_tokens is None or response.output_tokens > remaining_tokens
                    or row["cost_usd"] is None
                    or sum(item.get("cost_usd") or 0 for item in calls) > self.limits.max_cost_usd):
                raise AttemptError("Response or billable usage exceeds a declared limit")
            return response.text
        except Exception as exc:
            row["error"] = type(exc).__name__
            raise
        finally:
            row["finished_at"] = now()


def main() -> None:
    parser = argparse.ArgumentParser(description="Versioned four-arm prospective study runner")
    parser.add_argument("--verify-ledger", type=Path)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--case", type=Path)
    parser.add_argument("--model", help="Name in the frozen model matrix")
    parser.add_argument("--provider", type=Path, help="Trusted operator model configuration TOML")
    parser.add_argument("--workspace", type=Path, default=PROJECT)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--stage", choices=("pilot", "retrospective", "prospective_shadow"))
    parser.add_argument("--execution", type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--receipt-root", type=Path)
    parser.add_argument("--roster", type=Path)
    parser.add_argument("--repetition", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    if args.verify_ledger:
        print(json.dumps(AttemptLedger(args.verify_ledger).verify(), sort_keys=True))
        return
    if not args.run or any(value is None for value in (
            args.case, args.model, args.provider, args.registry, args.ledger, args.stage,
            args.execution, args.bundle, args.receipt_root, args.roster)):
        parser.error("Real execution requires --run, case, model, provider, registry, ledger, stage and signed stage inputs")
    case = Case.from_dict(strict_json(args.case.read_text(encoding="utf-8")))
    gateway = ToolGateway(args.workspace, args.registry)
    study_dir = PROJECT / "benchmarks" / "study-v1"
    provider = lambda _: load_provider(args.provider)
    runner = ProspectiveRunner(gateway=gateway, provider_factory=provider,
                               ledger=AttemptLedger(args.ledger),
                               policies=default_policies(study_dir))
    roster = strict_json(args.roster.read_text(encoding="utf-8"))
    results = asyncio.run(runner.run_case(
        case=case, model_id=args.model, stage=args.stage,
        repetition=args.repetition, seed=args.seed,
        study_path=study_dir / "plan.json", execution_path=args.execution,
        bundle_path=args.bundle, receipt_root=args.receipt_root,
        trust_roster=roster))
    print(json.dumps({"schema": SCHEMA, "results": results}, allow_nan=False))


if __name__ == "__main__":
    main()
