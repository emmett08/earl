import asyncio
import json
import os
import subprocess
import sys

import pytest
from mcp import StdioServerParameters

from eal.host import dispatch_request, parse_request
from eal.knowledge import EALKnowledgeBase


@pytest.mark.parametrize("request_text", [
    "not JSON", "[]", '{"operation":"exec","argv":["echo"]}',
    '{"operation":"validate","source":"", "argv":["echo"]}',
    '{"operation":"validate"}', '{"operation":"validate","source":4}',
    '{"operation":"validate","source":"","source":"different"}',
    '{"operation":"collect","source":"", "context":[]}',
    '{"operation":"collect","source":"", "context":{"number":1e309}}',
    '{"operation":"plan","source":""}',
    '{"operation":"collect_claim","source":"", "context":{}, "claim":""}',
    '{"operation":"packet","claim":"works"}',
    '{"operation":"assess_known","entry_id":"source.eal","claim":""}',
    '{"operation":"assess_known","entry_id":"","claim":"ready"}',
    '{"operation":"assess_known","entry_id":"source.eal","claim":"ready","context":{}}',
    '{"operation":"sources","limit":true}',
    '{"operation":"find_claims","query":[]}',
    '{"operation":"grounded","arguments":[], "attacks":[["a"]]}',
    '{"operation":"grounded","arguments":null, "attacks":[]}',
    '{"operation":"compile_aspic","source":"","context":{},"collection_id":"saved","goal":null}',
    '{"operation":"compile_aspic","source":"","context":{},"collection_id":"saved","goal":" "}',
    '{"operation":"compile_aspic","source":"","context":{},"collection_id":null,"goal":"ready"}',
    '{"operation":"compile_aspic","source":"","context":{},"collection_id":"","goal":"ready"}',
    '{"operation":"compile_aspic","source":"","context":{},"collection_id":"saved","goal":"ready","semantics":[]}',
])
def test_strict_host_request_rejects_unstructured_and_extra_fields(request_text):
    with pytest.raises(ValueError):
        parse_request(request_text)


@pytest.mark.parametrize("payload,expected", [
    ({"operation": "plan", "source": "source", "claim": "works"}, "eal_plan"),
    ({"operation": "collect_claim", "source": "source", "context": {}, "claim": "works"}, "eal_collect_claim"),
    ({"operation": "packet", "assessment_id": "assessment-1", "claim": "works"}, "eal_packet"),
    ({"operation": "sources"}, "eal_sources"),
    ({"operation": "assess_known", "entry_id": "source.eal", "claim": "ready"}, "eal_assess_known"),
    ({"operation": "compile_aspic", "source": "source", "context": {},
      "collection_id": "saved", "goal": "ready", "semantics": "grounded"}, "eal_compile_aspic"),
])
def test_host_exposes_claim_scoped_operations(payload, expected):
    tool, arguments = parse_request(json.dumps(payload))
    assert tool == expected
    assert arguments == {key: value for key, value in payload.items() if key != "operation"}


def test_host_dispatches_text_model_request_through_actual_mcp(tmp_path):
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "eal.server", "--workspace", str(tmp_path)],
        env=dict(os.environ),
    )
    request = json.dumps({"operation": "grounded", "arguments": ["a", "b", "c"], "attacks": [["a", "b"], ["b", "c"]]})
    response = asyncio.run(dispatch_request(request, parameters))
    assert not response["is_error"]
    assert response["protocol_version"]
    assert response["result"]["accepted"] == ["a", "c"]
    assert response["result"]["rejected"] == ["b"]


def test_host_cli_reports_server_startup_failure_as_json(tmp_path):
    completed = subprocess.run(
        [sys.executable, "-m", "eal.host", "--workspace", str(tmp_path), "--registry", str(tmp_path / "absent.toml")],
        input=json.dumps({"operation": "validate", "source": ""}), text=True, capture_output=True, timeout=10,
    )
    assert completed.returncode == 2
    response = json.loads(completed.stdout)
    assert response["is_error"]
    assert "Connection closed" in response["error"]


def test_text_host_assesses_registered_claim_without_model_tool_support(tmp_path):
    from test_mcp import SOURCE

    (tmp_path / "source.eal").write_text(SOURCE)
    collector = tmp_path / "collector.py"
    collector.write_text('import json\nprint(json.dumps({"value":{"passed":True}}))\n')
    registry = tmp_path / "tools.toml"
    registry.write_text('[tools.runner]\nkind="command"\nversion="1"\nargv='
                        + json.dumps([sys.executable, str(collector)]) + '\n')
    EALKnowledgeBase(tmp_path, registry).register("source.eal", context={"site": "bench"}, claims=["works"])
    completed = subprocess.run(
        [sys.executable, "-m", "eal.host", "--workspace", str(tmp_path),
         "--registry", str(registry), "--known-entry", "source.eal"],
        input=json.dumps({"operation": "assess_known", "entry_id": "source.eal", "claim": "works"}),
        text=True, capture_output=True, check=True, timeout=15,
    )
    result = json.loads(completed.stdout)
    assert not result["is_error"]
    assert result["result"]["status"] == "supported"
    assert result["result"]["collected_count"] == 1


@pytest.mark.parametrize("arguments,message", [
    (["--url", "ftp://localhost/mcp"], "http or https"),
    (["--url", "http://example.com/mcp"], "require --token-env"),
    (["--url", "http://localhost/mcp", "--token-env", "EAL_TEST_MISSING_TOKEN"], "missing or empty"),
    (["--transport", "invalid"], "Invalid server configuration arguments"),
    (["--timeout", "invalid"], "invalid float value"),
])
def test_host_cli_configuration_failures_are_one_json_response(tmp_path, arguments, message):
    environment = {key: value for key, value in os.environ.items() if not key.startswith("EAL_MCP_")}
    environment.pop("EAL_TEST_MISSING_TOKEN", None)
    completed = subprocess.run([sys.executable, "-m", "eal.host", "--workspace", str(tmp_path), *arguments],
        input='{"operation":"describe"}', text=True, capture_output=True, env=environment, timeout=10)
    assert completed.returncode == 2
    response = json.loads(completed.stdout)
    assert response["is_error"]
    assert message in response["error"]


def test_http_host_configuration_connects_without_launching_a_server(tmp_path, monkeypatch, capsys):
    import io
    import eal.host as host
    from fastmcp.client.transports import StreamableHttpTransport

    config = tmp_path / "mcp.toml"
    config.write_text('[server]\ntransport="http"\n[server.http]\nport=32123\npath="/eal"\n')
    monkeypatch.setattr(sys, "argv", ["eal-host", "--config", str(config)])
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b'{"operation":"describe"}')))
    for name in list(os.environ):
        if name.startswith("EAL_MCP_"):
            monkeypatch.delenv(name)
    async def dispatch(text, target, **kwargs):
        assert isinstance(target, StreamableHttpTransport)
        assert target.url == "http://127.0.0.1:32123/eal"
        return {"is_error": False, "result": {"connected": True}}
    monkeypatch.setattr(host, "dispatch_request", dispatch)
    host.main()
    assert json.loads(capsys.readouterr().out)["result"]["connected"]


def test_http_host_redacts_credential_from_remote_result_and_error(monkeypatch, capsys):
    import io
    import eal.host as host

    token = "host-secret-token"
    monkeypatch.setenv("EAL_TEST_TOKEN", token)
    monkeypatch.setattr(sys, "argv", ["eal-host", "--url", "http://localhost/mcp",
                                      "--token-env", "EAL_TEST_TOKEN"])
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b'{"operation":"describe"}')))
    async def dispatch(*args, **kwargs):
        return {"is_error": False, "result": {"remote_message": token}}
    monkeypatch.setattr(host, "dispatch_request", dispatch)
    host.main()
    output = capsys.readouterr().out
    assert token not in output
    assert json.loads(output)["result"]["remote_message"] == "[redacted]"
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b'{"operation":"describe"}')))
    async def fail(*args, **kwargs):
        raise ValueError("Remote failure echoes " + token)
    monkeypatch.setattr(host, "dispatch_request", fail)
    with pytest.raises(SystemExit) as caught:
        host.main()
    assert caught.value.code == 2
    output = capsys.readouterr().out
    assert token not in output
    assert "[redacted]" in json.loads(output)["error"]
