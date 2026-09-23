import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SOURCE = '''language "EAL/0.1";
environment lab { require "site" == "bench"; }
tool runner { version "1"; mode deterministic; }
evidence measured { tool runner; kind test; environment lab; max_age 60; require "passed" == true; }
reasoning measurement { mode structured; rationale "The bounded observation supplies support."; }
claim works { statement "The requested check passes."; environment lab; }
argument result { conclusion works; reasoning measurement; evidence measured; }
'''


def test_real_mcp_stdio_lifecycle_collection_reason_explain(tmp_path):
    script = tmp_path / "tool.py"
    script.write_text("import json,sys\nrequest=json.load(sys.stdin)\nprint(json.dumps({'value':{'passed':True}}))\n")
    registry = tmp_path / "tools.toml"
    registry.write_text('[tools.runner]\nkind="command"\nmode="deterministic"\nversion="1"\nargv=' + json.dumps([sys.executable, str(script)]) + '\n')
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "eal.server", "--workspace", str(tmp_path), "--registry", str(registry)],
        env=dict(os.environ),
    )

    async def exercise():
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                hello = await session.initialize()
                assert hello.protocolVersion == "2025-11-25"
                names = {entry.name for entry in (await session.list_tools()).tools}
                assert {"eal_describe", "eal_format", "eal_validate", "eal_collect", "eal_reason", "eal_explain", "eal_grounded"} <= names
                described = await session.call_tool("eal_describe", {})
                assert not described.isError
                assert "EAL/0.2" in described.structuredContent["languages"]
                formatted = await session.call_tool("eal_format", {"source": SOURCE})
                assert not formatted.isError
                assert "source_digest" in formatted.structuredContent
                valid = await session.call_tool("eal_validate", {"source": SOURCE})
                assert not valid.isError
                assert valid.structuredContent["valid"]
                collected = await session.call_tool("eal_collect", {"source": SOURCE, "context": {"site": "bench"}})
                assert not collected.isError
                collection_id = collected.structuredContent["collection_id"]
                reasoned = await session.call_tool("eal_reason", {"source": SOURCE, "context": {"site": "bench"}, "collection_id": collection_id})
                assert not reasoned.isError
                assert reasoned.structuredContent["claims"]["works"]["status"] == "supported"
                explained = await session.call_tool("eal_explain", {"assessment_id": reasoned.structuredContent["assessment_id"], "claim": "works"})
                assert explained.structuredContent["result"]["status"] == "supported"
                grounded = await session.call_tool("eal_grounded", {"arguments": ["a", "b"], "attacks": [["a", "b"]]})
                assert grounded.structuredContent["accepted"] == ["a"]
                error = await session.call_tool("eal_explain", {"assessment_id": "missing"})
                assert error.isError

    asyncio.run(exercise())
