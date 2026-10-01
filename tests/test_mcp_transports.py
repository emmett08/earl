"""The shared EAL operation contract over actual stdio and HTTP connections."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import sys
import threading

import httpx2
import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport
from fastmcp.utilities.tests import find_available_port, run_server_async

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
CONTEXT = {"site": "bench"}


def command_workspace(path: Path, *, detect_overlap: bool = False) -> Path:
    """A real collector counts acquisitions and detects concurrent execution."""
    path.mkdir(exist_ok=True, parents=True)
    collector = path / "collector.py"
    collector.write_text(
        "import json,pathlib,sys,time\n"
        "json.load(sys.stdin)\n"
        f"workspace=pathlib.Path({str(path)!r})\n"
        "active=workspace/'active'\n"
        + ("active.mkdir()\n" if detect_overlap else "")
        + "try:\n"
        "    counter=workspace/'invocations'\n"
        "    counter.write_text(str(int(counter.read_text())+1 if counter.exists() else 1))\n"
        + ("    time.sleep(0.2)\n" if detect_overlap else "")
        + "    print(json.dumps({'value':{'passed':True,'private':'collector data'}}))\n"
        "finally:\n"
        + ("    active.rmdir()\n" if detect_overlap else "    pass\n")
    )
    registry = path / "tools.toml"
    registry.write_text(
        '[tools.runner]\nkind="command"\nversion="1"\n'
        + "argv=" + json.dumps([sys.executable, str(collector)]) + "\n"
    )
    return registry


def local_http_client(headers=None, timeout=None, auth=None, **kwargs):
    # Local sockets must bypass the execution environment's external proxy.
    return httpx2.AsyncClient(headers=headers, timeout=timeout, auth=auth, trust_env=False, **kwargs)


def stdio_transport(workspace: Path, registry: Path, *, known_entries=(), max_in_flight=1):
    arguments = ["-m", "eal.server", "--workspace", str(workspace),
                 "--registry", str(registry), "--max-in-flight", str(max_in_flight)]
    for entry in known_entries:
        arguments.extend(["--known-entry", entry])
    return StdioTransport(command=sys.executable, args=arguments, env=dict(os.environ))


@asynccontextmanager
async def connected(workspace: Path, registry: Path, transport: str, *,
                    known_entries=(), max_in_flight=1, auth=None, token=None):
    if transport == "stdio":
        async with Client(stdio_transport(workspace, registry, known_entries=known_entries,
                                         max_in_flight=max_in_flight), mode="auto") as client:
            yield client
    else:
        server = create_server(ReasoningService(workspace, registry),
                               known_entries=known_entries or None,
                               max_in_flight=max_in_flight, auth=auth)
        async with run_server_async(server) as url:
            transport = StreamableHttpTransport(url, auth=token,
                                               httpx_client_factory=local_http_client)
            async with Client(transport, mode="auto") as client:
                yield client


async def tool_value(client: Client, name: str, arguments: dict | None = None):
    result = await client.call_tool(name, arguments)
    assert not result.is_error
    assert result.structured_content is not None
    return result.structured_content


def test_stdio_and_http_share_schemas_and_application_results(tmp_path):
    async def exercise(transport):
        workspace = tmp_path / transport
        registry = command_workspace(workspace)
        async with connected(workspace, registry, transport) as client:
            assert client.protocol_version == "2026-07-28"
            tools = await client.list_tools()
            schemas = {tool.name: (tool.input_schema, tool.output_schema) for tool in tools}
            assert all(schema[0]["additionalProperties"] is False for schema in schemas.values())
            description = await tool_value(client, "eal_describe")
            formatted = await tool_value(client, "eal_format", {"source": SOURCE})
            validated = await tool_value(client, "eal_validate", {"source": SOURCE})
            plan = await tool_value(client, "eal_plan", {"source": SOURCE, "claim": "works"})
            assert validated["valid"] and plan["evidence_ids"] == ["measured"]
            collected = await tool_value(client, "eal_collect", {"source": SOURCE, "context": CONTEXT})
            reasoned = await tool_value(client, "eal_reason", {
                "source": SOURCE, "context": CONTEXT, "collection_id": collected["collection_id"],
            })
            assert reasoned["claims"]["works"]["status"] == "supported"
            compiled = await tool_value(client, "eal_compile_aspic", {
                "source": SOURCE, "context": CONTEXT, "collection_id": collected["collection_id"],
                "goal": "works",
            })
            assert compiled["claim_status"] == compiled["authored_claim_status"] == "supported"
            assert compiled["formal"]["grounded_status"] == "accepted"
            explained = await tool_value(client, "eal_explain", {
                "assessment_id": reasoned["assessment_id"], "claim": "works",
            })
            assert explained["result"]["status"] == "supported"
            packet = await tool_value(client, "eal_packet", {
                "assessment_id": reasoned["assessment_id"], "claim": "works",
            })
            assert packet["claims"]["works"]["status"] == "supported"
            selected = await tool_value(client, "eal_collect_claim", {
                "source": SOURCE, "context": CONTEXT, "claim": "works",
            })
            assert selected["plan"]["evidence_ids"] == ["measured"]
            grounded = await tool_value(client, "eal_grounded", {
                "arguments": ["a", "b"], "attacks": [["a", "b"]],
            })
            errors = []
            for name, arguments in (
                ("eal_validate", {"source": SOURCE, "ignored": True}),
                ("eal_validate", {"source": 4}),
                ("eal_grounded", {"arguments": '["a"]', "attacks": []}),
                ("eal_explain", {"assessment_id": "missing"}),
            ):
                result = await client.call_tool(name, arguments, raise_on_error=False)
                assert result.is_error
                errors.append([item.text for item in result.content if item.type == "text"])
            # Compare stable application values; durable IDs and times are independently generated.
            return schemas, description, formatted, validated, plan, grounded, errors

    stdio = asyncio.run(exercise("stdio"))
    http = asyncio.run(exercise("http"))
    assert stdio == http


@pytest.mark.parametrize("transport", ["stdio", "http"])
def test_registered_exposure_rejects_source_and_context_injection(tmp_path, transport):
    registry = command_workspace(tmp_path)
    service = ReasoningService(tmp_path, registry)
    catalogue = WorkspaceKnowledgeCatalogue(service)
    for name in ("selected.eal", "hidden.eal"):
        (tmp_path / name).write_text(SOURCE)
        catalogue.register(name, context=CONTEXT, claims=["works"])

    async def exercise():
        async with connected(tmp_path, registry, transport, known_entries=["selected.eal"]) as client:
            assert {tool.name for tool in await client.list_tools()} == {
                "eal_sources", "eal_find_claims", "eal_assess_known",
            }
            listed = await tool_value(client, "eal_sources")
            assert [entry["entry_id"] for entry in listed["sources"]] == ["selected.eal"]
            assert "source" not in listed["sources"][0] and "context" not in listed["sources"][0]
            matches = await tool_value(client, "eal_find_claims", {"query": "requested check"})
            assert [entry["entry_id"] for entry in matches["matches"]] == ["selected.eal"]
            for name, arguments in (
                ("eal_assess_known", {"entry_id": "hidden.eal", "claim": "works"}),
                ("eal_assess_known", {"entry_id": "selected.eal", "claim": "works", "context": {"site": "other"}}),
                ("eal_collect", {"source": SOURCE, "context": CONTEXT}),
                ("eal_sources", {"limit": True}),
            ):
                result = await client.call_tool(name, arguments, raise_on_error=False)
                assert result.is_error
            first = await tool_value(client, "eal_assess_known", {"entry_id": "selected.eal", "claim": "works"})
            second = await tool_value(client, "eal_assess_known", {"entry_id": "selected.eal", "claim": "works"})
            assert first["status"] == second["status"] == "supported"
            assert (first["collected_count"], first["reused_count"]) == (1, 0)
            assert (second["collected_count"], second["reused_count"]) == (0, 1)
            assert "collector data" not in str(first)

    asyncio.run(exercise())
    assert (tmp_path / "invocations").read_text() == "1"


def test_explicit_registered_exposure_requires_at_least_one_entry(tmp_path):
    with pytest.raises(ValueError):
        create_server(ReasoningService(tmp_path), exposure="registered", known_entries=[])


@pytest.mark.parametrize("transport", ["stdio", "http"])
def test_concurrent_collection_requests_preserve_serial_collector_execution(tmp_path, transport):
    registry = command_workspace(tmp_path, detect_overlap=True)

    async def exercise():
        async with connected(tmp_path, registry, transport, max_in_flight=2) as client:
            collections = await asyncio.gather(*(
                tool_value(client, "eal_collect", {"source": SOURCE, "context": CONTEXT})
                for _ in range(2)
            ))
            assert all(value["records"]["measured"]["status"] == "ok" for value in collections)
            assert collections[0]["collection_id"] != collections[1]["collection_id"]

    asyncio.run(exercise())
    assert (tmp_path / "invocations").read_text() == "2"
    assert not (tmp_path / "active").exists()


@pytest.mark.parametrize("max_in_flight", [1, 2])
def test_http_admission_limit_bounds_active_operations(tmp_path, max_in_flight):
    """Admission bounds ordinary operations as well as acquiring operations."""
    started = [threading.Event(), threading.Event()]
    release = threading.Event()
    mutex = threading.Lock()
    active = 0
    peak = 0

    class PausedService(ReasoningService):
        def validate(self, source):
            nonlocal active, peak
            with mutex:
                active += 1
                peak = max(peak, active)
                started[active - 1].set()
            try:
                assert release.wait(3), "Test did not release the admitted operation"
                return super().validate(source)
            finally:
                with mutex:
                    active -= 1

    server = create_server(PausedService(tmp_path), max_in_flight=max_in_flight)

    async def exercise():
        async with run_server_async(server) as url:
            transport = StreamableHttpTransport(url, httpx_client_factory=local_http_client)
            async with Client(transport, mode="auto") as client:
                requests = [asyncio.create_task(tool_value(client, "eal_validate", {"source": SOURCE}))
                            for _ in range(2)]
                try:
                    assert await asyncio.to_thread(started[0].wait, 1)
                    second_admitted = await asyncio.to_thread(started[1].wait, 0.2)
                    assert second_admitted is (max_in_flight == 2)
                finally:
                    release.set()
                    values = await asyncio.gather(*requests)
                assert all(value["valid"] for value in values)

    asyncio.run(exercise())
    assert peak == max_in_flight


def test_independent_stdio_servers_recheck_observation_reuse_after_admission(tmp_path):
    registry = command_workspace(tmp_path, detect_overlap=True)
    (tmp_path / "selected.eal").write_text(SOURCE)
    catalogue = WorkspaceKnowledgeCatalogue(ReasoningService(tmp_path, registry))
    catalogue.register("selected.eal", context=CONTEXT, claims=["works"])

    async def exercise():
        async with connected(tmp_path, registry, "stdio", known_entries=["selected.eal"]) as first:
            async with connected(tmp_path, registry, "stdio", known_entries=["selected.eal"]) as second:
                results = await asyncio.gather(*(
                    tool_value(client, "eal_assess_known", {"entry_id": "selected.eal", "claim": "works"})
                    for client in (first, second)
                ))
                assert all(result["status"] == "supported" for result in results)
                assert sorted((result["collected_count"], result["reused_count"]) for result in results) == [(0, 1), (1, 0)]

    asyncio.run(exercise())
    assert (tmp_path / "invocations").read_text() == "1"


def test_http_bearer_authentication_rejects_missing_and_wrong_tokens(tmp_path):
    from eal.server_auth import BearerTokenVerifier

    token = "host-integration-token"
    registry = command_workspace(tmp_path)
    server = create_server(ReasoningService(tmp_path, registry), auth=BearerTokenVerifier(token))

    async def exercise():
        async with run_server_async(server) as url:
            for credentials in (None, "wrong-token"):
                async with local_http_client() as probe:
                    headers = {} if credentials is None else {"Authorization": f"Bearer {credentials}"}
                    assert (await probe.get(url, headers=headers)).status_code == 401
                transport = StreamableHttpTransport(url, auth=credentials,
                                                   httpx_client_factory=local_http_client)
                with pytest.raises(Exception):
                    async with Client(transport, mode="auto", init_timeout=3):
                        pytest.fail("Unauthenticated HTTP session was admitted")
            transport = StreamableHttpTransport(url, auth=token,
                                               httpx_client_factory=local_http_client)
            async with Client(transport, mode="auto") as client:
                assert "EAL/3" in (await tool_value(client, "eal_describe"))["languages"]
                assert "eal_collect" in {tool.name for tool in await client.list_tools()}

    asyncio.run(exercise())
    assert not (tmp_path / "invocations").exists()


def test_http_launcher_uses_configured_path_and_token_environment(tmp_path):
    """Exercise the HTTP composition root, including TOML-relative service paths."""
    command_workspace(tmp_path)
    port = find_available_port()
    config = tmp_path / "mcp.toml"
    config.write_text(f'''
[service]
workspace = "."
registry = "tools.toml"
[server]
transport = "http"
[server.http]
host = "127.0.0.1"
port = {port}
path = "/engineering"
token_env = "EAL_TEST_HTTP_TOKEN"
''')
    token = "launcher-integration-token"

    async def exercise():
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "eal.server", "--config", str(config),
            env={**os.environ, "EAL_TEST_HTTP_TOKEN": token},
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            async with asyncio.timeout(10):
                while True:
                    try:
                        _, writer = await asyncio.open_connection("127.0.0.1", port)
                    except OSError:
                        if process.returncode is not None:
                            pytest.fail((await process.stderr.read()).decode())
                        await asyncio.sleep(0.02)
                    else:
                        writer.close()
                        await writer.wait_closed()
                        break
            transport = StreamableHttpTransport(
                f"http://127.0.0.1:{port}/engineering", auth=token,
                httpx_client_factory=local_http_client,
            )
            async with Client(transport, mode="auto") as client:
                assert client.protocol_version == "2026-07-28"
                assert (await tool_value(client, "eal_validate", {"source": SOURCE}))["valid"]
                collected = await tool_value(client, "eal_collect", {"source": SOURCE, "context": CONTEXT})
                assert collected["records"]["measured"]["status"] == "ok"
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
            output, errors = await process.communicate()
            assert token.encode() not in output + errors

    asyncio.run(exercise())
    assert (tmp_path / "invocations").read_text() == "1"
