from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone

import pytest

from eal.evaluator import canonical_digest
from eal.runtime import ReasoningService, ToolRegistry, bounded_path


SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool runner { version "1.0"; mode deterministic; }
evidence measured {
  tool runner; kind test; environment lab; max_age 60;
  input {"value": 7}; require "passed" == true;
}
reasoning observation { method "structured/1"; rationale "The exact requested measurement supports the bounded claim."; }
claim works { statement "The configured measurement passes."; environment lab; }
argument result { conclusion works; reasoning observation; evidence measured; }
'''
CONTEXT = {"site": "bench"}


def service_for_command(tmp_path, script, *, timeout=2, limit=4096, mode="deterministic"):
    adapter = tmp_path / "adapter.py"
    adapter.write_text(script)
    registry = tmp_path / "tools.toml"
    registry.write_text(
        '[tools.runner]\nkind = "command"\nversion = "1.0"\n'
        f'mode = "{mode}"\nargv = {json.dumps([sys.executable, str(adapter)])}\n'
        f'timeout_seconds = {timeout}\nmax_output_bytes = {limit}\n'
    )
    return ReasoningService(tmp_path, registry, tmp_path / "runs.sqlite3")


def test_real_command_collection_reasoning_and_durability(tmp_path):
    service = service_for_command(
        tmp_path,
        "import json, sys\nr=json.load(sys.stdin)\nprint(json.dumps({'value': {'passed': r['input']['value'] == 7}}))\n",
    )
    collection = service.collect(SOURCE, CONTEXT)
    record = collection["records"]["measured"]
    assert record["status"] == "ok"
    assert record["value"] == {"passed": True}
    assert record["data_digest"] == canonical_digest(record["value"])
    assert len(record["process_environment_digest"]) == 64
    assert len(record["stdout_digest"]) == 64
    assert record["returncode"] == 0
    restarted = ReasoningService(tmp_path, database_path=tmp_path / "runs.sqlite3")
    assessment = restarted.reason(SOURCE, CONTEXT, collection["collection_id"])
    assert assessment["claims"]["works"]["status"] == "supported"
    assert restarted.explain(assessment["assessment_id"], "works")["result"]["status"] == "supported"
    assert restarted.store.get(record["run_id"], kind="observation") == record


@pytest.mark.parametrize(
    ("script", "timeout", "limit", "expected"),
    [
        ("import time\ntime.sleep(5)\n", 0.1, 4096, "timeout"),
        ("print('x' * 10000)\n", 2, 128, "output_limit"),
        ("import sys\nprint('failure', file=sys.stderr)\nsys.exit(9)\n", 2, 4096, "status 9"),
        ("print('not JSON')\n", 2, 4096, "Expecting value"),
        ("print('{\"value\":1,\"value\":2}')\n", 2, 4096, "Duplicate JSON key"),
        ("print('{\"value\":NaN}')\n", 2, 4096, "Non-finite"),
        ("print(r'{\"value\":{\"text\":\"\\ud800\"}}')\n", 2, 4096, "valid Unicode"),
        ("print(r'{\"value\":true,\"details\":\"\\udfff\"}')\n", 2, 4096, "valid Unicode"),
        ("print('{\"passed\":true}')\n", 2, 4096, "Tool output must"),
    ],
)
def test_execution_failures_are_persisted_and_cannot_support(tmp_path, script, timeout, limit, expected):
    service = service_for_command(tmp_path, script, timeout=timeout, limit=limit)
    collection = service.collect(SOURCE, CONTEXT)
    record = collection["records"]["measured"]
    assert record["status"] == "error"
    assert expected in record["error"]["message"]
    assert record["stdout_bytes"] + record["stderr_bytes"] <= limit
    assert service.store.get(record["run_id"], kind="observation")["error"] == record["error"]
    result = service.reason(SOURCE, CONTEXT, collection["collection_id"])
    assert result["claims"]["works"]["status"] == "unsupported"


def test_tool_modes_bound_to_operator_registry(tmp_path):
    service = service_for_command(tmp_path, "print('{\"value\":{\"passed\":true}}')\n", mode="nondeterministic")
    refused = service.collect(SOURCE, CONTEXT)
    assert refused["records"]["measured"]["status"] == "error"
    source = SOURCE.replace("mode deterministic", "mode nondeterministic")
    collected = service.collect(source, CONTEXT)
    assert collected["records"]["measured"]["mode"] == "nondeterministic"
    assert service.reason(source, CONTEXT, collected["collection_id"])["claims"]["works"]["status"] == "supported"


def test_import_preserves_observation_age_and_scope(tmp_path):
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    observation = {"observed_at": past, "context": CONTEXT, "value": {"passed": True}}
    data = tmp_path / "observation.json"
    data.write_text(json.dumps(observation))
    registry = tmp_path / "tools.toml"
    registry.write_text('[tools.runner]\nkind="json_file"\nmode="deterministic"\nversion="1.0"\npath="observation.json"\n')
    service = ReasoningService(tmp_path, registry)
    collection = service.collect(SOURCE, CONTEXT)
    assert collection["records"]["measured"]["collected_at"] == past
    assert service.reason(SOURCE, CONTEXT, collection["collection_id"])["claims"]["works"]["status"] == "unsupported"
    observation["context"] = {"site": "elsewhere"}
    data.write_text(json.dumps(observation))
    assert service.collect(SOURCE, CONTEXT)["records"]["measured"]["status"] == "error"
    data.write_text('{"value":{"passed":true}}')
    record = service.collect(SOURCE, CONTEXT)["records"]["measured"]
    assert record["status"] == "error"
    assert "require observed_at and context" in record["error"]["message"]


def test_workspace_paths_reject_traversal_and_symlinks(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    (workspace / "linked.json").symlink_to(outside)
    for path in ("../outside.json", "linked.json", str(outside)):
        with pytest.raises(ValueError, match="outside the workspace"):
            bounded_path(workspace, path)


def test_missing_tool_and_wrong_input_do_not_support(tmp_path):
    service = ReasoningService(tmp_path)
    collection = service.collect(SOURCE, CONTEXT)
    assert "not in the operator registry" in collection["records"]["measured"]["error"]["message"]
    with pytest.raises(ValueError, match="unique declared"):
        service.collect(SOURCE, CONTEXT, ["missing"])


def test_registry_rejects_shell_strings_and_unknown_keys(tmp_path):
    registry = tmp_path / "tools.toml"
    registry.write_text('[tools.runner]\nkind="command"\nmode="deterministic"\nversion="1.0"\nargv="echo unsafe"\n')
    with pytest.raises(ValueError, match="argv"):
        ToolRegistry.load(registry)
    registry.write_text('[tools.runner]\nkind="command"\nmode="deterministic"\nversion="1.0"\nargv=["echo"]\ncommand="echo"\n')
    with pytest.raises(ValueError, match="Unknown"):
        ToolRegistry.load(registry)


def test_source_input_never_becomes_shell_code(tmp_path):
    service = service_for_command(tmp_path, "import json,sys\nr=json.load(sys.stdin)\nprint(json.dumps({'value':{'passed':True}, 'details':r['input']}))\n")
    payload = "$(touch injected); `touch injected`"
    source = SOURCE.replace('{"value": 7}', json.dumps({"value": payload}))
    collected = service.collect(source, CONTEXT)
    assert collected["records"]["measured"]["details"] == {"value": payload}
    assert not (tmp_path / "injected").exists()
