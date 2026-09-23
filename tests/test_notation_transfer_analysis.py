"""Independent analysis checks with synthetic records only; no model calls."""
import copy
import io
import json
from pathlib import Path
import sys
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import analyse_notation_transfer as analysis
from eal.benchmark import score_answer


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


@pytest.fixture
def run(tmp_path):
    tasks = {}
    for name, expected in (("a", {"x": "supported"}),
                           ("b", {"x": "contested", "y": "supported"})):
        unavailable = {claim: "unsupported" for claim in expected}
        tasks[name] = {"family": "family-" + name, "expected": expected,
                       "available_information_references": {
                           view: unavailable if view in {"answer", "answer_irrelevant"} else expected
                           for view in (*analysis.VIEWS, "raw_only")}}
    frozen = {"schema": "EAL/notation-transfer-freeze/2", "scoring_schema": analysis.SCORING_SCHEMA,
              "tasks": tasks, "plan": {"task_ids": list(tasks), "repetitions": 2},
              "provider_identity": {"model": "synthetic-model"}, "schedule": []}
    messages = {}
    for task in tasks:
        for repetition in range(2):
            for condition in analysis.conditions():
                trial = f"trial-{len(frozen['schedule']):05d}"
                message = [{"role": "user", "content": json.dumps([task, repetition, condition])}]
                messages[trial] = message
                frozen["schedule"].append(dict(trial_id=trial, task_id=task, repetition=repetition,
                    condition=condition, messages_digest=analysis.digest(message)))
    frozen["freeze_digest"] = analysis.digest(frozen)
    dump(tmp_path / "freeze.json", frozen)
    for row in frozen["schedule"]:
        record = dict(row, freeze_digest=frozen["freeze_digest"], messages=messages[row["trial_id"]])
        task = tasks[row["task_id"]]
        reference = task["available_information_references"][row["condition"]["information"]]
        save_record(tmp_path, frozen, record, reference)
    return tmp_path, frozen


def save_record(root, frozen, record, claims, state="responded", cost=0.001, text=None):
    record = copy.deepcopy(record)
    record.update(state=state, scoring_schema=analysis.SCORING_SCHEMA, cost_usd=cost,
                  response_model_matches=True,
                  response=dict(text=text if text is not None else json.dumps({"claims": claims, "basis": []}),
                                input_tokens=100, output_tokens=20, model="synthetic-model", metadata={}))
    task = frozen["tasks"][record["task_id"]]
    report = {"status": "completed" if state == "responded" else "incomplete",
              "final": {"claims": claims} if state == "responded" else None}
    record["score"] = score_answer(task["expected"], report)
    reference = task["available_information_references"][record["condition"]["information"]]
    record["available_information_score"] = score_answer(reference, report)
    proposed = analysis.proposal(task["expected"], record["condition"]["candidate_quality"], record["repetition"])
    record["proposal_correct_given_available_information"] = proposed == reference if proposed is not None else None
    dump(root / "trials" / (record["trial_id"] + ".json"), record)
    return record


def get_record(run, condition, task="a", rep=0):
    root, frozen = run
    row = next(r for r in frozen["schedule"] if r["task_id"] == task
               and r["repetition"] == rep and r["condition"]["id"] == condition)
    return json.loads((root / "trials" / (row["trial_id"] + ".json")).read_text())


def find(items, **fields):
    return next(item for item in items if all(item[k] == v for k, v in fields.items()))


def test_complete_run_reports_all_conditions_and_both_oracles(run, tmp_path):
    root, _ = run
    result = analysis.analyse(root)
    assert result["scheduled"] == result["finalized_attempts"] == 72
    assert result["all_scheduled_finalized"]
    assert len(result["conditions"]) == 18 and len(result["task_conditions"]) == 36
    assert result["family_count"] == result["task_count"] == 2
    answer = find(result["conditions"], id="eal_correct_answer")
    assert answer["metrics"]["full_information"]["correctness"] == {"count": 0, "denominator": 4, "rate": 0.0}
    assert answer["metrics"]["available_information"]["correctness"]["rate"] == 1
    assert answer["metrics"]["full_information"]["damage"]["rate"] == 1
    assert answer["metrics"]["available_information"]["damage"]["rate"] is None
    assert answer["metrics"]["available_information"]["correction"]["rate"] == 1
    absent = find(result["conditions"], id="eal_raw_only")["metrics"]["available_information"]
    assert absent["proposal_absent"] == 4 and absent["damage"]["denominator"] == 0
    contrast = find(result["paired_comparisons"], name="eal_original_incorrect_raw_minus_answer")
    assert contrast["metrics"]["available_information"]["reference_changed_pairs"] == 4
    assert contrast["metrics"]["full_information"]["reference_changed_pairs"] == 0
    assert contrast["metrics"]["full_information"]["task_weighted_difference"] == 1
    assert contrast["metrics"]["available_information"]["task_weighted_difference"] == 0
    assert all(c["coverage_complete"] for c in result["paired_comparisons"])
    output = tmp_path / "analysis.json"
    analysis.write_outputs(result, output)
    assert json.loads(output.read_text())["finalized_attempts"] == 72
    assert {p.name for p in tmp_path.glob("analysis.*.csv")} == {
        "analysis.conditions.csv", "analysis.tasks.csv", "analysis.contrasts.csv",
        "analysis.transitions.csv", "analysis.trials.csv"}


def test_proposal_correctness_is_reclassified_under_available_information(run):
    root, _ = run
    result = analysis.analyse(root)
    row = find(result["trials"], task_id="a", repetition=1, condition_id="eal_incorrect_answer")
    assert row["full_information_proposal_correct"] is False
    assert row["available_information_proposal_correct"] is True
    assert row["full_information_transition"] == "incorrect_to_incorrect_complete"
    assert row["available_information_transition"] == "correct_to_correct"


def test_provider_identity_finish_reasons_and_token_completeness(run):
    root, _ = run
    record = get_record(run, "eal_raw_only")
    record["response"]["metadata"].update(finish_reason="stop", cached_input_tokens=60, reasoning_tokens=0)
    dump(root / "trials" / (record["trial_id"] + ".json"), record)
    result = analysis.analyse(root)
    resources = result["totals"]["resources"]
    assert result["configured_model"] == "synthetic-model"
    assert resources["response_models"] == {"synthetic-model": 72}
    assert resources["finish_reasons"] == {"<unknown>": 71, "stop": 1}
    assert resources["input_tokens"]["known_total"] == 7200
    assert resources["output_tokens"]["known_total"] == 1440
    assert resources["cached_input_tokens"] == {"known_total": 60, "known_attempts": 1,
            "unknown_attempts": 71, "complete_for_attempted": False}
    assert resources["reasoning_tokens"]["known_attempts"] == 1
    row = find(result["trials"], trial_id=record["trial_id"])
    assert row["cached_input_tokens"] == 60 and row["finish_reason"] == "stop"


def test_length_provider_error_retains_usage_and_failed_endpoint(run):
    root, frozen = run
    record = get_record(run, "eal_raw_only")
    record = save_record(root, frozen, record, {"x": "supported"}, state="provider_error")
    record["response"]["metadata"]["finish_reason"] = "length"
    dump(root / "trials" / (record["trial_id"] + ".json"), record)
    result = analysis.analyse(root)
    assert result["totals"]["provider_errors_length"] == 1
    assert result["totals"]["state_by_finish_reason"]["provider_error"] == {"length": 1}
    assert result["totals"]["resources"]["input_tokens"]["known_attempts"] == 72
    assert result["totals"]["resources"]["attempted_cost_usd"] is not None
    assert find(result["trials"], trial_id=record["trial_id"])["full_information_correct"] is False


def test_false_support_depends_on_reference_and_all_claims_must_be_correct(run):
    root, frozen = run
    a = get_record(run, "eal_correct_answer")
    save_record(root, frozen, a, {"x": "supported"})
    b = get_record(run, "eal_raw_only", task="b")
    save_record(root, frozen, b, {"x": "supported", "y": "supported"})
    result = analysis.analyse(root)
    row = find(result["trials"], trial_id=a["trial_id"])
    assert row["full_information_correct"] is True and row["full_information_false_support"] is False
    assert row["available_information_correct"] is False and row["available_information_false_support"] is True
    mixed = find(result["trials"], trial_id=b["trial_id"])
    assert mixed["full_information_correct"] is False and mixed["full_information_false_support"] is True


def test_failures_uncertain_and_missing_are_distinct_and_later_records_survive(run):
    root, frozen = run
    malformed = get_record(run, "eal_correct_answer")
    save_record(root, frozen, malformed, {}, state="malformed_response", text="not JSON")
    error = get_record(run, "eal_correct_answer_raw")
    error = save_record(root, frozen, error, {"x": "supported"}, state="provider_error", cost=None)
    error["response"]["input_tokens"] = None
    dump(root / "trials" / (error["trial_id"] + ".json"), error)
    marker = get_record(run, "eal_correct_answer_irrelevant")
    marker = {k: marker[k] for k in ("trial_id", "task_id", "repetition", "condition", "messages_digest", "freeze_digest", "messages")}
    marker["state"] = "attempt_started"
    dump(root / "trials" / (marker["trial_id"] + ".json"), marker)
    missing = get_record(run, "eal_raw_only")
    (root / "trials" / (missing["trial_id"] + ".json")).unlink()
    result = analysis.analyse(root)
    assert (result["finalized_attempts"], result["uncertain_attempts"], result["missing_scheduled"]) == (70, 1, 1)
    assert result["totals"]["complete_responses"] == 68
    assert result["totals"]["malformed_responses"] == result["totals"]["provider_errors"] == 1
    assert result["totals"]["metrics"]["available_information"]["correctness"]["denominator"] == 70
    assert result["totals"]["resources"]["cost_unknown_attempts"] == 2
    assert result["totals"]["resources"]["attempted_cost_usd"] is None
    assert result["totals"]["resources"]["input_tokens"]["unknown_attempts"] == 2
    assert result["missing_trial_ids"] == [missing["trial_id"]]
    contrast = find(result["paired_comparisons"], name="notation_raw_only")
    assert contrast["paired_finalized_attempts"] == 3 and not contrast["coverage_complete"]
    assert contrast["metrics"]["full_information"]["task_weighted_difference"] is None
    assert len(result["trials"]) == 72


def test_partial_pair_description_weights_tasks_not_available_endpoints(run):
    root, frozen = run
    for task in ("a", "b"):
        for rep in range(2):
            right = get_record(run, "json_raw_only", task, rep)
            save_record(root, frozen, right, {k: "out_of_scope" for k in frozen["tasks"][task]["expected"]})
    a = get_record(run, "eal_raw_only", "a", 0)
    save_record(root, frozen, a, {"x": "out_of_scope"})
    missing = get_record(run, "eal_raw_only", "a", 1)
    (root / "trials" / (missing["trial_id"] + ".json")).unlink()
    contrast = find(analysis.analyse(root)["paired_comparisons"], name="notation_raw_only")
    metric = contrast["metrics"]["full_information"]
    assert metric["observed_pairs_only_task_weighted_difference"] == 0.5
    assert metric["task_weighted_difference"] is None
    assert metric["paired_outcomes"]["left_only_correct"] == 2


@pytest.mark.parametrize("mutation,match", [
    (lambda r: r.update(freeze_digest="wrong"), "freeze digest"),
    (lambda r: r.update(messages=[]), "prompt digest"),
    (lambda r: r.update(repetition=1), "scheduled endpoint"),
    (lambda r: r["score"].update(correct=1), "non-boolean"),
    (lambda r: r["score"].update(correct=False), "disagrees"),
    (lambda r: r.update(proposal_correct_given_available_information=True), "Proposal correctness"),
    (lambda r: r.update(cost_usd=-1), "Invalid or missing cost"),
    (lambda r: r["response"].update(input_tokens=True), "Invalid token"),
    (lambda r: r.update(response_model_matches=False), "model match"),
])
def test_rejects_tampered_or_unknown_measurements(run, mutation, match):
    root, _ = run
    record = get_record(run, "eal_raw_only")
    mutation(record)
    dump(root / "trials" / (record["trial_id"] + ".json"), record)
    with pytest.raises(ValueError, match=match):
        analysis.analyse(root)


def test_rejects_duplicate_and_unknown_trial_ids(run):
    root, _ = run
    record = get_record(run, "eal_raw_only")
    dump(root / "trials" / "zz-duplicate.json", record)
    with pytest.raises(ValueError, match="Duplicate trial ID"):
        analysis.analyse(root)
    (root / "trials" / "zz-duplicate.json").unlink()
    record["trial_id"] = "foreign"
    dump(root / "trials" / "foreign.json", record)
    with pytest.raises(ValueError, match="Unknown trial ID"):
        analysis.analyse(root)


def test_rejects_incomplete_or_duplicate_frozen_schedule(run):
    root, frozen = run
    frozen["schedule"].pop()
    frozen.pop("freeze_digest")
    frozen["freeze_digest"] = analysis.digest(frozen)
    dump(root / "freeze.json", frozen)
    with pytest.raises(ValueError, match="Frozen schedule does not cover"):
        analysis.analyse(root)


@pytest.mark.parametrize("text", [
    '{"claims":{"x":"supported","extra":"supported"},"basis":[]}',
    '{"claims":{"x":{"status":"supported"}},"basis":[]}',
    '{"claims":{"x":"supported"},"basis":[],"basis":[]}',
    '{"claims":{"x":"unknown"},"basis":[]}',
])
def test_malformed_responses_fail_as_whole_attempts(run, text):
    root, frozen = run
    record = get_record(run, "eal_raw_only")
    save_record(root, frozen, record, {}, state="malformed_response", text=text)
    result = analysis.analyse(root)
    row = find(result["trials"], trial_id=record["trial_id"])
    assert not row["full_information_correct"] and not row["available_information_correct"]
    assert row["full_information_transition"] == "absent_to_incomplete"
    assert not row["available_information_false_support"]


def test_empty_attempts_are_not_success_or_zero_cost(run):
    root, _ = run
    for path in (root / "trials").glob("*.json"):
        path.unlink()
    result = analysis.analyse(root)
    assert result["finalized_attempts"] == result["uncertain_attempts"] == 0
    assert result["missing_scheduled"] == 72
    assert len(result["conditions"]) == 18
    assert result["totals"]["metrics"]["full_information"]["correctness"]["rate"] is None
    assert result["totals"]["resources"]["attempted_cost_usd"] is None
    assert all(not pair["coverage_complete"] for pair in result["paired_comparisons"])


def make_archive(root, entries=None):
    if entries is None:
        entries = [("trials/" + p.name, p.read_bytes()) for p in sorted((root / "trials").glob("*.json"))]
    with tarfile.open(root / "trials.tar.gz", "w:gz") as archive:
        for name, content in entries:
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))


def test_archive_analysis_matches_loose_and_combined_records_exactly(run):
    root, _ = run
    expected = analysis.analyse(root)
    make_archive(root)
    assert analysis.analyse(root) == expected
    for path in (root / "trials").glob("*.json"):
        path.unlink()
    assert analysis.analyse(root) == expected


def test_archive_and_loose_byte_mismatch_is_rejected(run):
    root, _ = run
    make_archive(root)
    path = next((root / "trials").glob("*.json"))
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="byte for byte"):
        analysis.analyse(root)


@pytest.mark.parametrize("name", ["../trial-00000.json", "/trials/trial-00000.json",
                                  "trials/nested/trial-00000.json", "trials/", "metadata.json"])
def test_archive_rejects_traversal_and_unexpected_members(run, name):
    root, _ = run
    make_archive(root, [(name, b"{}")])
    with pytest.raises(ValueError, match="Unsafe or unexpected"):
        analysis.analyse(root)


def test_archive_rejects_duplicate_members_and_size_limits(run, monkeypatch):
    root, _ = run
    make_archive(root, [("trials/trial-00000.json", b"{}"), ("trials/trial-00000.json", b"{}")])
    with pytest.raises(ValueError, match="Duplicate trial archive member"):
        analysis.analyse(root)
    make_archive(root)
    monkeypatch.setattr(analysis, "MAX_ARCHIVE_MEMBERS", 1)
    with pytest.raises(ValueError, match="member count limit"):
        analysis.analyse(root)
    monkeypatch.setattr(analysis, "MAX_ARCHIVE_MEMBERS", 10000)
    monkeypatch.setattr(analysis, "MAX_ARCHIVE_BYTES", 1)
    with pytest.raises(ValueError, match="total size limit"):
        analysis.analyse(root)


def test_archive_rejects_symlinks(run):
    root, _ = run
    with tarfile.open(root / "trials.tar.gz", "w:gz") as archive:
        member = tarfile.TarInfo("trials/trial-00000.json")
        member.type = tarfile.SYMTYPE
        member.linkname = "/tmp/unrelated"
        archive.addfile(member)
    with pytest.raises(ValueError, match="Unsafe or unexpected"):
        analysis.analyse(root)


def test_archive_caps_expanded_stream_before_tar_header_parsing(run, monkeypatch):
    root, _ = run
    make_archive(root)
    monkeypatch.setattr(analysis, "MAX_TAR_STREAM_BYTES", 1)
    with pytest.raises(ValueError, match="expanded stream size limit"):
        analysis.analyse(root)


def test_constant_label_baselines_use_each_oracle_and_coverage(run):
    root, _ = run
    result = analysis.analyse(root)
    baseline = result["constant_label_baselines"]
    assert baseline["full_information"]["scheduled"]["supported"]["correctness"] == {
        "count": 36, "denominator": 72, "rate": 0.5}
    assert baseline["available_information"]["scheduled"]["unsupported"]["correctness"]["count"] == 32
    missing = get_record(run, "eal_raw_only")
    (root / "trials" / (missing["trial_id"] + ".json")).unlink()
    baseline = analysis.analyse(root)["constant_label_baselines"]
    assert baseline["full_information"]["scheduled"]["supported"]["correctness"]["denominator"] == 72
    assert baseline["full_information"]["finalized_attempts"]["supported"]["correctness"] == {
        "count": 35, "denominator": 71, "rate": 35 / 71}
