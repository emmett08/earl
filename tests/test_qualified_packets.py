"""Qualified declarations survive packet projection without weakening bounds."""
from __future__ import annotations

import json
import sys

import pytest

from eal.knowledge import EALKnowledgeBase, ModelContextAdapter
from eal.packets import AssessmentPacketBuilder
from test_packets import _assessment


SOURCE = '''language "EAL/3"
environment lab {
  require site == "bench"
}
tool reader {
  version "1"
}
reasoning measured {
  method "structured/1"
  rationale "The retained synthetic observation meets the stated predicate."
}
pattern check(env: environment, collector: tool, criterion: reasoning) {
  context environment env, tool collector, kind test, max_age 60 {
    evidence readings {
      require ok == true
    }
    claim works {
      statement "The synthetic observation reports a passing check."
    }
    argument assess = [evidence readings] via criterion => works
  }
}
apply suite.case = check(env=lab, collector=reader, criterion=measured)
'''


def test_registered_pattern_assessment_and_model_context_preserve_qualified_ids(tmp_path):
    (tmp_path / "case.eal").write_text(SOURCE)
    collector = tmp_path / "collector.py"
    collector.write_text(
        "import json, sys\n"
        "request = json.load(sys.stdin)\n"
        "assert request['evidence_id'] == 'suite.case.readings'\n"
        "print(json.dumps({'value': {'ok': True, 'secret': 'raw-tool-secret'}, "
        "'observed_at': '2040-01-01T00:00:00Z'}))\n"
    )
    registry = tmp_path / "tools.toml"
    registry.write_text(
        '[tools.reader]\nkind="command"\nversion="1"\n'
        f'argv={json.dumps([sys.executable, str(collector)])}\n'
    )
    database = tmp_path / "records.sqlite3"
    knowledge = EALKnowledgeBase(tmp_path, registry, database)
    knowledge.register("case.eal", entry_id="demo", context={"site": "bench"})
    result = knowledge.assess("demo", "suite.case.works", now="2040-01-01T00:00:01Z")
    assert (result["status"], result["collected_count"], result["reused_count"]) == ("supported", 1, 0)
    packet = result["packet"]
    assert set(packet["claims"]) == {"suite.case.works"}
    assert packet["arguments"]["suite.case.assess"]["conclusion"] == "suite.case.works"
    assert set(packet["evidence"]) == {"suite.case.readings"}
    assert packet["claims"]["suite.case.works"]["observation_ids"][0]["evidence_id"] == "suite.case.readings"
    assert "raw-tool-secret" not in json.dumps(packet)
    assert knowledge.explain(result["assessment_id"], "suite.case.works")["result"]["status"] == "supported"

    reopened = EALKnowledgeBase(tmp_path, registry, database)
    prepared = ModelContextAdapter(reopened).prepare(
        "What did this synthetic check establish?", "demo", "suite.case.works",
        now="2040-01-01T00:00:01Z",
    )
    assert prepared["assessment"]["reused_count"] == 1
    assert prepared["assessment"]["collected_count"] == 0
    assert prepared["context"]["claim_id"] == "suite.case.works"
    assert prepared["context"]["claims"]["suite.case.works"]["evidence_ids"] == ["suite.case.readings"]
    assert "raw-tool-secret" not in json.dumps(prepared["context"])


def test_qualified_dependencies_keep_premises_binding_assumptions_and_objections():
    assessment = _assessment()
    assessment["arguments"]["experiment"]["dependencies"]["premises"] = ["other"]
    names = {name: "module.case." + name for group in (
        "claims", "arguments", "assumptions", "objections", "evidence")
        for name in assessment[group]}
    names.update(causal_reason="module.case.causal_reason", structured_reason="module.case.structured_reason")

    def qualify(value):
        if isinstance(value, dict):
            return {names.get(key, key): qualify(item) for key, item in value.items()}
        if isinstance(value, list):
            return [qualify(item) for item in value]
        if isinstance(value, str):
            if value.startswith("objection:"):
                return "objection:" + names.get(value.removeprefix("objection:"), value.removeprefix("objection:"))
            return names.get(value, value)
        return value

    packet = AssessmentPacketBuilder().build(qualify(assessment), claims=[names["pressure"]])
    assert packet["premise_claims"][names["other"]]["status"] == "supported"
    assert packet["arguments"][names["experiment"]]["premises"] == [names["other"]]
    assert packet["arguments"][names["experiment"]]["method_result"]["binding"]["evidence_id"] == names["trial"]
    assert packet["assumptions"][names["calibration"]]["validation"] == names["calibration_check"]
    assert packet["objections"][names["sensor_fault"]]["target"] == names["experiment"]
    assert packet["objections"][names["sensor_fault"]]["attackers"] == [names["counter_fault"]]
    assert "SUPER_SECRET_TOOL_CREDENTIAL" not in json.dumps(packet)


@pytest.mark.parametrize("name", ["plain_name", "_suite.part_2.claim", "a." + "b" * 126])
def test_packet_accepts_simple_and_bounded_qualified_names(name):
    assessment = {"valid": True, "assessment_id": "stored-1", "claims": {
        name: {"status": "unsupported", "statement": "A synthetic test claim."}}}
    assert set(AssessmentPacketBuilder().build(assessment)["claims"]) == {name}


@pytest.mark.parametrize("name", [
    "", ".claim", "suite.", "suite..claim", "suite.2claim", "suite./claim",
    "suite.claim;exec", "suite.claim\n", "suite.claim\x00", "suite.café",
    "suite.<script>", "suite.$(command)", "a." + "b" * 127, "a" * 129,
])
def test_packet_rejects_malformed_or_oversize_qualified_names(name):
    assessment = {"valid": True, "assessment_id": "stored-1", "claims": {
        name: {"status": "unsupported", "statement": "A synthetic test claim."}}}
    with pytest.raises(ValueError, match="bounded EAL identifiers"):
        AssessmentPacketBuilder().build(assessment)


@pytest.mark.parametrize("field", ["supporting_arguments", "objections"])
def test_packet_rejects_malicious_dependency_names(field):
    assessment = {"valid": True, "assessment_id": "stored-1", "claims": {
        "suite.claim": {"status": "unsupported", field: ["suite.claim;exec"]}}}
    with pytest.raises(ValueError, match="bounded EAL identifiers"):
        AssessmentPacketBuilder().build(assessment)
