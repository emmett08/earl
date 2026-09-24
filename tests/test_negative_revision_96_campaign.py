"""Offline gates for the bounded 96-call developmental campaign."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

DIR=Path(__file__).resolve().parents[1]/"benchmarks/experiments/negative-revision-96"


def _checker():
    spec=importlib.util.spec_from_file_location("negative96_checker",DIR/"checker.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_corpus_has_distinct_semantic_patterns():
    roots=json.loads((DIR/"specifications.json").read_text())["roots"]
    assert len(roots)==8
    assert len({root["pattern"] for root in roots})==8
    assert all(root.get("ancestry") and root.get("brief") for root in roots)


def test_checker_rejects_small_bound_detector_and_unrelated_audit():
    checker=_checker()
    root=DIR/"roots/bearing_vibration"
    graph=json.loads((root/"graph.json").read_text())
    state=json.loads((root/"covered_clear.json").read_text())
    assert checker.evaluate(graph,state["records"],now="2040-01-31T08:30:00Z",context=graph["context"])["qualified_absence"]=="supported"
    state["records"]["trace_reader"]["value"]["payload"]["calibration"]["detection_limit"]=0.1
    assert checker.evaluate(graph,state["records"],now="2040-01-31T08:30:00Z",context=graph["context"])["qualified_absence"]=="unsupported"
    root=DIR/"roots/network_loss"
    graph=json.loads((root/"graph.json").read_text())
    state=json.loads((root/"partial_violation.json").read_text())
    state["records"]["audit_reader"]["value"]["finding"]="unrelated"
    assert checker.evaluate(graph,state["records"],now="2040-01-31T08:30:00Z",context=graph["context"])["bounded_property_supported"]=="contested"


def test_freeze_preflight_and_96_slots(tmp_path):
    completed=subprocess.run([sys.executable,str(DIR/"run.py"),str(tmp_path/"run"),"--freeze-only"],
                             text=True,capture_output=True,check=True)
    result=json.loads(completed.stdout)
    freeze=json.loads((tmp_path/"run/freeze.json").read_text())
    assert result["cases"]==96
    assert sum(c["stage"]=="A" for c in freeze["cases"])==48
    assert sum(c["stage"]=="B" for c in freeze["cases"])==48
    assert len(freeze["snapshots"])==24
    for case in freeze["cases"]:
        assert "expected" not in json.dumps(case["messages"])
    ledger=json.loads((tmp_path/"run/ledger.json").read_text())
    ledger["attempts"].append({"index":0,"status":"pending"})
    (tmp_path/"run/ledger.json").write_text(json.dumps(ledger))
    failed=subprocess.run([sys.executable,str(DIR/"run.py"),str(tmp_path/"run"),"--resume"],
                          text=True,capture_output=True)
    assert failed.returncode!=0
    assert "never silently retry" in failed.stderr
