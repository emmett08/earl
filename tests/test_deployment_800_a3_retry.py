"""Offline A3 retry and concurrent terminal-stop regression tests.

The fake providers never use the network or an API credential. The tests run
the actual signed A3 runner against its complete frozen allocation and stop in
the first two local batches.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "benchmarks/experiments/deployment-800"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

import run_a3 as a3  # noqa: E402
from eal.providers import ModelResponse, ProviderError  # noqa: E402


@pytest.fixture(scope="module")
def frozen_dir(tmp_path_factory):
    path = tmp_path_factory.mktemp("a3-offline-frozen")
    frozen = a3.prepare()
    a3.study.write_json(path / "freeze.json", frozen)
    a3.study.write_json(path / "ledger.json", {
        "schema": a3.LEDGER_SCHEMA, "a3_freeze_sha256": frozen["a3_freeze_sha256"],
        "status": "frozen", "attempts": {}, "failures": []})
    return path


def _case_digests(frozen_dir: Path, n: int) -> dict[str, str]:
    cases = json.loads((frozen_dir / "freeze.json").read_text())["base"]["cases"]
    return {a3.study.digest(c["messages"]): c["case_id"] for c in cases[:n]}


def _install_fake(monkeypatch, case_by_digest: dict[str, str], handler):
    actual_load = a3.study._load

    class Fake:
        def __init__(self, real):
            self.real = real

        def identity(self):
            return self.real.identity()

        async def complete(self, messages, max_output_tokens):
            case_id = case_by_digest.get(a3.study.digest(messages))
            return await handler(case_id, self.identity())

        async def complete_request(self, *args, **kwargs):
            raise AssertionError("First two offline batches contain no native request")

    def fake_load():
        plan, manifest, providers = actual_load()
        return plan, manifest, {key: Fake(value) for key, value in providers.items()}

    monkeypatch.setattr(a3.study, "_load", fake_load)


def _reply(identity: dict) -> ModelResponse:
    model = identity["model"]
    if model == "gpt-4.1-nano":
        model = "gpt-4.1-nano-2025-04-14"
    return ModelResponse("{}", 10, 1, model, {"cached_input_tokens": 0})


def _copy_freeze(frozen_dir: Path, tmp_path: Path) -> Path:
    out = tmp_path / "run"
    out.mkdir()
    shutil.copy(frozen_dir / "freeze.json", out / "freeze.json")
    shutil.copy(frozen_dir / "ledger.json", out / "ledger.json")
    return out


def test_peer_terminal_error_prevents_delayed_retry(monkeypatch, frozen_dir, tmp_path):
    out = _copy_freeze(frozen_dir, tmp_path)
    target = _case_digests(frozen_dir, 2)
    first_failed = asyncio.Event()

    async def handler(case_id, identity):
        if case_id == "deployment-0000":
            first_failed.set()
            raise ProviderError("Model endpoint returned HTTP 500")
        if case_id == "deployment-0001":
            await first_failed.wait()
            raise ProviderError("Model endpoint returned HTTP 400")
        raise AssertionError("No subsequent case may be dispatched")

    _install_fake(monkeypatch, target, handler)
    outcome = asyncio.run(a3.run(out, resume=True, freeze_only=False))
    ledger = a3.study.read_json(out / "ledger.json")
    assert outcome["status"] == "stopped_provider_or_author_failure"
    assert outcome["requests"] == 2
    assert set(ledger["failures"]) == {"deployment-0000", "deployment-0001"}
    assert len(ledger["attempts"]["deployment-0000"]["requests"]) == 1
    assert "retry" in ledger["attempts"]["deployment-0000"]["error"]


def test_identical_retry_logged_then_success(monkeypatch, frozen_dir, tmp_path):
    out = _copy_freeze(frozen_dir, tmp_path)
    target = _case_digests(frozen_dir, 4)
    counts: dict[str, int] = {}

    async def handler(case_id, identity):
        counts[case_id] = counts.get(case_id, 0) + 1
        if case_id == "deployment-0000" and counts[case_id] == 1:
            raise ProviderError("Model endpoint returned HTTP 500")
        if case_id == "deployment-0002":
            raise ProviderError("Model endpoint returned HTTP 400")
        return _reply(identity)

    _install_fake(monkeypatch, target, handler)
    outcome = asyncio.run(a3.run(out, resume=True, freeze_only=False))
    ledger = a3.study.read_json(out / "ledger.json")
    first = ledger["attempts"]["deployment-0000"]
    assert outcome["status"] == "stopped_provider_or_author_failure"
    assert first["status"] == "completed" and first["retry_count"] == 1
    assert [request["status"] for request in first["requests"]] == ["failed", "completed"]
    assert first["requests"][0]["prompt_sha256"] == first["requests"][1]["prompt_sha256"]
    assert first["requests"][0]["usage"] is None
    assert first["requests"][1]["usage"]["input_tokens"] == 10
    assert outcome["requests"] >= 4
