"""Synthetic protocol checks; these are not human authoring outcomes."""
from __future__ import annotations

import json
import hashlib
import importlib
from pathlib import Path
import subprocess
import sys

import pytest

from experiments.authoring_revision.analysis import analyse, grade
from experiments.authoring_revision.assignments import freeze
from experiments.authoring_revision.protocol import read_json
from experiments.authoring_revision.recording import adjudicate, review, submit
from experiments.authoring_revision.replay import replay


def _write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _study(tmp_path: Path, source_commit: str = "0" * 40) -> tuple[Path, Path, list[dict]]:
    runner = tmp_path / "runner.py"
    runner.write_text(
        "import json, os\n"
        "bundle=json.load(open(os.environ['EAL_STUDY_CASES']))\n"
        "assert os.path.exists(os.environ['EAL_STUDY_SOURCE'])\n"
        "print(json.dumps({'schema':'eal-authoring-results/1',"
        "'cases':{case_id:{'cooling':'supported'} for case_id in bundle['cases']}}))\n",
        encoding="utf-8")
    runner_hash = hashlib.sha256(runner.read_bytes()).hexdigest()
    plan = {
        "schema": "eal-authoring-plan/1", "study_id": "synthetic",
        "target_population": "Synthetic task fixtures for instrument tests only",
        "source_commit": source_commit, "assignment_seed": 17,
        "arms": ["eal2", "typed_rules"],
        "runner_sha256": {"eal2": runner_hash, "typed_rules": runner_hash},
        "practical_margins": {"correct_case_fraction": 0.1, "active_seconds": 120,
                              "semantic_defects": 1},
        "tasks": [{
            "id": task_id, "family": "thermal", "initial_brief": "Check measured cooling",
            "revision_brief": "Reassess after a pump change",
            "cases": {"initial": ["normal"], "revision": ["changed"]},
            "target_claims": {"initial": ["cooling"], "revision": ["cooling"]},
            "inputs": {"initial": {"normal": {"capacity_kw": 10}},
                       "revision": {"changed": {"capacity_kw": 9}}},
        } for task_id in ("loop_a", "loop_b")],
    }
    oracle = {"schema": "eal-authoring-oracle/1", "tasks": {
        task_id: {"initial": {"normal": {"cooling": "supported"}},
                  "revision": {"changed": {"cooling": "unavailable"}}}
        for task_id in ("loop_a", "loop_b")
    }}
    plan_path = _write(tmp_path / "plan.json", plan)
    oracle_path = _write(tmp_path / "oracle.json", oracle)
    participants = _write(tmp_path / "participants.json", ["engineer1", "engineer2",
                                                            "engineer3", "engineer4"])
    run = tmp_path / "run"
    freeze(plan_path, oracle_path, participants, run)
    return run, oracle_path, read_json(run / "assignments.json")


def test_counterbalanced_assignments_and_oracle_integrity(tmp_path: Path) -> None:
    run, oracle_path, assignments = _study(tmp_path)
    for task in ("loop_a", "loop_b"):
        assert sorted(a["arm"] for a in assignments if a["task_id"] == task) == [
            "eal2", "eal2", "typed_rules", "typed_rules"]
        assert sorted(a["order"] for a in assignments if a["task_id"] == task) == [1, 1, 2, 2]
    assert all({a["arm"] for a in assignments if a["participant_id"] == p}
               == {"eal2", "typed_rules"} for p in ("engineer1", "engineer2", "engineer3", "engineer4"))
    oracle = read_json(oracle_path)
    oracle["tasks"]["loop_a"]["initial"]["normal"]["cooling"] = "unsupported"
    _write(oracle_path, oracle)
    with pytest.raises(ValueError, match="Oracle differs"):
        analyse(run, oracle_path)


def test_retained_failure_malformed_result_and_qualitative_adjudication(tmp_path: Path) -> None:
    run, oracle_path, assignments = _study(tmp_path)
    assignment = assignments[0]
    source = tmp_path / "source.eal"
    source.write_text("synthetic source", encoding="utf-8")
    invalid = _write(tmp_path / "invalid.json", {"schema": "eal-authoring-results/1",
                                                "cases": {"normal": {"cooling": ["supported"]}}})
    with pytest.raises(ValueError, match="Results must"):
        submit(run, assignment["id"], "initial", 40, source, tmp_path / "not_found.json")
    assert not (run / "submissions" / f"{assignment['id']}-initial").exists()
    recorded = submit(run, assignment["id"], "initial", 40, source, invalid)
    assert recorded["active_seconds"] == 40
    assert recorded["failure"] is None
    assert grade(invalid.read_bytes(), {"normal": {"cooling": "supported"}})["complete_correct"] is False
    revised = _write(tmp_path / "revision.json", {"schema": "eal-authoring-results/1",
                                                "cases": {"changed": {"cooling": "supported"}}})
    submit(run, assignment["id"], "revision", 12, source, revised)
    submission_id = f"{assignment['id']}-revision"
    review_input = _write(tmp_path / "review.json", {
        "schema": "eal-authoring-review/1", "reviewer_id": "reviewer1",
        "submission_id": submission_id, "review_seconds": 25,
        "findings": [{"id": "stale_pump", "location": "cooling",
                      "description": "The result uses a revoked pump observation."}],
    })
    review(run, review_input)
    second_review = _write(tmp_path / "review2.json", {
        "schema": "eal-authoring-review/1", "reviewer_id": "reviewer3",
        "submission_id": submission_id, "review_seconds": 11,
        "findings": [{"id": "old_pump", "location": "cooling",
                      "description": "The primary pump reading was revoked."}],
    })
    review(run, second_review)
    decision = _write(tmp_path / "adjudication.json", {
        "schema": "eal-authoring-adjudication/1", "adjudicator_id": "reviewer2",
        "submission_id": submission_id, "adjudication_seconds": 8,
        "confirmed_defects": [{"id": "stale_pump", "finding_refs": [
            "reviewer1:stale_pump", "reviewer3:old_pump"],
                               "description": "Revoked observation used"}],
        "rationale": "The submitted observation was revoked.",
    })
    adjudicate(run, decision)
    provenance = replay(run, submission_id, "independent_operator", "synthetic_runner/1",
                        tmp_path / "runner.py")
    assert provenance["returncode"] == 0
    report = analyse(run, oracle_path)
    row = next(r for r in report["rows"] if r["submission_id"] == submission_id)
    assert (row["false_support"], row["adjudicated_defects"], row["review_seconds"]) == (1, 1, 36)
    assert row["reported_findings"] == 2
    assert row["complete_correct"] is False
    assert sum(r["submitted"] for r in report["rows"]) == 2
    assert len(report["rows"]) == len(assignments) * 2
    assert sum(r["complete_correct"] for r in report["rows"]) == 0
    source_copy = run / "submissions" / f"{assignment['id']}-initial" / "artefact" / "source.eal"
    source_copy.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="artefact changed"):
        analyse(run, oracle_path)


def test_perfect_participant_result_is_unscored_without_replay(tmp_path: Path) -> None:
    run, oracle_path, assignments = _study(tmp_path)
    assignment = assignments[0]
    source = tmp_path / "source.eal"
    source.write_text("synthetic source", encoding="utf-8")
    perfect = _write(tmp_path / "perfect.json", {"schema": "eal-authoring-results/1",
                                               "cases": {"normal": {"cooling": "supported"}}})
    submit(run, assignment["id"], "initial", 15, source, perfect)
    row = next(row for row in analyse(run, oracle_path)["rows"]
               if row["id"] == assignment["id"] and row["stage"] == "initial")
    assert row["submitted"] and not row["replayed"]
    assert row["score_origin"] == "unscored" and not row["complete_correct"]
    assert row["correct_cases"] == 0
    wrong_runner = tmp_path / "other.py"
    wrong_runner.write_text('print("{}")\n', encoding="utf-8")
    wrong_runner.write_text('print("different")\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Runner script differs"):
        replay(run, f"{assignment['id']}-initial", "operator", "runner/1", wrong_runner)


def test_replay_checks_real_revision_and_clean_checkout(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    pin = "f" * 40
    run, oracle_path, assignments = _study(tmp_path, source_commit=pin)
    assignment = assignments[0]
    source = tmp_path / "source.eal"
    source.write_text("synthetic source", encoding="utf-8")
    submit(run, assignment["id"], "initial", 15, source, None)
    submission_id = f"{assignment['id']}-initial"
    runner = tmp_path / "runner.py"
    with pytest.raises(ValueError, match="pinned Git HEAD"):
        replay(run, submission_id, "operator", "runner/1", runner)
    assert not (run / "replays" / submission_id).exists()
    replay_module = importlib.import_module("experiments.authoring_revision.replay")
    monkeypatch.setattr(replay_module, "_checkout_identity", lambda: (pin, False))
    with pytest.raises(ValueError, match="inside the assessed repository"):
        replay(run, submission_id, "operator", "runner/1", runner)
    monkeypatch.setattr(replay_module, "REPOSITORY", tmp_path)
    monkeypatch.setattr(replay_module, "_checkout_identity", lambda: (pin, True))
    with pytest.raises(ValueError, match="clean repository"):
        replay(run, submission_id, "operator", "runner/1", runner)
    monkeypatch.setattr(replay_module, "_checkout_identity", lambda: (pin, False))
    provenance = replay(run, submission_id, "operator", "runner/1", runner)
    assert provenance["repository_head"] == pin
    assert provenance["repository_dirty"] is False
    assert provenance["source_commit_verification"] == "matched_clean"
    assert not analyse(run, oracle_path)["source_provenance_limited"]
    provenance_path = run / "replays" / submission_id / "record.json"
    forged = read_json(provenance_path)
    forged["repository_head"] = "e" * 40
    _write(provenance_path, forged)
    with pytest.raises(ValueError, match="revision provenance"):
        analyse(run, oracle_path)


def test_example_cooling_replays_both_arms_from_copied_source(tmp_path: Path) -> None:
    here = Path(__file__).resolve().parents[1]
    example = here / "experiments" / "authoring_revision"
    fixture = here / "experiments" / "composition_revision"
    run = tmp_path / "run"
    subprocess.run([sys.executable, "-m", "experiments.authoring_revision", "freeze",
                    "--plan", str(example / "example-plan.json"),
                    "--oracle", str(example / "example-oracle.json"),
                    "--participants", str(example / "example-participants.json"),
                    "--output", str(run)], cwd=here, check=True, capture_output=True)
    assignments = read_json(run / "assignments.json")
    selected = {arm: next(a for a in assignments if a["arm"] == arm)
                for arm in ("eal2", "typed_rules")}
    for arm, assignment in selected.items():
        source = fixture / ("cooling.eal" if arm == "eal2" else "baseline.py")
        subprocess.run([sys.executable, "-m", "experiments.authoring_revision", "submit",
                        "--run", str(run), "--assignment", assignment["id"],
                        "--stage", "initial", "--active-seconds", "1",
                        "--artefact", str(source)], cwd=here, check=True, capture_output=True)
        completed = subprocess.run([sys.executable, "-m", "experiments.authoring_revision", "replay",
                                    "--run", str(run),
                                    "--submission", f"{assignment['id']}-initial",
                                    "--operator", "independent_operator",
                                    "--runner-version", "cooling_runner/1",
                                    "--runner", str(example / "cooling_runner.py")],
                                   cwd=here, check=True, capture_output=True)
        assert json.loads(completed.stdout)["returncode"] == 0
    report = analyse(run, example / "example-oracle.json")
    assert report["source_provenance_limited"] is True
    replayed = [row for row in report["rows"] if row["replayed"]]
    assert {row["arm"] for row in replayed} == {"eal2", "typed_rules"}
    assert all(row["complete_correct"] and row["correct_cases"] == 3
               for row in replayed)
    assert all(not row["complete_correct"] and row["score_origin"] == "unscored"
               for row in report["rows"] if row["stage"] == "revision")
    first = next(iter(selected.values()))
    provenance = run / "replays" / f"{first['id']}-initial" / "record.json"
    altered = read_json(provenance)
    altered["runner_sha256"] = "0" * 64
    _write(provenance, altered)
    with pytest.raises(ValueError, match="runner identity"):
        analyse(run, example / "example-oracle.json")


def test_extra_support_and_missing_are_distinct() -> None:
    expected = {"adequate": {"acceptable": "contested", "pump_ready": "supported"},
                "other_region": {"acceptable": "out_of_scope"}}
    actual = {"schema": "eal-authoring-results/1", "cases": {
        "adequate": {"acceptable": "supported", "invented": "supported"},
        "other_region": {"acceptable": "out_of_scope"},
        "extra": {"ready": "supported"},
    }}
    outcome = grade(json.dumps(actual).encode(), expected)
    assert outcome["false_support"] == 3
    assert outcome["missing_claims"] == 1
    assert outcome["extra_claims"] == 2
    assert outcome["complete_correct"] is False
    both = {"schema": "eal-authoring-results/1", "cases": expected}
    assert grade(json.dumps(both).encode(), expected)["complete_correct"] is True
