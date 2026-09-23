"""Exercise collection, typed method execution and revision through the real host service."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

from eal.reachability import reachability_registry
from eal.runtime import ReasoningService

ROOT = Path(__file__).resolve().parents[1]


def test_new_graph_observation_changes_host_assessment(tmp_path):
    examples = tmp_path / "examples"
    examples.mkdir()
    for name in ("finite-reachability-observation.json", "finite-reachability-tools.toml"):
        shutil.copyfile(ROOT / "examples" / name, examples / name)
    source = (ROOT / "examples/finite-reachability.eal").read_text()
    service = ReasoningService(tmp_path, examples / "finite-reachability-tools.toml",
                               tmp_path / "study.sqlite", method_registry=reachability_registry())
    assert service.validate(source)["valid"]
    context = {"site": "simulation"}
    first = service.collect(source, context)
    assert first["records"]["graph_record"]["status"] == "ok"
    safe = service.reason(source, context, first["collection_id"], "2040-01-01T09:05:00Z")
    assert safe["claims"]["bounded_safe"]["status"] == "supported"
    assert safe["arguments"]["safety_route"]["reasoning_result"]["details"]["counterexample"] == []

    record_path = examples / "finite-reachability-observation.json"
    changed = json.loads(record_path.read_text())
    changed["value"]["payload"]["edges"].append([2, 3])
    record_path.write_text(json.dumps(changed))
    second = service.collect(source, context)
    unsafe = service.reason(source, context, second["collection_id"], "2040-01-01T09:05:00Z")
    assert unsafe["claims"]["bounded_safe"]["status"] == "unsupported"
    assert unsafe["arguments"]["safety_route"]["reasoning_result"]["details"]["counterexample"] == [0, 1, 2, 3]
    assert service.explain(safe["assessment_id"], "bounded_safe")["result"]["status"] == "supported"
    assert service.explain(unsafe["assessment_id"], "bounded_safe")["result"]["status"] == "unsupported"
