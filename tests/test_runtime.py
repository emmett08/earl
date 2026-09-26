from __future__ import annotations

import json
import os
import sqlite3
import sys
import stat
from datetime import datetime, timedelta, timezone

import pytest

from eal.evaluator import canonical_digest
from eal.parser import parse
from eal.runtime import ReasoningService, ToolBinding, ToolRegistry, acquisition_request, bounded_path


SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool runner { version "1.0"; }
evidence measured {
  tool runner; kind test; environment lab; max_age 60;
  input {"value": 7}; require "passed" == true;
}
reasoning observation { method "structured/1"; rationale "The exact requested measurement supports the bounded claim."; }
claim works { statement "The configured measurement passes."; environment lab; }
argument result { conclusion works; reasoning observation; evidence measured; }
'''
CONTEXT = {"site": "bench"}


def service_for_command(tmp_path, script, *, timeout=2, limit=4096):
    adapter = tmp_path / "adapter.py"
    adapter.write_text(script)
    registry = tmp_path / "tools.toml"
    registry.write_text(
        '[tools.runner]\nkind = "command"\nversion = "1.0"\n'
        f'argv = {json.dumps([sys.executable, str(adapter)])}\n'
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
    assert record["tool_binding_digest"] == service.current_binding_digests(parse(SOURCE))["measured"]
    assert record["acquisition_request"] == acquisition_request(parse(SOURCE), "measured", CONTEXT)
    assert "mode" not in record and "mode" not in record["acquisition_request"]
    assert len(record["process_environment_digest"]) == 64
    assert len(record["stdout_digest"]) == 64
    assert record["returncode"] == 0
    restarted = ReasoningService(tmp_path, tmp_path / "tools.toml", tmp_path / "runs.sqlite3")
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


def test_tool_version_bound_to_operator_registry(tmp_path):
    service = service_for_command(tmp_path, "print('{\"value\":{\"passed\":true}}')\n")
    refused = service.collect(SOURCE.replace('version "1.0"', 'version "2.0"'), CONTEXT)
    assert refused["records"]["measured"]["status"] == "error"
    assert "version differs" in refused["records"]["measured"]["error"]["message"]
    collected = service.collect(SOURCE, CONTEXT)
    assert service.reason(SOURCE, CONTEXT, collected["collection_id"])["claims"]["works"]["status"] == "supported"


def test_changed_registry_configuration_under_same_version_requires_recollection(tmp_path):
    service = service_for_command(tmp_path, "print('{\"value\":{\"passed\":true}}')\n")
    first = service.collect(SOURCE, CONTEXT)
    assert service.reason(SOURCE, CONTEXT, first["collection_id"])["claims"]["works"]["status"] == "supported"
    registry_path = tmp_path / "tools.toml"
    registry_path.write_text(registry_path.read_text().replace("max_output_bytes = 4096", "max_output_bytes = 8192"))
    assessment = service.reason(SOURCE, CONTEXT, first["collection_id"])
    assert assessment["claims"]["works"]["status"] == "unsupported"
    assert "Current operator tool binding differs from the collected binding" in assessment["evidence"]["measured"]["reasons"]
    second = service.collect(SOURCE, CONTEXT)
    assert first["records"]["measured"]["tool_binding_digest"] != second["records"]["measured"]["tool_binding_digest"]
    assert service.reason(SOURCE, CONTEXT, second["collection_id"])["claims"]["works"]["status"] == "supported"


def test_binding_identity_uses_private_store_key_and_is_stable_on_restart(tmp_path):
    service = service_for_command(tmp_path, "print('{\"value\":{\"passed\":true}}')\n")
    registry_path = tmp_path / "tools.toml"
    registry_path.write_text(registry_path.read_text() + '[tools.runner.env]\nTOKEN = "guessable-secret"\n')
    collection = service.collect(SOURCE, CONTEXT)
    record = collection["records"]["measured"]
    assert record["status"] == "ok"
    key_path = tmp_path / "runs.sqlite3.binding-key"
    assert key_path.exists() and len(key_path.read_bytes()) == 32
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
    assert "guessable-secret" not in json.dumps(record)
    binding = ToolRegistry.load(registry_path).bindings["runner"]
    unkeyed_configuration = {"name": binding.name, "kind": binding.kind,
                             "version": binding.version, "argv": list(binding.argv),
                             "path": binding.path, "timeout_seconds": binding.timeout_seconds,
                             "max_output_bytes": binding.max_output_bytes,
                             "env": dict(binding.env)}
    assert record["tool_binding_digest"] != canonical_digest(unkeyed_configuration)
    assert record["process_environment_digest"] != canonical_digest({**os.environ, **binding.env})
    restarted = ReasoningService(tmp_path, registry_path, tmp_path / "runs.sqlite3")
    assert restarted.current_binding_digests(parse(SOURCE))["measured"] == record["tool_binding_digest"]
    assert restarted.reason(SOURCE, CONTEXT, collection["collection_id"])["claims"]["works"]["status"] == "supported"
    registry_path.write_text(registry_path.read_text().replace('TOKEN = "guessable-secret"',
                                                              'TOKEN = "different-secret"'))
    reassessed = restarted.reason(SOURCE, CONTEXT, collection["collection_id"])
    assert reassessed["claims"]["works"]["status"] == "unsupported"
    assert "Current operator tool binding differs from the collected binding" in reassessed["evidence"]["measured"]["reasons"]
    assert "different-secret" not in json.dumps(reassessed)


def test_copying_database_without_private_key_invalidates_old_observations(tmp_path):
    service = service_for_command(tmp_path, "print('{\"value\":{\"passed\":true}}')\n")
    collection = service.collect(SOURCE, CONTEXT)
    copy = tmp_path / "copy"
    copy.mkdir()
    database = copy / "runs.sqlite3"
    with sqlite3.connect(service.store.path) as original, sqlite3.connect(database) as target:
        original.backup(target)
    recreated = ReasoningService(copy, tmp_path / "tools.toml", database)
    assessed = recreated.reason(SOURCE, CONTEXT, collection["collection_id"])
    assert assessed["claims"]["works"]["status"] == "unsupported"
    assert "Current operator tool binding differs from the collected binding" in assessed["evidence"]["measured"]["reasons"]


def test_public_or_symlinked_binding_key_is_rejected(tmp_path):
    service = service_for_command(tmp_path, "print('{\"value\":{\"passed\":true}}')\n")
    path = tmp_path / "runs.sqlite3.binding-key"
    path.chmod(0o644)
    with pytest.raises(PermissionError, match="private regular file"):
        ReasoningService(tmp_path, tmp_path / "tools.toml", tmp_path / "runs.sqlite3")
    path.unlink()
    path.symlink_to(tmp_path / "adapter.py")
    with pytest.raises(OSError):
        ReasoningService(tmp_path, tmp_path / "tools.toml", tmp_path / "runs.sqlite3")


def test_toml_rejects_obsolete_mode(tmp_path):
    registry = tmp_path / "tools.toml"
    registry.write_text('[tools.runner]\nkind="command"\nversion="1.0"\nmode="deterministic"\nargv=["echo"]\n')
    with pytest.raises(ValueError, match="Unknown registry settings"):
        ToolRegistry.load(registry)


def test_import_preserves_observation_age_and_scope(tmp_path):
    from eal.parser import parse

    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    observation = {"observed_at": past, "context": CONTEXT, "value": {"passed": True},
                   "request": acquisition_request(parse(SOURCE), "measured", CONTEXT)}
    data = tmp_path / "observation.json"
    data.write_text(json.dumps(observation))
    registry = tmp_path / "tools.toml"
    registry.write_text('[tools.runner]\nkind="json_file"\nversion="1.0"\npath="observation.json"\n')
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
    registry.write_text('[tools.runner]\nkind="command"\nversion="1.0"\nargv="echo unsafe"\n')
    with pytest.raises(ValueError, match="argv"):
        ToolRegistry.load(registry)
    registry.write_text('[tools.runner]\nkind="command"\nversion="1.0"\nargv=["echo"]\ncommand="echo"\n')
    with pytest.raises(ValueError, match="Unknown"):
        ToolRegistry.load(registry)


def test_source_input_never_becomes_shell_code(tmp_path):
    service = service_for_command(tmp_path, "import json,sys\nr=json.load(sys.stdin)\nprint(json.dumps({'value':{'passed':True}, 'details':r['input']}))\n")
    payload = "$(touch injected); `touch injected`"
    source = SOURCE.replace('{"value": 7}', json.dumps({"value": payload}))
    collected = service.collect(source, CONTEXT)
    assert collected["records"]["measured"]["details"] == {"value": payload}
    assert not (tmp_path / "injected").exists()


def test_command_observation_cannot_override_requested_acquisition(tmp_path):
    script = ("import json,sys\n"
              "r=json.load(sys.stdin)\n"
              "print(json.dumps({'value':{'passed':True}, 'request':"
              "{'tool':r['tool'], 'tool_version':r['tool_version'], "
              "'input':{'value':99}, 'context':r['context']}}))\n")
    service = service_for_command(tmp_path, script)
    record = service.collect(SOURCE, CONTEXT)["records"]["measured"]
    assert record["status"] == "error"
    assert "Observation request differs" in record["error"]["message"]
    assert record["stdout_bytes"] > 0
    assert service.store.get(record["run_id"], kind="observation") == record


def test_file_output_limit_retains_bounded_bytes_and_file_identity(tmp_path):
    (tmp_path / "observation.json").write_text("x" * 4096)
    registry = tmp_path / "tools.toml"
    registry.write_text('[tools.runner]\nkind="json_file"\n'
                        'version="1.0"\npath="observation.json"\nmax_output_bytes=128\n')
    service = ReasoningService(tmp_path, registry)
    record = service.collect(SOURCE, CONTEXT)["records"]["measured"]
    assert record["status"] == "error"
    assert record["error"]["message"] == "output_limit"
    assert record["file"] == "observation.json" and record["output_truncated"] is True
    assert record["stdout_bytes"] == 128
    assert service.store.get(record["run_id"], kind="observation") == record


def test_unknown_operator_adapter_fails_closed_and_stores_error(tmp_path):
    registry = ToolRegistry({"runner": ToolBinding("runner", "unknown", "1.0")})
    service = ReasoningService(tmp_path)
    service.runtime.registry = registry
    record = service.collect(SOURCE, CONTEXT)["records"]["measured"]
    assert record["status"] == "error"
    assert "Unsupported operator tool kind" in record["error"]["message"]
    assert service.store.get(record["run_id"], kind="observation") == record
