"""The comparison retains paired assignments and scores actual revisions."""
import json

import pytest

from experiments.composition_comparison.experiment import (freeze_fixture, load_frozen_fixture,
                                                          run, summarise)


FIXTURE = {"schema": "eal2-composition-revision/1", "base_time": "2040-01-01T00:00:00Z",
           "context": {"loop_id": "coolant-loop-A", "load_kw": 8}, "cases": [
               {"id": "initial", "observations": {},
                "expected": {"power_sufficient": "supported", "flow_sufficient": "unsupported",
                             "rejection_sufficient": "unsupported", "cooling_at_8kw": "unsupported"},
                "affected": []},
               {"id": "revoked", "revision_of": "initial", "observations": {},
                "expected": {"power_sufficient": "unsupported", "flow_sufficient": "unsupported",
                             "rejection_sufficient": "unsupported", "cooling_at_8kw": "unsupported"},
                "affected": ["power_sufficient"]}]}


def _evaluator(case, arm):
    claims = dict(case["expected"])
    if arm == "typed_rule" and case["id"] == "revoked":
        claims["power_sufficient"] = "supported"
    return {"claims": claims, "elapsed_seconds": 0.01,
            "source_digest": ("1" if arm == "eal" else "2") * 64}


def test_paired_results_score_claims_and_actual_changes(tmp_path):
    output = tmp_path / "study"
    summary = run(output, fixture=FIXTURE, evaluator=_evaluator)
    assert summary["assigned_pairs"] == 2
    assert summary["cells"]["eal"]["correct"] == 2
    assert summary["cells"]["typed_rule"]["correct"] == 1
    assert summary["paired_correctness"]["eal_only_correct"] == 1
    assert summary["cells"]["typed_rule"]["false_support_claims"] == 1
    assert summary["cells"]["typed_rule"]["revisions_correct"] == 0
    row = next(item for item in summary["trials"] if item["case_id"] == "revoked"
               and item["arm"] == "typed_rule")
    assert row["stale_claims"] == ["power_sufficient"]
    assert row["actual_affected"] == []
    assert summary["cost"]["total_cost_usd"] is None
    assert json.loads((output / "summary.json").read_text()) == summary
    assert len(list((output / "trials").glob("*/*.json"))) == 4


def test_failure_preserves_its_pair_and_counts_as_incorrect(tmp_path):
    def evaluator(case, arm):
        if (case["id"], arm) == ("revoked", "eal"):
            raise RuntimeError("assessment failed")
        return _evaluator(case, arm)

    summary = run(tmp_path / "study", fixture=FIXTURE, evaluator=evaluator)
    assert summary["cells"]["eal"]["failed"] == 1
    assert summary["cells"]["eal"]["revisions_unscored"] == 1
    assert summary["assigned_trials"] == 4
    rows = {row["arm"]: row for row in summary["trials"] if row["case_id"] == "revoked"}
    assert rows["eal"]["state"] == "failed"
    assert rows["eal"]["failure"] == "RuntimeError: assessment failed"
    assert rows["typed_rule"]["state"] == "complete"


def test_predeclared_affected_set_must_follow_expected_statuses(tmp_path):
    bad = json.loads(json.dumps(FIXTURE))
    bad["cases"][1]["affected"] = []
    with pytest.raises(ValueError, match="affected set"):
        run(tmp_path / "invalid", fixture=bad, evaluator=_evaluator)
    assert not (tmp_path / "invalid").exists()


def test_summary_rejects_missing_or_duplicate_assignments():
    with pytest.raises(ValueError, match="exactly one retained assignment"):
        summarise(FIXTURE, [])


def test_external_cases_require_exact_pre_execution_freeze(tmp_path):
    cases = tmp_path / "independent.json"
    cases.write_text(json.dumps(FIXTURE))
    manifest_path = tmp_path / "frozen.json"
    frozen = freeze_fixture(cases, manifest_path)
    fixture, loaded = load_frozen_fixture(cases, manifest_path)
    assert loaded == frozen
    seen = []

    def evaluator(case, arm):
        seen.append((case["id"], arm, case["context"], case["assessed_at"], case["observed_at"]))
        return _evaluator(case, arm)

    result = run(tmp_path / "results", fixture=fixture, evaluator=evaluator,
                 external_freeze=loaded, fixture_bytes=cases.read_bytes())
    assert result["assigned_trials"] == 4
    assert all(context == FIXTURE["context"] and assessed == observed == FIXTURE["base_time"]
               for _, _, context, assessed, observed in seen)
    assert json.loads((tmp_path / "results" / "manifest.json").read_text())["external_freeze"] == frozen
    assert (tmp_path / "results" / "fixture.json").read_bytes() == cases.read_bytes()
    cases.write_text(json.dumps(FIXTURE, indent=2))  # Even whitespace is bound by the freeze.
    with pytest.raises(ValueError, match="differs from its frozen manifest"):
        load_frozen_fixture(cases, manifest_path)


def test_freeze_refuses_internally_inconsistent_fixture(tmp_path):
    bad = json.loads(json.dumps(FIXTURE))
    bad["cases"][1]["affected"] = []
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="affected set"):
        freeze_fixture(path, tmp_path / "freeze.json")
    assert not (tmp_path / "freeze.json").exists()
