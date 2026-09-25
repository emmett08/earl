"""Operator-pinned EAL reuse is exercised without a language model."""

import asyncio
import hashlib
import json
import os
import sys
import subprocess
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from eal.artifacts import ArtifactRegistry, _require_complete_collection
from eal.agent import run_unaided
from eal.providers import ModelResponse
from eal.parser import parse
from eal.runtime import ReasoningService
from eal.sampled_negative import sampled_negative_registry


SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool runner { version "1"; mode deterministic; }
evidence measured { tool runner; kind test; environment lab; max_age 60; require "passed" == true; }
reasoning measurement { method "structured/1"; rationale "The specified observation supplies support."; }
claim works { statement "The requested bounded test passes."; environment lab; }
claim other { statement "Another unobserved claim holds."; environment lab; }
argument result { conclusion works; reasoning measurement; evidence measured; }
'''


def setup_artifact(tmp_path, *, source=SOURCE, claims=("works",), method_fingerprint=None,
                   path="checked.eal", context_site="bench", now=None):
    source_path = tmp_path / path
    if source_path.parent == tmp_path:
        source_path.write_text(source)
    tool = tmp_path / "collector.py"
    tool.write_text("import json,sys\njson.load(sys.stdin)\nprint(json.dumps({'value': {'passed': True}}))\n")
    tools = tmp_path / "tools.toml"
    tools.write_text('[tools.runner]\nkind="command"\nmode="deterministic"\nversion="1"\nargv='
                     + json.dumps([sys.executable, str(tool)]) + "\n")
    service = ReasoningService(tmp_path, tools)
    fingerprint = method_fingerprint or service.method_registry.fingerprint
    digest = hashlib.sha256(source.encode()).hexdigest()
    manifest = tmp_path / "artifacts.toml"
    lines = ["[artifacts.test]", f"path = {json.dumps(path)}", f"sha256 = {json.dumps(digest)}",
             f"method_registry_fingerprint = {json.dumps(fingerprint)}",
             f"claims = {json.dumps(list(claims))}"]
    if now is not None:
        lines.append(f"now = {json.dumps(now)}")
    lines.extend(["[artifacts.test.context]", f"site = {json.dumps(context_site)}"])
    manifest.write_text("\n".join(lines) + "\n")
    return service, manifest, tools


def test_registered_artifact_returns_only_configured_statuses_and_trace(tmp_path):
    service, manifest, _ = setup_artifact(tmp_path)
    registry = ArtifactRegistry.load(service, manifest)
    result = registry.assess("test")
    assert result["claims"] == {"works": "supported"}
    assert result["verification"] == "server_assessment"
    assert "source" not in result and "other" not in result["claims"]
    assert result["source_digest"] == hashlib.sha256(SOURCE.encode()).hexdigest()
    assert service.explain(result["assessment_id"], "works")["result"]["status"] == "supported"
    assert service.explain(result["assessment_id"], "other")["result"]["status"] == "unsupported"
    assert registry.finish("test", result["assessment_id"])["claims"] == {"works": "supported"}


def test_claim_gate_uses_structural_verdict_and_rechecks_saved_evidence(tmp_path):
    service, manifest, _ = setup_artifact(tmp_path)
    (tmp_path / "collector.py").write_text(
        "import json,sys\njson.load(sys.stdin)\nprint(json.dumps({'value': {'passed': False}}))\n")
    registry = ArtifactRegistry.load(service, manifest)
    packet = registry.assess_claim("test", "works")
    assert packet["status"] == "unsupported"
    assert registry.finish_claim("test", packet["assessment_id"], "works") == packet

    assessment = service.store.get(packet["assessment_id"], kind="assessment")
    collection = service.store.get(packet["collection_id"], kind="collection")
    assessment["evidence"]["measured"]["reasons"] = ["a plausible but unverified explanation"]
    with pytest.raises(ValueError, match="predicate contract"):
        _require_complete_collection(parse(SOURCE), {"measured"}, collection, assessment)


@pytest.mark.parametrize("value", [{}, {"passed": 1}])
def test_claim_gate_rejects_uncheckable_observation(tmp_path, value):
    service, manifest, _ = setup_artifact(tmp_path)
    (tmp_path / "collector.py").write_text(
        "import json,sys\njson.load(sys.stdin)\n"
        + "print(json.dumps({'value': " + repr(value) + "}))\n")
    registry = ArtifactRegistry.load(service, manifest)
    with pytest.raises(ValueError, match="predicate contract"):
        registry.assess_claim("test", "works")


def test_artifact_rejects_unregistered_claims_changed_source_and_methods(tmp_path):
    service, manifest, _ = setup_artifact(tmp_path)
    registry = ArtifactRegistry.load(service, manifest)
    with pytest.raises(ValueError, match="Unknown registered artifact"):
        registry.assess("another")
    (tmp_path / "checked.eal").write_text(SOURCE + "// changed\n")
    with pytest.raises(ValueError, match="pinned digest"):
        registry.assess("test")
    service, manifest, _ = setup_artifact(tmp_path, claims=("missing",))
    with pytest.raises(ValueError, match="claim absent"):
        ArtifactRegistry.load(service, manifest)
    service, manifest, _ = setup_artifact(tmp_path, method_fingerprint="0" * 64)
    with pytest.raises(ValueError, match="method registry differs"):
        ArtifactRegistry.load(service, manifest)


def test_artifact_rejects_path_traversal_and_wrong_context(tmp_path):
    service, manifest, _ = setup_artifact(tmp_path, path="../outside.eal")
    with pytest.raises(ValueError, match="workspace-relative"):
        ArtifactRegistry.load(service, manifest)
    service, manifest, _ = setup_artifact(tmp_path, context_site="other")
    result = ArtifactRegistry.load(service, manifest).assess("test")
    assert result["claims"] == {"works": "out_of_scope"}


def test_mcp_artifact_accepts_only_id_and_exposes_retrievable_assessment(tmp_path):
    _, manifest, tools = setup_artifact(tmp_path)
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "eal.server", "--workspace", str(tmp_path),
              "--registry", str(tools), "--artifacts", str(manifest)],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
    )

    async def exercise():
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = {tool.name: tool for tool in (await session.list_tools()).tools}
                assert "eal_assess_artifact" in tools
                assert set(tools["eal_assess_artifact"].inputSchema["properties"]) == {"artifact_id"}
                attempt = await session.call_tool("eal_assess_artifact", {
                    "artifact_id": "test", "source": SOURCE.replace('"bench"', '"other"')})
                assert attempt.isError
                answer = await session.call_tool("eal_assess_artifact", {"artifact_id": "test"})
                assert not answer.isError, answer
                compact = answer.structuredContent
                assert compact["claims"] == {"works": "supported"}
                assert "source" not in compact
                explanation = await session.call_tool("eal_explain", {
                    "assessment_id": compact["assessment_id"], "claim": "works"})
                assert explanation.structuredContent["result"]["status"] == "supported"

    asyncio.run(exercise())


def test_text_only_recipient_gets_compact_packet_but_cannot_change_host_status(tmp_path):
    service, manifest, _ = setup_artifact(tmp_path)
    artifacts = ArtifactRegistry.load(service, manifest)
    class ContradictoryRecipient:
        def identity(self):
            return {"provider": "scripted", "model": "scripted-non-tool", "measurement_kind": "interface_only",
                    "sampling": {}, "pricing": {"input_usd_per_million": 1, "output_usd_per_million": 1}}

        async def complete(self, messages, max_output_tokens):
            prompt = json.dumps(messages)
            assert SOURCE not in prompt
            assert 'language \\"EAL/2\\"' not in prompt
            assert hashlib.sha256(SOURCE.encode()).hexdigest() in prompt
            return ModelResponse('{"claims":{"works":"unsupported"}}', 30, 8, model="scripted-non-tool")

    async def consult(input_packet):
        assert set(input_packet) == {"task", "checked_assessment"}
        model = await run_unaided(input_packet["task"], ContradictoryRecipient(),
                                  initial_data={"checked_assessment": input_packet["checked_assessment"]},
                                  required_claims=("works",))
        assert model["tool_calls"] == []
        assert model["final"]["claims"]["works"]["status"] == "unsupported"
        return json.dumps(model["final"]["claims"])

    handoff = asyncio.run(artifacts.assist_text_only("test", "Explain the registered assessment", consult))
    assert handoff["checked_answer"]["claims"] == {"works": "supported"}
    assert "unsupported" in handoff["recipient_output_unverified"]
    packet = handoff["checked_answer"]
    second = artifacts.assess("test")
    assert artifacts.finish("test", packet["assessment_id"])["claims"] == {"works": "supported"}
    assert artifacts.finish("test", second["assessment_id"])["claims"] == {"works": "supported"}
    assert ArtifactRegistry.load(service, manifest).finish("test", packet["assessment_id"])["claims"] == {"works": "supported"}


def test_claim_packet_and_explanation_are_pinned_and_claim_scoped(tmp_path):
    service, manifest, _ = setup_artifact(tmp_path, claims=("works", "other"))
    registry = ArtifactRegistry.load(service, manifest)
    packet = registry.assess_claim("test", "works")
    assert packet["status"] == "supported"
    assert packet["scope"]["environment"] == "lab"
    assert packet["scope"]["status"] == "matched"
    assert packet["decisive"]["arguments"][0]["id"] == "result"
    assert packet["evidence_integrity"] == "consistency_checked_not_authenticated"
    assert len(json.dumps(packet).encode()) < 3072
    assert "other" not in json.dumps(packet)
    explained = registry.explain_claim("test", packet["assessment_id"], "works")
    assert explained["packet"] == packet
    assert set(explained["arguments"]) == {"result"}
    assert set(explained["evidence"]) == {"measured"}
    assert "other" not in json.dumps(explained)
    with pytest.raises(ValueError, match="prior host assessment"):
        registry.explain_claim("test", packet["assessment_id"], "other")
    assert ArtifactRegistry.load(service, manifest).finish_claim("test", packet["assessment_id"], "works") == packet
    (tmp_path / "checked.eal").write_text(SOURCE + "// source revision\n")
    with pytest.raises(ValueError, match="pinned digest"):
        registry.finish_claim("test", packet["assessment_id"], "works")


def test_text_only_claim_handoff_keeps_recipient_prose_separate(tmp_path):
    service, manifest, _ = setup_artifact(tmp_path)
    registry = ArtifactRegistry.load(service, manifest)

    async def recipient(input_packet):
        assert input_packet["checked_assessment"]["status"] == "supported"
        assert "claims" not in input_packet["checked_assessment"]
        return "The claim is unsupported."

    result = asyncio.run(registry.assist_text_only("test", "Explain the result", recipient, claim="works"))
    assert result["checked_answer"]["status"] == "supported"
    assert result["recipient_output_unverified"] == "The claim is unsupported."


def test_recipient_mcp_exposes_only_principal_granted_claim(tmp_path):
    _, manifest, tools = setup_artifact(tmp_path, claims=("works", "other"))
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "eal.server", "--workspace", str(tmp_path), "--registry", str(tools),
              "--artifacts", str(manifest), "--recipient-only", "--recipient-principal", "caller_a",
              "--recipient-grant", "test:works"],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
    )

    async def exercise():
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {tool.name for tool in (await session.list_tools()).tools}
                assert names == {"eal_assess_artifact_claim", "eal_explain_artifact_claim",
                                 "eal_finish_artifact_claim"}
                denied = await session.call_tool("eal_assess_artifact_claim", {"artifact_id": "test", "claim": "other"})
                assert denied.isError
                answer = await session.call_tool("eal_assess_artifact_claim", {"artifact_id": "test", "claim": "works"})
                assert not answer.isError
                packet = answer.structuredContent
                assert packet["status"] == "supported"
                trace = await session.call_tool("eal_explain_artifact_claim", {
                    "artifact_id": "test", "claim": "works", "assessment_id": packet["assessment_id"]})
                assert not trace.isError
                assert "other" not in json.dumps(trace.structuredContent)
                denied_trace = await session.call_tool("eal_explain_artifact_claim", {
                    "artifact_id": "test", "claim": "other", "assessment_id": packet["assessment_id"]})
                assert denied_trace.isError

    asyncio.run(exercise())


def test_recipient_mcp_assessment_cannot_be_replayed_across_principals(tmp_path):
    _, manifest, tools = setup_artifact(tmp_path)

    def parameters(principal):
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", "eal.server", "--workspace", str(tmp_path), "--registry", str(tools),
                  "--artifacts", str(manifest), "--recipient-only", "--recipient-principal", principal,
                  "--recipient-grant", "test:works"],
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        )

    async def exercise():
        async with stdio_client(parameters("reader_a")) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("eal_assess_artifact_claim",
                                                 {"artifact_id": "test", "claim": "works"})
                assert not result.isError
                assessment_id = result.structuredContent["assessment_id"]
        args = {"artifact_id": "test", "claim": "works", "assessment_id": assessment_id}
        async with stdio_client(parameters("reader_b")) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                assert (await session.call_tool("eal_finish_artifact_claim", args)).isError
                assert (await session.call_tool("eal_explain_artifact_claim", args)).isError
        # A new process for the original principal can still retrieve its
        # issued assessment from the persistent host store.
        async with stdio_client(parameters("reader_a")) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                finished = await session.call_tool("eal_finish_artifact_claim", args)
                assert not finished.isError
                assert finished.structuredContent["status"] == "supported"

    asyncio.run(exercise())


def test_compact_packet_follows_failed_premise_and_active_objection_predicates():
    from scripts.run_cross_model_campaign import _host_assessment

    cohort = Path(__file__).resolve().parents[1] / "benchmarks/experiments/cross-model-delivery"
    manifest = json.loads((cohort / "manifest.json").read_text())

    def packet_for(root_id, state_id):
        root = next(root for root in manifest["roots"] if root["id"] == root_id)
        state = next(state for state in root["states"] if state["id"] == state_id)
        return _host_assessment(root, state, cohort)[0]

    mismatch = packet_for("release_provenance", "digest_mismatch")
    assert mismatch["schema"] == "eal2-claim-packet/2"
    assert mismatch["status"] == "unsupported"
    reason = mismatch["decisive"]["arguments"][0]["reason"]
    assert "stage_qualifies" in reason and "sha256:8c4a" in reason and "sha256:fb90" in reason
    challenge = packet_for("network_failover", "buffer_challenge")
    assert challenge["status"] == "contested"
    objection = challenge["decisive"]["objections"][0]
    assert objection["status"] == "active" and "switch_buffer_overrun" in objection["reason"]
    for packet in (mismatch, challenge):
        assert packet["decisive"]["argument_count"] >= len(packet["decisive"]["arguments"])
        assert packet["decisive"]["objection_count"] >= len(packet["decisive"]["objections"])
        assert "details_truncated" in packet["decisive"]
        assert len(json.dumps(packet, ensure_ascii=False).encode("utf-8")) <= 3072


def test_operator_cli_assesses_artifact_before_any_model_call(tmp_path):
    _, manifest, tools = setup_artifact(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "eal.artifacts", "--workspace", str(tmp_path),
         "--registry", str(tools), "--artifacts", str(manifest), "--id", "test"],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        capture_output=True, text=True, check=True,
    )
    packet = json.loads(result.stdout)
    assert packet["claims"] == {"works": "supported"}
    assert "source" not in packet and packet["verification"] == "server_assessment"


def test_pinned_negative_argument_retracts_and_restores_on_changed_observations(tmp_path):
    """The compact route uses the actual registered method and objection graph."""
    from scripts.experiment_negative_revisions import PARTIAL_WITNESS, trace

    source = (Path(__file__).resolve().parents[1] / "arguments/negative-revision/counterexample.eal").read_text()
    (tmp_path / "negative.eal").write_text(source)
    trace_path = tmp_path / "current-trace.json"
    collector = tmp_path / "collector.py"
    collector.write_text(
        "import json,sys\nfrom pathlib import Path\n"
        "request=json.load(sys.stdin)\n"
        "if request['tool']=='trace_reader': value=json.loads(Path(" + json.dumps(str(trace_path)) + ").read_text())\n"
        "elif request['tool'] in ('first_test','second_test'): value={'passed':True,'subject':'rig-9','scope':'vibration-interval-9','property':{'operator':'lt','value':1}}\n"
        "else: value={'independently_explained':False}\n"
        "print(json.dumps({'value':value,'observed_at':'2040-01-31T08:20:00Z'}))\n"
    )
    tools_path = tmp_path / "tools.toml"
    tools_path.write_text("".join(
        f'[tools.{name}]\nkind="command"\nmode="deterministic"\nversion="1"\n'
        f'argv={json.dumps([sys.executable, str(collector)])}\n'
        for name in ("first_test", "second_test", "trace_reader", "independent_check")))
    service = ReasoningService(tmp_path, tools_path, method_registry=sampled_negative_registry())
    manifest = tmp_path / "artifacts.toml"
    manifest.write_text(
        '[artifacts.negative]\npath="negative.eal"\n'
        f'sha256="{hashlib.sha256(source.encode()).hexdigest()}"\n'
        f'method_registry_fingerprint="{service.method_registry.fingerprint}"\n'
        'claims=["property_supported","violating_sample"]\n'
        'now="2040-01-31T08:30:00Z"\n'
        '[artifacts.negative.context]\nsite="test-rig-9"\n')
    artifacts = ArtifactRegistry.load(service, manifest)

    def assess(events, scope="vibration-interval-9"):
        trace_path.write_text(json.dumps(trace("counterexample", events, scope=scope)))
        return artifacts.assess("negative")

    before = assess([{"time": 4, "value": 0.8}])
    challenged = assess(PARTIAL_WITNESS)
    restored = assess(PARTIAL_WITNESS, scope="other-interval")
    assert before["claims"] == {"property_supported": "supported", "violating_sample": "unsupported"}
    assert challenged["claims"] == {"property_supported": "contested", "violating_sample": "supported"}
    assert restored["claims"] == before["claims"]
    assert artifacts.finish("negative", challenged["assessment_id"])["claims"] == challenged["claims"]
    assert artifacts.finish("negative", restored["assessment_id"])["claims"] == restored["claims"]
