"""Synthetic harness tests, explicitly ineligible as reviewed study cases."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import httpx

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from eal.providers import ModelResponse, ProviderError
from gateway_v1 import Grant, GitObjectReader, HTTPSJSONReader, ReadOnlyGateway, canonical, digest
from ledger_v1 import AttemptLedger, LedgerError
from receipts_v1 import ReceiptError, SCHEMA as RECEIPT_SCHEMA, verify_stage
from runner_v1 import (AttemptError, Case, EAL2Host, EALPolicy, GenericGraphHost, GenericPolicy,
                       Limits, ProsePolicy, ProspectiveRunner, authorise_stage,
                       default_policies, policy_manifest)

PLAN_SHA = digest((Path(__file__).with_name("plan.json")).read_bytes())


EAL = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool runner { version "1.0"; mode deterministic; }
evidence measured {
  tool runner; kind test; environment lab; max_age 60;
  input {"value": "7"}; require "passed" == true;
}
reasoning observation { method "structured/1"; rationale "This exact record supports the claim."; }
claim works { statement "The bounded test passed."; environment lab; }
argument result { conclusion works; reasoning observation; evidence measured; }
'''

GRAPH = {
    "schema": "generic-argument-graph/1", "id": "bench_test", "claim": "works",
    "scope": {"site": {"type": "str", "equals": "bench"}},
    "evidence": {"runner": {"tool_version": "1.0", "mode": "deterministic",
                            "max_age_seconds": 60, "input": {"value": "7"}}},
    "routes": [{"id": "passing_test", "all": [{"op": "is_true", "record": "runner",
                                                "path": ["value", "passed"]}]}],
    "objections": [],
}


class FixtureProvider:
    def identity(self):
        return {"provider": "synthetic_fixture", "adapter": "fixture", "model": "fixture-v1",
                "measurement_kind": "interface_only", "pricing": {
                    "input_usd_per_million": 1, "output_usd_per_million": 1}}

    async def complete(self, messages, max_output_tokens):
        payload = json.loads(messages[-1]["content"])
        if payload["task"].startswith("Select"):
            result = {"calls": [{"tool_id": "runner", "arguments": {"value": "7"}}]}
        elif "author EAL/2" in messages[0]["content"]:
            result = {"source": EAL, "claim": "works", "status": "supported",
                      "explanation": "I think this is supported", "recommendation": "Proceed"}
        elif "generic JSON" in messages[0]["content"]:
            result = {"graph": GRAPH, "status": "supported",
                      "explanation": "I think this is supported", "recommendation": "Proceed"}
        else:
            result = {"status": "supported", "explanation": "I think this is supported",
                      "recommendation": "Proceed"}
            if "Claim, Grounds, Warrant" in messages[0]["content"]:
                result.update({k: k for k in ("claim", "grounds", "warrant", "backing",
                                               "qualifier", "rebuttal")})
        return ModelResponse(json.dumps(result), 10, 20, "fixture-v1")


def git_repo(path: Path) -> str:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    (path / "case.json").write_text('{"passed": true}\n', encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "case.json"], check=True)
    env = {**os.environ, "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
           "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
           "GIT_AUTHOR_DATE": "2024-01-01T00:00:00+00:00",
           "GIT_COMMITTER_DATE": "2024-01-01T00:00:00+00:00"}
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "fixture"], check=True, env=env)
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


class FakeReader:
    def read(self, grant, arguments, decision_cut, stage):
        return {"passed": True}, "2024-01-01T00:00:00+00:00", {
            "source_revision": "fixture", "raw_sha256": digest(b"fixture"), "source": "local test"}


class BadProvider(FixtureProvider):
    async def complete(self, messages, max_output_tokens):
        return None


class WrongIdentityProvider(FixtureProvider):
    def identity(self):
        return {**super().identity(), "model": "other-model"}


class BilledFailureProvider(FixtureProvider):
    async def complete(self, messages, max_output_tokens):
        raise ProviderError("fixture outage", response=ModelResponse("", 100, 20, "fixture-v1"))


class MutatingPolicy(ProsePolicy):
    def finalise(self, answer, traces, case):
        traces[0]["value"]["passed"] = False
        case.scope["site"] = "changed_by_policy"
        return super().finalise(answer, traces, case)


class MockEPolicy(EALPolicy):
    def finalise(self, answer, traces, case):
        return {"authoritative_status": "supported", "checked_status": "supported",
                "explanation": "mock", "recommendation": "mock", "host_result": {}}


class ConfigurableEPolicy(MockEPolicy):
    def __init__(self, variant):
        super().__init__()
        self.variant = variant


def signed_pilot_bundle(root: Path, plan: bytes, case: Case, grant: Grant,
                        provider_identity: dict, policies=None, review_entries=None):
    secrets = {role: [Ed25519PrivateKey.generate() for _ in range(count)]
               for role, count in (("domain_reviewer", 2), ("security_owner", 1),
                                   ("method_reviewer", 1))}
    roster = {}
    for role, keys in secrets.items():
        for index, key in enumerate(keys):
            roster[f"{role}-{index}"] = {"role": role, "public_key_hex": key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw).hex()}
    artifacts = {
        "independent_case_manifest_sha256": ({"schema": "eal2-real-case-manifest/1",
                                              "stage": "feasibility_pilot", "cases": [case.as_dict()]},
                                             ("domain_reviewer", 2)),
        "reference_review_sha256": ({"schema": "eal2-real-reference-review/1",
                                     "entries": review_entries if review_entries is not None else
                                     [{"case_id": case.id, "reference_id": case.reference_id,
                                       "case_sha256": digest(case.as_dict()),
                                       "synthetic_review": True}]},
                                    ("domain_reviewer", 2)),
        "tool_allowlist_and_isolation_sha256": ({"schema": "eal2-real-tool-allowlist/1",
                                                "grants": [grant.signed_spec()],
                                                "operator_isolation": {"fixture": "no real isolation"}},
                                               ("security_owner", 1)),
        "prompt_and_method_parity_sha256": (policy_manifest(policies or default_policies()),
                                            ("method_reviewer", 1)),
        "model_snapshot_manifest_sha256": ({"schema": "eal2-real-model-matrix/1",
                                             "models": [{"id": "fixture-v1",
                                                         "identity_sha256": digest(provider_identity),
                                                         "resolved_model": "fixture-v1"}]},
                                            ("method_reviewer", 1)),
    }
    plan_hash = digest(plan)
    bundle = {"schema": RECEIPT_SCHEMA, "investigation_id": "INV-EAL-REAL-001",
              "plan_sha256": plan_hash, "artifacts": {}}
    for name, (value, (role, count)) in artifacts.items():
        relative = f"{name}.json"
        (root / relative).write_bytes(canonical(value))
        sha = digest((root / relative).read_bytes())
        message = canonical({"schema": RECEIPT_SCHEMA, "investigation_id": "INV-EAL-REAL-001",
                             "plan_sha256": plan_hash, "receipt": name, "sha256": sha})
        bundle["artifacts"][name] = {"path": relative, "sha256": sha,
                                     "attestations": [
                                         {"key_id": f"{role}-{index}",
                                          "signature_hex": secrets[role][index].sign(message).hex()}
                                         for index in range(count)]}
    return bundle, roster


class GatewayAndLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repository"
        self.repo.mkdir()
        self.commit = git_repo(self.repo)
        self.grant = Grant("runner", "git_object", "1.0", "deterministic", "test-principal",
                           {"path": ("case.json",)}, {"repository": str(self.repo),
                                                    "commit": self.commit}, ("case_1",))
        self.gateway = ReadOnlyGateway({"runner": self.grant})
        self.case = Case("case_1", "unreviewed_family", "test-principal",
                         "2024-01-01T00:01:00+00:00", "Did the pinned test pass?",
                         {"site": "bench"}, {"test": "passed"}, "unreviewed_reference",
                         ({"tool_id": "runner", "arguments": {"path": "case.json"}},))

    def test_actual_pinned_git_object_and_rejected_request(self):
        trace = self.gateway.capture(case_id=self.case.id, family_id=self.case.family_id,
                                     principal=self.case.principal, decision_cut=self.case.decision_cut,
                                     stage="smoke", tool_id="runner", arguments={"path": "case.json"})
        self.assertEqual(trace["status"], "ok")
        self.assertEqual(trace["value"], {"text": '{"passed": true}\n'})
        self.assertEqual(trace["metadata"]["source_revision"], self.commit)
        for principal, arguments in (("intruder", {"path": "case.json"}),
                                     ("test-principal", {"path": "../secrets"})):
            denied = self.gateway.capture(case_id="case_1", family_id="family", principal=principal,
                                          decision_cut=self.case.decision_cut, stage="smoke",
                                          tool_id="runner", arguments=arguments)
            self.assertEqual(denied["status"], "error")
            self.assertIsNone(denied["value"])

    def test_later_commit_cannot_be_retrospectively_seen(self):
        trace = self.gateway.capture(case_id="case_1", family_id="family", principal="test-principal",
                                     decision_cut="2023-12-31T00:00:00+00:00", stage="smoke",
                                     tool_id="runner", arguments={"path": "case.json"})
        self.assertEqual(trace["status"], "error")
        self.assertIn("postdates", trace["error"]["message"])

    def test_same_principal_cannot_use_another_cases_grant(self):
        trace = self.gateway.capture(case_id="case_2", family_id="family", principal="test-principal",
                                     decision_cut=self.case.decision_cut, stage="smoke",
                                     tool_id="runner", arguments={"path": "case.json"})
        self.assertEqual(trace["status"], "error")
        self.assertIn("outside this case", trace["error"]["message"])
        self.assertEqual(self.gateway.catalogue("test-principal", "case_2"), [])

    def test_https_get_transport_fixture_and_snapshot_rejection(self):
        grant = Grant("ci", "https_json_get", "1", "nondeterministic", "test-principal",
                      {"run": ("42",)}, {"endpoint": "https://ci.example.invalid/api/runs",
                                      "token_env": "EAL_STUDY_TOKEN_TEST", "snapshot_id": "snap-a"},
                      ("case_1",))
        gateway = ReadOnlyGateway({"ci": grant})
        seen = []
        response_body = {"snapshot_id": "snap-a", "observed_at": "2024-01-01T00:00:00Z",
                         "value": {"passed": True}}
        raw_override = [None]
        def handler(request):
            seen.append(request)
            if raw_override[0] is not None:
                return httpx.Response(200, content=raw_override[0])
            return httpx.Response(200, json=response_body)
        actual_client = httpx.Client
        def make_client(**kwargs):
            return actual_client(transport=httpx.MockTransport(handler), **kwargs)
        with patch.dict(os.environ, {"EAL_STUDY_TOKEN_TEST": "fixture-secret"}), \
             patch("gateway_v1.httpx.Client", side_effect=make_client):
            trace = gateway.capture(case_id="case_1", family_id="family",
                                    principal="test-principal", decision_cut="2024-01-01T00:01:00Z",
                                    stage="retrospective_execution", tool_id="ci", arguments={"run": "42"})
            self.assertEqual(trace["status"], "ok")
            self.assertEqual(trace["value"], {"passed": True})
            self.assertEqual(str(seen[0].url), "https://ci.example.invalid/api/runs?run=42")
            self.assertEqual(seen[0].headers["Authorization"], "Bearer fixture-secret")
            self.assertNotIn("fixture-secret", json.dumps(trace))
            response_body["snapshot_id"] = "snap-b"
            mismatch = gateway.capture(case_id="case_1", family_id="family",
                                       principal="test-principal", decision_cut="2024-01-01T00:01:00Z",
                                       stage="retrospective_execution", tool_id="ci", arguments={"run": "42"})
            self.assertEqual(mismatch["status"], "error")
            self.assertIn("snapshot identity", mismatch["error"]["message"])
            response_body["snapshot_id"] = "snap-a"
            response_body["observed_at"] = "2025-01-01T00:00:00Z"
            future = gateway.capture(case_id="case_1", family_id="family",
                                     principal="test-principal", decision_cut="2024-01-01T00:01:00Z",
                                     stage="retrospective_execution", tool_id="ci", arguments={"run": "42"})
            self.assertEqual(future["status"], "error")
            self.assertIn("postdates", future["error"]["message"])
            raw_override[0] = b'{"snapshot_id":"snap-a","snapshot_id":"snap-b","observed_at":"2024-01-01T00:00:00Z","value":{}}'
            duplicate = gateway.capture(case_id="case_1", family_id="family",
                                        principal="test-principal", decision_cut="2024-01-01T00:01:00Z",
                                        stage="retrospective_execution", tool_id="ci", arguments={"run": "42"})
            self.assertEqual(duplicate["status"], "error")
            self.assertIn("invalid JSON", duplicate["error"]["message"])

    def test_hash_chain_duplicate_outcome_and_interrupted_assignment(self):
        ledger = AttemptLedger(self.root / "attempts.jsonl")
        ledger.append({"kind": "start", "attempt_id": "a"})
        self.assertEqual(ledger.verify()["interrupted"], ["a"])
        with self.assertRaises(LedgerError):
            ledger.append({"kind": "start", "attempt_id": "a"})
        with self.assertRaises(LedgerError):
            ledger.verify(require_complete=True)
        ledger.append({"kind": "outcome", "attempt_id": "a", "result": {"status": "failed"}})
        with self.assertRaises(LedgerError):
            ledger.append({"kind": "outcome", "attempt_id": "a"})
        self.assertEqual(ledger.verify(require_complete=True)["completed"], 1)
        original = ledger.path.read_bytes()
        ledger.path.write_bytes(original.replace(b"failed", b"passed"))
        with self.assertRaises(LedgerError):
            ledger.verify()

    def test_partial_line_is_fail_closed(self):
        ledger = AttemptLedger(self.root / "attempts.jsonl")
        ledger.append({"kind": "start", "attempt_id": "a"})
        with ledger.path.open("ab") as stream:
            stream.write(b'{"partial":')
        with self.assertRaises(LedgerError):
            ledger.append({"kind": "outcome", "attempt_id": "a"})

    def test_concurrent_block_reservation_has_one_complete_winner(self):
        path = self.root / "concurrent.jsonl"
        barrier = Barrier(2)
        starts = [{"kind": "start", "attempt_id": f"arm-{arm}"} for arm in ("P", "T", "E", "J")]
        def reserve():
            barrier.wait()
            try:
                AttemptLedger(path).reserve_block(starts)
                return "accepted"
            except LedgerError:
                return "duplicate"
        with ThreadPoolExecutor(max_workers=2) as workers:
            outcomes = list(workers.map(lambda _: reserve(), range(2)))
        self.assertCountEqual(outcomes, ["accepted", "duplicate"])
        self.assertEqual(AttemptLedger(path).verify()["assigned"], 4)

    def test_real_stages_block_without_external_receipts(self):
        with self.assertRaises(ReceiptError):
            verify_stage(stage="feasibility_pilot", bundle={}, root=self.root,
                         trust_roster={}, plan_bytes=b"plan")

    def test_signed_manifest_binds_grants_and_provider_identity(self):
        identity = FixtureProvider().identity()
        plan_path = self.root / "plan.json"
        plan_path.write_bytes(canonical({"schema": "eal2-real-workflow-execution-plan/1",
                                         "investigation_id": "INV-EAL-REAL-001",
                                         "stage": "feasibility_pilot", "status": "pilot_ready",
                                         "supersedes_spec_sha256": PLAN_SHA,
                                         "limits": Limits().__dict__,
                                         "schedule": [{"case_id": self.case.id, "model_id": "fixture-v1",
                                                       "acquisition": "fixed_capture", "repetition": 0,
                                                       "seed": 0}]}))
        bundle, roster = signed_pilot_bundle(self.root, plan_path.read_bytes(), self.case,
                                             self.grant, identity)
        good = authorise_stage(stage="feasibility_pilot", case=self.case,
                               model_id="fixture-v1", gateway=self.gateway,
                               actual_policies=default_policies(), receipt_bundle=bundle,
                               receipt_root=self.root, trust_roster=roster, plan_path=plan_path)
        self.assertEqual(good["model_identity_sha256"], digest(identity))
        alternate = Grant("runner", "git_object", "1.0", "deterministic", "test-principal",
                          {"path": ("case.json",)}, {"repository": str(self.repo),
                                                   "commit": "b" * 40}, ("case_1",))
        with self.assertRaisesRegex(AttemptError, "Runtime grants differ"):
            authorise_stage(stage="feasibility_pilot", case=self.case, model_id="fixture-v1",
                            gateway=ReadOnlyGateway({"runner": alternate}),
                            actual_policies=default_policies(), receipt_bundle=bundle,
                            receipt_root=self.root, trust_roster=roster, plan_path=plan_path)
        with self.assertRaisesRegex(AttemptError, "signed execution plan"):
            authorise_stage(stage="feasibility_pilot", case=self.case, model_id="other-model",
                            gateway=self.gateway, actual_policies=default_policies(),
                            receipt_bundle=bundle, receipt_root=self.root,
                            trust_roster=roster, plan_path=plan_path)
        custom = default_policies()
        custom["E"] = ConfigurableEPolicy("reviewed-v1")
        custom_bundle, custom_roster = signed_pilot_bundle(
            self.root, plan_path.read_bytes(), self.case, self.grant, identity, custom)
        approved = authorise_stage(stage="feasibility_pilot", case=self.case,
                                   model_id="fixture-v1", gateway=self.gateway,
                                   actual_policies=custom, receipt_bundle=custom_bundle,
                                   receipt_root=self.root, trust_roster=custom_roster,
                                   plan_path=plan_path)
        self.assertEqual(approved["stage"], "feasibility_pilot")
        custom["E"].variant = "unreviewed-v2"
        with self.assertRaisesRegex(AttemptError, "Runtime arms, prompts or checker versions"):
            authorise_stage(stage="feasibility_pilot", case=self.case,
                            model_id="fixture-v1", gateway=self.gateway,
                            actual_policies=custom, receipt_bundle=custom_bundle,
                            receipt_root=self.root, trust_roster=custom_roster,
                            plan_path=plan_path)
        # Restore the original independent bundle before its tamper check.
        bundle, roster = signed_pilot_bundle(self.root, plan_path.read_bytes(), self.case,
                                             self.grant, identity)
        unreviewed = default_policies()
        unreviewed["E"] = MockEPolicy()
        with self.assertRaisesRegex(AttemptError, "Runtime arms, prompts or checker versions"):
            authorise_stage(stage="feasibility_pilot", case=self.case, model_id="fixture-v1",
                            gateway=self.gateway, actual_policies=unreviewed,
                            receipt_bundle=bundle, receipt_root=self.root,
                            trust_roster=roster, plan_path=plan_path)
        unrelated, unrelated_roster = signed_pilot_bundle(
            self.root, plan_path.read_bytes(), self.case, self.grant, identity,
            review_entries=[{"case_id": "different_case", "reference_id": self.case.reference_id,
                             "case_sha256": digest(self.case.as_dict())}])
        with self.assertRaisesRegex(AttemptError, "does not bind this exact case"):
            authorise_stage(stage="feasibility_pilot", case=self.case,
                            model_id="fixture-v1", gateway=self.gateway,
                            actual_policies=default_policies(), receipt_bundle=unrelated,
                            receipt_root=self.root, trust_roster=unrelated_roster,
                            plan_path=plan_path)
        wrong_digest, wrong_roster = signed_pilot_bundle(
            self.root, plan_path.read_bytes(), self.case, self.grant, identity,
            review_entries=[{"case_id": self.case.id, "reference_id": self.case.reference_id,
                             "case_sha256": "0" * 64}])
        with self.assertRaisesRegex(AttemptError, "does not bind this exact case"):
            authorise_stage(stage="feasibility_pilot", case=self.case,
                            model_id="fixture-v1", gateway=self.gateway,
                            actual_policies=default_policies(), receipt_bundle=wrong_digest,
                            receipt_root=self.root, trust_roster=wrong_roster,
                            plan_path=plan_path)
        duplicate, duplicate_roster = signed_pilot_bundle(
            self.root, plan_path.read_bytes(), self.case, self.grant, identity,
            review_entries=[{"case_id": self.case.id, "reference_id": self.case.reference_id,
                             "case_sha256": digest(self.case.as_dict())}] * 2)
        with self.assertRaisesRegex(AttemptError, "does not bind this exact case"):
            authorise_stage(stage="feasibility_pilot", case=self.case,
                            model_id="fixture-v1", gateway=self.gateway,
                            actual_policies=default_policies(), receipt_bundle=duplicate,
                            receipt_root=self.root, trust_roster=duplicate_roster,
                            plan_path=plan_path)
        original_plan = plan_path.read_bytes()
        plan_path.write_bytes(canonical({"schema": "eal2-real-workflow-execution-plan/1",
                                         "investigation_id": "INV-EAL-REAL-001",
                                         "stage": "feasibility_pilot", "status": "pilot_ready",
                                         "supersedes_spec_sha256": "a" * 64}))
        with self.assertRaisesRegex(AttemptError, "separately versioned ready execution plan"):
            authorise_stage(stage="feasibility_pilot", case=self.case, model_id="fixture-v1",
                            gateway=self.gateway, actual_policies=default_policies(),
                            receipt_bundle=bundle, receipt_root=self.root,
                            trust_roster=roster, plan_path=plan_path)
        plan_path.write_bytes(original_plan)
        (self.root / bundle["artifacts"]["reference_review_sha256"]["path"]).write_text("changed")
        with self.assertRaises(ReceiptError):
            authorise_stage(stage="feasibility_pilot", case=self.case, model_id="fixture-v1",
                            gateway=self.gateway, actual_policies=default_policies(),
                            receipt_bundle=bundle, receipt_root=self.root,
                            trust_roster=roster, plan_path=plan_path)


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.grant = Grant("runner", "git_object", "1.0", "deterministic", "test-principal",
                           {"value": ("7",)}, {"repository": str(self.root), "commit": "a" * 40},
                           ("case_1",))
        self.gateway = ReadOnlyGateway({"runner": self.grant}, readers={"git_object": FakeReader()})
        self.ledger = AttemptLedger(self.root / "attempts.jsonl")
        self.runner = ProspectiveRunner(gateway=self.gateway, provider_factory=lambda _: FixtureProvider(),
                                        ledger=self.ledger, limits=Limits())
        self.case = Case("case_1", "unreviewed_family", "test-principal",
                         "2024-01-01T00:01:00+00:00", "Did the test pass?",
                         {"site": "bench"}, {"test": "passed"}, "unreviewed_reference",
                         ({"tool_id": "runner", "arguments": {"value": "7"}},))

    async def test_fixed_capture_is_identical_for_four_arms_and_host_status_wins(self):
        results = await self.runner.run_case(case=self.case, model_id="fixture-v1", stage="smoke",
                                             acquisition="fixed_capture")
        self.assertEqual({r["arm"] for r in results}, {"P", "T", "E", "J"})
        self.assertEqual({digest(r["tool_traces"]) for r in results}, {digest(results[0]["tool_traces"])})
        self.assertTrue(all(r["status"] == "completed" for r in results), results)
        for arm in ("E", "J"):
            item = next(r for r in results if r["arm"] == arm)
            self.assertEqual(item["authoritative"]["authoritative_status"], "supported")
            self.assertEqual(item["authoritative"]["checked_status"], "supported")
        self.assertEqual(self.ledger.verify(require_complete=True)["completed"], 4)
        with self.assertRaises(LedgerError):
            await self.runner.run_case(case=self.case, model_id="fixture-v1", stage="smoke",
                                       acquisition="fixed_capture")

    async def test_later_arm_collision_does_not_reserve_earlier_arms(self):
        later = digest({"stage": "smoke", "case_id": self.case.id,
                        "family_id": self.case.family_id, "model_id": "fixture-v1",
                        "arm": "J", "repetition": 0, "acquisition": "fixed_capture",
                        "runner_schema": "eal2-real-workflow-runner/1"})
        self.ledger.append({"kind": "start", "attempt_id": later})
        original = self.ledger.path.read_bytes()
        with self.assertRaises(LedgerError):
            await self.runner.run_case(case=self.case, model_id="fixture-v1", stage="smoke",
                                       acquisition="fixed_capture")
        self.assertEqual(self.ledger.path.read_bytes(), original)
        self.assertEqual(self.ledger.verify()["interrupted"], [later])

    async def test_selected_acquisition_is_a_separate_estimand_and_records_prompts(self):
        results = await self.runner.run_case(case=self.case, model_id="fixture-v1", stage="smoke",
                                             acquisition="selected_acquisition")
        self.assertTrue(all(len(r["model_calls"]) == 2 for r in results), results)
        self.assertTrue(all(len(r["tool_traces"]) == 1 for r in results))
        self.assertEqual(self.ledger.verify(require_complete=True)["completed"], 4)
        for result in results:
            self.assertIn("messages", result["model_calls"][0])
            self.assertIn("messages", result["model_calls"][1])

    async def test_real_stage_never_calls_provider_when_receipts_missing(self):
        with self.assertRaises(AttemptError):
            await self.runner.run_case(case=self.case, model_id="fixture-v1",
                                       stage="retrospective_execution", acquisition="fixed_capture")
        self.assertEqual(self.ledger.verify()["events"], 0)

    async def test_wrong_provider_response_produces_four_final_failures(self):
        runner = ProspectiveRunner(gateway=self.gateway, provider_factory=lambda _: BadProvider(),
                                   ledger=self.ledger, limits=Limits())
        results = await runner.run_case(case=self.case, model_id="fixture-v1", stage="smoke",
                                        acquisition="fixed_capture")
        self.assertTrue(all(row["status"] == "failed" for row in results))
        self.assertTrue(all(row["error"]["message"] == "Provider returned an invalid response object"
                            for row in results))
        self.assertEqual(self.ledger.verify(require_complete=True)["completed"], 4)

    async def test_failed_provider_usage_cost_is_retained(self):
        runner = ProspectiveRunner(gateway=self.gateway,
                                   provider_factory=lambda _: BilledFailureProvider(),
                                   ledger=self.ledger, limits=Limits())
        results = await runner.run_case(case=self.case, model_id="fixture-v1", stage="smoke",
                                        acquisition="fixed_capture")
        self.assertTrue(all(row["status"] == "failed" for row in results))
        self.assertTrue(all(row["model_calls"][0]["provider_failure_usage"]["cost_usd"] == 0.00012
                            for row in results))
        self.assertEqual(self.ledger.verify(require_complete=True)["completed"], 4)

    async def test_injected_policy_cannot_change_other_arm_captures(self):
        policies = default_policies()
        policies["P"] = MutatingPolicy()
        runner = ProspectiveRunner(gateway=self.gateway, provider_factory=lambda _: FixtureProvider(),
                                   ledger=self.ledger, limits=Limits(), policies=policies)
        results = await runner.run_case(case=self.case, model_id="fixture-v1", stage="smoke",
                                        acquisition="fixed_capture")
        for row in results:
            if row["arm"] != "P":
                self.assertEqual(row["tool_traces"][0]["value"], {"passed": True})
                self.assertEqual(json.loads(row["model_calls"][0]["messages"][1]["content"])["scope"],
                                 {"site": "bench"})
        self.assertEqual(self.case.scope, {"site": "bench"})

    async def test_host_owned_status_overrides_opposed_prose(self):
        trace = self.gateway.capture(case_id=self.case.id, family_id=self.case.family_id,
                                     principal=self.case.principal, decision_cut=self.case.decision_cut,
                                     stage="smoke", tool_id="runner", arguments={"value": "7"})
        opposed = {"source": EAL, "claim": "works", "graph": GRAPH,
                   "status": "unsupported", "explanation": "The check failed", "recommendation": "Stop"}
        for policy in (EALPolicy(EAL2Host()), GenericPolicy(GenericGraphHost())):
            result = policy.finalise(opposed, [trace], self.case)
            self.assertEqual(result["authoritative_status"], "supported")
            self.assertEqual(result["explanation"], "The check failed")
            if policy.id == "E":
                packet = result["host_result"]["assessment"]
                self.assertEqual(packet["claims"]["works"]["status"], "supported")
                self.assertIn("measured", packet["evidence"])

    async def test_foreign_or_tampered_trace_cannot_be_checked(self):
        trace = self.gateway.capture(case_id=self.case.id, family_id=self.case.family_id,
                                     principal=self.case.principal, decision_cut=self.case.decision_cut,
                                     stage="smoke", tool_id="runner", arguments={"value": "7"})
        for change in ({"case_id": "case_2"}, {"value": {"passed": False}},
                       {"observed_at": "2025-01-01T00:00:00+00:00"}):
            mutated = {**trace, **change}
            for policy, answer in ((EALPolicy(), {"source": EAL, "claim": "works"}),
                                   (GenericPolicy(), {"graph": GRAPH})):
                with self.assertRaises(AttemptError):
                    policy.finalise(answer, [mutated], self.case)

    async def test_signed_provider_identity_mismatch_is_recorded_for_all_arms(self):
        repo = self.root / "repo"
        repo.mkdir()
        commit = git_repo(repo)
        grant = Grant("runner", "git_object", "1.0", "deterministic", "test-principal",
                      {"path": ("case.json",)}, {"repository": str(repo), "commit": commit},
                      ("case_1",))
        gateway = ReadOnlyGateway({"runner": grant})
        case = Case("case_1", "unreviewed_family", "test-principal",
                    "2024-01-01T00:01:00+00:00", "Did this test pass?", {"site": "bench"},
                    {"test": "passed"}, "unreviewed_reference",
                    ({"tool_id": "runner", "arguments": {"path": "case.json"}},))
        plan = self.root / "plan.json"
        plan.write_bytes(canonical({"schema": "eal2-real-workflow-execution-plan/1",
                                    "investigation_id": "INV-EAL-REAL-001",
                                    "stage": "feasibility_pilot", "status": "pilot_ready",
                                    "supersedes_spec_sha256": PLAN_SHA,
                                    "limits": Limits().__dict__,
                                    "schedule": [{"case_id": case.id, "model_id": "fixture-v1",
                                                  "acquisition": "fixed_capture", "repetition": 0,
                                                  "seed": 0}]}))
        bundle, roster = signed_pilot_bundle(self.root, plan.read_bytes(), case, grant,
                                             FixtureProvider().identity())
        runner = ProspectiveRunner(gateway=gateway, provider_factory=lambda _: WrongIdentityProvider(),
                                   ledger=self.ledger, limits=Limits())
        results = await runner.run_case(case=case, model_id="fixture-v1", stage="feasibility_pilot",
                                        acquisition="fixed_capture", receipt_bundle=bundle,
                                        receipt_root=self.root, trust_roster=roster, plan_path=plan)
        self.assertEqual(len(results), 4)
        self.assertTrue(all(r["status"] == "failed" and
                            "Provider identity drifted" in r["error"]["message"] for r in results))
        self.assertEqual(self.ledger.verify(require_complete=True)["completed"], 4)


if __name__ == "__main__":
    unittest.main()
