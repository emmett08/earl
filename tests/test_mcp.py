import asyncio
import json
import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from eal.catalogue import WorkspaceKnowledgeCatalogue
from eal.runtime import ReasoningService
from eal.server import create_server


SOURCE = '''language "EAL/3"

environment lab {
  require "site" == "bench"
}

tool runner {
  version "1"
}

evidence measured {
  tool runner
  kind test
  environment lab
  max_age 60
  require "passed" == true
}

reasoning measurement {
  method "structured/1"
  rationale "The bounded observation supplies support."
}

claim works {
  statement "The requested check passes."
  environment lab
}

argument result = [evidence measured] via measurement => works
'''


def test_real_mcp_stdio_lifecycle_collection_reason_explain(tmp_path):
    script = tmp_path / "tool.py"
    script.write_text("import json,sys\nrequest=json.load(sys.stdin)\nprint(json.dumps({'value':{'passed':True}}))\n")
    registry = tmp_path / "tools.toml"
    registry.write_text('[tools.runner]\nkind="command"\nversion="1"\nargv='
                        + json.dumps([sys.executable, str(script)]) + '\n')
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
                assert {"eal_describe", "eal_format", "eal_validate", "eal_plan", "eal_collect",
                        "eal_collect_claim", "eal_reason", "eal_explain", "eal_packet", "eal_grounded"} <= names
                assert not {"eal_sources", "eal_find_claims", "eal_assess_known"} & names
                described = await session.call_tool("eal_describe", {})
                assert not described.isError
                assert "EAL/3" in described.structuredContent["languages"]
                formatted = await session.call_tool("eal_format", {"source": SOURCE})
                assert not formatted.isError
                assert "source_digest" in formatted.structuredContent
                valid = await session.call_tool("eal_validate", {"source": SOURCE})
                assert not valid.isError
                assert valid.structuredContent["valid"]
                planned = await session.call_tool("eal_plan", {"source": SOURCE, "claim": "works"})
                assert planned.structuredContent["evidence_ids"] == ["measured"]
                collected = await session.call_tool("eal_collect", {"source": SOURCE, "context": {"site": "bench"}})
                assert not collected.isError
                collection_id = collected.structuredContent["collection_id"]
                reasoned = await session.call_tool("eal_reason", {"source": SOURCE, "context": {"site": "bench"}, "collection_id": collection_id})
                assert not reasoned.isError
                assert reasoned.structuredContent["claims"]["works"]["status"] == "supported"
                explained = await session.call_tool("eal_explain", {"assessment_id": reasoned.structuredContent["assessment_id"], "claim": "works"})
                assert explained.structuredContent["result"]["status"] == "supported"
                packet = await session.call_tool("eal_packet", {"assessment_id": reasoned.structuredContent["assessment_id"], "claim": "works"})
                assert packet.structuredContent["claims"]["works"]["status"] == "supported"
                selected = await session.call_tool("eal_collect_claim", {"source": SOURCE, "context": {"site": "bench"}, "claim": "works"})
                assert selected.structuredContent["plan"]["evidence_ids"] == ["measured"]
                grounded = await session.call_tool("eal_grounded", {"arguments": ["a", "b"], "attacks": [["a", "b"]]})
                assert grounded.structuredContent["accepted"] == ["a"]
                error = await session.call_tool("eal_explain", {"assessment_id": "missing"})
                assert error.isError

    asyncio.run(exercise())


def test_mcp_registered_claim_reuses_prior_tool_result_across_sessions(tmp_path):
    (tmp_path / "source.eal").write_text(SOURCE)
    (tmp_path / "hidden.eal").write_text(SOURCE)
    counter = tmp_path / "invocations"
    script = tmp_path / "tool.py"
    script.write_text(
        "import json,sys,pathlib\n"
        "request=json.load(sys.stdin)\n"
        f"counter=pathlib.Path({str(counter)!r})\n"
        "counter.write_text(str(int(counter.read_text())+1 if counter.exists() else 1))\n"
        "print(json.dumps({'value':{'passed':True,'private':'collector data'}}))\n"
    )
    registry = tmp_path / "tools.toml"
    registry.write_text('[tools.runner]\nkind="command"\nversion="1"\nargv='
                        + json.dumps([sys.executable, str(script)]) + '\n')
    index = WorkspaceKnowledgeCatalogue(ReasoningService(tmp_path, registry))
    index.register("source.eal", context={"site": "bench"}, claims=["works"])
    index.register("hidden.eal", context={"site": "bench"}, claims=["works"])
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "eal.server", "--workspace", str(tmp_path), "--registry", str(registry),
              "--known-entry", "source.eal"],
        env=dict(os.environ),
    )

    async def one_session(*, first: bool):
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {entry.name for entry in (await session.list_tools()).tools}
                assert names == {"eal_sources", "eal_find_claims", "eal_assess_known"}
                listed = await session.call_tool("eal_sources", {})
                assert not listed.isError
                assert len(listed.structuredContent["sources"]) == 1
                entry = listed.structuredContent["sources"][0]
                assert entry["entry_id"] == "source.eal"
                assert entry["claims"] == ["works"]
                assert "context" not in entry and "source" not in entry
                matches = await session.call_tool("eal_find_claims", {"query": "requested check"})
                assert [item["entry_id"] for item in matches.structuredContent["matches"]] == ["source.eal"]
                if first:
                    hidden = await session.call_tool("eal_assess_known", {
                        "entry_id": "hidden.eal", "claim": "works"})
                    assert hidden.isError
                    generic = await session.call_tool("eal_collect", {
                        "source": SOURCE, "context": {"site": "bench"}})
                    assert generic.isError
                    injected = await session.call_tool("eal_assess_known", {
                        "entry_id": "source.eal", "claim": "works", "context": {"site": "other"}})
                    assert injected.isError
                assessed = await session.call_tool("eal_assess_known", {
                    "entry_id": "source.eal", "claim": "works"})
                assert not assessed.isError
                result = assessed.structuredContent
                assert result["status"] == "supported"
                assert result["collected_count"] == (1 if first else 0)
                assert result["reused_count"] == (0 if first else 1)
                assert "collector data" not in str(result)
                return result

    first = asyncio.run(one_session(first=True))
    second = asyncio.run(one_session(first=False))
    assert first["collection_id"] != second["collection_id"]
    assert counter.read_text() == "1"


def test_known_entry_startup_requires_registered_source(tmp_path):
    service = ReasoningService(tmp_path)
    with pytest.raises(KeyError, match="Unknown catalogue entry"):
        create_server(service, known_entries=["missing.eal"])
    with pytest.raises(ValueError, match="Known entries"):
        create_server(service, known_entries=["duplicate", "duplicate"])
