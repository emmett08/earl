"""Integrity and discrimination checks for the paid-free inference pilot."""

import json
from pathlib import Path

import pytest

from experiments.inference_machinery_v1 import run


def test_freeze_and_offline_evaluation_keep_every_case(tmp_path):
    assert len(run.verify_freeze()) == 64
    report = run.prepare(tmp_path)
    assert len(report["engine"]) == 12
    assert report["case_ids"] == [f"C{n:02d}" for n in range(1, 13)]
    assert report["arms"] == {}
    assert all(row["snapshot_digest"] for row in report["engine"])
    assert all(row["status"] in run.STATUSES for row in report["engine"])
    raw = (tmp_path / "prompt-raw.txt").read_text()
    aided = (tmp_path / "prompt-eal_assisted.txt").read_text()
    assert aided.startswith(raw.strip() + "\nChecked EAL/2 result")
    assert '"expected"' not in raw + aided
    assert '"reason"' not in raw + aided
    assert '"status":' not in raw


def test_oracle_mismatch_is_recorded_without_case_selection(tmp_path, monkeypatch):
    source, programme, cases, oracle = run.load_inputs()
    altered = {key: dict(value) for key, value in oracle.items()}
    altered["C01"]["status"] = "unsupported"
    monkeypatch.setattr(run, "load_inputs", lambda: (source, programme, cases, altered))
    report = run.prepare(tmp_path)
    assert len(report["engine"]) == 12
    assert report["engine"][0]["expected"] == "unsupported"
    assert not report["engine"][0]["correct"]


def test_case_scoring_preserves_invalid_and_wrong_answers():
    _, _, cases, oracle = run.load_inputs()
    ids = [case["id"] for case in cases]
    correct = {"answers": [{"case_id": case_id, "status": oracle[case_id]["status"]}
                           for case_id in ids]}
    assert run._score(correct, oracle, ids)["correct"] == len(ids)
    wrong = json.loads(json.dumps(correct))
    wrong["answers"][0]["status"] = "unsupported"
    assert run._score(wrong, oracle, ids)["correct"] == len(ids) - 1
    wrong["answers"].reverse()
    assert not run._score(wrong, oracle, ids)["valid"]
    assert not run._score(None, oracle, ids)["valid"]


def test_changed_frozen_input_is_rejected(tmp_path, monkeypatch):
    for filename in (*run.FILES, "freeze.json"):
        (tmp_path / filename).write_bytes((run.HERE / filename).read_bytes())
    (tmp_path / "oracles.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(run, "HERE", Path(tmp_path))
    with pytest.raises(ValueError, match="frozen inference study input changed"):
        run.verify_freeze()


def test_conservative_two_call_scenario_is_below_stop():
    assert 2 * run._scenario(run.REQUEST_BYTE_CAP, run.OUTPUT_CAP) < run.SCENARIO_LIMIT
