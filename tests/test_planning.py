"""Claim collection plans cover every source capable of changing the result."""

import pytest

from eal.parser import parse
from eal.planning import EvidencePlanner
from eal.semantics import validate


SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
environment field { require "site" == "field"; }
tool collector { version "1"; }
evidence alternative { tool collector; kind test; environment lab; max_age 60; require "ok" == true; }
evidence direct { tool collector; kind test; environment lab; max_age 60; require "ok" == true; }
evidence backing_record { tool collector; kind test; environment lab; max_age 60; require "ok" == true; }
evidence validation { tool collector; kind test; environment lab; max_age 60; require "ok" == true; }
evidence premise { tool collector; kind test; environment lab; max_age 60; require "ok" == true; }
evidence challenge { tool collector; kind test; environment lab; max_age 60; require "ok" == true; }
evidence defence { tool collector; kind test; environment lab; max_age 60; require "ok" == true; }
evidence reply { tool collector; kind test; environment lab; max_age 60; require "ok" == true; }
evidence objection_premise { tool collector; kind test; environment lab; max_age 60; require "ok" == true; }
evidence unrelated { tool collector; kind test; environment lab; max_age 60; require "ok" == true; }
evidence foreign { tool collector; kind test; environment field; max_age 60; require "ok" == true; }
assumption calibrated { statement "The collector is calibrated."; environment lab; validate validation; }
reasoning checked { method "structured/1"; rationale "The measured facts support the claim."; backing backing_record; }
reasoning inferred { method "structured/1"; rationale "The premise supports the claim."; }
claim root { statement "The selected result."; environment lab; }
claim leaf { statement "A required premise."; environment lab; }
claim attacker { statement "A premise for the challenge."; environment lab; }
claim other { statement "An unrelated result."; environment lab; }
claim foreign_claim { statement "A foreign result."; environment field; }
argument primary { conclusion root; reasoning checked; evidence direct; assumptions calibrated; }
argument alternative_route { conclusion root; reasoning inferred; evidence alternative; }
argument nested { conclusion root; reasoning inferred; premises leaf; }
argument leaf_route { conclusion leaf; reasoning inferred; evidence premise; }
argument attacker_route { conclusion attacker; reasoning inferred; evidence objection_premise; }
argument other_route { conclusion other; reasoning inferred; evidence unrelated; }
argument foreign_route { conclusion foreign_claim; reasoning inferred; evidence foreign; }
objection original { target assumption calibrated; evidence challenge; }
objection answer { target objection original; evidence defence; }
objection rejoinder { target objection answer; evidence reply; }
objection grounds { target claim root; premises attacker; }
objection scoped_out { target reasoning inferred; evidence foreign; }
'''


def test_plan_follows_alternatives_premises_backing_assumptions_and_defence_chains():
    program = parse(SOURCE)
    assert not validate(program)
    plan = EvidencePlanner(program).plan("root")
    assert plan.evidence_ids == (
        "alternative", "direct", "backing_record", "validation", "premise",
        "challenge", "defence", "reply", "objection_premise",
    )
    assert plan.estimated_calls == len(plan.evidence_ids)
    assert set(plan.closure.claims) == {"root", "leaf", "attacker"}
    assert set(plan.closure.arguments) == {
        "primary", "alternative_route", "nested", "leaf_route", "attacker_route",
    }
    assert set(plan.closure.objections) == {"original", "answer", "rejoinder", "grounds"}
    assert plan.closure.assumptions == {"calibrated"}
    assert plan.closure.reasoning == {"checked", "inferred"}
    assert plan.calls[0].tool == "collector"
    assert plan.calls[0].tool_version == "1"
    assert plan.calls[0].environment == "lab"


def test_planning_is_deterministic_and_excludes_unrelated_evidence():
    planner = EvidencePlanner(parse(SOURCE))
    first = planner.plan("root")
    assert first == planner.plan("root")
    assert planner.plan("other").evidence_ids == ("unrelated",)
    assert planner.plan("foreign_claim").evidence_ids == ("foreign",)
    with pytest.raises(ValueError, match="Unknown claim"):
        planner.plan("missing")


def test_objection_premise_can_lead_back_to_a_claim_without_nontermination():
    source = SOURCE.replace(
        'objection grounds { target claim root; premises attacker; }',
        'objection grounds { target claim root; premises root; }',
    )
    program = parse(source)
    assert not validate(program)
    plan = EvidencePlanner(program).plan("root")
    assert "grounds" in plan.closure.objections
    assert plan.evidence_ids == (
        "alternative", "direct", "backing_record", "validation", "premise",
        "challenge", "defence", "reply",
    )


def test_pattern_application_preserves_the_collected_evidence_identity():
    expanded = SOURCE.replace(
        'argument alternative_route { conclusion root; reasoning inferred; evidence alternative; }',
        '''pattern support(c: claim, r: reasoning, e: evidence) {
          conclusion c; reasoning r; evidence e;
        }
        apply alternative_route = support(c=root, r=inferred, e=alternative);''',
    )
    program = parse(expanded)
    assert not validate(program)
    direct = EvidencePlanner(parse(SOURCE)).plan("root")
    reused = EvidencePlanner(program).plan("root")
    assert reused.calls == direct.calls
    assert reused.closure == direct.closure
    assert program.arguments["alternative_route"].origin.pattern == "support"
