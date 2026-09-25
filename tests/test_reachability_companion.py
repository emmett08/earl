"""Exercise collection, typed method execution and revision through the real host service."""
from __future__ import annotations

import json

from eal.reachability import reachability_registry
from eal.runtime import ReasoningService
from _runtime_cases import REACHABILITY_SOURCE, write_case


def test_new_graph_observation_changes_host_assessment(tmp_path):
    _, record_path, registry = write_case(tmp_path, 'reachability')
    source = REACHABILITY_SOURCE
    service = ReasoningService(tmp_path, registry,
                               tmp_path / "study.sqlite", method_registry=reachability_registry())
    assert service.validate(source)["valid"]
    context = {"site": "simulation"}
    first = service.collect(source, context)
    assert first["records"]["graph_record"]["status"] == "ok"
    safe = service.reason(source, context, first["collection_id"], "2040-01-01T09:05:00Z")
    assert safe["claims"]["bounded_safe"]["status"] == "supported"
    assert safe["arguments"]["safety_route"]["reasoning_result"]["details"]["counterexample"] == []

    changed = json.loads(record_path.read_text())
    changed["value"]["payload"]["edges"].append([2, 3])
    record_path.write_text(json.dumps(changed))
    second = service.collect(source, context)
    unsafe = service.reason(source, context, second["collection_id"], "2040-01-01T09:05:00Z")
    assert unsafe["claims"]["bounded_safe"]["status"] == "unsupported"
    assert unsafe["arguments"]["safety_route"]["reasoning_result"]["details"]["counterexample"] == [0, 1, 2, 3]
    assert service.explain(safe["assessment_id"], "bounded_safe")["result"]["status"] == "supported"
    assert service.explain(unsafe["assessment_id"], "bounded_safe")["result"]["status"] == "unsupported"
