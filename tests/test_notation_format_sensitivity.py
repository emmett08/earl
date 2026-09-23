"""Fence-only post-hoc sensitivity preserves the primary records and contract."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyse_notation_format_sensitivity as sensitivity
import analyse_notation_transfer as primary


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def run(tmp_path):
    full, absent = {"x": "supported"}, {"x": "unsupported"}
    task = dict(family="synthetic", expected=full, available_information_references={
        view: absent if view in {"answer", "answer_irrelevant"} else full
        for view in (*primary.VIEWS, "raw_only")})
    frozen = dict(schema="EAL/notation-transfer-freeze/2", scoring_schema=primary.SCORING_SCHEMA,
                  tasks={"a": task}, plan=dict(task_ids=["a"], repetitions=1),
                  provider_identity=dict(model="synthetic"), schedule=[])
    for condition in primary.conditions():
        messages = [{"role": "user", "content": condition["id"]}]
        frozen["schedule"].append(dict(trial_id=f"trial-{len(frozen['schedule']):05d}",
            task_id="a", repetition=0, condition=condition, messages_digest=primary.digest(messages)))
    frozen["freeze_digest"] = primary.digest(frozen)
    dump(tmp_path / "freeze.json", frozen)
    for row in frozen["schedule"]:
        record = dict(row, freeze_digest=frozen["freeze_digest"],
                      messages=[{"role": "user", "content": row["condition"]["id"]}])
        save(tmp_path, frozen, record, json.dumps(dict(claims=full, basis=[])))
    return tmp_path, frozen


def save(root, frozen, record, text, state="responded"):
    record = copy.deepcopy(record)
    response = dict(text=text, input_tokens=100, output_tokens=20, model="synthetic", metadata={})
    record.update(state=state, response=response, cost_usd=0.001, response_model_matches=True,
                  scoring_schema=primary.SCORING_SCHEMA)
    task = frozen["tasks"][record["task_id"]]
    answer = primary.admitted_answer(response, task["expected"]) if state == "responded" else None
    for oracle, field in primary.ORACLES.items():
        reference = (task["expected"] if oracle == "full_information" else
                     task["available_information_references"][record["condition"]["information"]])
        record[field] = primary.expected_score(reference, answer)
    proposed = primary.proposal(task["expected"], record["condition"]["candidate_quality"], record["repetition"])
    available = task["available_information_references"][record["condition"]["information"]]
    record["proposal_correct_given_available_information"] = proposed == available if proposed is not None else None
    dump(root / "trials" / (record["trial_id"] + ".json"), record)
    return record


def get(run, condition):
    root, frozen = run
    row = next(r for r in frozen["schedule"] if r["condition"]["id"] == condition)
    return json.loads((root / "trials" / (row["trial_id"] + ".json")).read_text())


@pytest.mark.parametrize("opening,newline", [("```json", "\n"), ("```", "\n"), ("```json", "\r\n")])
def test_accepts_only_exact_whole_fence_variants(opening, newline):
    body = '{"claims":{"x":"supported"},"basis":[]}'
    assert sensitivity.fence_answer(" \n" + opening + newline + body + newline + "```\n", {"x": "supported"}) == {"x": "supported"}


@pytest.mark.parametrize("text", [
    'Here is JSON:\n```json\n{"claims":{"x":"supported"},"basis":[]}\n```',
    '```json\n{"claims":{"x":"supported"},"basis":[]}\n```\nDone.',
    '```JSON\n{"claims":{"x":"supported"},"basis":[]}\n```',
    '```python\n{"claims":{"x":"supported"},"basis":[]}\n```',
    '```json {"claims":{"x":"supported"},"basis":[]} ```',
    '```json\n{"claims":{"x":"supported"},"basis":[]}\n```\n```\n{}\n```',
    '```json\n{"claims":{"x":"supported"},"basis":[],"basis":[]}\n```',
    '```json\n{"claims":{"x":"supported","extra":"supported"},"basis":[]}\n```',
    '```json\n{"claims":{"x":{"status":"supported"}},"basis":[]}\n```',
    '```json\n{"claims":{"x":"supported"},"basis":[],}\n```',
    '```json\n{"claims":{"x":"supported"},"basis":NaN}\n```',
    '{"claims":{"x":"supported"},"basis":[]}',
])
def test_no_extraction_schema_repair_or_nonfinite_json(text):
    assert sensitivity.fence_answer(text, {"x": "supported"}) is None


def test_recovery_reports_both_references_and_keeps_primary_bytes(run):
    root, frozen = run
    r = get(run, "eal_correct_answer")
    save(root, frozen, r, '```json\n{"claims":{"x":"supported"},"basis":[]}\n```', "malformed_response")
    before = {p: p.read_bytes() for p in root.rglob("*.json")}
    result = sensitivity.analyse(root)
    assert result["all_scheduled_finalized"] and result["finalized_attempts"] == 18
    assert result["totals"]["recovered_by_fence_removal"] == 1
    assert result["totals"]["modes"]["strict"]["wellformed"]["count"] == 17
    assert result["totals"]["modes"]["fence_only"]["wellformed"]["count"] == 18
    row = next(t for t in result["trials"] if t["trial_id"] == r["trial_id"])
    assert row["modes"]["fence_only"]["metrics"]["full_information"] == dict(correct=True, false_support=False)
    assert row["modes"]["fence_only"]["metrics"]["available_information"] == dict(correct=False, false_support=True)
    assert row["modes"]["strict"]["metrics"]["full_information"]["correct"] is False
    assert row["primary_record_digest"] and row["response_text_sha256"]
    assert len(result["conditions"]) == len(result["task_conditions"]) == 18
    assert len(result["tasks"]) == 1
    assert "post-hoc" in result["analysis_kind"] and "not prespecified" in result["selected_after_observing"]
    assert before == {p: p.read_bytes() for p in root.rglob("*.json")}


def test_notation_contrast_changes_only_in_separate_sensitivity(run):
    root, frozen = run
    r = get(run, "eal_raw_only")
    save(root, frozen, r, '```\n{"claims":{"x":"supported"},"basis":[]}\n```', "malformed_response")
    result = sensitivity.analyse(root)
    for mode, difference in (("strict", -1), ("fence_only", 0)):
        contrast = next(c for c in result["paired_comparisons"][mode] if c["name"] == "notation_raw_only")
        assert contrast["metrics"]["full_information"]["task_weighted_difference"] == difference


def test_provider_failures_uncertain_and_missing_stay_distinct(run):
    root, frozen = run
    error = get(run, "eal_correct_answer")
    save(root, frozen, error, '```json\n{"claims":{"x":"supported"},"basis":[]}\n```', "provider_error")
    unknown = get(run, "eal_correct_answer_raw")
    unknown = {k: unknown[k] for k in ("trial_id", "task_id", "repetition", "condition", "messages_digest", "freeze_digest", "messages")}
    unknown["state"] = "attempt_started"
    dump(root / "trials" / (unknown["trial_id"] + ".json"), unknown)
    absent = get(run, "eal_raw_only")
    (root / "trials" / (absent["trial_id"] + ".json")).unlink()
    result = sensitivity.analyse(root)
    assert (result["finalized_attempts"], result["uncertain_attempts"], result["missing_scheduled"]) == (16, 1, 1)
    assert result["totals"]["provider_errors"] == 1
    assert result["totals"]["recovered_by_fence_removal"] == 0
    assert result["totals"]["modes"]["fence_only"]["wellformed"] == dict(count=15, denominator=16, rate=15/16)
    contrast = next(c for c in result["paired_comparisons"]["fence_only"] if c["name"] == "notation_raw_only")
    assert not contrast["coverage_complete"] and contrast["metrics"]["full_information"]["task_weighted_difference"] is None
    assert not result["all_scheduled_finalized"]
    assert result["totals"]["recovered_by_claim_map_only"] == 0


@pytest.mark.parametrize("mutation,match", [
    (lambda r: r.update(messages=[]), "prompt digest"),
    (lambda r: r.update(freeze_digest="wrong"), "freeze digest"),
    (lambda r: r["score"].update(correct=False), "disagrees"),
])
def test_primary_validation_is_required(run, mutation, match):
    root, _ = run
    r = get(run, "eal_raw_only")
    mutation(r)
    dump(root / "trials" / (r["trial_id"] + ".json"), r)
    with pytest.raises(ValueError, match=match):
        sensitivity.analyse(root)


@pytest.mark.parametrize("extra", [',"extra":[]', ',"basis":42', ''])
def test_claim_map_only_ignores_other_keys_and_basis_shape(extra):
    text = '{"claims":{"x":"supported"}' + extra + '}'
    assert sensitivity.claim_map_answer(text, {"x": "supported"}) == {"x": "supported"}


@pytest.mark.parametrize("text", [
    '```json\n{"claims":{"x":"supported"},"basis":[]}\n```',
    'Here: {"claims":{"x":"supported"}}',
    '{"claims":{"x":"supported"},}',
    '{"claims":{"x":"supported","extra":"supported"}}',
    '{"claims":{"x":"supported"},"claims":{"x":"unsupported"}}',
    '{"claims":{}}',
    '{"claims":{"x":"unknown"}}',
    '{"claims":{"x":{"status":"supported"}}}',
    '{"claims":{"x":true}}',
    '{"claims":{"x":"supported"},"basis":NaN}',
    '[{"claims":{"x":"supported"}}]',
])
def test_claim_map_only_does_not_extract_or_repair(text):
    assert sensitivity.claim_map_answer(text, {"x": "supported"}) is None


def test_claim_map_extra_fields_recover_agreement_and_false_support_separately(run):
    root, frozen = run
    r = get(run, "eal_correct_answer")
    save(root, frozen, r, '{"claims":{"x":"supported"},"basis":[],"contested":[]}', "malformed_response")
    error = get(run, "eal_correct_answer_raw")
    save(root, frozen, error, '{"claims":{"x":"supported"},"extra":[]}', "provider_error")
    before = {p: p.read_bytes() for p in root.rglob("*.json")}
    result = sensitivity.analyse(root)
    assert result["totals"]["recovered_by_fence_removal"] == 0
    assert result["totals"]["recovered_by_claim_map_only"] == 1
    row = next(t for t in result["trials"] if t["trial_id"] == r["trial_id"])
    assert row["modes"]["claim_map_only"]["claim_map_admitted"]
    assert "wellformed" not in row["modes"]["claim_map_only"]
    assert row["modes"]["claim_map_only"]["metrics"]["full_information"] == dict(correct=True, false_support=False)
    assert row["modes"]["claim_map_only"]["metrics"]["available_information"] == dict(correct=False, false_support=True)
    for mode in ("strict", "fence_only"):
        assert not row["modes"][mode]["wellformed"]
    failed = next(t for t in result["trials"] if t["trial_id"] == error["trial_id"])
    assert not failed["modes"]["claim_map_only"]["claim_map_admitted"]
    assert before == {p: p.read_bytes() for p in root.rglob("*.json")}
