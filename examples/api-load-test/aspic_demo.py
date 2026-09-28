"""Run the optional synthetic ASPIC+ method through EAL and MCP."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from eal.aspic import aspic_registry
from eal.runtime import ReasoningService

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = (HERE / "aspic-source.eal").read_text()
CONTEXT = {"service": "orders-api", "build_id": "demo-build-42", "dataset": "synthetic"}
NOW = "2026-09-25T10:00:30Z"
CLAIM = "run_passes"


async def mcp(database):
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + environment.get("PYTHONPATH", "")
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "eal.server", "--workspace", str(ROOT),
              "--registry", str(HERE / "aspic-tools.toml"), "--database", str(database),
              "--methods", "eal.aspic:aspic_registry"],
        env=environment,
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()

            async def call(tool, arguments):
                response = await session.call_tool(tool, arguments)
                if response.isError:
                    raise RuntimeError(f"{tool} failed: {response.content}")
                return response.structuredContent

            valid = await call("eal_validate", {"source": SOURCE})
            assert valid["valid"], valid
            collection = await call("eal_collect", {"source": SOURCE, "context": CONTEXT})
            assessment = await call("eal_reason", {
                "source": SOURCE, "context": CONTEXT,
                "collection_id": collection["collection_id"], "now": NOW})
            trace = await call("eal_explain", {
                "assessment_id": assessment["assessment_id"], "claim": CLAIM})
            assert trace["result"]["status"] == "supported", trace
            return assessment["claims"][CLAIM]["status"]


def main():
    with tempfile.TemporaryDirectory(prefix="eal-aspic-demo-") as folder:
        service = ReasoningService(ROOT, HERE / "aspic-tools.toml",
                                   Path(folder) / "runs.sqlite3",
                                   method_registry=aspic_registry())
        validated = service.validate(SOURCE)
        assert validated["valid"], validated
        collection = service.collect(SOURCE, CONTEXT)
        assert all(item["status"] == "ok" for item in collection["records"].values()), collection
        assessment = service.reason(SOURCE, CONTEXT, collection["collection_id"], NOW)
        result = assessment["arguments"]["formal_run"]["reasoning_result"]
        assert assessment["claims"][CLAIM]["status"] == "supported", assessment
        mcp_status = asyncio.run(mcp(Path(folder) / "mcp.sqlite3"))
        print(json.dumps({
            "dataset": "synthetic",
            "claim_status": assessment["claims"][CLAIM]["status"],
            "formal_status": result["details"]["grounded_status"],
            "defeat_kinds": sorted({row["kind"] for row in result["details"]["defeats"]}),
            "mcp_claim_status": mcp_status,
        }, indent=2))


if __name__ == "__main__":
    main()
