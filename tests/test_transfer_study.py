"""Operational checks for the paired cross-session developer study."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from experiments.transfer_study.analysis import (analyse, blind_id, export_answers,
                                                 resolve_scores, save_ratings)
from experiments.transfer_study.design import StudyDesign
from experiments.transfer_study.model_gateway import ModelGateway
from experiments.transfer_study.openai_responses import respond
from experiments.transfer_study.operations import SessionOperations
from experiments.transfer_study.workspace import StudyRun, read_json, write_json


DEMO = Path(__file__).resolve().parents[1] / "experiments" / "transfer_study" / "demo"


def _plan(tmp_path: Path, *, later_now: str | None = None) -> Path:
    target = tmp_path / "materials"
    shutil.copytree(DEMO, target)
    if later_now:
        plan = read_json(target / "plan.json")
        plan["cases"][0]["later_now"] = later_now
        write_json(target / "plan.json", plan)
    return target / "plan.json"


def _sessions(run: StudyRun, *, fresh: bool = False) -> dict[str, dict]:
    later_sessions = {}
    operations = SessionOperations(run)
    for item in run.allocation["assignments"]:
        initial = run.open(item["case_id"], item["slot_id"], "initial")
        if item["arm"] == "eal":
            workspace = Path(initial["workspace"])
            shutil.copyfile(DEMO / "eal-authoring-example.eal", workspace / "source.eal")
            shutil.copyfile(DEMO / "eal-authoring-tools.toml", workspace / "tools.toml")
            operations.register(initial["session_id"], source="source.eal",
                                registry="tools.toml", entry_id="orders", claim="ready",
                                context={"service": "orders"})
            context = operations.assess(initial["session_id"], registry="tools.toml",
                                        entry_id="orders", claim="ready", prompt=initial["question"])
            assert context["assessment"]["collected_count"] == 1
            first = ModelGateway(run).invoke(initial["session_id"], initial["question"],
                                             context_path=Path(context["context_path"]))
        else:
            first = ModelGateway(run).invoke(initial["session_id"], initial["question"])
        run.submit(initial["session_id"], first["response"]["content"], 4.0)
        later = run.open(item["case_id"], item["slot_id"], "later")
        if item["arm"] == "eal":
            context = operations.assess(later["session_id"], registry="tools.toml",
                                        entry_id="orders", claim="ready", prompt=later["question"])
            assert context["assessment"]["reused_count"] == (0 if fresh else 1)
            second = ModelGateway(run).invoke(later["session_id"], later["question"],
                                              context_path=Path(context["context_path"]))
        else:
            second = ModelGateway(run).invoke(later["session_id"], later["question"])
        run.submit(later["session_id"], second["response"]["content"], 3.0)
        later_sessions[item["arm"]] = later
        assert initial["model_version"] != later["model_version"]
        assert initial["developer"] != later["developer"]
    return later_sessions


def test_allocation_and_handover_preserve_only_project_artifacts(tmp_path):
    plan = _plan(tmp_path)
    design = StudyDesign.load(plan)
    assert design.allocations(42) == design.allocations(42)
    assert {item["arm"] for item in design.allocations(42)["assignments"]} == {"eal", "ordinary"}
    run = StudyRun.create(plan, tmp_path / "run", 42)
    first = run.open("orders_fixture", "A", "initial")
    with pytest.raises(ValueError, match="must be submitted"):
        run.open("orders_fixture", "A", "later")
    # Opening a session does not copy the unreleased later question or the other arm.
    assert first["question"] not in (Path(first["workspace"]) / "README.md").read_text()
    assert not (Path(first["workspace"]) / "source.eal").exists()


def test_full_paired_study_uses_independent_scores_and_fresh_context(tmp_path):
    run = StudyRun.create(_plan(tmp_path), tmp_path / "run", 42)
    later = _sessions(run)
    ordinary_calls = read_json(run.root / "calls" / f"{later['ordinary']['session_id']}.json")
    assert len(ordinary_calls[0]["request"]["messages"]) == 1
    assert "current orders service report" not in str(ordinary_calls[0]["request"]["messages"])
    assert (Path(later["eal"]["workspace"]) / ".eal" / "runs.sqlite3").exists()

    exported = export_answers(run)
    assert all("arm" not in answer and "model" not in answer for answer in exported["answers"])
    ratings = {"schema": "EAL/transfer-ratings/1", "ratings": [], "adjudications": []}
    for answer in exported["answers"]:
        ordinary = answer["blind_id"] == blind_id(run, later["ordinary"]["session_id"])
        for rater in ("r1", "r2"):
            ratings["ratings"].append({"blind_id": answer["blind_id"], "rater": rater,
                                       "correct": not ordinary, "material_error": ordinary,
                                       "reason": "Synthetic reference judgement"})
    write_json(tmp_path / "judge.json", ratings)
    assert save_ratings(run, tmp_path / "judge.json")["scored_answers"] == 4
    report = analyse(run)
    assert report["summaries"]["different_developer_different_model"]["correctness_difference"] == 1
    assert report["summaries"]["overall"]["arm_totals"]["eal"]["eal_reused"] == 1
    assert report["summaries"]["overall"]["bootstrap_95_interval"] is None


def test_expired_measurement_is_recollected_without_refreshing_its_age(tmp_path):
    run = StudyRun.create(_plan(tmp_path, later_now="2026-10-15T00:00:00Z"),
                          tmp_path / "run", 42)
    later = _sessions(run, fresh=True)
    event = read_json(run.root / "events" / f"{later['eal']['session_id']}.json")[-1]
    assert event["reused_count"] == 0 and event["collected_count"] == 1


def test_invalid_transfer_and_model_binding_rejected(tmp_path):
    plan = _plan(tmp_path)
    raw = read_json(plan)
    raw["cases"][0]["slots"][1]["recipient"] = "bob"
    write_json(plan, raw)
    with pytest.raises(ValueError, match="independent developer teams"):
        StudyDesign.load(plan)
    raw["cases"][0]["slots"][1]["recipient"] = "dave"
    raw["cases"][0]["slots"][1]["later_model"] = "fixture_small"
    write_json(plan, raw)
    with pytest.raises(ValueError, match="same model transition"):
        StudyDesign.load(plan)


def test_disagreement_requires_independent_adjudication(tmp_path):
    run = StudyRun.create(_plan(tmp_path), tmp_path / "run", 42)
    _sessions(run)
    answers = export_answers(run)["answers"]
    ratings = {"schema": "EAL/transfer-ratings/1", "ratings": [], "adjudications": []}
    for answer in answers:
        for index, rater in enumerate(("r1", "r2")):
            ratings["ratings"].append({"blind_id": answer["blind_id"], "rater": rater,
                                       "correct": index == 0, "material_error": False,
                                       "reason": "Independently assessed"})
    with pytest.raises(ValueError, match="Unadjudicated disagreement"):
        resolve_scores(run, ratings)
    ratings["adjudications"] = [{"blind_id": answer["blind_id"], "rater": "lead",
                                 "correct": True, "material_error": False,
                                 "reason": "Resolved against oracle"} for answer in answers]
    assert all(value["adjudicated"] for value in resolve_scores(run, ratings).values())


def test_failed_model_call_is_retained(tmp_path):
    plan = _plan(tmp_path)
    raw = read_json(plan)
    raw["models"]["fixture_small"]["command"] = ["python3", "-c", "raise SystemExit(3)"]
    write_json(plan, raw)
    run = StudyRun.create(plan, tmp_path / "run", 42)
    session = run.open("orders_fixture", "A", "initial")
    with pytest.raises(RuntimeError, match="exited 3"):
        ModelGateway(run).invoke(session["session_id"], session["question"])
    calls = read_json(run.root / "calls" / f"{session['session_id']}.json")
    assert calls[0]["error"]["type"] == "RuntimeError"
    run.submit(session["session_id"], "No result: model adapter failed", 1.0)


def test_responses_adapter_uses_pinned_model_and_omits_remote_session_state(monkeypatch):
    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return json.dumps({"id": "resp-test", "model": "model-version-1",
                               "status": "completed", "error": None,
                               "output": [{"type": "message", "content": [
                                   {"type": "output_text", "text": "Scoped answer"}]}],
                               "usage": {"input_tokens": 12, "output_tokens": 3}}).encode()

    def open_request(http, timeout):
        payload = json.loads(http.data)
        assert payload == {"model": "model-version-1", "store": False,
                           "input": [{"role": "user", "content": "Question"}]}
        assert timeout == 540
        return Reply()

    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    monkeypatch.setattr("urllib.request.urlopen", open_request)
    output = respond({"schema": "EAL/transfer-model-request/1",
                      "model_version": "model-version-1",
                      "messages": [{"role": "user", "content": "Question"}]})
    assert output["content"] == "Scoped answer"
    assert output["usage"] == {"input_tokens": 12, "output_tokens": 3}
