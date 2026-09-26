"""Independent expected outcomes and local revision traces for the coolant task."""
from __future__ import annotations

import copy

from experiments.composition_revision import baseline
from experiments.composition_revision.study import BASE_TIME, CONTEXT, SOURCE_PATH, _record, load_cases, run_arm
from eal.parser import parse


def test_both_assessors_match_expected_claims_and_affected_set() -> None:
    fixture = load_cases()
    prior = {}
    for case in fixture["cases"]:
        for arm in ("eal", "typed_rule"):
            result = run_arm(case, arm)
            assert result["claims"] == case["expected"], (case["id"], arm)
            if predecessor := case.get("revision_of"):
                changed = {name for name, status in result["claims"].items()
                           if status != prior[arm][predecessor][name]}
                assert changed == set(case["affected"]), (case["id"], arm)
            prior.setdefault(arm, {})[case["id"]] = result["claims"]


def test_local_objection_does_not_defeat_the_independent_flow_route() -> None:
    by_id = {case["id"]: case for case in load_cases()["cases"]}
    for arm in ("eal", "typed_rule"):
        with_backup = run_arm(by_id["pump_a_disputed_with_alternative"], arm)
        alone = run_arm(by_id["pump_a_disputed_alone"], arm)
        assert with_backup["argument_statuses"]["pump_a_route"] == "contested"
        assert with_backup["argument_statuses"]["pump_b_route"] == "supported"
        assert with_backup["claims"]["cooling_at_8kw"] == "supported"
        assert alone["claims"]["flow_sufficient"] == "contested"
        assert alone["claims"]["cooling_at_8kw"] == "contested"


def test_shared_premise_and_expiry_recompute_only_dependent_claims() -> None:
    by_id = {case["id"]: case for case in load_cases()["cases"]}
    for arm in ("eal", "typed_rule"):
        revoked = run_arm(by_id["shared_supply_revoked"], arm)
        expired = run_arm(by_id["flow_readings_expire"], arm)
        assert revoked["claims"]["power_sufficient"] == "unsupported"
        assert revoked["claims"]["flow_sufficient"] == "unsupported"
        assert revoked["claims"]["rejection_sufficient"] == "supported"
        assert expired["evidence_statuses"]["power_bus"] == "available"
        assert expired["evidence_statuses"]["pump_a_flow"] == "unavailable"
        assert expired["evidence_statuses"]["pump_b_flow"] == "unavailable"
        assert expired["evidence_statuses"]["exchanger_test"] == "available"


def test_baseline_rejects_tampering_and_boolean_number_confusion() -> None:
    original = load_cases()["cases"][0]
    altered = copy.deepcopy(original)
    altered["observations"]["power_bus"]["voltage_v"] = True
    for arm in ("eal", "typed_rule"):
        result = run_arm(altered, arm)
        assert result["evidence_statuses"]["power_bus"] == "unavailable"
        assert result["claims"]["power_sufficient"] == "unsupported"
        assert result["claims"]["cooling_at_8kw"] == "unsupported"

    # The typed comparator checks its own source identity and data digest.
    spec = baseline.EVIDENCE["power_bus"]
    record = _record(spec.name, {"voltage_v": 25}, source_digest=baseline.CONFIG_DIGEST,
                     kind=spec.kind, requested_input=spec.request, context=CONTEXT)
    record["value"]["voltage_v"] = 12
    assert not baseline._record_available(spec, record, now=BASE_TIME, context=CONTEXT)


def test_matched_configuration_and_freshness_boundary() -> None:
    program = parse(SOURCE_PATH.read_text())
    assert set(program.claims) == set(baseline.CLAIM_DECLARATIONS)
    for name, claim in program.claims.items():
        other = baseline.CLAIM_DECLARATIONS[name]
        assert (claim.statement, claim.environment) == (other.statement, other.environment)
    assert set(program.reasoning) == set(baseline.REASONING)
    for name, reasoning in program.reasoning.items():
        other = baseline.REASONING[name]
        assert (reasoning.method, reasoning.rationale) == (other.method, other.rationale)
    assert [(p.path, p.operator, p.expected) for p in program.environments["loop_a"].predicates] == [
        (p.field, p.operator, p.value) for p in baseline.SCOPE]
    assert set(program.evidence) == set(baseline.EVIDENCE)
    for name, item in program.evidence.items():
        other = baseline.EVIDENCE[name]
        assert item.kind == other.kind
        assert item.max_age == other.max_age
        assert item.input == other.request
        assert [(p.path, p.operator, p.expected) for p in item.predicates] == [
            (p.field, p.operator, p.value) for p in other.criteria]
    assert all(criterion.unit is not None for item in baseline.EVIDENCE.values()
               for criterion in item.criteria if criterion.field in
               {"voltage_v", "flow_lpm", "removed_heat_kw"})
    assert set(program.arguments) == {rule.name for rule in baseline.RULES}
    for rule in baseline.RULES:
        authored = program.arguments[rule.name]
        assert (authored.conclusion, authored.reasoning, authored.evidence, authored.premises) == (
            rule.conclusion, rule.reasoning, rule.evidence, rule.premises)
    nominal = load_cases()["cases"][0]
    boundary = {**nominal, "assessed_at": "2026-09-23T12:01:00Z"}
    for arm in ("eal", "typed_rule"):
        assert run_arm(boundary, arm)["claims"]["cooling_at_8kw"] == "supported"
        widened = {**nominal, "context": {**CONTEXT, "operator_note": "extra metadata", "load_kw": 8.0}}
        assert run_arm(widened, arm)["claims"]["cooling_at_8kw"] == "supported"


def test_external_case_can_supply_its_observation_instant() -> None:
    nominal = load_cases()["cases"][0]
    case = {**nominal, "observed_at": "2026-09-23T13:00:00Z",
            "assessed_at": "2026-09-23T13:00:01Z"}
    for arm in ("eal", "typed_rule"):
        assert run_arm(case, arm)["claims"]["cooling_at_8kw"] == "supported"
