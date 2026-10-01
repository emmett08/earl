"""Opaque credentials preserve the real HTTP host's JSON contract."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

from fastmcp.utilities.tests import run_server_async
import pytest

from eal.host_redaction import sanitise_response
from eal.runtime import ReasoningService
from eal.server import create_server
from eal.server_auth import BearerTokenVerifier


def host_environment(token: str) -> dict[str, str]:
    environment = {name: value for name, value in os.environ.items()
                   if not name.startswith("EAL_MCP_")
                   and name.lower() not in {"http_proxy", "https_proxy", "all_proxy"}}
    environment["NO_PROXY"] = "127.0.0.1,localhost,::1"
    environment["EAL_HOST_TEST_TOKEN"] = token
    return environment


async def invoke_host(url: str, token: str, source: str, workspace: Path):
    return await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "eal.host", "--workspace", str(workspace),
         "--url", url, "--token-env", "EAL_HOST_TEST_TOKEN", "--timeout", "10"],
        input=json.dumps({"operation": "validate", "source": source}),
        text=True, capture_output=True, env=host_environment(token), timeout=15,
    )


@pytest.mark.parametrize("token", ["oauth", "is_error", "result", "operation", "validate", "text"])
def test_http_host_preserves_envelope_and_nested_schema_on_success_and_tool_failure(tmp_path, token):
    class CredentialEchoService(ReasoningService):
        def validate(self, source):
            if source == "failure":
                raise ValueError("Remote diagnostic echoed credential=" + token)
            return {
                "valid": True,
                "result": {"operation": token, "is_error": False,
                           "nested": [{"result": token}]},
                "encoded": json.dumps({"result": {"operation": token}}),
            }

    server = create_server(CredentialEchoService(tmp_path), auth=BearerTokenVerifier(token))

    async def exercise():
        async with run_server_async(server) as url:
            completed = await invoke_host(url, token, "success", tmp_path)
            assert completed.returncode == 0, completed.stderr
            response = json.loads(completed.stdout)
            assert set(response) == {"operation", "protocol_version", "is_error", "result", "content"}
            assert response["operation"] == "validate"
            assert response["protocol_version"] == "2026-07-28"
            assert response["is_error"] is False
            expected = {
                "valid": True,
                "result": {"operation": "[redacted]", "is_error": False,
                           "nested": [{"result": "[redacted]"}]},
            }
            payload = response["result"]
            assert {key: payload[key] for key in expected} == expected
            assert json.loads(payload["encoded"]) == {"result": {"operation": "[redacted]"}}
            for block in response["content"]:
                if block["type"] == "text":
                    assert json.loads(block["text"]) == payload

            failed = await invoke_host(url, token, "failure", tmp_path)
            assert failed.returncode == 1, failed.stderr
            failure = json.loads(failed.stdout)
            assert set(failure) == set(response)
            assert failure["operation"] == "validate"
            assert failure["is_error"] is True
            assert failure["result"] is None
            messages = [block["text"] for block in failure["content"] if block["type"] == "text"]
            assert any("[redacted]" in message for message in messages)
            assert all(token not in message for message in messages)

    asyncio.run(exercise())


@pytest.mark.parametrize("token", ["oauth", "is_error", "result", "operation"])
def test_http_host_preserves_failure_envelope_without_disclosing_credential(tmp_path, token):
    server = create_server(ReasoningService(tmp_path), auth=BearerTokenVerifier("different-token"))

    async def exercise():
        async with run_server_async(server) as url:
            failed = await invoke_host(url, token, "success", tmp_path)
            assert failed.returncode == 2
            response = json.loads(failed.stdout)
            assert set(response) == {"is_error", "error"}
            assert response["is_error"] is True
            assert response["error"]
            assert token not in response["error"]

    asyncio.run(exercise())


@pytest.mark.parametrize("token", ["operation", "is_error", "result", "2026-07-28"])
def test_public_response_metadata_is_stable_when_it_coincides_with_a_credential(token):
    response = {"operation": "operation", "protocol_version": "2026-07-28",
                "is_error": False, "result": {"result": token}}
    sanitised = sanitise_response(response, token)
    assert sanitised["operation"] == response["operation"]
    assert sanitised["protocol_version"] == response["protocol_version"]
    assert sanitised["is_error"] is False
    assert sanitised["result"] == {"result": "[redacted]"}


def test_json_text_decodes_escaped_credentials_before_value_redaction():
    token = 'opaque\\"secret'
    encoded = json.dumps({"result": token})
    response = {"is_error": False, "content": [{"type": "text", "text": encoded}]}
    sanitised = sanitise_response(response, token)
    assert json.loads(sanitised["content"][0]["text"]) == {"result": "[redacted]"}


def test_json_string_text_decodes_escaped_credentials_before_value_redaction():
    token = 'opaque\\"secret'
    response = {"is_error": False, "content": [{"type": "text", "text": json.dumps(token)}]}
    sanitised = sanitise_response(response, token)
    assert json.loads(sanitised["content"][0]["text"]) == "[redacted]"


def test_json_text_with_only_a_schema_key_collision_keeps_its_representation():
    encoded = '{\n  "result": true\n}'
    response = {"content": [{"type": "text", "text": encoded}]}
    assert sanitise_response(response, "result") == response
