"""Adequacy cannot be inferred from fluent prose, availability or raw support."""
from copy import deepcopy

import pytest

from eal.adequacy import AdequacyContract, AdequacyEvaluator, AdequacyRegistry
from eal.evaluator import evaluate
from eal.parser import parse
from test_evaluator import CONTEXT, NOW, record


SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool runner { version "1"; mode deterministic; }
evidence report { tool runner; kind test; environment lab; max_age 60;
 require "complete" == true;
}
reasoning summary { method "structured/1"; rationale "Complete report counts establish this report-only criterion."; }
claim bounded { statement "The complete report contains at least 100 requests and at most one error."; environment lab; }
argument observed { conclusion bounded; reasoning summary; evidence report; }
'''
VALUE = {"complete": True, "request_count": 100, "error_count": 1}


def clause(identifier, path, expected, *, operator="==", role="threshold", target="evidence", reference="report", **kwargs):
    return {"id": identifier, "role": role, "target": target, "reference": reference,
            "path": path, "operator": operator, "expected": expected,
            "rationale": "This reviewed clause tests the identified report criterion.", **kwargs}


def setup(source=SOURCE, values=None, clauses=None, **settings):
    program = parse(source)
    records = {key: record(program, key, value) for key, value in (values or {"report": VALUE}).items()}
    collection = {"source_digest": program.source_digest, "context": CONTEXT, "records": records,
                  "collection_id": "collection-1"}
    assessment = evaluate(program, records, now=NOW, context=CONTEXT)
    assessment.update(collection_id="collection-1", assessment_id="assessment-1")
    config = {"source_digest": program.source_digest, "claim": "bounded", "statement": program.claims["bounded"].statement,
              "environment": "lab", "methods": ["structured/1"], "correspondence": "reviewed_source",
              "obligations": clauses if clauses is not None else [
                  clause("count", "request_count", 100, operator=">=", role="coverage"),
                  clause("errors", "error_count", 1, operator="<=")], **settings}
    return config, {"source": source, "assessment": assessment, "collection": collection, "context": CONTEXT}


def assess(config, inputs, **kwargs):
    return AdequacyEvaluator().assess(AdequacyContract.from_dict(config), **inputs, **kwargs)


def test_report_criteria_are_executed_separately_from_raw_support():
    config, inputs = setup()
    answer = assess(config, inputs)
    assert answer["status"] == "adequate"
    assert answer["claim_status"] == "supported"
    assert all(item["status"] == "satisfied" for item in answer["obligations"])
    assert answer["correspondence"]["prose_verified"] is False
    assert len(answer["contract_digest"]) == 64
    # The existing source's authored relation still supplies EAL support; the
    # independent stricter obligation correctly fails for this observation.
    config, inputs = setup(values={"report": {**VALUE, "error_count": 2}})
    answer = assess(config, inputs)
    assert answer["claim_status"] == "supported"
    assert answer["status"] == "insufficient"


@pytest.mark.parametrize("change", ["prose", "source", "context", "collection", "statement", "method"])
def test_changed_correspondence_or_execution_identity_cannot_be_adequate(change):
    config, inputs = setup()
    kwargs = {}
    if change == "prose":
        kwargs["prose"] = "The service always succeeds for every production request."
    elif change == "source":
        inputs["source"] += "\n// amended\n"
    elif change == "context":
        inputs["context"] = {"site": "production"}
    elif change == "collection":
        inputs["assessment"]["collection_id"] = "unrelated"
    elif change == "statement":
        inputs["assessment"]["claims"]["bounded"]["statement"] = "The service always succeeds."
    else:
        config["methods"] = ["deductive/1"]
    assert assess(config, inputs, **kwargs)["status"] == "unresolved"


@pytest.mark.parametrize("replacement", [True, "100", None, float("inf")])
def test_missing_or_mistyped_fields_are_unresolved_not_false(replacement):
    config, inputs = setup(clauses=[clause("size", "request_count", 100)])
    # Alter the expected predicate, keeping the acquired payload valid.
    if replacement == float("inf"):
        config["obligations"][0]["expected"] = replacement
        with pytest.raises(ValueError):
            assess(config, inputs)
    else:
        config["obligations"][0]["expected"] = replacement
        assert assess(config, inputs)["obligations"][0]["status"] == "unresolved"


def test_empty_obligations_and_unresolved_mapping_never_upgrade_support():
    config, inputs = setup(clauses=[])
    assert assess(config, inputs)["status"] == "unresolved"


@pytest.mark.parametrize("field", ["assessment_id", "collection_id"])
def test_missing_stored_identity_is_an_assessment_contract_error(field):
    config, inputs = setup()
    del inputs["assessment"][field]
    answer = assess(config, inputs)
    assert answer["status"] == "unresolved"
    assert answer["diagnostics"][0]["code"] == "assessment_contract_error"


def test_missing_collection_identity_cannot_be_adequate():
    config, inputs = setup()
    del inputs["collection"]["collection_id"]
    assert assess(config, inputs)["status"] == "unresolved"


def test_unrelated_context_predicate_cannot_stand_for_main_conclusion():
    config, inputs = setup(clauses=[clause("unrelated", "site", "bench", target="context", reference="")])
    answer = assess(config, inputs)
    assert answer["obligations"][0]["status"] == "satisfied"
    assert answer["status"] == "unresolved"


def test_unrelated_fresh_evidence_cannot_stand_for_main_conclusion():
    source = SOURCE + '''
evidence unrelated { tool runner; kind test; environment lab; max_age 60; require "passed" == true; }
'''
    config, inputs = setup(source, values={"report": VALUE, "unrelated": {"passed": True}},
                           clauses=[clause("unrelated", "passed", True, reference="unrelated")])
    assert assess(config, inputs)["status"] == "unresolved"
    config, inputs = setup(correspondence="unresolved")
    assert assess(config, inputs)["status"] == "unresolved"


@pytest.mark.parametrize("key,value", [("status", "error"), ("data_digest", "bad"), ("collected_at", "2026-09-23T11:00:00Z")])
def test_failed_stale_or_substituted_observation_cannot_support_negative_predicate(key, value):
    config, inputs = setup(clauses=[clause("no_errors", "error_count", 0)])
    inputs["collection"]["records"]["report"][key] = value
    answer = assess(config, inputs)
    assert answer["status"] == "unresolved"
    assert answer["obligations"][0]["status"] == "unresolved"


def test_valid_negative_finding_is_insufficient_not_collection_failure():
    config, inputs = setup(clauses=[clause("no_errors", "error_count", 0)])
    answer = assess(config, inputs)
    assert answer["status"] == "insufficient"
    assert answer["obligations"][0]["status"] == "violated"
    assert inputs["collection"]["records"]["report"]["status"] == "ok"


def test_assumption_validation_needs_its_own_evidence_adequacy_mapping():
    source = SOURCE.replace("evidence report; }", "evidence report; assumptions stable; }") + '''
assumption stable { statement "The report acquisition is complete."; environment lab; validate report; }
'''
    config, inputs = setup(source)
    answer = assess(config, inputs)
    assert answer["claim_status"] == "supported" and answer["status"] == "unresolved"
    assert any("conditional" in reason for reason in answer["reasons"])
    config["obligations"].append(clause("validation", "complete", True, role="assumption", about="assumption:stable"))
    assert assess(config, inputs)["status"] == "adequate"


def test_unrelated_fresh_evidence_cannot_validate_assumption():
    source = SOURCE.replace("evidence report; }", "evidence report; assumptions stable; }") + '''
evidence calibration { tool runner; kind test; environment lab; max_age 60; require "calibrated" == true; }
assumption stable { statement "The sensor is calibrated."; environment lab; validate calibration; }
'''
    config, inputs = setup(source, values={"report": VALUE, "calibration": {"calibrated": True}})
    config["obligations"].append(clause("wrong_validation", "complete", True, role="assumption", about="assumption:stable"))
    assert assess(config, inputs)["status"] == "unresolved"


def test_inactive_objection_needs_complete_relevant_evidence_not_missing_collection():
    source = SOURCE + '''
evidence fault { tool runner; kind test; environment lab; max_age 60; require "found" == true; }
objection sensor_fault { target argument observed; evidence fault; }
'''
    config, inputs = setup(source, values={"report": VALUE, "fault": {"found": False, "instrument": "runner"}})
    assert inputs["assessment"]["claims"]["bounded"]["status"] == "supported"
    assert assess(config, inputs)["status"] == "unresolved"
    config["obligations"].append(clause("fault_identity", "instrument", "runner", role="objection",
                                       reference="fault", about="objection:sensor_fault"))
    assert assess(config, inputs)["status"] == "adequate"
    del inputs["collection"]["records"]["fault"]
    assert assess(config, inputs)["status"] == "unresolved"


def test_independent_accepted_derivation_survives_an_unmapped_alternative_assumption():
    source = SOURCE + '''
assumption stable { statement "An additional provisional condition holds."; environment lab; validate report; }
argument alternative { conclusion bounded; reasoning summary; evidence report; assumptions stable; }
'''
    config, inputs = setup(source)
    assert assess(config, inputs)["status"] == "adequate"


def test_registry_load_roundtrip_and_rejection_of_duplicate_or_unknown_fields(tmp_path):
    config, inputs = setup()
    registry = AdequacyRegistry.from_document({"schema": "eal-adequacy/1", "contracts": {"report": config}})
    assert registry.assess("report", **inputs)["status"] == "adequate"
    config["obligations"].append(deepcopy(config["obligations"][0]))
    with pytest.raises(ValueError, match="unique"):
        AdequacyContract.from_dict(config)
    with pytest.raises(ValueError, match="unknown"):
        AdequacyContract.from_dict({**config, "self_declared_sufficient": True})


LOGIC = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool runner { version "1"; mode deterministic; }
evidence fact { tool runner; kind test; environment lab; max_age 60; require "recorded" == true; }
evidence logic { tool runner; kind logical_case; environment lab; max_age 60; require "conclusion" == "p"; }
reasoning observed_rule { method "structured/1"; rationale "The recorded observation establishes the scoped atom."; }
reasoning deduction { method "deductive/1"; rationale "Consequence of explicitly bound premises."; require "entailed" == true; }
claim observed { statement "The observed condition p holds."; environment lab; }
claim bounded { statement "The scoped condition p follows."; environment lab; }
argument observation { conclusion observed; reasoning observed_rule; evidence fact; }
argument proof { conclusion bounded; reasoning deduction; evidence logic; premises observed; }
'''


def test_deductive_premises_need_explicit_bindings_to_accepted_named_claims():
    config, inputs = setup(LOGIC, values={"fact": {"recorded": True}, "logic": {"premises": ["p"], "conclusion": "p"}},
                           clauses=[clause("consequence", "reasoning_result.details.entailed", True,
                                           target="argument", reference="proof", role="inference")],
                           methods=["structured/1", "deductive/1"])
    assert inputs["assessment"]["claims"]["bounded"]["status"] == "supported"
    assert assess(config, inputs)["status"] == "unresolved"
    config["premise_bindings"] = [{"argument": "proof", "formula": "p", "claim": "observed"}]
    assert assess(config, inputs)["status"] == "adequate"
    config["premise_bindings"][0]["formula"] = "unrelated"
    assert assess(config, inputs)["status"] == "unresolved"


def test_zero_premise_tautology_needs_no_empirical_premise_binding():
    # A typed envelope permits scalar acquisition checks around the closed
    # logical_case payload, including a formula-valued conclusion.
    from test_typed_propositions import SOURCE as TYPED, VALUE as TYPED_VALUE
    source = TYPED.replace('kind experiment', 'kind logical_case').replace('method "causal/1"', 'method "deductive/1"')
    source = source.replace('quantity "pressure"; unit "kPa"', 'quantity "proposition"; unit "1"')
    source = source.replace('query {"assignment":"randomised"}', 'query {"premises":[],"conclusion":{"implies":["p","p"]}}')
    source = source.replace('result "estimate" >= 5', 'result "entailed" == true')
    source = source.replace("claim raised", "claim bounded").replace("conclusion raised", "conclusion bounded")
    data = deepcopy(TYPED_VALUE)
    data.update(method="deductive/1", quantity="proposition", unit="1",
                payload={"premises": [], "conclusion": {"implies": ["p", "p"]}})
    config, inputs = setup(source, values={"trial": data}, methods=["deductive/1"],
                           clauses=[clause("entails", "reasoning_result.details.entailed", True,
                                           target="argument", reference="contrast", role="inference")])
    assert assess(config, inputs)["status"] == "adequate"


def test_installed_method_outputs_use_the_same_adequacy_contract():
    from eal.extensions import example_registry
    from test_method_extensions import custom_source
    from test_typed_propositions import VALUE as TYPED_VALUE
    source = custom_source().replace("claim raised", "claim bounded").replace("conclusion raised", "conclusion bounded")
    data = deepcopy(TYPED_VALUE)
    data.update(method="engineering/rms/1", unit="kPa", payload={"origin": 0, "samples": [5, -5]})
    config, inputs = setup(source, values={"trial": data}, methods=["engineering/rms/1"],
                           clauses=[clause("rms", "reasoning_result.details.rms", 5,
                                           target="argument", reference="contrast", role="inference")])
    registry = example_registry()
    inputs["assessment"] = evaluate(parse(source), inputs["collection"]["records"], now=NOW, context=CONTEXT, registry=registry)
    inputs["assessment"].update(assessment_id="assessment-1", collection_id="collection-1")
    answer = AdequacyEvaluator(method_registry=registry).assess(AdequacyContract.from_dict(config), **inputs)
    assert answer["status"] == "adequate"
    # An unrelated default registry cannot attest to the installed method's result.
    assert assess(config, inputs)["status"] == "unresolved"
