"""An optional, bounded finite-state model checker for EAL/3.

The host installs this method explicitly. An EAL source cannot load Python code.
It decides reachability in the *supplied graph*, not whether that graph describes
an actual device. The path is a checkable counterexample when one exists.
"""
from __future__ import annotations

from collections import deque

from .methods import MethodContract, default_registry


def finite_reachability(payload: dict) -> dict:
    """Find a shortest path to a forbidden state within the inclusive horizon."""
    count = payload["node_count"]
    start = payload["start"]
    forbidden = payload["forbidden"]
    horizon = payload["horizon"]
    edges = payload["edges"]
    if start >= count or any(node >= count for node in forbidden):
        raise ValueError("Start and forbidden states must belong to the graph")
    if len(set(forbidden)) != len(forbidden) or len({tuple(edge) for edge in edges}) != len(edges):
        raise ValueError("Duplicate forbidden states or transition edges")
    if any(source >= count or target >= count for source, target in edges):
        raise ValueError("A transition endpoint is outside the graph")
    adjacency = [[] for _ in range(count)]
    for source, target in edges:
        adjacency[source].append(target)
    for successors in adjacency:
        successors.sort()
    queue = deque([(start,)])
    seen = {start}
    forbidden_set = set(forbidden)
    while queue:
        path = queue.popleft()
        if path[-1] in forbidden_set:
            return {"reachable": True, "shortest_length": len(path) - 1,
                    "counterexample": list(path), "visited": len(seen)}
        if len(path) - 1 == horizon:
            continue
        for successor in adjacency[path[-1]]:
            if successor not in seen:
                seen.add(successor)
                queue.append((*path, successor))
    return {"reachable": False, "shortest_length": -1,
            "counterexample": [], "visited": len(seen)}


NODE = {"type": "integer", "minimum": 0, "maximum": 7}
COUNT = {"type": "integer", "minimum": 1, "maximum": 8}
HORIZON = {"type": "integer", "minimum": 0, "maximum": 8}
FORBIDDEN = {"type": "array", "items": NODE, "minItems": 1, "maxItems": 8}
EDGES = {"type": "array", "items": {"type": "array", "items": NODE,
                                      "minItems": 2, "maxItems": 2}, "maxItems": 64}

REACHABILITY_CONTRACT = MethodContract(
    identifier="engineering/reachability/1", evidence_kind="finite_graph",
    input_schema={"type": "object", "properties": {
        "node_count": COUNT, "edges": EDGES, "start": NODE,
        "forbidden": FORBIDDEN, "horizon": HORIZON},
        "required": ["node_count", "edges", "start", "forbidden", "horizon"],
        "additionalProperties": False},
    query_schema={"type": "object", "properties": {
        "start": NODE, "forbidden": FORBIDDEN, "horizon": HORIZON},
        "required": ["start", "forbidden", "horizon"],
        "additionalProperties": False},
    output_schema={"type": "object", "properties": {
        "reachable": {"type": "boolean"},
        "shortest_length": {"type": "integer", "minimum": -1, "maximum": 8},
        "counterexample": {"type": "array", "items": NODE, "maxItems": 9},
        "visited": {"type": "integer", "minimum": 1, "maximum": 8}},
        "required": ["reachable", "shortest_length", "counterexample", "visited"],
        "additionalProperties": False},
    outputs={"reachable": "boolean", "shortest_length": "dimensionless",
             "visited": "dimensionless"},
    quantities=("proposition",), exact_unit=True,
    implementation=finite_reachability, implementation_version="finite-graph-bfs-1",
    timeout_seconds=2.0,
)


def reachability_registry():
    """Operator factory: ``--methods eal.reachability:reachability_registry``."""
    return default_registry().with_method(REACHABILITY_CONTRACT)
