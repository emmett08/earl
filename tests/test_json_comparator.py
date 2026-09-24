"""Independent JSON graph arm under the same reviewed-task and evidence gate."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from benchmarks import equal_checker


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "experiments" / "eal2-reviewed-rag" / "json_checker.py"
FIXTURES = ROOT / "benchmarks" / "experiments" / "cross-model-delivery"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
SPEC = importlib.util.spec_from_file_location("json_reviewed_checker", BENCHMARK)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
JsonReviewedChecker = MODULE.JsonReviewedChecker


def _checker(root: dict, **changes) -> JsonReviewedChecker:
    params = dict(
        trusted_question=root["brief"], authorised_tasks={root["id"]},
        authorised_families={root["id"]}, authorised_artifacts={root["id"]},
        authorised_claims={root["claim"]},
    )
    params.update(changes)
    return JsonReviewedChecker.from_root(root, **params)


def _records(root: dict, state_id: str) -> dict:
    return equal_checker.evidence_for_state(root["id"], state_id, FIXTURES)


@pytest.mark.parametrize("root", MANIFEST["roots"], ids=lambda root: root["id"])
def test_frozen_states_match_independent_graph_except_refused_stale(root):
    checker = _checker(root)
    for state in root["states"]:
        result = checker.assess_bound(_records(root, state["id"]), root["now"])
        expected = ("refused" if root["id"] == "thermal_soak"
                    and state["id"] == "stale_qualifying" else state["expected"])
        assert result["status"] == expected, (root["id"], state["id"], result)
        assert result["claim"] == root["claim"]
        assert result["task_id"] == root["id"]
        assert len(result["graph_sha256"]) == len(result["contract_sha256"]) == 64


@pytest.mark.parametrize("root", MANIFEST["roots"], ids=lambda root: root["id"])
def test_frozen_tamper_states_distinguish_negative_finding_from_missing_freshness(root):
    checker = _checker(root)
    for state in root["tamper"]:
        result = checker.assess_bound(_records(root, state["id"]), root["now"])
        expected = ("refused" if state["id"] in
                    {"future_timestamp", "stale_alert", "stale_answer"}
                    else state["expected"])
        assert result["status"] == expected, (root["id"], state["id"], result)


@pytest.mark.parametrize("change", [
    {"trusted_question": "A fluent paraphrase of an unreviewed question"},
    {"authorised_tasks": set()}, {"authorised_families": set()},
    {"authorised_artifacts": set()}, {"authorised_claims": set()},
])
def test_wrong_question_or_grant_refuses_before_evidence_evaluation(monkeypatch, change):
    root = MANIFEST["roots"][0]
    checker = _checker(root, **change)

    def assessed(*_args, **_kwargs):
        pytest.fail("Unreviewed task attempted to assess evidence")

    monkeypatch.setattr(equal_checker, "evaluate", assessed)
    result = checker.assess_bound(_records(root, "matching_stage"), root["now"])
    assert result["status"] == "refused"


def test_pinned_context_time_and_graph_identity_refuse_before_evidence(monkeypatch):
    root = MANIFEST["roots"][0]
    graph = equal_checker.graph_for_root(root["id"])
    other_context = JsonReviewedChecker(graph, task_id=root["id"],
                                        reviewed_question=root["brief"],
                                        trusted_question=root["brief"],
                                        family_id=root["id"], artifact_id=root["id"],
                                        claim=root["claim"], context={"lane": "East-9"},
                                        assessment_time=root["now"],
                                        authorised_tasks={root["id"]},
                                        authorised_families={root["id"]},
                                        authorised_artifacts={root["id"]},
                                        authorised_claims={root["claim"]})

    def assessed(*_args, **_kwargs):
        pytest.fail("Changed task scope attempted evidence assessment")

    monkeypatch.setattr(equal_checker, "evaluate", assessed)
    records = _records(root, "matching_stage")
    assert other_context.assess_bound(records, root["now"])["status"] == "refused"
    assert _checker(root).assess_bound(records, "2026-09-24T12:01:00Z")["status"] == "refused"
    with pytest.raises(ValueError, match="graph path"):
        JsonReviewedChecker.from_root({**root, "graph": "other.json"},
                                      trusted_question=root["brief"],
                                      authorised_tasks={root["id"]},
                                      authorised_families={root["id"]},
                                      authorised_artifacts={root["id"]},
                                      authorised_claims={root["claim"]})


def test_required_optional_objection_and_answer_records_are_complete():
    root = MANIFEST["roots"][2]
    checker = _checker(root)
    records = _records(root, "qualifying_test")
    for name in ("failover_reader", "buffer_alert_reader", "packet_trace_reader"):
        absent = copy.deepcopy(records)
        del absent[name]
        result = checker.assess_bound(absent, root["now"])
        assert result["status"] == "refused"
        assert any(item["record"] == name for item in result["trace"]["unresolved_evidence"])
    extra = copy.deepcopy(records)
    extra["unrelated_reader"] = copy.deepcopy(records["packet_trace_reader"])
    assert checker.assess_bound(extra, root["now"])["status"] == "refused"


def test_wrong_tool_scope_future_and_missing_field_refuse_but_false_finding_is_valid():
    root = MANIFEST["roots"][2]
    checker = _checker(root)
    original = _records(root, "qualifying_test")
    for altered in (
        lambda r: r["buffer_alert_reader"]["request"].update(tool="unrelated"),
        lambda r: r["buffer_alert_reader"]["context"].update(switch="NS-8"),
        lambda r: r["buffer_alert_reader"].update(observed_at="2999-01-01T00:00:00Z"),
        lambda r: r["buffer_alert_reader"]["value"].pop("finding"),
        lambda r: r["failover_reader"]["value"].update(pass_=1),
    ):
        records = copy.deepcopy(original)
        altered(records)
        if "pass_" in records["failover_reader"]["value"]:
            records["failover_reader"]["value"]["pass"] = records["failover_reader"]["value"].pop("pass_")
        assert checker.assess_bound(records, root["now"])["status"] == "refused"
    records = copy.deepcopy(original)
    records["failover_reader"]["value"]["pass"] = False
    assert checker.assess_bound(records, root["now"])["status"] == "unsupported"


def test_checker_cannot_be_changed_by_mutating_the_original_graph_or_a_packet():
    root = MANIFEST["roots"][0]
    graph = equal_checker.graph_for_root(root["id"])
    checker = JsonReviewedChecker(graph, task_id=root["id"],
                                  reviewed_question=root["brief"],
                                  trusted_question=root["brief"],
                                  family_id=root["id"], artifact_id=root["id"],
                                  claim=root["claim"], context=root["context"],
                                  assessment_time=root["now"],
                                  authorised_tasks={root["id"]},
                                  authorised_families={root["id"]},
                                  authorised_artifacts={root["id"]},
                                  authorised_claims={root["claim"]})
    graph["routes"][0]["all"][0]["value"] = "another_release"
    records = _records(root, "matching_stage")
    first = checker.assess_bound(records, root["now"])
    assert first["status"] == "supported"
    first["status"] = "unsupported"
    records["stage_reader"]["value"]["digest"] = "sha256:other"
    assert checker.assess_bound(records, root["now"])["status"] == "unsupported"
    checker.graph["routes"][0]["all"][0]["value"] = "tampered_after_binding"
    assert checker.assess_bound(records, root["now"])["status"] == "refused"


def test_ambiguous_string_grant_is_configuration_error():
    root = MANIFEST["roots"][0]
    with pytest.raises(ValueError, match="exact task identifiers"):
        _checker(root, authorised_tasks=root["id"])
