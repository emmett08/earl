"""Focused checks of the separate developmental 800-assignment schedule."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from eal.providers import ChatCompletionsProvider


PATH = Path(__file__).resolve().parents[1] / "benchmarks/experiments/deployment-800/run.py"
SPEC = importlib.util.spec_from_file_location("deployment800", PATH)
assert SPEC and SPEC.loader
STUDY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STUDY)


def test_balanced_incomplete_stage_and_independent_route() -> None:
    frozen = STUDY.prepare(allow_pending_review=True)
    cases = frozen["cases"]
    assert len(cases) == 800
    assert [sum(c["stage"] == stage for c in cases)
            for stage in ("fixed", "author", "recipient")] == [384, 96, 320]
    for fmt in STUDY.FORMATS:
        for instructed in (False, True):
            assert sum(c["format"] == fmt and c["instruction"] == instructed
                       for c in cases if c["stage"] == "fixed") == 96
    assert sum(c["delivery"] == "native_request" for c in cases if c["stage"] == "fixed") == 96
    manifest = STUDY.read_json(STUDY.HERE / "manifest.json")
    for root in manifest["roots"]:
        for state in root["states"]:
            eal, _, _ = STUDY._host_assessment(root, state, STUDY.HERE)
            graph = STUDY._graph_assessment(root, state)
            assert eal["status"] == graph["status"] == state["expected"]
    assert [root["states"][1]["expected"] for root in manifest["roots"]].count("supported") == 4
    assert frozen["parity"]["tamper_pass"] == 120


def test_three_author_turns_link_only_their_own_transcript() -> None:
    frozen = STUDY.prepare(allow_pending_review=True)
    cases = frozen["cases"]
    group = next(c["author_group"] for c in cases if c["stage"] == "author")
    author = sorted((c for c in cases if c.get("author_group") == group and c["stage"] == "author"),
                    key=lambda c: c["turn"])
    ledger = {"attempts": {author[0]["case_id"]: {"status": "completed", "response": {"text": "FIRST"}},
                           author[1]["case_id"]: {"status": "completed", "response": {"text": "SECOND"}}}}
    messages = STUDY._author_messages(author[2], ledger, cases)
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user", "assistant", "user"]
    assert [m["content"] for m in messages if m["role"] == "assistant"] == ["FIRST", "SECOND"]
    assert "alert" in messages[3]["content"].lower()
    assert "resolution" in messages[5]["content"].lower()
    with pytest.raises(ValueError, match="prior response"):
        STUDY._author_messages(author[2], {"attempts": {}}, cases)


def test_no_paid_freeze_without_actual_review_record() -> None:
    plan, manifest, _ = STUDY._load()
    altered = {**plan, "review_attestation": "unwritten-independent-review.json"}
    with pytest.raises(ValueError, match="review record is required"):
        STUDY._review(altered, manifest, allow_pending=False)


def test_actual_native_function_payload_and_one_call() -> None:
    root = STUDY.read_json(STUDY.HERE / "manifest.json")["roots"][0]
    operation = STUDY._native_operation(root, "eal")
    seen = []

    def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen.append(payload)
        return httpx.Response(200, json={"model": "gpt-6-luna", "usage": {
            "prompt_tokens": 139, "completion_tokens": 22}, "choices": [{
            "finish_reason": "tool_calls", "message": {"content": None, "tool_calls": [{
                "id": "call_1", "type": "function", "function": {"name": "eal_assess_artifact",
                    "arguments": json.dumps({"artifact_id": root["id"], "claim": root["claim"],
                                             **root["context"]})}}]}}]})

    provider = ChatCompletionsProvider(model="gpt-6-luna", api_key_env=None,
                                       capabilities={"native_tools": True, "reasoning_effort": "none"},
                                       transport=httpx.MockTransport(respond))
    result = asyncio.run(provider.complete_request(
        [{"role": "user", "content": root["brief"]}], 384,
        operations=operation, native_tools=True))
    assert len(seen) == 1
    assert seen[0]["tool_choice"] == "required" and seen[0]["parallel_tool_calls"] is False
    assert seen[0]["tools"][0]["function"]["name"] == "eal_assess_artifact"
    assert json.loads(result.text) == {"operation": "eal_assess_artifact",
                                       "artifact_id": root["id"], "claim": root["claim"], **root["context"]}
    assert result.input_tokens == 139 and result.output_tokens == 22
    assert result.metadata["native_tool_call"]["id"] == "call_1"
