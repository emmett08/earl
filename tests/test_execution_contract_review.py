"""Adversarial acquisition, time and host regressions for the current contract."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest

from eal.host import dispatch_request
from eal.parser import parse
from eal.runtime import ReasoningService, acquisition_request


SOURCE = '''language "EAL/3"

environment lab {
  require "site" == "bench"
}

tool reader {
  version "1"
}

evidence reading {
  tool reader
  kind measurement
  environment lab
  max_age 60
  input {"sensor": "A"}
  require "passed" == true
}

reasoning support {
  method "structured/1"
  rationale "The declared observation supports the bounded claim."
}

claim works {
  statement "The requested check passes."
  environment lab
}

argument result = [evidence reading] via support => works
'''
CONTEXT = {"site": "bench"}
NOW = "2026-09-23T12:00:00Z"


def file_service(tmp_path):
    envelope = {"observed_at": NOW, "context": CONTEXT, "value": {"passed": True},
                "request": acquisition_request(parse(SOURCE), "reading", CONTEXT)}
    path = tmp_path / "observation.json"
    path.write_text(json.dumps(envelope))
    registry = tmp_path / "tools.toml"
    registry.write_text('[tools.reader]\nkind="json_file"\nversion="1"\npath="observation.json"\n')
    return ReasoningService(tmp_path, registry), path, envelope


@pytest.mark.parametrize(("field", "wrong"), [
    ("tool", "unrelated_reader"), ("tool_version", "0"),
    ("input", {"sensor": "B"}), ("context", {"site": "other"}),
])
def test_import_cannot_rebind_a_measurement_from_another_acquisition(tmp_path, field, wrong):
    service, path, envelope = file_service(tmp_path)
    envelope["request"][field] = wrong
    path.write_text(json.dumps(envelope))
    collection = service.collect(SOURCE, CONTEXT)
    record = collection["records"]["reading"]
    assert record["status"] == "error"
    assert "Observation request differs" in record["error"]["message"]
    assert service.store.get(record["run_id"], kind="observation") == record
    assessment = service.reason(SOURCE, CONTEXT, collection["collection_id"], NOW)
    assert assessment["claims"]["works"]["status"] == "unsupported"


def test_import_rejects_obsolete_unrequested_mode_metadata(tmp_path):
    service, path, envelope = file_service(tmp_path)
    envelope["request"]["mode"] = "deterministic"
    path.write_text(json.dumps(envelope))
    record = service.collect(SOURCE, CONTEXT)["records"]["reading"]
    assert record["status"] == "error"
    assert "Observation request differs" in record["error"]["message"]


def test_import_requires_acquisition_identity_and_retains_measurement_age(tmp_path):
    service, path, envelope = file_service(tmp_path)
    del envelope["request"]
    path.write_text(json.dumps(envelope))
    assert service.collect(SOURCE, CONTEXT)["records"]["reading"]["status"] == "error"
    envelope["request"] = acquisition_request(parse(SOURCE), "reading", CONTEXT)
    path.write_text(json.dumps(envelope))
    collected = service.collect(SOURCE, CONTEXT)
    record = collected["records"]["reading"]
    assert record["status"] == "ok" and record["collected_at"] == NOW
    assert record["acquisition_request"] == envelope["request"]
    assert service.reason(SOURCE, CONTEXT, collected["collection_id"], NOW)["claims"]["works"]["status"] == "supported"
    late = service.reason(SOURCE, CONTEXT, collected["collection_id"], "2026-09-23T12:02:00Z")
    assert late["claims"]["works"]["status"] == "unsupported"
    assert late["collection_id"] == collected["collection_id"]
    assert service.explain(late["assessment_id"])["collection_id"] == collected["collection_id"]


def test_import_allows_local_renaming_but_rejects_changed_acquisition_input(tmp_path):
    service, _, _ = file_service(tmp_path)
    renamed = SOURCE.replace("evidence reading", "evidence measurement").replace('evidence reading', 'evidence measurement')
    renamed = renamed.replace("environment lab", "environment bench")
    collection = service.collect(renamed, CONTEXT)
    assert service.reason(renamed, CONTEXT, collection["collection_id"], NOW)["claims"]["works"]["status"] == "supported"
    changed = renamed.replace('"sensor": "A"', '"sensor": "B"')
    record = service.collect(changed, CONTEXT)["records"]["measurement"]
    assert record["status"] == "error"
    assert "Observation request differs" in record["error"]["message"]


def test_excessive_import_nesting_becomes_a_durable_failed_observation(tmp_path):
    service, path, _ = file_service(tmp_path)
    path.write_text('{"value":' + '[' * 5000 + '0' + ']' * 5000 + '}')
    collection = service.collect(SOURCE, CONTEXT)
    record = collection["records"]["reading"]
    assert record["status"] == "error"
    assert "nesting" in record["error"]["message"]
    assert service.store.get(record["run_id"], kind="observation") == record


@pytest.mark.skipif(os.name != "posix", reason="POSIX FIFO regression")
def test_file_adapter_rejects_fifo_without_waiting_for_a_writer(tmp_path):
    service, path, _ = file_service(tmp_path)
    path.unlink()
    os.mkfifo(path)
    started = time.monotonic()
    record = service.collect(SOURCE, CONTEXT)["records"]["reading"]
    assert time.monotonic() - started < 2
    assert record["status"] == "error"
    assert "regular file" in record["error"]["message"]


@pytest.mark.parametrize(("collection_id", "now"), [("", NOW), (None, "")])
def test_explicit_empty_identity_or_time_is_never_replaced_by_a_default(tmp_path, collection_id, now):
    with pytest.raises(ValueError):
        ReasoningService(tmp_path).reason(SOURCE, CONTEXT, collection_id, now)


def test_mcp_rejects_unknown_arguments_and_coercible_json_types(tmp_path):
    parameters = StdioServerParameters(command=sys.executable,
        args=["-m", "eal.server", "--workspace", str(tmp_path)], env=dict(os.environ))

    async def exercise():
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                described = await session.list_tools()
                assert all(tool.inputSchema["additionalProperties"] is False for tool in described.tools)
                for arguments in ({"source": SOURCE, "ignored": True}, {"source": 4}):
                    result = await session.call_tool("eal_validate", arguments)
                    assert result.isError
                invalid = await session.call_tool("eal_grounded", {"arguments": '["a"]', "attacks": []})
                assert invalid.isError  # SDK coercion must not reinterpret text as a list.
                valid = await session.call_tool("eal_validate", {"source": SOURCE})
                assert not valid.isError and valid.structuredContent["valid"]

    asyncio.run(exercise())


def test_one_shot_host_bounds_an_unresponsive_server(tmp_path):
    parameters = StdioServerParameters(command=sys.executable, args=["-c", "import time; time.sleep(20)"])
    with pytest.raises(TimeoutError):
        asyncio.run(dispatch_request('{"operation":"describe"}', parameters, timeout_seconds=0.1))


def test_one_shot_host_checks_the_discovered_schema_before_invoking(tmp_path):
    marker = tmp_path / "invoked"
    server = tmp_path / "restricted_server.py"
    server.write_text('from pathlib import Path\nfrom typing import Literal\n'
        'from mcp.server.fastmcp import FastMCP\nserver = FastMCP("schema fixture")\n'
        '@server.tool()\ndef eal_validate(source: Literal["allowed"]):\n'
        f'    Path({str(marker)!r}).write_text("called")\n'
        '    return {"valid":True}\nserver.run(transport="stdio")\n')
    with pytest.raises(Exception) as caught:
        asyncio.run(dispatch_request('{"operation":"validate","source":"wrong"}',
            StdioServerParameters(command=sys.executable, args=[str(server)])))

    def messages(error):
        if isinstance(error, BaseExceptionGroup):
            return " ".join(messages(child) for child in error.exceptions)
        return str(error)

    assert "Discovered input schema rejected" in messages(caught.value)
    assert not marker.exists()
