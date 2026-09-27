"""Check that the experiment copies code identically and controls packet exposure."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_trial import CONTEXT, GUIDANCE, copy_source, manifest, verify_context  # noqa: E402
from compare_live import compare  # noqa: E402


def test_common_code_start_and_packet_isolation(tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    (a / "fulfilment.py").write_text("value = 1\n")
    start = manifest(a)
    control, treatment = tmp_path / "control", tmp_path / "treatment"
    copy_source(a, control)
    copy_source(a, treatment)
    for folder in (control, treatment):
        (folder / "AGENTS.md").write_text(GUIDANCE)
    (treatment / CONTEXT).write_text('{"schema":"architecture-extension-agent-context/1"}\n')
    assert manifest(control) == manifest(treatment) == start
    verify_context(control, {"packet_sha256": None})
    import hashlib
    digest = hashlib.sha256((treatment / CONTEXT).read_bytes()).hexdigest()
    verify_context(treatment, {"packet_sha256": digest})
    with pytest.raises(ValueError, match="unexpected EAL context packet"):
        verify_context(treatment, {"packet_sha256": None})
    (treatment / CONTEXT).write_text("tampered")
    with pytest.raises(ValueError, match="changed or disappeared"):
        verify_context(treatment, {"packet_sha256": digest})


def test_comparison_rejects_different_b_starts(tmp_path):
    block = {"id": "one", "a_class": "codex_action", "b_class": "codex_action",
             "a_model": "model-a", "b_model": "model-b",
             "a_effort": "high", "b_effort": "high"}
    pair = tmp_path / "pair"
    for arm, digest in (("control", "original"), ("treatment", "different")):
        directory = pair / f"architecture-b-one-{arm}"
        directory.mkdir(parents=True)
        (directory / "preparation.json").write_text(json.dumps({
            "source": {"tree_sha256": digest}, "guidance_sha256": "shared",
            "packet_sha256": "packet" if arm == "treatment" else None,
        }))
    with pytest.raises(ValueError, match="same byte-identified A source"):
        compare(pair, tmp_path / "preflight", tmp_path / "a", block, "0.154.0")


def test_comparison_reads_separate_mcp_artifacts_and_metrics(tmp_path):
    block = {"id": "one", "a_class": "codex_action", "b_class": "claude_code",
             "a_model": "model-a", "b_model": "model-b",
             "a_effort": "high", "b_effort": "high"}
    start = {"schema": "architecture-extension-source/1",
             "files": {"fulfilment.py": "filehash"}, "tree_sha256": "a-hash"}
    a = tmp_path / "a"
    a.mkdir()
    for filename, value in (("manifest.json", start), ("assessment.json", {"stage": "a"}),
                            ("cognitive-complexity.json", {"schema": "python-cognitive-complexity/1"})):
        (a / filename).write_text(json.dumps(value))
    pair, preflight = tmp_path / "pair", tmp_path / "preflight"
    for arm in ("control", "treatment"):
        directory = pair / f"architecture-b-one-{arm}"
        directory.mkdir(parents=True)
        packet = "packet-hash" if arm == "treatment" else None
        for filename, value in (
            ("preparation.json", {"source": start, "guidance_sha256": "shared",
                                  "packet_sha256": packet}),
            ("manifest.json", {"tree_sha256": arm}),
            ("assessment.json", {"arm": arm}),
            ("cognitive-complexity.json", {"schema": "python-cognitive-complexity/1",
                                           "total": 1 if arm == "control" else 2}),
        ):
            (directory / filename).write_text(json.dumps(value))
        (directory / "agent-execution.json").write_text(json.dumps([
            {"type": "system", "subtype": "init", "model": "claude-sonnet-5"},
            {"type": "result", "subtype": "success", "is_error": False, "num_turns": 9},
        ]))
        host = preflight / f"architecture-b-preflight-one-{arm}"
        host.mkdir(parents=True)
        (host / "pre-b-mcp.json").write_text(json.dumps({
            "status": "ok", "source_sha256": "argument-hash", "context": {"stage": "pre-A"},
            "packet_sha256": "packet-hash",
        }))
    result = compare(pair, preflight, a, block, "0.154.0")
    assert result["b_start_sha256"] == "a-hash"
    assert result["cognitive_complexity"]["treatment"]["total"] == 2
    assert result["exposure"]["control"]["eal_context_delivered"] is False
    assert result["exposure"]["treatment"]["eal_context_delivered"] is True
    assert result["agent_runners"]["a"].startswith("openai/codex-action@")
    assert result["agent_runners"]["b"].startswith("anthropics/claude-code-action/base-action@")
    assert result["claude_execution_observed"]["b"]["control"]["initial_model"] == "claude-sonnet-5"

    (pair / "architecture-b-one-control" / "agent-execution.json").unlink()
    with pytest.raises(FileNotFoundError):
        compare(pair, preflight, a, block, "0.154.0")

    with pytest.raises(ValueError, match="Unrecognised executable agent class"):
        compare(pair, preflight, a, {**block, "b_class": "unavailable"}, "0.154.0")
