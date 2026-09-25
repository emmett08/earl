"""CLI and MCP checks for one captured run and a blocked live-source replay."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXAMPLE = Path(__file__).resolve().parent
ROOT = EXAMPLE.parents[1]
RECEIPT_SHA256 = "5af7e43b779e01419821d5996596f1887a027bff871c0e55c7b66aef3c19d0c4"
CONTEXT = {"repository": "emmett08/earl", "decision": "workflow-result"}


def _environment():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env


def _cli(workspace, registry, operation, *args):
    command = [sys.executable, "-m", "eal.cli", "--workspace", str(workspace),
               "--registry", str(registry), operation, *args]
    result = subprocess.run(command, capture_output=True, text=True, env=_environment(), timeout=30, check=True)
    return json.loads(result.stdout)


async def _mcp(workspace, registry, source, *, expected_status, expected_acquisition, now=None):
    settings = StdioServerParameters(
        command=sys.executable,
        args=["-m", "eal.server", "--workspace", str(workspace), "--registry", str(registry)],
        env=_environment(),
    )
    async with stdio_client(settings) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert {"eal_validate", "eal_collect", "eal_reason", "eal_explain"} <= names
            validated = await session.call_tool("eal_validate", {"source": source})
            assert not validated.isError and validated.structuredContent["valid"]
            collected = await session.call_tool("eal_collect", {"source": source, "context": CONTEXT})
            assert not collected.isError
            assert collected.structuredContent["records"]["workflow_result"]["status"] == "ok"
            assert collected.structuredContent["records"]["workflow_result"]["value"]["acquisition"] == expected_acquisition
            reason_args = {
                "source": source, "context": CONTEXT,
                "collection_id": collected.structuredContent["collection_id"],
            }
            if now is not None:
                reason_args["now"] = now
            assessed = await session.call_tool("eal_reason", reason_args)
            assert not assessed.isError
            assert assessed.structuredContent["claims"]["workflow_passed"]["status"] == expected_status
            explained = await session.call_tool("eal_explain", {
                "assessment_id": assessed.structuredContent["assessment_id"], "claim": "workflow_passed",
            })
            assert not explained.isError
            assert explained.structuredContent["result"]["status"] == expected_status
    return {"tools_discovered": True, "collector_status": "ok", "claim_status": expected_status}


def offline():
    receipt = EXAMPLE / "receipt.json"
    if hashlib.sha256(receipt.read_bytes()).hexdigest() != RECEIPT_SHA256:
        raise ValueError("Offline GitHub API projection has changed")
    captured_at = json.loads(receipt.read_text())["provenance"]["projection_recorded_at"]
    with tempfile.TemporaryDirectory(prefix="eal-workflow-example-") as temporary:
        workspace = Path(temporary)
        source = workspace / "source.eal"
        shutil.copyfile(EXAMPLE / "source.eal", source)
        registry = workspace / "tools.toml"
        argv = [sys.executable, str(EXAMPLE / "collect_workflow.py"),
                "--offline-receipt", str(receipt)]
        registry.write_text(
            '[tools.github_workflow]\nkind="command"\n'
            f"argv={json.dumps(argv)}\nversion=\"1\"\nmode=\"nondeterministic\"\n"
            "timeout_seconds=30\nmax_output_bytes=32768\n"
        )
        valid = _cli(workspace, registry, "validate", "source.eal")
        assert valid["valid"]
        collection = _cli(workspace, registry, "collect", "source.eal", "--context", json.dumps(CONTEXT))
        assert collection["records"]["workflow_result"]["status"] == "ok"
        assert collection["records"]["workflow_result"]["value"]["acquisition"] == "offline_receipt"
        assessment = _cli(workspace, registry, "reason", "source.eal", "--context", json.dumps(CONTEXT),
                          "--collection", collection["collection_id"])
        assert assessment["claims"]["workflow_passed"]["status"] == "unsupported"
        explained = _cli(workspace, registry, "explain", assessment["assessment_id"], "--claim", "workflow_passed")
        assert explained["result"]["status"] == "unsupported"
        mcp = asyncio.run(_mcp(workspace, registry, source.read_text(),
                               expected_status="unsupported", expected_acquisition="offline_receipt"))
        historical = workspace / "captured.eal"
        shutil.copyfile(EXAMPLE / "captured.eal", historical)
        captured_registry = workspace / "capture-tools.toml"
        captured_registry.write_text(
            '[tools.github_workflow]\nkind="command"\n'
            f"argv={json.dumps([sys.executable, str(EXAMPLE / 'captured_workflow.py')])}\n"
            'version="1"\nmode="deterministic"\n'
            'timeout_seconds=5\nmax_output_bytes=32768\n'
        )
        assert _cli(workspace, captured_registry, "validate", "captured.eal")["valid"]
        saved = _cli(workspace, captured_registry, "collect", "captured.eal", "--context", json.dumps(CONTEXT))
        assert saved["records"]["workflow_result"]["status"] == "ok"
        assert saved["records"]["workflow_result"]["collected_at"] == captured_at
        assert saved["records"]["workflow_result"]["value"]["acquisition"] == "captured_api"
        checked = _cli(workspace, captured_registry, "reason", "captured.eal",
                       "--context", json.dumps(CONTEXT), "--collection", saved["collection_id"],
                       "--now", captured_at)
        assert checked["claims"]["workflow_passed"]["status"] == "supported"
        retrieved = _cli(workspace, captured_registry, "explain", checked["assessment_id"],
                         "--claim", "workflow_passed")
        assert retrieved["result"]["status"] == "supported"
        captured_mcp = asyncio.run(_mcp(workspace, captured_registry, historical.read_text(),
                                        expected_status="supported", expected_acquisition="captured_api",
                                        now=captured_at))
    return {"receipt_sha256": RECEIPT_SHA256,
            "fixture": "projected_actual_github_api_response; not live evidence",
            "capture_time": captured_at,
            "cli": {"validation": "valid", "collector_status": "ok", "claim_status": "unsupported"},
            "mcp": mcp,
            "historical_capture": {"cli_claim_status": "supported", "mcp": captured_mcp}}


def main():
    parser = argparse.ArgumentParser(description="Exercise the workflow example")
    parser.add_argument("--offline", action="store_true", help="Use the pinned API projection, never network")
    args = parser.parse_args()
    if not args.offline:
        parser.error("Specify --offline; live collection uses the commands in README.md")
    print(json.dumps(offline(), indent=2))


if __name__ == "__main__":
    main()
