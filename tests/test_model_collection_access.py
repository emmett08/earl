"""General MCP collection requires an explicit operator grant for every tool."""

import json
import sys

import pytest

from eal.runtime import ReasoningService


SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool reader { version "1"; }
evidence reading { tool reader; kind test; environment lab; max_age 60; require "ok" == true; }
reasoning measurement { method "structured/1"; rationale "The check returned ok."; }
claim works { statement "The check succeeded."; environment lab; }
argument result { conclusion works; reasoning measurement; evidence reading; }
'''


def test_model_access_denial_precedes_command_execution(tmp_path):
    marker = tmp_path / "invoked"
    script = tmp_path / "reader.py"
    script.write_text("import pathlib\npathlib.Path('invoked').touch()\nprint('" +
                      json.dumps({"value": {"ok": True}}) + "')\n")
    registry = tmp_path / "tools.toml"
    registry.write_text('[tools.reader]\nkind="command"\nversion="1"\nargv='
                        + json.dumps([sys.executable, str(script)]) + '\n')
    service = ReasoningService(tmp_path, registry)
    with pytest.raises(ValueError, match="reviewed collection route"):
        service.collect_claim(SOURCE, {"site": "bench"}, "works", model_access=True)
    assert not marker.exists()
    assert not service.store.list(kind="collection")

    registry.write_text(registry.read_text() + 'model_access="general"\n')
    collected = service.collect_claim(SOURCE, {"site": "bench"}, "works", model_access=True)
    assert collected["records"]["reading"]["status"] == "ok"
    assert marker.exists()
