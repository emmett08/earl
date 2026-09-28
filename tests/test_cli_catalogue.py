"""The CLI lets a later process use a registered source without supplying EAL."""

from __future__ import annotations

import json
import subprocess
import sys


SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool reader { version "1"; }
evidence observation {
  tool reader; kind test; environment lab; max_age 60;
  require "ok" == true;
}
reasoning authored { method "structured/1"; rationale "The observation supports this claim."; }
claim ready { statement "The service is ready."; environment lab; }
argument route { conclusion ready; reasoning authored; evidence observation; }
'''


def _cli(workspace, *args, registry=False):
    command = [sys.executable, "-m", "eal.cli", "--workspace", str(workspace)]
    if registry:
        command += ["--registry", str(workspace / "tools.toml")]
    result = subprocess.run(command + list(args), text=True, capture_output=True, timeout=30)
    return result.returncode, json.loads(result.stdout)


def _workspace(tmp_path):
    (tmp_path / "ready.eal").write_text(SOURCE)
    (tmp_path / "reader.py").write_text(
        "import json, pathlib, sys\n"
        "json.load(sys.stdin)\n"
        "count = pathlib.Path(__file__).with_name('invocations.txt')\n"
        "count.write_text(count.read_text() + 'x' if count.exists() else 'x')\n"
        "print(json.dumps({'value': {'ok': True, 'secret': 'not for the model'}}))\n"
    )
    (tmp_path / "tools.toml").write_text(
        '[tools.reader]\nkind="command"\nversion="1"\n'
        f'argv={json.dumps([sys.executable, str(tmp_path / "reader.py")])}\n'
    )


def test_registered_cli_reuses_observations_across_processes_and_prepares_model_context(tmp_path):
    _workspace(tmp_path)
    (tmp_path / "context.json").write_text('{"site":"bench"}')

    code, registered = _cli(tmp_path, "register", "ready.eal", "--entry-id", "service",
                            "--claim", "ready", "--context", "@context.json")
    assert code == 0
    assert registered["entry_id"] == "service"
    assert registered["context"] == {"site": "bench"}
    assert "source" not in registered

    code, sources = _cli(tmp_path, "sources")
    assert code == 0
    assert sources["entries"][0]["claim_metadata"]["ready"]["statement"] == "The service is ready."
    code, matches = _cli(tmp_path, "find", "service", "--claim", "ready")
    assert code == 0
    assert [entry["entry_id"] for entry in matches["matches"]] == ["service"]

    code, first = _cli(tmp_path, "assess-known", "service", "--claim", "ready", registry=True)
    assert code == 0
    assert first["status"] == "supported"
    assert first["collected_count"] == 1
    assert first["reused_count"] == 0

    code, second = _cli(tmp_path, "assess-known", "service", "--claim", "ready", registry=True)
    assert code == 0
    assert second["status"] == "supported"
    assert second["collection_id"] != first["collection_id"]
    assert second["reused_count"] == 1
    assert second["collected_count"] == 0

    code, prepared = _cli(tmp_path, "model-context", "service", "--claim", "ready",
                          "--question", "Is the service ready?", registry=True)
    assert code == 0
    assert prepared["schema"] == "EAL/model-context/2"
    assert prepared["assessment"]["reused_count"] == 1
    assert prepared["messages"][1] == {"role": "user", "content": "Is the service ready?"}
    assert "not for the model" not in json.dumps(prepared)
    assert (tmp_path / "invocations.txt").read_text() == "x"

    code, history = _cli(tmp_path, "history", "service")
    assert code == 0
    assert len(history["assessments"]) == 3
    assert history["assessments"][0]["assessment_id"] == prepared["assessment"]["assessment_id"]

    code, forced = _cli(tmp_path, "assess-known", "service", "--claim", "ready",
                        "--reuse", "fresh", registry=True)
    assert code == 0
    assert forced["reused_count"] == 0
    assert forced["collected_count"] == 1
    assert (tmp_path / "invocations.txt").read_text() == "xx"


def test_register_tree_and_unknown_claim_fail_without_collection(tmp_path):
    _workspace(tmp_path)
    (tmp_path / "invalid.eal").write_text("invalid source")
    code, result = _cli(tmp_path, "register-tree", ".", "--context", '{"site":"bench"}')
    assert code == 0
    assert [item["entry_id"] for item in result["registered"]] == ["ready.eal"]
    assert [item["path"] for item in result["rejected"]] == ["invalid.eal"]

    code, result = _cli(tmp_path, "assess-known", "ready.eal", "--claim", "missing", registry=True)
    assert code == 2
    assert "not selected" in result["error"]
    assert not (tmp_path / "invocations.txt").exists()
