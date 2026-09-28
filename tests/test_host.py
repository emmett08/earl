import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from mcp import StdioServerParameters

from eal.host import dispatch_request, parse_request


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
    assert response["protocol_version"] == "2025-11-25"
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


def test_host_cli_preassesses_text_only_task_and_finalises_without_recipient_status(tmp_path):
    from test_artifacts import setup_artifact

    _, manifest, tools = setup_artifact(tmp_path)
    base = [sys.executable, "-m", "eal.host", "--workspace", str(tmp_path),
            "--registry", str(tools), "--artifacts", str(manifest),
            "--artifact-id", "test", "--claim", "works", "--recipient-principal", "caller_a"]
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    initial = subprocess.run(base, input="Explain the result", text=True, capture_output=True,
                             check=True, timeout=15, env=env)
    result = json.loads(initial.stdout)
    packet = result["checked_answer"]
    assert packet["status"] == "supported"
    assert result["model_input"] == {"task": "Explain the result", "checked_assessment": packet}
    final = subprocess.run(base + ["--assessment-id", packet["assessment_id"]],
                           input="The status is unsupported", text=True, capture_output=True,
                           check=True, timeout=15, env=env)
    finished = json.loads(final.stdout)
    assert finished["checked_answer"] == packet
    assert finished["recipient_output_unverified"] == "The status is unsupported"
