"""Run the load-test argument through the CLI and the actual MCP stdio server."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXAMPLE = Path(__file__).resolve().parent
ROOT = EXAMPLE.parents[1]
CONTEXT = {"service": "orders-api", "build_id": "demo-build-42", "dataset": "synthetic"}
ASSESS_AT = "2026-09-25T10:00:00Z"
CLAIM = "performance_criteria_met"
FAILED_CLAIM = "performance_criteria_failed"
METHOD_FACTORY = "eal.api_load_methods:registry"


def environment() -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    return env


def cli(database: Path, operation: str, *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "eal.cli", "--workspace", str(ROOT),
         "--registry", str(EXAMPLE / "tools.toml"), "--database", str(database),
         "--methods", METHOD_FACTORY, operation, *args],
        capture_output=True, text=True, env=environment(), timeout=30, check=True,
    )
    return json.loads(result.stdout)


async def mcp(database: Path) -> dict[str, str]:
    settings = StdioServerParameters(
        command=sys.executable,
        args=["-m", "eal.server", "--workspace", str(ROOT),
              "--registry", str(EXAMPLE / "tools.toml"), "--database", str(database),
              "--methods", METHOD_FACTORY],
        env=environment(),
    )
    source = (EXAMPLE / "source.eal").read_text()
    async with stdio_client(settings) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()

            async def call(name, arguments):
                result = await session.call_tool(name, arguments)
                if result.is_error:
                    raise RuntimeError(f"{name} failed: {result.content}")
                return result.structured_content

            validated = await call("eal_validate", {"source": source})
            assert validated["valid"], validated
            collected = await call("eal_collect", {"source": source, "context": CONTEXT})
            assert collected["records"]["load_test"]["status"] == "ok", collected
            assessed = await call("eal_reason", {
                "source": source, "context": CONTEXT, "collection_id": collected["collection_id"],
                "now": ASSESS_AT,
            })
            assert assessed["claims"][CLAIM]["status"] == "supported", assessed
            assert assessed["claims"][FAILED_CLAIM]["status"] == "unsupported", assessed
            statuses = {}
            for claim in (CLAIM, FAILED_CLAIM):
                explained = await call("eal_explain", {"assessment_id": assessed["assessment_id"], "claim": claim})
                assert explained["result"]["status"] == assessed["claims"][claim]["status"], explained
                statuses[claim] = explained["result"]["status"]
            return statuses


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="eal-load-test-") as temporary:
        database = Path(temporary) / "runs.sqlite3"
        source = "examples/api-load-test/source.eal"
        validated = cli(database, "validate", source)
        assert validated["valid"], validated
        collected = cli(database, "collect", source, "--context", json.dumps(CONTEXT))
        assert collected["records"]["load_test"]["status"] == "ok", collected
        assessed = cli(database, "reason", source, "--context", json.dumps(CONTEXT),
                       "--collection", collected["collection_id"], "--now", ASSESS_AT)
        assert assessed["claims"][CLAIM]["status"] == "supported", assessed
        assert assessed["claims"][FAILED_CLAIM]["status"] == "unsupported", assessed
        explanations = {claim: cli(database, "explain", assessed["assessment_id"], "--claim", claim)
                        for claim in (CLAIM, FAILED_CLAIM)}
        for claim, explanation in explanations.items():
            assert explanation["result"]["status"] == assessed["claims"][claim]["status"]
        mcp_statuses = asyncio.run(mcp(database))
        print(json.dumps({
            "dataset": "synthetic", "assessed_at": ASSESS_AT,
            "metrics": collected["records"]["load_test"]["value"],
            "cli_claim_status": explanations[CLAIM]["result"]["status"],
            "mcp_claim_status": mcp_statuses[CLAIM],
            "cli_failed_claim_status": explanations[FAILED_CLAIM]["result"]["status"],
            "mcp_failed_claim_status": mcp_statuses[FAILED_CLAIM],
        }, indent=2))


if __name__ == "__main__":
    main()
