"""Offline continuation checks: failed outcomes and their original bytes are evidence."""
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import continue_notation_transfer as continuation
import notation_transfer_experiment as study
from eal.providers import ChatCompletionsProvider, ModelResponse, ProviderError, response_cost


@pytest.fixture(scope="module")
def full_freeze():
    return study.freeze(ROOT / "benchmarks/experiments/eal2-notation-transfer-diagnostic.json")


@pytest.fixture
def frozen(full_freeze):
    result = copy.deepcopy(full_freeze)
    result["schedule"] = result["schedule"][:3]
    rehash(result)
    return result


@pytest.fixture(autouse=True)
def prohibit_live_requests(monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("Continuation tests must never make a live model request")

    monkeypatch.setattr(ChatCompletionsProvider, "complete", forbidden)
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-placeholder-never-sent")


def rehash(frozen):
    frozen.pop("freeze_digest", None)
    frozen["freeze_digest"] = study.digest(frozen)


def response(frozen, *, finish="stop", model=None, known_usage=True):
    return ModelResponse(
        "truncated" if finish == "length" else '{"claims": {}, "basis": []}',
        100 if known_usage else None,
        frozen["plan"]["max_output_tokens"] if finish == "length" else 20,
        frozen["provider_identity"]["model"] if model is None else model,
        {"finish_reason": finish, "cached_input_tokens": 0,
         "response_choices": [{"finish_reason": finish,
                               "message": {"role": "assistant", "content": "truncated"}}]},
    )


class OfflineProvider:
    def __init__(self, frozen, outcomes=(), before_request=None):
        self.frozen = frozen
        self.outcomes = list(outcomes)
        self.calls = []
        self.before_request = before_request

    def identity(self):
        return copy.deepcopy(self.frozen["provider_identity"])

    async def complete(self, messages, max_output_tokens):
        if self.before_request:
            self.before_request()
        self.calls.append((copy.deepcopy(messages), max_output_tokens))
        if self.outcomes:
            result = self.outcomes.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
        packet = json.loads(messages[1]["content"])
        body = {"claims": {name: "supported" for name in packet["requested_claims"]}, "basis": []}
        return ModelResponse(json.dumps(body), 100, 20, self.frozen["provider_identity"]["model"],
                             {"finish_reason": "stop", "cached_input_tokens": 0})


def install_provider(monkeypatch, provider):
    monkeypatch.setattr(study, "provider_from_config", lambda config: provider)
    # Support either direct imports or calls through the original runner module.
    if hasattr(continuation, "provider_from_config"):
        monkeypatch.setattr(continuation, "provider_from_config", lambda config: provider)


def trial_path(output, row):
    return output / "trials" / (row["trial_id"] + ".json")


def initial_failure(frozen, output, monkeypatch, failure=None):
    failure = failure or ProviderError("offline truncated outcome", response=response(frozen, finish="length"))
    provider = OfflineProvider(frozen, [failure])
    install_provider(monkeypatch, provider)
    result = asyncio.run(study.execute(frozen, output))
    assert result["attempted"] == 1
    assert result["status"] == "provider_failure_or_unknown_usage"
    assert len(provider.calls) == 1
    return trial_path(output, frozen["schedule"][0])


def approvals(path):
    return {path.stem: hashlib.sha256(path.read_bytes()).hexdigest()}


def test_prepare_and_resume_preserve_failed_outcome_and_never_recharge(frozen, tmp_path, monkeypatch):
    first = initial_failure(frozen, tmp_path, monkeypatch)
    original_trial = first.read_bytes()
    original_freeze = (tmp_path / "freeze.json").read_bytes()
    assert json.loads(original_trial)["score"]["correct"] is False
    metadata = continuation.prepare(tmp_path, approvals(first))
    sidecar = tmp_path / "continuation.json"
    assert metadata == json.loads(sidecar.read_text())
    original_sidecar = sidecar.read_bytes()

    def inspect_before_call():
        assert sidecar.read_bytes() == original_sidecar
        assert first.read_bytes() == original_trial
        assert (tmp_path / "freeze.json").read_bytes() == original_freeze
        if provider.calls:
            assert json.loads((tmp_path / "continuation-status.json").read_text())["status"] == "running"
            assert json.loads((tmp_path / "execution-status.json").read_text())["status"] == "running"

    provider = OfflineProvider(frozen, before_request=inspect_before_call)
    install_provider(monkeypatch, provider)
    result = asyncio.run(continuation.execute(tmp_path))
    assert result["status"] == "completed"
    assert result["attempted"] == 3
    assert len(provider.calls) == 2
    expected_messages = [study.messages_for(frozen["tasks"][row["task_id"]], row["condition"],
                                           row["repetition"], frozen["common_reference"])
                         for row in frozen["schedule"][1:]]
    assert [call[0] for call in provider.calls] == expected_messages
    assert all(call[1] == frozen["plan"]["max_output_tokens"] for call in provider.calls)
    assert first.read_bytes() == original_trial
    assert json.loads(first.read_text())["state"] == "provider_error"
    assert (tmp_path / "freeze.json").read_bytes() == original_freeze
    assert sidecar.read_bytes() == original_sidecar
    assert (tmp_path / "continuation-status.json").exists()
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "execution-status.json").exists()

    saved_trials = {p.name: p.read_bytes() for p in (tmp_path / "trials").glob("*.json")}
    resumed = asyncio.run(continuation.execute(tmp_path))
    assert resumed["status"] == "completed"
    assert resumed["attempted"] == 3
    assert len(provider.calls) == 2
    assert {p.name: p.read_bytes() for p in (tmp_path / "trials").glob("*.json")} == saved_trials
    assert sidecar.read_bytes() == original_sidecar
    expected_cost = sum(json.loads(raw)["cost_usd"] for raw in saved_trials.values())
    assert sum(group["known_cost_usd"] for group in resumed["conditions"].values()) == pytest.approx(expected_cost)


@pytest.mark.parametrize("approval_kind", ["absent", "wrong_digest", "wrong_trial"])
def test_prior_failure_requires_exact_explicit_approval(frozen, tmp_path, monkeypatch, approval_kind):
    first = initial_failure(frozen, tmp_path, monkeypatch)
    approved = approvals(first)
    if approval_kind == "absent":
        approved = {}
    elif approval_kind == "wrong_digest":
        approved[first.stem] = "0" * 64
    else:
        approved = {"trial-99999": next(iter(approved.values()))}
    with pytest.raises(ValueError):
        continuation.prepare(tmp_path, approved)
    assert not (tmp_path / "continuation.json").exists()


@pytest.mark.parametrize("corruption", [
    "nonlength", "unknown_input", "unknown_output", "missing_cache", "negative_cache",
    "excess_cache", "boolean_cache", "wrong_model", "wrong_cost", "missing_cost", "wrong_model_match",
])
def test_approval_cannot_override_invalid_failure_evidence(frozen, tmp_path, monkeypatch, corruption):
    first = initial_failure(frozen, tmp_path, monkeypatch)
    record = json.loads(first.read_text())
    if corruption == "nonlength":
        record["response"]["metadata"]["finish_reason"] = "content_filter"
        record["response"]["metadata"]["response_choices"][0]["finish_reason"] = "content_filter"
    elif corruption == "unknown_input":
        record["response"]["input_tokens"] = None
    elif corruption == "unknown_output":
        record["response"]["output_tokens"] = None
    elif corruption == "missing_cache":
        record["response"]["metadata"].pop("cached_input_tokens")
    elif corruption == "negative_cache":
        record["response"]["metadata"]["cached_input_tokens"] = -1
    elif corruption == "excess_cache":
        record["response"]["metadata"]["cached_input_tokens"] = record["response"]["input_tokens"] + 1
    elif corruption == "boolean_cache":
        record["response"]["metadata"]["cached_input_tokens"] = False
    elif corruption == "wrong_model":
        record["response"]["model"] = "unfrozen-model"
    elif corruption == "wrong_cost":
        record["cost_usd"] += 0.01
    elif corruption == "missing_cost":
        record["cost_usd"] = None
    elif corruption == "wrong_model_match":
        record["response_model_matches"] = False
    study.write(first, record)
    # Approval matches these bytes, but does not establish eligible evidence.
    with pytest.raises(ValueError):
        continuation.prepare(tmp_path, approvals(first))
    assert not (tmp_path / "continuation.json").exists()


@pytest.mark.parametrize("corruption", ["digest", "original_script", "runtime"])
def test_freeze_audit_rejects_drift_before_requests(frozen, tmp_path, monkeypatch, corruption):
    first = initial_failure(frozen, tmp_path, monkeypatch)
    changed = copy.deepcopy(frozen)
    if corruption == "digest":
        changed["freeze_digest"] = "0" * 64
    elif corruption == "original_script":
        changed["script_sha256"] = "0" * 64
        rehash(changed)
    else:
        changed["runtime"]["source_digest"] = "0" * 64
        rehash(changed)
    study.write(tmp_path / "freeze.json", changed)
    provider = OfflineProvider(frozen)
    install_provider(monkeypatch, provider)
    with pytest.raises(ValueError):
        asyncio.run(continuation.execute(tmp_path, approvals(first)))
    assert provider.calls == []


def test_missing_freeze_does_not_create_a_new_campaign(tmp_path):
    with pytest.raises(ValueError):
        continuation.prepare(tmp_path, {})
    assert not (tmp_path / "freeze.json").exists()


def test_prepare_rejects_gap_in_existing_records(frozen, tmp_path, monkeypatch):
    first = initial_failure(frozen, tmp_path, monkeypatch)
    first.rename(trial_path(tmp_path, frozen["schedule"][1]))
    with pytest.raises(ValueError):
        continuation.prepare(tmp_path, {})


def test_uncertain_attempt_is_never_retried(frozen, tmp_path, monkeypatch):
    first = initial_failure(frozen, tmp_path, monkeypatch)
    row = frozen["schedule"][1]
    target = trial_path(tmp_path, row)
    study.write(target, {**row, "freeze_digest": frozen["freeze_digest"], "state": "attempt_started"})
    original_marker = target.read_bytes()
    provider = OfflineProvider(frozen)
    install_provider(monkeypatch, provider)
    with pytest.raises(ValueError):
        asyncio.run(continuation.execute(tmp_path, approvals(first)))
    assert provider.calls == []
    assert target.read_bytes() == original_marker


def test_later_uncertain_attempt_stops_an_existing_continuation(frozen, tmp_path, monkeypatch):
    first = initial_failure(frozen, tmp_path, monkeypatch)
    continuation.prepare(tmp_path, approvals(first))
    row = frozen["schedule"][1]
    target = trial_path(tmp_path, row)
    study.write(target, {**row, "freeze_digest": frozen["freeze_digest"], "state": "attempt_started"})
    original_marker = target.read_bytes()
    provider = OfflineProvider(frozen)
    install_provider(monkeypatch, provider)
    result = asyncio.run(continuation.execute(tmp_path))
    assert result["status"] == "unresolved_attempt_not_retried"
    assert result["attempted"] == 1
    assert result["uncertain_attempts"] == 1
    assert provider.calls == []
    assert target.read_bytes() == original_marker


def test_new_known_length_failure_advances_and_stays_failed(frozen, tmp_path, monkeypatch):
    first = initial_failure(frozen, tmp_path, monkeypatch)
    original_trial = first.read_bytes()
    error = ProviderError("offline length failure", response=response(frozen, finish="length"))
    def sidecar_exists_before_request():
        assert (tmp_path / "continuation.json").exists()

    provider = OfflineProvider(frozen, [error], before_request=sidecar_exists_before_request)
    install_provider(monkeypatch, provider)
    result = asyncio.run(continuation.execute(tmp_path, approvals(first)))
    assert result["status"] == "completed"
    assert result["attempted"] == 3
    assert len(provider.calls) == 2
    second = json.loads(trial_path(tmp_path, frozen["schedule"][1]).read_text())
    assert second["state"] == "provider_error"
    assert second["score"]["correct"] is False
    assert second["cost_usd"] == response_cost(error.response, frozen["provider_identity"])
    assert first.read_bytes() == original_trial


@pytest.mark.parametrize("problem", ["unknown_usage", "model_mismatch", "nonlength_error",
                                    "unknown_length_usage", "length_model_mismatch"])
def test_new_unsafe_outcome_stops_before_next_request(frozen, tmp_path, monkeypatch, problem):
    first = initial_failure(frozen, tmp_path, monkeypatch)
    if problem == "unknown_usage":
        outcome = response(frozen, known_usage=False)
    elif problem == "model_mismatch":
        outcome = response(frozen, model="unfrozen-model")
    elif problem == "unknown_length_usage":
        outcome = ProviderError("offline length", response=response(frozen, finish="length", known_usage=False))
    elif problem == "length_model_mismatch":
        outcome = ProviderError("offline length", response=response(frozen, finish="length", model="unfrozen-model"))
    else:
        outcome = ProviderError("offline refusal", response=response(frozen, finish="content_filter"))
    provider = OfflineProvider(frozen, [outcome])
    install_provider(monkeypatch, provider)
    result = asyncio.run(continuation.execute(tmp_path, approvals(first)))
    assert result["status"] != "completed"
    assert result["attempted"] == 2
    assert len(provider.calls) == 1
    assert trial_path(tmp_path, frozen["schedule"][1]).exists()
    assert not trial_path(tmp_path, frozen["schedule"][2]).exists()
    # A saved unsafe outcome must also prevent subsequent requests.
    try:
        resumed = asyncio.run(continuation.execute(tmp_path))
    except ValueError:
        pass
    else:
        assert resumed["status"] != "completed"
    assert len(provider.calls) == 1


def test_prior_cost_counts_against_original_frozen_cap(frozen, tmp_path, monkeypatch):
    row = frozen["schedule"][1]
    messages = study.messages_for(frozen["tasks"][row["task_id"]], row["condition"],
                                  row["repetition"], frozen["common_reference"])
    rates = frozen["provider_identity"]["pricing"]
    allowance = ((len(json.dumps(messages, ensure_ascii=False).encode()) + 2048)
                 * rates["input_usd_per_million"]
                 + frozen["plan"]["max_output_tokens"] * rates["output_usd_per_million"]) / 1_000_000
    measured = response(frozen, finish="length")
    prior_cost = response_cost(measured, frozen["provider_identity"])
    frozen["plan"]["max_campaign_model_cost_usd"] = allowance + prior_cost / 2
    rehash(frozen)
    first = initial_failure(frozen, tmp_path, monkeypatch, ProviderError("offline length", response=measured))
    original_freeze = (tmp_path / "freeze.json").read_bytes()
    provider = OfflineProvider(frozen)
    install_provider(monkeypatch, provider)
    result = asyncio.run(continuation.execute(tmp_path, approvals(first)))
    assert result["status"] == "cost_threshold"
    assert result["attempted"] == 1
    assert provider.calls == []
    assert (tmp_path / "freeze.json").read_bytes() == original_freeze
    assert json.loads(first.read_text())["cost_usd"] == prior_cost


def test_changed_approved_record_is_rejected_on_resume(frozen, tmp_path, monkeypatch):
    first = initial_failure(frozen, tmp_path, monkeypatch)
    continuation.prepare(tmp_path, approvals(first))
    original_sidecar = (tmp_path / "continuation.json").read_bytes()
    # A semantically equivalent reserialization still changes approved evidence bytes.
    first.write_text(json.dumps(json.loads(first.read_text()), separators=(",", ":")) + "\n")
    provider = OfflineProvider(frozen)
    install_provider(monkeypatch, provider)
    with pytest.raises(ValueError):
        asyncio.run(continuation.execute(tmp_path))
    assert provider.calls == []
    assert (tmp_path / "continuation.json").read_bytes() == original_sidecar


def test_cli_defaults_to_reviewable_sidecar_without_model_calls(frozen, tmp_path, monkeypatch, capsys):
    first = initial_failure(frozen, tmp_path, monkeypatch)
    approved = approvals(first)
    original_trial = first.read_bytes()
    original_freeze = (tmp_path / "freeze.json").read_bytes()
    provider = OfflineProvider(frozen)
    install_provider(monkeypatch, provider)
    monkeypatch.setattr(sys, "argv", ["continue_notation_transfer.py", "--output", str(tmp_path),
                                     "--approve-failure", f"{first.stem}:{approved[first.stem]}"])
    continuation.main()
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "continuation_prepared_no_model_calls"
    assert (tmp_path / "continuation.json").exists()
    assert provider.calls == []
    assert first.read_bytes() == original_trial
    assert (tmp_path / "freeze.json").read_bytes() == original_freeze
    assert not trial_path(tmp_path, frozen["schedule"][1]).exists()
