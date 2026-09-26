"""The opt-in ASPIC+ compiler consumes the same collected EAL snapshot at each entry point."""

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from eal.runtime import ReasoningService


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/api-load-test"
SOURCE = (EXAMPLE / "aspic-compiled.eal").read_text(encoding="utf-8")
REGISTRY = EXAMPLE / "aspic-tools.toml"
CONTEXT = {"service": "orders-api", "build_id": "demo-build-42", "dataset": "synthetic"}
NOW = "2026-09-25T10:30:00Z"


def assert_compiled_result(compiled, authored):
    assert compiled["profile"] == "EAL/2-compiled-aspic/2"
    assert compiled["claim"] == "run_passes"
    assert compiled["source_digest"] == authored["source_digest"]
    assert compiled["authored_claim_status"] == authored["claims"]["run_passes"]["status"]
    assert compiled["claim_status"] == authored["claims"]["run_passes"]["status"] == "supported"
    assert compiled["formal"]["grounded_status"] == "accepted"
    assert compiled["routes"]["primary_run"]["status"] == "rejected"
    assert compiled["routes"]["independent_probe"]["status"] == "accepted"
    mapping = compiled["source_map"]
    assert mapping["arguments"]["primary_run"]["rule_id"] in {
        a["rule_id"] for a in compiled["formal"]["arguments"] if "rule_id" in a}
    assert mapping["evidence"]["probe_record"]["identity"]["run_id"]
    assert mapping["contraries"][0]["target_name"] == "primary_run"
    assert mapping["arguments"]["report_arg"]["rule_kind"] == "strict"
    assert mapping["arguments"]["report_arg"]["strict_annotation"]["review"].startswith("synthetic-review/")
    assert mapping["arguments"]["independent_probe"]["rank"] == 700
    assert mapping["evidence"]["probe_record"]["rank"] == 700


def test_service_compilation_is_opt_in_and_collection_bound(tmp_path):
    service = ReasoningService(ROOT, REGISTRY, database_path=tmp_path / "runs.sqlite3")
    assert service.validate(SOURCE)["valid"]
    collection = service.collect(SOURCE, CONTEXT)
    assert {row["status"] for row in collection["records"].values()} == {"ok"}
    authored = service.reason(SOURCE, CONTEXT, collection["collection_id"], NOW)
    assert "formal" not in authored
    assert authored["arguments"]["primary_run"]["status"] == "contested"
    assert authored["arguments"]["independent_probe"]["status"] == "supported"
    compiled = service.compile_aspic(
        SOURCE, CONTEXT, collection["collection_id"], "run_passes", NOW)
    assert compiled["collection_id"] == collection["collection_id"]
    assert_compiled_result(compiled, authored)
    # The opt-in operation does not change subsequent ordinary assessments.
    later = service.reason(SOURCE, CONTEXT, collection["collection_id"], NOW)
    assert later["claims"] == authored["claims"]
    assert later["arguments"] == authored["arguments"]

    with pytest.raises(ValueError, match="source or context"):
        service.compile_aspic(SOURCE + "\n", CONTEXT, collection["collection_id"],
                              "run_passes", NOW)
    with pytest.raises(ValueError, match="source or context"):
        service.compile_aspic(SOURCE, {**CONTEXT, "dataset": "measured"},
                              collection["collection_id"], "run_passes", NOW)


def test_cli_collect_reason_and_opt_in_compile_share_stored_snapshot(tmp_path):
    base = [sys.executable, "-m", "eal.cli", "--workspace", str(ROOT),
            "--registry", str(REGISTRY), "--database", str(tmp_path / "runs.sqlite3")]
    source_path = "examples/api-load-test/aspic-compiled.eal"

    def call(operation, *args, expected=0):
        run = subprocess.run(base + [operation, source_path, "--context", json.dumps(CONTEXT),
                                     *args], capture_output=True, text=True, timeout=30)
        assert run.returncode == expected, (run.stdout, run.stderr)
        return json.loads(run.stdout)

    collection = call("collect")
    authored = call("reason", "--collection", collection["collection_id"], "--now", NOW)
    compiled = call("compile-aspic", "--collection", collection["collection_id"],
                    "--goal", "run_passes", "--now", NOW)
    assert_compiled_result(compiled, authored)
    assert "formal" not in authored


def test_mcp_exposes_opt_in_compilation_and_rejects_other_collection_source_or_context(tmp_path):
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "eal.server", "--workspace", str(ROOT),
              "--registry", str(REGISTRY), "--database", str(tmp_path / "runs.sqlite3")],
        env=dict(os.environ),
    )

    async def exercise():
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                names = {tool.name for tool in (await session.list_tools()).tools}
                assert "eal_compile_aspic" in names
                collected = await session.call_tool("eal_collect", {
                    "source": SOURCE, "context": CONTEXT})
                assert not collected.isError
                collection_id = collected.structuredContent["collection_id"]
                common = {"source": SOURCE, "context": CONTEXT,
                          "collection_id": collection_id, "now": NOW}
                reasoned = await session.call_tool("eal_reason", common)
                assert not reasoned.isError
                compiled = await session.call_tool("eal_compile_aspic", {
                    **common, "goal": "run_passes"})
                assert not compiled.isError, compiled
                assert_compiled_result(compiled.structuredContent, reasoned.structuredContent)
                wrong_source = await session.call_tool("eal_compile_aspic", {
                    **common, "source": SOURCE + "\n", "goal": "run_passes"})
                assert wrong_source.isError
                wrong_context = await session.call_tool("eal_compile_aspic", {
                    **common, "context": {**CONTEXT, "dataset": "measured"},
                    "goal": "run_passes"})
                assert wrong_context.isError

    asyncio.run(exercise())
