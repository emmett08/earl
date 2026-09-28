"""A text-only client can reuse a host-owned EAL assessment across sessions."""

import json
import sys

from eal.knowledge import EALKnowledgeBase, ModelContextAdapter


SOURCE = '''language "EAL/2";
environment lab { require "site" == "bench"; }
tool reader { version "1"; }
evidence reading { tool reader; kind test; environment lab; max_age 3600;
  input {"sample": 1}; require "ok" == true; }
reasoning measured { method "structured/1";
  rationale "This report supports the declared test result."; }
claim works { statement "The supplied test passed at the bench."; environment lab; }
argument result { conclusion works; reasoning measured; evidence reading; }
'''


def test_prompt_adapter_reuses_compatible_measurements_across_sessions_and_source_revisions(tmp_path):
    (tmp_path / "source.eal").write_text(SOURCE)
    collector = tmp_path / "reader.py"
    collector.write_text(
        "import json, pathlib, sys\n"
        "request = json.load(sys.stdin)\n"
        "path = pathlib.Path('calls.txt')\n"
        "path.write_text(path.read_text() + 'x' if path.exists() else 'x')\n"
        "print(json.dumps({'value': {'ok': True}}))\n"
    )
    registry = tmp_path / "tools.toml"
    registry.write_text(
        '[tools.reader]\nkind="command"\nversion="1"\n'
        f'argv={json.dumps([sys.executable, str(collector)])}\n'
        'model_access="reviewed"\n'
    )
    first = EALKnowledgeBase(tmp_path, registry)
    first.register("source.eal", context={"site": "bench"}, claims=["works"])
    initial = ModelContextAdapter(first).prepare("Did the bench test pass?", "source.eal", "works")
    assert initial["assessment"]["status"] == "supported"
    assert initial["assessment"]["collected_count"] == 1
    assert initial["messages"][1] == {"role": "user", "content": "Did the bench test pass?"}
    assert "source" not in initial["assessment"]
    assert (tmp_path / "calls.txt").read_text() == "x"

    second = EALKnowledgeBase(tmp_path, registry)
    reused = ModelContextAdapter(second).prepare("What was the result?", "source.eal", "works")
    assert reused["assessment"]["reused_count"] == 1
    assert reused["assessment"]["collected_count"] == 0
    assert reused["assessment"]["collection_id"] != initial["assessment"]["collection_id"]
    assert (tmp_path / "calls.txt").read_text() == "x"
    assert second.history("source.eal")["assessments"][0]["assessment_id"] == reused["assessment"]["assessment_id"]
    assert "reader.py" not in reused["messages"][0]["content"]

    (tmp_path / "source.eal").write_text(SOURCE.replace("The supplied test passed", "The recorded test passed"))
    revised = second.assess("source.eal", "works")
    assert revised["source_digest"] != reused["assessment"]["source_digest"]
    assert revised["reused_count"] == 1
    assert (tmp_path / "calls.txt").read_text() == "x"

    (tmp_path / "source.eal").write_text(SOURCE.replace('"sample": 1', '"sample": 2'))
    changed_request = second.assess("source.eal", "works")
    assert changed_request["collected_count"] == 1
    assert changed_request["reused_count"] == 0
    assert (tmp_path / "calls.txt").read_text() == "xx"
