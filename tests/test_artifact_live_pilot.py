"""Offline checks for the bounded artifact recipient experiment."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import shutil

import pytest

from eal.providers import ModelResponse
from scripts.run_artifact_live_pilot import prepare, preflight_summary, run, verify


SOURCE = '''language "EAL/2";
environment rig { require "site" == "pilot"; }
tool reader { version "1"; mode deterministic; }
evidence result { tool reader; kind test; environment rig; max_age 3600; require "passed" == true; }
reasoning relation { method "structured/1"; rationale "The bound test record supplies provisional support."; }
claim accepted { statement "The bounded rig test passed."; environment rig; }
argument route { conclusion accepted; reasoning relation; evidence result; }
'''


def fixture_plan(tmp_path: Path) -> Path:
    roots = []
    for i in range(4):
        directory = tmp_path / f"root{i}"
        directory.mkdir()
        (directory / "source.eal").write_text(SOURCE, encoding="utf-8")
        states = []
        for j, passed in enumerate((True, False, True)):
            stem = f"state{j}"
            envelope = {
                "observed_at": "2040-01-01T12:00:00Z",
                "context": {"site": "pilot"},
                "request": {"tool": "reader", "tool_version": "1", "mode": "deterministic",
                            "input": {}, "context": {"site": "pilot"}},
                "value": {"passed": passed},
            }
            (directory / f"{stem}.json").write_text(json.dumps(envelope), encoding="utf-8")
            (directory / f"{stem}.toml").write_text(
                '[tools.reader]\nkind="json_file"\nmode="deterministic"\nversion="1"\n'
                f'path="{stem}.json"\n', encoding="utf-8")
            states.append({"id": stem, "registry": f"root{i}/{stem}.toml",
                           "expected": "supported" if passed else "unsupported"})
        roots.append({"id": f"root{i}", "brief": "Assess the registered rig claim using the current observation.",
                      "source": f"root{i}/source.eal", "claim": "accepted", "context": {"site": "pilot"},
                      "now": "2040-01-01T12:01:00Z", "states": states})
    path = tmp_path / "pilot.json"
    path.write_text(json.dumps({"schema": "eal2-artifact-live-pilot/1", "roots": roots}), encoding="utf-8")
    return path


class FakeProvider:
    def __init__(self, *, usage=True, response_model="fixed"):
        self.calls = 0
        self.usage = usage
        self.response_model = response_model

    def identity(self):
        return {"provider": "fake", "adapter": "fake", "model": "fixed",
                "pricing": {"input_usd_per_million": 0.1, "output_usd_per_million": 0.4,
                            "cached_input_usd_per_million": 0.025}}

    async def complete(self, messages, max_output_tokens):
        self.calls += 1
        assert max_output_tokens == 256
        assert all("Frozen oracle status:" not in message["content"] for message in messages)
        return ModelResponse('{"claims":{"accepted":"supported"},"explanation":"The record passes."}',
                             100 if self.usage else None, 20 if self.usage else None,
                             self.response_model, {"cached_input_tokens": 0})


def test_freeze_parity_and_48_reproducible_requests_without_provider_calls(tmp_path):
    path = fixture_plan(tmp_path)
    provider = FakeProvider()
    freeze = prepare(path, provider.identity())
    assert len(freeze["cases"]) == 48
    assert len({(row["root_id"], row["state_id"], row["arm"]) for row in freeze["cases"]}) == 48
    assert {row["expected"] for row in freeze["cases"]} == {"supported", "unsupported"}
    assert all(row["host"]["claims"][row["claim"]] == row["expected"] for row in freeze["cases"])
    assert all(row["prompt_bytes"] <= 16_000 for row in freeze["cases"])
    again = prepare(path, provider.identity())
    assert freeze["stable_digest"] == again["stable_digest"]
    assert freeze["freeze_digest"] != again["freeze_digest"]  # Run IDs are deliberately retained.
    assert len(freeze["host_snapshots"]) == 12
    result = asyncio.run(run(path, tmp_path / "freeze", provider, freeze_only=True))
    assert result["status"] == "frozen" and result["attempts"] == 0
    assert verify(path, tmp_path / "freeze", provider)["status"] == "verified"
    assert provider.calls == 0


def test_fake_run_keeps_authoritative_status_separate_from_model_answer(tmp_path):
    path = fixture_plan(tmp_path)
    provider = FakeProvider()
    output = tmp_path / "trials"
    result = asyncio.run(run(path, output, provider))
    assert result["status"] == "complete"
    assert provider.calls == 48
    retained = json.loads((output / "trials.json").read_text(encoding="utf-8"))
    assert len(retained["attempts"]) == 48
    assert all(row["usage"]["input_tokens"] == 100 for row in retained["attempts"])
    wrong = [row for row in retained["attempts"] if not row["recipient"]["correct"]]
    assert len(wrong) == 16
    assert all(row["authoritative"]["fixture_consistent"] for row in wrong)
    with pytest.raises(ValueError, match="Output already exists"):
        asyncio.run(run(path, output, provider))
    resumed = asyncio.run(run(path, output, provider, resume=True))
    assert resumed["status"] == "complete" and provider.calls == 48
    assert verify(path, output, provider)["attempts"] == 48


def test_missing_usage_preserves_attempt_and_blocks_automatic_retry(tmp_path):
    path = fixture_plan(tmp_path)
    provider = FakeProvider(usage=False)
    output = tmp_path / "unknown"
    result = asyncio.run(run(path, output, provider))
    assert result["status"] == "stopped_provider_failure" and result["attempts"] == 1
    retained = json.loads((output / "trials.json").read_text(encoding="utf-8"))
    assert retained["attempts"][0]["usage"] is None
    with pytest.raises(ValueError, match="manual reconciliation"):
        asyncio.run(run(path, output, provider, resume=True))
    assert provider.calls == 1


def test_material_change_blocks_resume_before_model_call(tmp_path):
    path = fixture_plan(tmp_path)
    provider = FakeProvider()
    output = tmp_path / "frozen"
    asyncio.run(run(path, output, provider, freeze_only=True))
    registry = tmp_path / "root0" / "state0.toml"
    registry.write_text(registry.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Frozen materials"):
        asyncio.run(run(path, output, provider, resume=True, freeze_only=True))
    assert provider.calls == 0


def test_model_identity_mismatch_retains_charged_response_and_stops(tmp_path):
    path = fixture_plan(tmp_path)
    provider = FakeProvider(response_model="changed-snapshot")
    output = tmp_path / "model_changed"
    result = asyncio.run(run(path, output, provider))
    assert result["status"] == "stopped_provider_failure" and provider.calls == 1
    retained = json.loads((output / "trials.json").read_text(encoding="utf-8"))
    first = retained["attempts"][0]
    assert first["status"] == "failed" and first["response"]["model"] == "changed-snapshot"
    assert first["usage"]["input_tokens"] == 100 and first["usage"]["model_cost_usd"] > 0
    assert result["measured_cost_usd"] == first["usage"]["model_cost_usd"]


def test_budget_stop_occurs_before_first_request(tmp_path):
    path = fixture_plan(tmp_path)
    provider = FakeProvider()
    result = asyncio.run(run(path, tmp_path / "no_spend", provider, max_cost_usd=1e-9))
    assert result["status"] == "stopped_budget" and result["attempts"] == 0
    assert provider.calls == 0


def test_preflight_summary_has_no_workspace_identity_and_is_portable(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    path = fixture_plan(first)
    shutil.copytree(first, second)
    left = preflight_summary(path)
    right = preflight_summary(second / "pilot.json")
    assert left == right
    assert left["model_calls"] == 0 and left["planned_request_count"] == 48
    assert str(tmp_path) not in json.dumps(left)


@pytest.mark.parametrize("tamper", ("message", "expected", "host_packet"))
def test_stored_freeze_tamper_blocks_calls(tmp_path, tamper):
    path = fixture_plan(tmp_path)
    provider = FakeProvider()
    output = tmp_path / "frozen"
    asyncio.run(run(path, output, provider, freeze_only=True))
    freeze_path = output / "freeze.json"
    frozen = json.loads(freeze_path.read_text(encoding="utf-8"))
    first = frozen["cases"][0]
    if tamper == "message":
        first["messages"][1]["content"] += "\nChanged request."
    elif tamper == "expected":
        first["expected"] = "out_of_scope"
    else:
        key = first["root_id"] + "/" + first["state_id"]
        frozen["host_snapshots"][key]["packet"]["claims"][first["claim"]] = "out_of_scope"
    freeze_path.write_text(json.dumps(frozen), encoding="utf-8")
    with pytest.raises(ValueError, match="modified"):
        asyncio.run(run(path, output, provider, resume=True))
    with pytest.raises(ValueError, match="modified"):
        verify(path, output, provider)
    assert provider.calls == 0
