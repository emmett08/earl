#!/usr/bin/env python3
"""Run the fixed EAL/2 + finite checker ablation; retain every generated case.

The reference enumerates reachable walks by horizon, independently of the
installed method's shortest-path traversal. No model provider is contacted.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eal.evaluator import canonical_digest, environment_fingerprint, evaluate
from eal.parser import parse
from eal.reachability import reachability_registry
from eal.methods import default_registry
from eal.semantics import validate

SEED = 20260923
PAIRS = 24
NOW = "2040-01-01T09:05:00Z"
OBSERVED = "2040-01-01T09:00:00Z"
STALE = "2040-01-01T07:00:00Z"
CONTEXT = {"site": "simulation"}
PROTOCOL = ROOT / "benchmarks/experiments/eal2-finite-model-checker.json"


def oracle(payload: dict) -> tuple[bool, list[int]]:
    """Enumerate every walk through the horizon; do not reuse checker code."""
    walks = [[payload["start"]]]
    forbidden = set(payload["forbidden"])
    all_paths = []
    for step in range(payload["horizon"] + 1):
        all_paths.extend(path for path in walks if path[-1] in forbidden)
        if step < payload["horizon"]:
            walks = [path + [target] for path in walks
                     for source, target in payload["edges"] if source == path[-1]]
    if not all_paths:
        return False, []
    return True, min(all_paths, key=lambda path: (len(path), path))


def generated_pairs():
    rng = random.Random(SEED)
    for pair in range(PAIRS):
        count = rng.randrange(6, 9)
        horizon = rng.randrange(1, 6)
        forbidden = count - 1
        edges = {(i, i + 1) for i in range(min(horizon - 1, count - 2))}
        # All added edges stay within non-forbidden states, including cycles.
        for source in range(count - 1):
            for target in range(count - 1):
                if rng.random() < 0.13:
                    edges.add((source, target))
        path_ends = {0}
        for _ in range(horizon - 1):
            path_ends |= {target for source, target in edges if source in path_ends}
        entry = rng.choice(sorted(path_ends))
        common = {"node_count": count, "start": 0, "forbidden": [forbidden],
                  "horizon": horizon}
        safe = {**common, "edges": [list(edge) for edge in sorted(edges)]}
        unsafe = {**common, "edges": [list(edge) for edge in sorted(edges | {(entry, forbidden)})]}
        assert not oracle(safe)[0] and oracle(unsafe)[0]
        yield pair, safe, unsafe


def source_for(pair: int, variant: str, payload: dict, computed: bool) -> str:
    model = f"model-{pair:02d}-{variant}"
    method = "engineering/reachability/1" if computed else "structured/1"
    formal = (f''' proposition {{ subject "controller-{pair:02d}"; quantity "proposition"; unit "1";
  scope "{model}"; valid_from "2040-01-01T08:00:00Z"; valid_until "2040-01-01T10:00:00Z";
  query {json.dumps({key: payload[key] for key in ('start', 'forbidden', 'horizon')}, separators=(',', ':'))};
  result "reachable" == false;
 }}''') if computed else ""
    binding = "binding graph_record;" if computed else ""
    return f'''language "EAL/2";
environment lab {{ require "site" == "simulation"; }}
tool graph_reader {{ version "1"; mode deterministic; }}
evidence graph_record {{ tool graph_reader; kind finite_graph; environment lab;
  max_age 3600; require "schema" == "EAL/typed-input/1"; }}
reasoning graph_step {{ method "{method}";
  rationale "The authored route asserts safety; the registered route computes bounded graph reachability."; }}
claim bounded_safe {{ statement "The supplied transition graph for {model} has no path from state zero to its forbidden state within {payload['horizon']} steps.";
  environment lab;{formal}
}}
argument route {{ conclusion bounded_safe; reasoning graph_step; evidence graph_record; {binding} }}
'''


def value_for(pair: int, variant: str, payload: dict) -> dict:
    return {"schema": "EAL/typed-input/1", "method": "engineering/reachability/1",
            "subject": f"controller-{pair:02d}", "quantity": "proposition", "unit": "1",
            "scope": f"model-{pair:02d}-{variant}",
            "valid_from": "2040-01-01T08:00:00Z", "valid_until": "2040-01-01T10:00:00Z",
            "payload": payload}


def bound_record(program, value: dict, collected_at: str = OBSERVED) -> dict:
    evidence = program.evidence["graph_record"]
    tool = program.tools[evidence.tool]
    return {"evidence_id": "graph_record", "source_digest": program.source_digest,
            "tool": tool.name, "tool_version": tool.version, "mode": tool.mode,
            "evidence_kind": evidence.kind, "environment": evidence.environment,
            "environment_fingerprint": environment_fingerprint(evidence.environment, CONTEXT),
            "input_digest": canonical_digest(evidence.input), "collected_at": collected_at,
            "run_id": "simulated-record", "status": "ok", "value": value,
            "data_digest": canonical_digest(value)}


def assess(program, value: dict, registry, *, at: str = OBSERVED) -> dict:
    return evaluate(program, {"graph_record": bound_record(program, value, at)},
                    now=NOW, context=CONTEXT, registry=registry)


def check_hand_cases():
    zero = {"node_count": 1, "edges": [], "start": 0, "forbidden": [0], "horizon": 0}
    direct = {"node_count": 2, "edges": [[0, 1]], "start": 0, "forbidden": [1], "horizon": 1}
    delayed = {**direct, "horizon": 0}
    assert oracle(zero) == (True, [0])
    assert oracle(direct) == (True, [0, 1])
    assert oracle(delayed) == (False, [])


def run() -> dict:
    check_hand_cases()
    registry = reachability_registry()
    authored_registry = default_registry()
    cases = []
    totals = {"computed_correct": 0, "authored_correct": 0,
              "authored_wrong_scope_supported": 0,
              "wrong_scope_refused": 0, "stale_refused": 0,
              "witnesses_valid": 0, "edge_order_invariant": 0}
    counterfeit = None
    for pair, safe, unsafe in generated_pairs():
        for variant, payload in (("safe", safe), ("unsafe", unsafe)):
            truth, oracle_path = oracle(payload)
            value = value_for(pair, variant, payload)
            computed = parse(source_for(pair, variant, payload, True))
            authored = parse(source_for(pair, variant, payload, False))
            assert not validate(computed, registry=registry)
            assert not validate(authored, registry=authored_registry)
            calculated = assess(computed, value, registry)
            asserted = assess(authored, value, authored_registry)
            status = calculated["claims"]["bounded_safe"]["status"]
            authored_status = asserted["claims"]["bounded_safe"]["status"]
            expected = "unsupported" if truth else "supported"
            details = calculated["arguments"]["route"]["reasoning_result"]["details"]
            witness = details["counterexample"]
            witness_valid = (not truth and witness == [] or truth and
                             len(witness) - 1 == details["shortest_length"] == len(oracle_path) - 1 and
                             witness[0] == payload["start"] and witness[-1] in payload["forbidden"] and
                             all([a, b] in payload["edges"] for a, b in zip(witness, witness[1:])))
            assert witness_valid, (pair, variant, details)
            totals["witnesses_valid"] += 1
            totals["computed_correct"] += status == expected
            totals["authored_correct"] += authored_status == expected
            wrong = deepcopy(value)
            wrong["scope"] = "other-model"
            wrong_scope_status = assess(computed, wrong, registry)["claims"]["bounded_safe"]["status"]
            authored_wrong_scope_status = assess(authored, wrong, authored_registry)["claims"]["bounded_safe"]["status"]
            stale_status = assess(computed, value, registry, at=STALE)["claims"]["bounded_safe"]["status"]
            totals["wrong_scope_refused"] += wrong_scope_status == "unsupported"
            totals["authored_wrong_scope_supported"] += authored_wrong_scope_status == "supported"
            totals["stale_refused"] += stale_status == "unsupported"
            reordered = deepcopy(value)
            reordered["payload"]["edges"].reverse()
            invariant_status = assess(computed, reordered, registry)["claims"]["bounded_safe"]["status"]
            totals["edge_order_invariant"] += invariant_status == status
            cases.append({"pair": pair, "variant": variant, "graph": payload,
                          "oracle_reachable": truth, "oracle_path": oracle_path,
                          "computed_status": status, "authored_status": authored_status,
                          "wrong_scope_status": wrong_scope_status,
                          "authored_wrong_scope_status": authored_wrong_scope_status,
                          "stale_status": stale_status,
                          "edge_order_status": invariant_status, "counterexample": witness,
                          "source_digest": computed.source_digest,
                          "model_input_digest": canonical_digest(value),
                          "method_registry_fingerprint": calculated["method_registry_fingerprint"]})
            if pair == 0 and variant == "unsafe":
                forged = deepcopy(value)
                forged["payload"] = safe
                forged_result = assess(computed, forged, registry)
                counterfeit = {"held_graph_unsafe": truth,
                               "supplied_graph_safe": not oracle(forged["payload"])[0],
                               "claim_status": forged_result["claims"]["bounded_safe"]["status"],
                               "record_binding": forged_result["arguments"]["route"]["reasoning_result"]["binding"]["status"]}
    complete = (len(cases) == 2 * PAIRS and totals["computed_correct"] == 2 * PAIRS and
                totals["authored_correct"] == PAIRS and
                totals["authored_wrong_scope_supported"] == 2 * PAIRS and
                totals["wrong_scope_refused"] == 2 * PAIRS and
                totals["stale_refused"] == 2 * PAIRS and
                totals["witnesses_valid"] == 2 * PAIRS and
                totals["edge_order_invariant"] == 2 * PAIRS and
                counterfeit == {"held_graph_unsafe": True, "supplied_graph_safe": True,
                                "claim_status": "supported", "record_binding": "supported"})
    return {"schema": "EAL/companion-experiment-result/1", "protocol": "INV-EAL2-COMPANION-001/1.0.1",
            "protocol_sha256": hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "method_source_sha256": hashlib.sha256((ROOT / "src/eal/reachability.py").read_bytes()).hexdigest(),
            "seed": SEED, "pairs": PAIRS, "graphs": len(cases), "assessment_time": NOW,
            "results": totals, "counterfeit": counterfeit, "cases": cases,
            "decision": "DM-001 and DM-003" if complete else "DM-002 or DM-004: inspect cases",
            "complete": complete,
            "interpretation": "Exact finite-model integration result, with no physical, model-generation or population claim"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "benchmarks/results/2026-09-23-finite-model-checker-v101/result.json")
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Refusing to replace a retained result: {args.output}")
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"complete": result["complete"], "graphs": result["graphs"],
                      "results": result["results"], "counterfeit": result["counterfeit"],
                      "output": str(args.output)}, indent=2))
    if not result["complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
