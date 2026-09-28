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
    run.submit(first["session_id"], "Initial fixture answer", 1)
    (Path(first["workspace"]) / "measurement.json").write_text(
        '{"ready": false, "observed_at": "2026-09-28T10:00:00Z"}', encoding="utf-8")
    later = run.open("orders_fixture", "A", "later")
    assert read_json(Path(later["workspace"]) / "measurement.json")["ready"] is True


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
    assert report["summaries"]["different_developer_different_model"]["correctness"]["estimate"] == 1
    assert report["summaries"]["overall"]["arm_totals"]["eal"]["metrics"]["eal_reused"]["total"] == 1
    assert report["summaries"]["overall"]["correctness"]["interval"] == [-1, 1]


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
    ratings["adjudications"][0]["rater"] = "r1"
    with pytest.raises(ValueError, match="third assessor"):
        resolve_scores(run, ratings)


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


def _rate_all(run, tmp_path, *, correct=True):
    ratings = {"schema": "EAL/transfer-ratings/1", "ratings": [], "adjudications": []}
    for answer in export_answers(run)["answers"]:
        for rater in ("r1", "r2"):
            ratings["ratings"].append({"blind_id": answer["blind_id"], "rater": rater,
                                       "correct": correct, "material_error": False,
                                       "reason": "Independent synthetic reference"})
    path = tmp_path / "ratings.json"
    write_json(path, ratings)
    save_ratings(run, path)


def test_missing_and_failed_sessions_keep_the_allocated_denominator(tmp_path):
    run = StudyRun.create(_plan(tmp_path), tmp_path / "run", 42)
    for item in run.allocation["assignments"]:
        initial = run.open(item["case_id"], item["slot_id"], "initial")
        run.submit(initial["session_id"], "Initial answer", 4)
        session = run.session_id(item["case_id"], item["slot_id"], "later")
        run.close(session, "withdrawn" if item["arm"] == "eal" else "no_answer",
                  "Synthetic withdrawal or nonresponse")
        with pytest.raises(ValueError, match="Closed session"):
            run.open(item["case_id"], item["slot_id"], "later")
    _rate_all(run, tmp_path)
    result = analyse(run)["summaries"]["overall"]
    assert result["pairs"] == 1
    assert result["correctness"]["estimate"] is None
    assert result["correctness"]["identified_bounds"] == [0, 1]
    assert result["correctness"]["unknown_pairs"] == 1
    assert result["arm_totals"]["eal"]["total_effort_minutes"]["total"] is None
    assert result["arm_totals"]["ordinary"]["statuses"]["no_answer"] == 1


def test_late_correct_answers_do_not_pass_the_time_bounded_endpoint(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    start = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
    monkeypatch.setattr("experiments.transfer_study.workspace.utc_now", lambda: start)
    run = StudyRun.create(_plan(tmp_path), tmp_path / "run", 42)
    for item in run.allocation["assignments"]:
        initial = run.open(item["case_id"], item["slot_id"], "initial")
        run.submit(initial["session_id"], "Initial answer", 1)
        later = run.open(item["case_id"], item["slot_id"], "later")
        monkeypatch.setattr("experiments.transfer_study.workspace.utc_now",
                            lambda: start + timedelta(minutes=16))
        with pytest.raises(ValueError, match="time budget"):
            ModelGateway(run).invoke(later["session_id"], "Too late")
        run.submit(later["session_id"], "Correct but late", 16)
        monkeypatch.setattr("experiments.transfer_study.workspace.utc_now", lambda: start)
    _rate_all(run, tmp_path)
    report = analyse(run)
    for arm in report["paired_rows"][0]["arms"].values():
        assert arm["later"]["correct_bounds"] == [0, 0]
        assert arm["later"]["restricted_time_bounds"] == [900, 900]
        assert arm["later"]["score"]["correct"] is True


def test_failed_attempts_consume_call_budget(tmp_path):
    plan = _plan(tmp_path)
    raw = read_json(plan)
    raw["max_model_calls"] = 1
    raw["models"]["fixture_small"]["command"] = ["python3", "-c", "raise SystemExit(3)"]
    write_json(plan, raw)
    run = StudyRun.create(plan, tmp_path / "run", 42)
    initial = run.open("orders_fixture", "A", "initial")
    with pytest.raises(RuntimeError):
        ModelGateway(run).invoke(initial["session_id"], "Attempt")
    with pytest.raises(ValueError, match="model-call budget"):
        ModelGateway(run).invoke(initial["session_id"], "Retry")


def test_confirmation_rejects_reused_developers_and_allocation_changes(tmp_path):
    import copy
    plan = _plan(tmp_path)
    raw = read_json(plan)
    raw["phase"] = "confirmation"
    case = copy.deepcopy(raw["cases"][0])
    case["id"] = "repeated"
    raw["cases"].append(case)
    write_json(plan, raw)
    with pytest.raises(ValueError, match="distinct developers across cases"):
        StudyDesign.load(plan)
    raw["phase"] = "pilot"
    write_json(plan, raw)
    run = StudyRun.create(plan, tmp_path / "run", 42)
    for item in run.allocation["assignments"]:
        for stage in ("initial", "later"):
            run.close(run.session_id(item["case_id"], item["slot_id"], stage),
                      "no_answer", "Synthetic nonresponse", 0)
    _rate_all(run, tmp_path)
    assert analyse(run)["summaries"]["overall"]["correctness"]["interval"] is None
    allocation = read_json(run.root / "allocation.json")
    allocation["assignments"][0]["arm"] = "tampered"
    write_json(run.root / "allocation.json", allocation)
    with pytest.raises(ValueError, match="Allocation does not match"):
        StudyRun(run.root)


def test_handover_digest_is_checked(tmp_path):
    run = StudyRun.create(_plan(tmp_path), tmp_path / "run", 42)
    initial = run.open("orders_fixture", "A", "initial")
    run.submit(initial["session_id"], "Done", 1)
    (run.root / "handoffs" / initial["session_id"] / "measurement.json").write_text("{}")
    with pytest.raises(ValueError, match="Handover snapshot differs"):
        run.open("orders_fixture", "A", "later")


def test_invalid_measurement_blocks_conclusion(tmp_path):
    run = StudyRun.create(_plan(tmp_path), tmp_path / "run", 42)
    for item in run.allocation["assignments"]:
        for stage in ("initial", "later"):
            run.close(run.session_id(item["case_id"], item["slot_id"], stage),
                      "invalid_measurement", "Reference answer could not be independently justified")
    _rate_all(run, tmp_path)
    assert analyse(run)["primary_decision"] == "invalid_measurement"


def test_invalid_initial_measurement_overrides_favourable_later_interval(tmp_path):
    import copy
    plan = _plan(tmp_path)
    raw = read_json(plan)
    template = raw["cases"][0]
    raw["phase"] = "confirmation"
    raw["primary_min_pairs"] = 12
    raw["cases"] = []
    for i in range(12):
        case = copy.deepcopy(template)
        case["id"] = f"case_{i}"
        for slot in case["slots"]:
            slot["sender"] += f"_{i}"
            slot["recipient"] += f"_{i}"
        raw["cases"].append(case)
    write_json(plan, raw)
    run = StudyRun.create(plan, tmp_path / "run", 42)
    for item in run.allocation["assignments"]:
        initial = run.session_id(item["case_id"], item["slot_id"], "initial")
        run.close(initial, "invalid_measurement" if item["case_id"] == "case_0" else "no_answer",
                  "Synthetic initial endpoint")
        later = run.open(item["case_id"], item["slot_id"], "later")
        if item["arm"] == "eal":
            run.submit(later["session_id"], "Correct later answer", 1)
        else:
            run.close(later["session_id"], "no_answer", "No final decision", 1)
    _rate_all(run, tmp_path)
    report = analyse(run)
    assert report["summaries"]["different_developer_different_model"]["correctness"]["interval"][0] > .1
    assert report["primary_decision"] == "invalid_measurement"


def test_alias_models_and_changed_seeds_cannot_create_valid_matched_cases(tmp_path):
    plan = _plan(tmp_path)
    raw = read_json(plan)
    original = raw["models"]["fixture_large"]["version"]
    raw["models"]["fixture_large"]["version"] = raw["models"]["fixture_small"]["version"]
    write_json(plan, raw)
    with pytest.raises(ValueError, match="distinct pinned versions"):
        StudyDesign.load(plan)
    raw["models"]["fixture_large"]["version"] = original
    write_json(plan, raw)
    run = StudyRun.create(plan, tmp_path / "run", 42)
    run.open("orders_fixture", "A", "initial")
    (run.case("orders_fixture").seed_dir / "measurement.json").write_text("{}")
    with pytest.raises(ValueError, match="Case seed differs"):
        run.open("orders_fixture", "B", "initial")


def test_participant_cannot_rate_study_answers(tmp_path):
    run = StudyRun.create(_plan(tmp_path), tmp_path / "run", 42)
    session = run.open("orders_fixture", "A", "initial")
    run.submit(session["session_id"], "Answer", 1)
    ratings = {"schema": "EAL/transfer-ratings/1", "ratings": [{
        "blind_id": blind_id(run, session["session_id"]), "rater": "alice",
        "correct": True, "material_error": False, "reason": "Own judgement"}], "adjudications": []}
    with pytest.raises(ValueError, match="must not be study participants"):
        resolve_scores(run, ratings)
