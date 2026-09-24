"""End-to-end refusal and durable issuance for a reviewed exact task."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from eal.applicability import NoApplicableTask, TaskApplicabilityRegistry, review_applicability_digest
from eal.host import parse_request
from eal.routing import TaskFamilyHost
from eal.server import create_server
from test_routing import routed


QUESTION = "Does the pilot rig inspection satisfy its reviewed test?"
OTHER = "Does the maintenance question satisfy its reviewed test?"


def reviewed(tmp_path, *, question=QUESTION, principal="caller_a", tasks=("pilot_task",),
             family_grants=("rig", "maintenance")):
    low_level, artifacts = routed(tmp_path)
    families = low_level.families
    entries = []
    for task_id, task_question, family_id in (
        ("pilot_task", QUESTION, "rig"),
        ("maintenance_task", OTHER, "maintenance"),
    ):
        digest = review_applicability_digest(
            families, task_id, task_question, family_id,
            {"site": "pilot"}, "accepted",
        )
        entries.append(f'''[tasks.{task_id}]
question = {json.dumps(task_question)}
family_id = "{family_id}"
bindings = {{ site = "pilot" }}
claim = "accepted"
reviewed_by = "reviewer-7"
reviewed_at = "2040-01-01T11:00:00Z"
review_contract_sha256 = "{digest}"
''')
    manifest = tmp_path / "tasks.toml"
    manifest.write_text('schema = "eal2-task-applicability/1"\n\n' + "\n".join(entries),
                        encoding="utf-8")
    applicability = TaskApplicabilityRegistry.load(families, manifest)
    host = TaskFamilyHost(
        families, principal=principal, authorised_families=set(family_grants),
        authorised_claims={"rig_pilot": {"accepted"}},
        applicability=applicability, task_text=question,
        authorised_tasks=set(tasks),
    )
    return host, artifacts


def test_nomination_cannot_promote_authorised_wrong_family(tmp_path, monkeypatch):
    host, artifacts = reviewed(tmp_path)
    assert [row["family_id"] for row in host.candidates("rig inspection")] == [
        "maintenance", "rig"
    ]
    monkeypatch.setattr(artifacts, "assess_claim", lambda *args: pytest.fail("wrong task collected"))
    with pytest.raises(NoApplicableTask):
        host.assess_task("maintenance_task")
    with pytest.raises(ValueError, match="requires assess_task"):
        host.assess("maintenance", {"site": "pilot"}, "accepted")
    assert not host._issued


def test_exact_task_packet_survives_restart_but_not_principal_or_task_replay(tmp_path):
    host, _ = reviewed(tmp_path)
    packet = host.assess_task("pilot_task")
    assert packet["status"] == "supported"
    restarted, _ = reviewed(tmp_path)
    assert restarted.finish_task("pilot_task", packet["assessment_id"]) == packet
    assert restarted.explain_task("pilot_task", packet["assessment_id"])["packet"] == packet
    other_principal, _ = reviewed(tmp_path, principal="caller_b")
    with pytest.raises(ValueError, match="not issued"):
        other_principal.finish_task("pilot_task", packet["assessment_id"])
    other_task, _ = reviewed(tmp_path, question=OTHER, tasks=("maintenance_task",))
    with pytest.raises(ValueError, match="not issued"):
        other_task.finish_task("maintenance_task", packet["assessment_id"])
    with pytest.raises(ValueError, match="requires finish_task"):
        restarted.finish("rig", {"site": "pilot"}, "accepted", packet["assessment_id"])


def test_unknown_text_or_revoked_task_grant_never_assesses(tmp_path, monkeypatch):
    host, artifacts = reviewed(tmp_path, question="A new task without a review")
    monkeypatch.setattr(artifacts, "assess_claim", lambda *args: pytest.fail("unreviewed collection"))
    with pytest.raises(NoApplicableTask):
        host.assess_task("pilot_task")
    revoked, _ = reviewed(tmp_path, tasks=())
    with pytest.raises(NoApplicableTask):
        revoked.assess_task("pilot_task")


def test_recipient_mcp_binds_task_text_outside_model_arguments(tmp_path):
    host, artifacts = reviewed(tmp_path)
    server = create_server(
        artifacts.service, artifacts, recipient_only=True, principal="caller_a",
        recipient_grants={"rig_pilot": {"accepted"}}, reviewed_task_host=host,
    )

    async def exercise():
        names = {tool.name for tool in (await server.list_tools())}
        assert {"eal_task_candidates", "eal_assess_reviewed_task",
                "eal_finish_reviewed_task", "eal_explain_reviewed_task"} <= names
        assert "eal_assess_artifact_claim" not in names
        with pytest.raises(ToolError):
            await server.call_tool("eal_assess_artifact_claim", {
                "artifact_id": "rig_pilot", "claim": "accepted",
            })
        with pytest.raises(ValueError, match="schema rejected"):
            await server.call_tool("eal_assess_reviewed_task", {
                "task_id": "pilot_task", "question": OTHER,
            })
        with pytest.raises(ToolError):
            await server.call_tool("eal_assess_reviewed_task", {"task_id": "maintenance_task"})
        assessed = await server.call_tool("eal_assess_reviewed_task", {"task_id": "pilot_task"})
        packet = assessed[1]
        finished = await server.call_tool("eal_finish_reviewed_task", {
            "task_id": "pilot_task", "assessment_id": packet["assessment_id"],
        })
        assert finished[1] == packet

    asyncio.run(exercise())


def test_text_model_host_uses_real_recipient_mcp_and_recovers_status(tmp_path):
    reviewed(tmp_path)
    task_file = tmp_path / "trusted-question.txt"
    task_file.write_text(QUESTION, encoding="utf-8")
    base = [sys.executable, "-m", "eal.host", "--workspace", str(tmp_path),
            "--registry", str(tmp_path / "tools.toml"),
            "--artifacts", str(tmp_path / "artifacts.toml"),
            "--families", str(tmp_path / "families.toml"),
            "--tasks", str(tmp_path / "tasks.toml"),
            "--recipient-task-file", str(task_file),
            "--recipient-principal", "caller_a",
            "--recipient-family-grant", "rig", "--recipient-task-grant", "pilot_task",
            "--recipient-grant", "rig_pilot:accepted"]
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    with pytest.raises(ValueError, match="Unknown request fields"):
        parse_request(json.dumps({"operation": "assess_reviewed_task",
                                  "task_id": "pilot_task", "question": OTHER}))
    initial = subprocess.run(
        base, input='{"operation":"assess_reviewed_task","task_id":"pilot_task"}',
        text=True, capture_output=True, timeout=20, check=True, env=env,
    )
    packet = json.loads(initial.stdout)["result"]
    assert packet["status"] == "supported"
    final = subprocess.run(
        base + ["--assessment-id", packet["assessment_id"], "--task-id", "pilot_task"],
        input="The test is unsupported", text=True, capture_output=True,
        timeout=20, check=True, env=env,
    )
    assert json.loads(final.stdout) == {
        "checked_answer": packet, "recipient_output_unverified": "The test is unsupported"
    }
