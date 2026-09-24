"""Independent checks that the recipient MCP surface enforces task applicability."""

from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from eal.server import create_server
from test_reviewed_task_route import OTHER, QUESTION, reviewed


def test_reviewed_server_cannot_bypass_task_gate_with_direct_artifact_tools(tmp_path):
    host, artifacts = reviewed(tmp_path)
    server = create_server(
        artifacts.service, artifacts, recipient_only=True, principal="caller_a",
        recipient_grants={"rig_pilot": {"accepted"}}, reviewed_task_host=host,
    )

    async def probe():
        names = {tool.name for tool in await server.list_tools()}
        assert names == {
            "eal_task_candidates", "eal_bound_task", "eal_assess_bound_task",
            "eal_explain_bound_task", "eal_finish_bound_task",
        }
        for operation, arguments in (
            ("eal_assess_artifact_claim", {"artifact_id": "rig_pilot", "claim": "accepted"}),
            ("eal_explain_artifact_claim", {"artifact_id": "rig_pilot", "claim": "accepted",
                                            "assessment_id": "forged"}),
            ("eal_finish_artifact_claim", {"artifact_id": "rig_pilot", "claim": "accepted",
                                           "assessment_id": "forged"}),
        ):
            with pytest.raises(ToolError, match="Unknown tool"):
                await server.call_tool(operation, arguments)

    asyncio.run(probe())
    assert artifacts.service.store.list(kind="assessment") == []


def test_reviewed_server_rejects_model_supplied_task_substitutions(tmp_path):
    host, artifacts = reviewed(tmp_path)
    server = create_server(
        artifacts.service, artifacts, recipient_only=True, principal="caller_a",
        recipient_grants={"rig_pilot": {"accepted"}}, reviewed_task_host=host,
    )

    async def probe():
        for extra in (
            {"task_id": "maintenance_task"},
            {"question": OTHER},
            {"family_id": "maintenance"},
            {"bindings": {"site": "field"}},
            {"context": {"site": "field"}},
        ):
            with pytest.raises(ValueError, match="Additional properties are not allowed"):
                await server.call_tool("eal_assess_bound_task", extra)

    asyncio.run(probe())
    assert artifacts.service.store.list(kind="assessment") == []


def test_candidate_suggestion_cannot_assess_unmatched_bound_question(tmp_path):
    host, artifacts = reviewed(tmp_path, question=QUESTION + " ")
    server = create_server(
        artifacts.service, artifacts, recipient_only=True, principal="caller_a",
        recipient_grants={"rig_pilot": {"accepted"}}, reviewed_task_host=host,
    )

    async def probe():
        suggested = await server.call_tool("eal_task_candidates", {})
        assert suggested[1]["meaning"] == "suggestions_only"
        assert suggested[1]["candidates"]
        with pytest.raises(ToolError):
            await server.call_tool("eal_bound_task", {})
        with pytest.raises(ToolError):
            await server.call_tool("eal_assess_bound_task", {})

    asyncio.run(probe())
    assert artifacts.service.store.list(kind="assessment") == []
