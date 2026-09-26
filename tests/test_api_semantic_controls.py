"""Independent fixed outcomes survive revisions and retain all assigned cases."""
import json

from experiments.api_load_test.semantic_controls import run


def test_offline_composition_and_revision_controls(tmp_path):
    output = tmp_path / "controls"
    result = run(output)
    assert result["assigned"] == result["correct"] == 7
    assert json.loads((output / "result.json").read_text()) == result
    rows = {row["id"]: row for row in result["trials"]}
    assert rows["revoke_one_route"]["argument_statuses"]["base"] == "unsupported"
    assert rows["objection_with_alternative"]["argument_statuses"]["base"] == "contested"
    assert rows["expired_evidence"]["evidence_statuses"]["a"] == "unavailable"
    assert rows["different_context"]["actual"]["downstream"] == "out_of_scope"
