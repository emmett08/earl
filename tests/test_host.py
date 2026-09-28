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
