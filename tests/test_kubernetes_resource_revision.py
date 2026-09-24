"""Synthetic Kubernetes revision: imported observations and bounded inference."""

from copy import deepcopy
import json
from pathlib import Path

from eal.evaluator import canonical_digest, environment_fingerprint, evaluate
from eal.parser import parse
from eal.runtime import ReasoningService, acquisition_request
from examples.kubernetes_resource_gate import assess_operating_basis


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "kubernetes-resource-revision"
SOURCE = (ROOT / "examples" / "kubernetes-resource-revision.eal").read_text()
PROGRAM = parse(SOURCE)
ROOT_CLAIM = "provisional_operating_basis"


def fixture(name):
    return json.loads((EXAMPLE / f"{name}.json").read_text())


def records(state):
    context = state["context"]
    result = {}
    for name, value in state["values"].items():
        evidence = PROGRAM.evidence[name]
        tool = PROGRAM.tools[evidence.tool]
        result[name] = {
            "evidence_id": name,
            "source_digest": PROGRAM.source_digest,
            "tool": tool.name,
            "tool_version": tool.version,
            "mode": tool.mode,
            "evidence_kind": evidence.kind,
            "environment": evidence.environment,
            "environment_fingerprint": environment_fingerprint(evidence.environment, context),
            "input_digest": canonical_digest(evidence.input),
            "acquisition_request": acquisition_request(PROGRAM, name, context),
            "collected_at": state["observed_at"],
            "run_id": f"synthetic-{name}",
            "status": "ok",
            "value": value,
            "data_digest": canonical_digest(value),
        }
        if name in state.get("measurement_details", {}):
            result[name]["details"] = {"measurement_identity": deepcopy(state["measurement_details"][name])}
    return result


def assess(state, *, supplied_records=None):
    return evaluate(PROGRAM, records(state) if supplied_records is None else supplied_records,
                    context=state["context"], now=state["now"])


def test_initial_batch_and_mitigation_revise_only_the_bounded_operating_basis():
    initial = assess(fixture("pre-batch"))
    batch = assess(fixture("after-batch"))
    repaired = assess(fixture("after-mitigation"))
    assert all(report["valid"] for report in (initial, batch, repaired))
    assert [report["claims"][ROOT_CLAIM]["status"] for report in (initial, batch, repaired)] == [
        "supported", "contested", "supported"]
    assert all(report["claims"]["bounded_canary"]["status"] == "supported"
               for report in (initial, batch, repaired))
    assert batch["objections"]["batch_cpu_interference"]["status"] == "active"
    assert batch["arguments"]["operating_route"]["status"] == "contested"
    assert batch["claims"][ROOT_CLAIM]["supporting_arguments"] == []
    assert repaired["objections"]["batch_cpu_interference"]["status"] == "inactive"
    assert initial["claims"][ROOT_CLAIM]["prose_verified"] is False
    lower = initial["arguments"]["success_sample"]["reasoning_result"]["details"]["lower"]
    assert 0.998 < lower < 1
    sampled = initial["arguments"]["latency_sample"]["reasoning_result"]["details"]
    assert sampled["coverage"] and sampled["holds"]
    assert sampled["continuous_truth_established"] is False


def test_after_batch_latency_violation_blocks_canary_as_well_as_operating_basis():
    state = fixture("after-batch")
    state["values"]["sampled_p99"]["events"][2]["value"] = 185
    report = assess(state)
    assert report["claims"]["sampled_latency"]["status"] == "unsupported"
    assert report["claims"]["bounded_canary"]["status"] == "unsupported"
    assert report["claims"][ROOT_CLAIM]["status"] == "unsupported"
    assert report["objections"]["batch_cpu_interference"]["status"] == "active"


def test_old_rollout_cannot_be_reused_and_historical_assessment_remains_scoped():
    before = fixture("pre-batch")
    historical = assess(before)
    later = fixture("after-batch")
    stale = records(later)
    stale["rollout_snapshot"] = records(before)["rollout_snapshot"]
    result = assess(later, supplied_records=stale)
    assert result["evidence"]["rollout_snapshot"]["status"] == "unavailable"
    assert result["claims"][ROOT_CLAIM]["status"] == "unsupported"
    assert historical["claims"][ROOT_CLAIM]["status"] == "supported"
    changed = deepcopy(later)
    changed["context"]["cluster_uid"] = "different-cluster"
    outside = assess(changed, supplied_records=records(later))
    assert outside["claims"][ROOT_CLAIM]["status"] == "out_of_scope"


def test_missing_attacker_record_exposes_open_evidence_coverage_obligation():
    state = fixture("after-batch")
    incomplete = records(state)
    del incomplete["observed_contention"]
    report = assess(state, supplied_records=incomplete)
    # The evaluator only assesses submitted authored attacks. Its support
    # label must never be read as proof that the collector searched exhaustively.
    assert report["evidence"]["observed_contention"]["status"] == "unavailable"
    assert report["claims"][ROOT_CLAIM]["status"] == "supported"
    gated = assess_operating_basis(incomplete, state["context"], state["now"])
    assert gated["raw_eal_status"] == "supported"
    assert gated["status"] == "unresolved"
    assert any("mandatory acquisition is missing" in reason for reason in gated["reasons"])
    without_manifest = records(state)
    del without_manifest["monitor_manifest"]
    assert assess_operating_basis(without_manifest, state["context"], state["now"])["status"] == "unresolved"


def test_application_gate_requires_complete_coherent_monitoring_before_acceptance():
    initial, batch, mitigation = (fixture(name) for name in (
        "pre-batch", "after-batch", "after-mitigation"))
    assert assess_operating_basis(records(initial), initial["context"], initial["now"])["status"] == "accepted"
    assert assess_operating_basis(records(batch), batch["context"], batch["now"])["status"] == "contested"
    assert assess_operating_basis(records(mitigation), mitigation["context"], mitigation["now"])["status"] == "accepted"


def test_application_gate_fails_closed_for_stale_failed_or_wrong_request():
    state = fixture("pre-batch")
    for name in ("observed_contention", "monitor_manifest"):
        for alteration in ("stale", "failed", "wrong_request"):
            supplied = records(state)
            monitor = supplied[name]
            if alteration == "stale":
                monitor["collected_at"] = "2026-09-24T10:20:00Z"
            elif alteration == "failed":
                monitor["status"] = "error"
            else:
                monitor["acquisition_request"]["context"]["cluster_uid"] = "other-cluster"
            gated = assess_operating_basis(supplied, state["context"], state["now"])
            assert gated["status"] == "unresolved", (name, alteration, gated["reasons"])


def test_application_gate_rejects_mismatched_target_window_and_false_nonfinding():
    state = fixture("pre-batch")
    for name, field, value in (
        ("observed_contention", "target_pod_uid", "another-pod"),
        ("monitor_manifest", "node_uid", "another-node"),
        ("observed_contention", "window_start", "2026-09-24T10:25:30Z"),
        ("monitor_manifest", "query_complete", False),
        ("observed_contention", "target_throttled_ratio", 0.28),
    ):
        supplied = records(state)
        item = supplied[name]
        item["value"][field] = value
        item["data_digest"] = canonical_digest(item["value"])
        gated = assess_operating_basis(supplied, state["context"], state["now"])
        assert gated["status"] == "unresolved", (name, field, gated["reasons"])


def test_application_gate_rejects_wrong_measurement_series_and_payload_binding():
    state = fixture("pre-batch")
    for name, field, value in (
        ("sampled_responses", "trial_id", "checkout-trial-1130"),
        ("sampled_p99", "target_pod_uid", "another-pod"),
        ("sampled_responses", "window_end", "2026-09-24T10:30:30Z"),
        ("sampled_p99", "series_id", "p99-1130"),
    ):
        supplied = records(state)
        supplied[name]["details"]["measurement_identity"][field] = value
        gated = assess_operating_basis(supplied, state["context"], state["now"])
        assert gated["status"] == "unresolved", (name, field, gated["reasons"])
        assert gated["raw_eal_status"] == "supported"
    unbound = records(state)
    del unbound["sampled_responses"]["details"]
    assert assess_operating_basis(unbound, state["context"], state["now"])["status"] == "unresolved"
    swapped = records(state)
    swapped["sampled_p99"]["details"]["measurement_identity"]["payload_digest"] = (
        state["measurement_details"]["sampled_responses"]["payload_digest"])
    assert assess_operating_basis(swapped, state["context"], state["now"])["status"] == "unresolved"
    wrong_series_payload = records(state)
    sample = wrong_series_payload["sampled_p99"]
    sample["value"]["events"][2]["value"] = 119
    sample["data_digest"] = canonical_digest(sample["value"])
    sample["details"]["measurement_identity"]["payload_digest"] = sample["data_digest"]
    gated = assess_operating_basis(wrong_series_payload, state["context"], state["now"])
    assert gated["raw_eal_status"] == "supported"
    assert gated["status"] == "unresolved"
    assert any("series payload digest differs" in reason for reason in gated["reasons"])


def test_actual_json_file_adapter_binds_request_scope_and_original_observation_time(tmp_path):
    state = fixture("after-batch")
    (tmp_path / "observations").mkdir()
    registry = []
    for name, value in state["values"].items():
        evidence = PROGRAM.evidence[name]
        tool = PROGRAM.tools[evidence.tool]
        file_name = f"observations/{tool.name}.json"
        payload = {"value": value, "observed_at": state["observed_at"],
                   "context": state["context"],
                   "request": acquisition_request(PROGRAM, name, state["context"])}
        if name in state.get("measurement_details", {}):
            payload["details"] = {"measurement_identity": state["measurement_details"][name]}
        (tmp_path / file_name).write_text(json.dumps(payload), encoding="utf-8")
        registry.append(f'[tools.{tool.name}]\nkind = "json_file"\npath = "{file_name}"\n'
                        f'version = "{tool.version}"\nmode = "{tool.mode}"\n')
    registry_path = tmp_path / "tools.toml"
    registry_path.write_text("\n".join(registry), encoding="utf-8")
    service = ReasoningService(tmp_path, registry_path)
    assert service.validate(SOURCE)["valid"]
    collected = service.collect(SOURCE, state["context"])
    assert all(item["collected_at"] == state["observed_at"] for item in collected["records"].values())
    report = service.reason(SOURCE, state["context"], collected["collection_id"], state["now"])
    assert report["claims"][ROOT_CLAIM]["status"] == "contested"
    assert assess_operating_basis(collected["records"], state["context"], state["now"])["status"] == "contested"
    assert service.explain(report["assessment_id"], ROOT_CLAIM)["result"]["status"] == "contested"
    # A file that claims another acquisition request fails before inference.
    payload["request"]["context"]["cluster_uid"] = "different-cluster"
    (tmp_path / file_name).write_text(json.dumps(payload), encoding="utf-8")
    bad = service.collect(SOURCE, state["context"], [name])["records"][name]
    assert bad["status"] == "error"
    assert "request differs" in bad["error"]["message"]
