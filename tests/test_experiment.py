"""Experiment design/accounting regression tests; these are not model trials."""
import asyncio
import json
import sys

import pytest

from eal.experiment import aggregate_experiment, cluster_interval, freeze_experiment, load_plan, make_schedule, run_experiment
from _runtime_cases import write_suite


def plan_file(tmp_path):
    suite = write_suite(tmp_path)
    provider = tmp_path / "provider.toml"
    provider.write_text('[provider]\nkind="command"\nmodel="scripted-regression-not-an-LLM"\nmeasurement_kind="interface_only"\nargv=' + json.dumps([sys.executable, "-c", "raise RuntimeError('must not run')"]) + '\n')
    plan = {"schema": "EAL/experiment-plan/1", "name": "regression-only", "suite": str(suite),
            "split": "development", "task_ids": ["pressure-trial"], "repetitions": 2,
            "order_seed": 29, "sampling_seeds": [101, 103], "concurrency": 2, "bootstrap_samples": 50,
            "per_mcp_call_usd": 0, "conditions": [
                {"id": "unaided", "provider": str(provider), "model_class": "fixture", "arm": "unaided"},
                {"id": "delegated", "provider": str(provider), "model_class": "fixture", "arm": "delegated",
                 "host_mode": "stateful", "interaction_mode": "text", "seed_supported": True}]}
    filename = tmp_path / "plan.json"
    filename.write_text(json.dumps(plan))
    return filename


def test_seeded_schedule_is_paired_and_rotates_condition_positions(tmp_path):
    plan = load_plan(plan_file(tmp_path))
    schedule = make_schedule(plan, ["first", "second"])
    assert schedule == make_schedule(plan, ["first", "second"])
    assert len(schedule) == 8
    blocks = {}
    for item in schedule:
        blocks.setdefault(item["block_id"], []).append(item)
    for values in blocks.values():
        assert {item["condition_id"] for item in values} == {"unaided", "delegated"}
        assert len({item["sampling_seed"] for item in values}) == 1
    assert {item["condition_position"] for item in schedule if item["condition_id"] == "unaided"} == {0, 1}


def test_freeze_preserves_reference_and_provider_identity_without_generating(tmp_path):
    plan = plan_file(tmp_path)
    freeze = freeze_experiment(plan)
    assert freeze["reference_checks"][0]["passed"]
    assert freeze["provider_identities"]["delegated"]["measurement_kind"] == "interface_only"
    assert len(freeze["schedule"]) == 4
    assert freeze["freeze_digest"] == freeze_experiment(plan)["freeze_digest"]
    assert freeze["runtime"]["source_digest"]
    output = tmp_path / "frozen"
    report = asyncio.run(run_experiment(plan, output, freeze_only=True))
    assert report["status"] == "frozen"
    assert (output / "freeze.json").exists()
    assert not (output / "trials.jsonl").exists()
    with pytest.raises(FileExistsError):
        asyncio.run(run_experiment(plan, output, freeze_only=True))


def test_cluster_interval_does_not_treat_repeated_calls_as_new_tasks():
    rows = [{"task_id": "easy", "value": 1}] * 20 + [{"task_id": "hard", "value": 0}] * 20
    interval = cluster_interval(rows, lambda row: row["value"], seed=3, samples=1000)
    assert interval["task_clusters"] == 2
    assert interval["estimate"] == .5
    assert interval["interval_95"] == [0, 1]
    assert cluster_interval(rows[:20], lambda row: row["value"])["interval_95"] is None
    assert cluster_interval(rows, lambda row: None)["estimate"] is None


def test_experiment_keeps_failed_repetitions_and_known_costs(tmp_path, monkeypatch):
    from eal import experiment
    counts = {}
    async def scripted_trial(task, root, provider, *, arm, **kwargs):
        counts[arm] = counts.get(arm, 0) + 1
        correct = counts[arm] == 1
        score = {"correct": correct, "correctly_resolved": correct, "justified_unresolved": False,
                 "unjustified": False, "unresolved": not correct,
                 "claims": {"result": {"expected": "supported", "actual": "supported" if correct else "unresolved",
                                       "category": "correct" if correct else "unresolved"}}}
        return {"task_id": task["id"], "arm": arm, "family": task["family"], "score": score,
                "cost": {"model_usd": .01, "tool_usd": 0, "total_usd": .01},
                "report": {"status": "completed" if correct else "incomplete", "stop_reason": "finished" if correct else "provider_error",
                           "attempts": [{"measurement_kind": "interface_only"}], "repairs": 0, "latency_seconds": 1,
                           "usage": {"token_usage_complete": True, "total_tokens": 100}}}
    monkeypatch.setattr(experiment, "evaluate_task", scripted_trial)
    output = tmp_path / "results"
    report = asyncio.run(run_experiment(plan_file(tmp_path), output))
    assert report["completed_trials"] == 4
    assert not report["reference_or_implementation_drift"]
    for condition in report["aggregate"]["conditions"].values():
        assert condition["completed_trials"] == 2
        assert condition["correct"] == 1
        assert condition["total_cost_usd"] == .02
        assert condition["cost_per_correct_task_usd"] == .02
    assert len((output / "trials.jsonl").read_text().splitlines()) == 4
    assert len(list((output / "trials").glob("*.json"))) == 4


def test_plan_rejects_fake_unaided_native_condition(tmp_path):
    filename = plan_file(tmp_path)
    plan = json.loads(filename.read_text())
    plan["conditions"][0]["interaction_mode"] = "native"
    filename.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="unaided"):
        load_plan(filename)
