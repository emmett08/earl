"""Synthetic contract checks. These fixture attempts are never study evidence."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks" / "prospective-v1"))

from eal.formatter import semantic_ir  # noqa: E402
from eal.parser import parse  # noqa: E402
from eal.providers import ModelResponse  # noqa: E402
from json_frontend_v1 import FrontendError, compile_json, from_source  # noqa: E402
from ledger_v1 import AttemptLedger, LedgerError  # noqa: E402
from preflight_v1 import PreflightError, SCHEMA as RECEIPT_SCHEMA, preflight  # noqa: E402
from protocol_v1 import Case, ToolGateway, canonical, digest  # noqa: E402
from runner_v1 import (EALPolicy, JSONPolicy, Limits, ProsePolicy,
                       ProspectiveRunner, ToulminPolicy, policy_manifest)  # noqa: E402


SOURCE = '''language "EAL/2";
environment github { require "repository" == "fixture/repo"; }
tool github_workflow { version "1"; mode nondeterministic; }
evidence workflow_result {
  tool github_workflow; kind test; environment github; max_age 3600;
  input {"repository": "fixture/repo", "run_id": 42};
  require "passed" == true;
}
reasoning warrant { method "structured/1"; rationale "The exact tool record reports passed."; }
claim ready { statement "The named workflow passed."; environment github; }
argument route { conclusion ready; reasoning warrant; evidence workflow_result; }
'''


def _fixture(tmp_path):
    collector = tmp_path / "read_ci.py"
    collector.write_text('''import json, sys
from datetime import datetime, timezone
request=json.load(sys.stdin)
print(json.dumps({"value":{"passed": True}, "context": request["context"],
  "request":{key:request[key] for key in ("tool","tool_version","mode","input","context")},
  "observed_at":datetime.now(timezone.utc).isoformat()}))
''', encoding="utf-8")
    registry = tmp_path / "tools.toml"
    registry.write_text('[tools.github_workflow]\nkind = "command"\n'
                        'argv = ["python3", "read_ci.py"]\nversion = "1"\n'
                        'mode = "nondeterministic"\ntimeout_seconds = 10\n'
                        'max_output_bytes = 32768\n', encoding="utf-8")
    future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    case = Case.from_dict({"schema": "eal2-ci-prospective-case/1", "id": "fixture-case",
                           "family_id": "synthetic-only", "task": "Did the exact workflow run pass?",
                           "scope": {"repository": "fixture/repo"},
                           "decision_cut": future, "reference_id": "fixture-not-reviewed",
                           "allowed": {"github_workflow": [{"repository": "fixture/repo", "run_id": 42}]},
                           "evidence_grants": {"workflow_result": {
                               "tool": "github_workflow", "environment": "github"}}})
    return case, ToolGateway(tmp_path, registry)


class FixtureProvider:
    def identity(self):
        return {"provider": "synthetic_fixture", "adapter": "fixture", "model": "fixture-v1",
                "measurement_kind": "interface_only",
                "pricing": {"input_usd_per_million": 1, "output_usd_per_million": 1}}

    async def complete(self, messages, max_output_tokens):
        system = messages[0]["content"]
        phase = json.loads(messages[-1]["content"])["phase"]
        if phase == "select_and_author":
            if "typed declaration" in system:
                value = {"program": from_source(SOURCE), "claim": "ready"}
            elif "author valid EAL/2 source" in system:
                value = {"source": SOURCE, "claim": "ready"}
            else:
                value = {"calls": [{"tool_id": "github_workflow",
                                    "arguments": {"repository": "fixture/repo", "run_id": 42}}]}
        else:
            value = {"status": "unsupported", "recommendation": "Do not proceed",
                     "explanation": "The model incorrectly disputes the checked result."}
            if "six one-line" in system:
                value.update({name: name for name in (
                    "claim", "grounds", "warrant", "backing", "qualifier", "rebuttal")})
        return ModelResponse(json.dumps(value), input_tokens=10, output_tokens=20,
                             model="fixture-v1")


def _policies():
    return {"P": ProsePolicy("Plain prose"), "T": ToulminPolicy("Toulmin prose"),
            "J": JSONPolicy("Typed JSON"), "E": EALPolicy("EAL text")}


def test_json_frontend_preserves_typed_meaning_and_rejects_extra_fields():
    document = from_source(SOURCE)
    source, meaning = compile_json(document)
    assert meaning == semantic_ir(parse(SOURCE))
    assert semantic_ir(parse(source)) == meaning
    document["declarations"]["tools"]["github_workflow"]["mode"] = True
    with pytest.raises(FrontendError):
        compile_json(document)
    document = from_source(SOURCE)
    document["declarations"]["claims"]["ready"]["invented"] = "answer"
    with pytest.raises(FrontendError):
        compile_json(document)


def test_real_preflight_refuses_pending_plan_before_attempt(tmp_path):
    case, gateway = _fixture(tmp_path)
    study = tmp_path / "plan.json"
    study.write_text(json.dumps({"schema": "eal2-ci-prospective-study/1",
                                 "study_id": "INV-EAL-CI-001",
                                 "status": "specified_not_ready"}), encoding="utf-8")
    execution = tmp_path / "execution.json"
    execution.write_text(json.dumps({"schema": "eal2-ci-prospective-execution/1",
                                     "investigation_id": "INV-EAL-CI-001",
                                     "stage": "retrospective", "status": "specified_not_ready",
                                     "supersedes_sha256": digest(study.read_bytes())}), encoding="utf-8")
    runner = ProspectiveRunner(gateway=gateway, provider_factory=lambda _: FixtureProvider(),
                               ledger=AttemptLedger(tmp_path / "ledger.jsonl"),
                               policies=_policies())
    with pytest.raises(PreflightError, match="ready execution"):
        asyncio.run(runner.run_case(case=case, model_id="fixture-v1", stage="retrospective",
                                    study_path=study, execution_path=execution,
                                    bundle_path=tmp_path / "absent.json", receipt_root=tmp_path,
                                    trust_roster={}))
    assert runner.ledger.verify()["assigned"] == 0


def test_actual_mcp_stdio_json_and_eal_and_one_attempt_ledger(tmp_path):
    case, gateway = _fixture(tmp_path)
    ledger = AttemptLedger(tmp_path / "attempts.jsonl")
    runner = ProspectiveRunner(gateway=gateway, provider_factory=lambda _: FixtureProvider(),
                               ledger=ledger, policies=_policies(),
                               limits=Limits(max_wall_seconds=60))
    outcomes = asyncio.run(runner.run_case(case=case, model_id="fixture-v1", stage="smoke"))
    assert len(outcomes) == 4
    assert {row["arm"] for row in outcomes} == {"P", "T", "J", "E"}
    by_arm = {row["arm"]: row for row in outcomes}
    assert all(row["status"] == "completed" for row in outcomes), outcomes
    assert by_arm["P"]["authoritative"]["authoritative_status"] == "unsupported"
    for name in ("J", "E"):
        row = by_arm[name]
        assert row["authoritative"]["authoritative_status"] == "supported"
        assert row["authoritative"]["raw_model_status"] == "unsupported"
        assert [call["tool"] for call in row["host_result"]["mcp_calls"]] == [
            "eal_describe", "eal_validate", "eal_collect", "eal_reason", "eal_explain"]
        assert len(row["tool_traces"]) == 1
    assert ledger.verify(require_complete=True)["completed"] == 4
    with pytest.raises(LedgerError, match="Duplicate assignment"):
        asyncio.run(runner.run_case(case=case, model_id="fixture-v1", stage="smoke"))
    assert ledger.verify()["events"] == 8
    text = ledger.path.read_text()
    ledger.path.write_text(text.replace("fixture-case", "other-case", 1))
    with pytest.raises(LedgerError, match="chain"):
        ledger.verify()


def test_source_grants_prevent_unreviewed_run_and_language_mismatch(tmp_path):
    case, gateway = _fixture(tmp_path)
    with pytest.raises(ValueError, match="allowlist"):
        gateway.authorise_source(case, SOURCE.replace('"run_id": 42', '"run_id": 43'), "ready")
    with pytest.raises(FrontendError):
        compile_json({"schema": "eal2-ci-json-frontend/2", "language": "EAL/2",
                      "declarations": from_source(SOURCE)["declarations"]})


def test_synthetic_signed_pilot_gate_binds_cases_grants_parity_and_model(tmp_path):
    """Cryptographic plumbing test only: fixture signatures are not real review."""
    case, gateway = _fixture(tmp_path)
    policies = _policies()
    identity = FixtureProvider().identity()
    assignment = {"stage": "pilot", "case_id": case.id, "model_id": "fixture-v1",
                  "repetition": 0, "seed": 0, "acquisition": "selected_acquisition"}
    study = tmp_path / "plan.json"
    study.write_bytes(canonical({"schema": "eal2-ci-prospective-study/1",
                                 "study_id": "INV-EAL-CI-001", "status": "specified_not_ready"}))
    execution = tmp_path / "execution.json"
    execution.write_bytes(canonical({"schema": "eal2-ci-prospective-execution/1",
                                     "investigation_id": "INV-EAL-CI-001", "stage": "pilot",
                                     "status": "ready", "supersedes_sha256": digest(study.read_bytes()),
                                     "schedule": [assignment]}))
    secrets = {role: [Ed25519PrivateKey.generate() for _ in range(count)]
               for role, count in {"domain_reviewer": 2, "security_owner": 1,
                                   "method_reviewer": 1}.items()}
    roster = {f"{role}-{number}": {"role": role,
              "public_key_hex": key.public_key().public_bytes(
                  encoding=serialization.Encoding.Raw,
                  format=serialization.PublicFormat.Raw).hex()}
              for role, keys in secrets.items() for number, key in enumerate(keys)}
    trace = gateway.capture(case, "github_workflow", {"repository": "fixture/repo", "run_id": 42})
    assert trace["status"] == "ok"
    documents = {
        "case_manifest": {"cases": [case.as_dict()]},
        "reference_review": {"entries": [{"case_id": case.id,
                          "case_sha256": digest(case.as_dict()), "reference_id": case.reference_id}]},
        "tool_isolation": {"schema": "eal2-ci-tool-review/1",
                           "registry_sha256": digest(gateway.registry_path.read_bytes()),
                           "tools": gateway.catalogue(case),
                           "operator_isolation": {"fixture": "private temporary directory"},
                           "decision_cut_enforced": True,
                           "actual_execution_receipts": {"github_workflow": {
                               "executed": True, "read_only": True,
                               "source_identity": "synthetic_local_command",
                               "receipt_sha256": digest(trace)}}},
        "arm_parity": {"schema": "eal2-ci-arm-review/1", "manifest": policy_manifest(policies),
                       "mcp_transport": "stdio", "mcp_operations": [
                           "eal_describe", "eal_validate", "eal_collect", "eal_reason", "eal_explain"],
                       "source_subset": "direct_declarations", "same_typed_backend": True},
        "json_eal_differential": {"schema": "eal2-ci-differential/1", "valid_cases": 1,
                                  "adversarial_cases": 1, "all_typed_meanings_equal": True,
                                  "all_checked_outputs_equal": True,
                                  "test_trace_sha256": digest(b"synthetic-differential-only")},
        "model_matrix": {"models": [{"id": "fixture-v1", "provider_family": "synthetic",
                                     "size_class": "undisclosed",
                                     "identity_sha256": digest(identity)}]},
    }
    roles = {"case_manifest": "domain_reviewer", "reference_review": "domain_reviewer",
             "tool_isolation": "security_owner", "arm_parity": "method_reviewer",
             "json_eal_differential": "method_reviewer", "model_matrix": "method_reviewer"}
    bundle = {"schema": RECEIPT_SCHEMA, "investigation_id": "INV-EAL-CI-001",
              "plan_sha256": digest(execution.read_bytes()), "artifacts": {}}
    for name, document in documents.items():
        path = tmp_path / f"{name}.json"
        path.write_bytes(canonical(document))
        sha = digest(path.read_bytes())
        message = canonical({"schema": RECEIPT_SCHEMA,
                             "investigation_id": "INV-EAL-CI-001",
                             "plan_sha256": bundle["plan_sha256"],
                             "receipt": name, "sha256": sha})
        role = roles[name]
        bundle["artifacts"][name] = {"path": path.name, "sha256": sha,
                                     "attestations": [
                                         {"key_id": f"{role}-{number}",
                                          "signature_hex": key.sign(message).hex()}
                                         for number, key in enumerate(secrets[role])]}
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_bytes(canonical(bundle))

    def gate():
        return preflight(stage="pilot", case=case, model_id="fixture-v1",
                         assignment=assignment, study_path=study,
                         execution_path=execution, bundle_path=bundle_path,
                         receipt_root=tmp_path, trust_roster=roster,
                         arm_manifest=policy_manifest(policies),
                         registry_sha256=digest(gateway.registry_path.read_bytes()),
                         tool_manifest=gateway.catalogue(case), provider_identity=identity)

    assert gate()["inference_scope"] == "pilot_only"
    reviewed_case = tmp_path / "case_manifest.json"
    original = reviewed_case.read_bytes()
    reviewed_case.write_bytes(original + b" ")
    with pytest.raises(PreflightError, match="changed"):
        gate()
    reviewed_case.write_bytes(original)
    signatures = bundle["artifacts"]["reference_review"]["attestations"]
    signatures[1] = dict(signatures[0])
    bundle_path.write_bytes(canonical(bundle))
    with pytest.raises(PreflightError, match="Independent reviewers"):
        gate()
