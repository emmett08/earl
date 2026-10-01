"""The production HTTP launcher guards Host and Origin before MCP execution."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import os
import sys

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.utilities.tests import find_available_port
import pytest

from test_mcp_transports import SOURCE, CONTEXT, command_workspace, local_http_client


@asynccontextmanager
async def running_http(workspace, *arguments, environ=None):
    registry = command_workspace(workspace)
    port = find_available_port()
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "eal.server", "--transport", "http",
        "--workspace", str(workspace), "--registry", str(registry),
        "--port", str(port), *arguments,
        env={**{key: value for key, value in os.environ.items() if not key.startswith("EAL_MCP_")},
             **(environ or {})},
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
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        await process.communicate()


def collection_request():
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "eal_collect", "arguments": {"source": SOURCE, "context": CONTEXT}}}


@pytest.mark.parametrize("host, token", [("127.0.0.1", None), ("0.0.0.0", "origin-test-token")])
def test_http_rejects_foreign_host_and_origin_before_collector_execution(tmp_path, host, token):
    async def exercise():
        arguments = ["--host", host] + (["--token-env", "EAL_TEST_TOKEN"] if token else [])
        environment = {"FASTMCP_HTTP_HOST_ORIGIN_PROTECTION": "false",
                       "FASTMCP_HTTP_ALLOWED_HOSTS": '["foreign.example"]',
                       "FASTMCP_HTTP_ALLOWED_ORIGINS": '["https://foreign.example"]'}
        if token:
            environment["EAL_TEST_TOKEN"] = token
        async with running_http(tmp_path, *arguments, environ=environment) as url:
            headers = {"Accept": "application/json, text/event-stream",
                       "MCP-Protocol-Version": "2025-11-25"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            async with local_http_client() as probe:
                foreign_host = await probe.post(url, json=collection_request(),
                                                headers={**headers, "Host": "foreign.example"})
                assert foreign_host.status_code == 421
                foreign_origin = await probe.post(url, json=collection_request(),
                                                  headers={**headers, "Origin": "https://foreign.example"})
                assert foreign_origin.status_code == 403
            assert not (tmp_path / "invocations").exists()
            transport = StreamableHttpTransport(url, auth=token, httpx_client_factory=local_http_client)
            async with Client(transport, mode="auto") as client:
                result = await client.call_tool("eal_collect", {"source": SOURCE, "context": CONTEXT})
                assert not result.is_error
        assert (tmp_path / "invocations").read_text() == "1"

    asyncio.run(exercise())


def test_http_accepts_authenticated_explicit_proxy_host_and_https_origin(tmp_path):
    async def exercise():
        async with running_http(
            tmp_path, "--token-env", "EAL_TEST_TOKEN",
            "--allowed-host", "engineering.example", "--allowed-origin", "https://engineering.example",
            environ={"EAL_TEST_TOKEN": "proxy-test-token"},
        ) as url:
            trusted_headers = {"Host": "engineering.example", "Origin": "https://engineering.example"}
            async with local_http_client() as probe:
                assert (await probe.post(url, json=collection_request(), headers=trusted_headers)).status_code == 401
                assert (await probe.post(url, json=collection_request(), headers={
                    **trusted_headers, "Origin": "https://foreign.example",
                    "Authorization": "Bearer proxy-test-token",
                })).status_code == 403
            transport = StreamableHttpTransport(
                url, headers=trusted_headers, auth="proxy-test-token", httpx_client_factory=local_http_client,
            )
            async with Client(transport, mode="auto") as client:
                result = await client.call_tool("eal_validate", {"source": SOURCE})
                assert result.structured_content["valid"]
        assert not (tmp_path / "invocations").exists()

    asyncio.run(exercise())
