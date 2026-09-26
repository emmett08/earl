"""Held-out claims require an explicit new, fixed case plan before execution."""
import json

import pytest

from experiments.api_load_test.cases import case_specs
from experiments.api_load_test.heldout_protocol import REQUIRED_OUTCOMES, freeze


def plan():
    return {"schema": "eal-api-heldout-plan/1", "target_population": "New API run decisions",
            "comparator_family": ["eal_mcp", "plain_validator"],
            "primary_outcome": "complete_correct_answer", "practical_margin": 0.05,
            "stopping_rule": {"kind": "fixed_case_count", "planned_cases": 2},
            "case_family_dependence": "cluster by independent workload family",
            "model_snapshots": ["pinned-snapshot-a"], "outcomes": sorted(REQUIRED_OUTCOMES),
            "source_commit": "a" * 40}


def cases():
    return [{"id": "heldout-1", "family": "new-service", "payload": {"task": "A"}},
            {"id": "heldout-2", "family": "new-service", "payload": {"task": "B"}}]


def test_freeze_retains_exact_new_assignments_without_running_models(tmp_path):
    output = tmp_path / "freeze"
    manifest = freeze(plan(), cases(), output)
    assert manifest["state"] == "frozen_unexecuted"
    assert len(manifest["assignments"]) == 2
    assert json.loads((output / "manifest.json").read_text()) == manifest
    with pytest.raises(FileExistsError):
        freeze(plan(), cases(), output)


@pytest.mark.parametrize("change", ["missing_margin", "outcomes", "adaptive_stop", "development_id", "duplicate"])
def test_incomplete_or_reused_development_design_cannot_be_frozen(tmp_path, change):
    declaration, new_cases = plan(), cases()
    if change == "missing_margin":
        del declaration["practical_margin"]
    elif change == "outcomes":
        declaration["outcomes"].remove("false_support")
    elif change == "adaptive_stop":
        declaration["stopping_rule"]["kind"] = "stop_when_favourable"
    elif change == "development_id":
        new_cases[0]["id"] = case_specs("pilot")[0]["id"]
    else:
        new_cases[1]["id"] = new_cases[0]["id"]
    with pytest.raises(ValueError):
        freeze(declaration, new_cases, tmp_path / "rejected")
    assert not (tmp_path / "rejected").exists()
