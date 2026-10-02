#!/usr/bin/env python3
"""Choose non-overlapping label positions from measured, finite candidates.

Coordinates use one declared physical unit throughout. This tool moves labels,
never the underlying data or geometry. Candidate rectangles should use actual
text measurements from a pilot PDF; geometric feasibility is not readability.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def rectangle(value):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("A rectangle must be [left, bottom, right, top]")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise ValueError("Rectangle coordinates must be finite numbers")
    if value[2] <= value[0] or value[3] <= value[1]:
        raise ValueError("Rectangle dimensions must be positive")
    return tuple(value)


def intersects(a, b, clearance=0):
    return not (a[2] + clearance <= b[0] or b[2] + clearance <= a[0]
                or a[3] + clearance <= b[1] or b[3] + clearance <= a[1])


def inside(rect, canvas, clearance=0):
    return (rect[0] >= canvas[0] + clearance and rect[1] >= canvas[1] + clearance
            and rect[2] <= canvas[2] - clearance and rect[3] <= canvas[3] - clearance)


def candidates_around(anchor, size, gap=2):
    """Generate eight anchors using measured label width/height, without rotation."""
    x, y = anchor
    w, h = size
    if not all(math.isfinite(v) for v in (x, y, w, h, gap)) or min(w, h) <= 0 or gap < 0:
        raise ValueError("Require finite anchor, positive measured size and nonnegative gap")
    origins = {
        "ne": (x+gap, y+gap), "nw": (x-gap-w, y+gap),
        "se": (x+gap, y-gap-h), "sw": (x-gap-w, y-gap-h),
        "n": (x-w/2, y+gap), "s": (x-w/2, y-gap-h),
        "e": (x+gap, y-h/2), "w": (x-gap-w, y-h/2),
    }
    return [{"id": key, "rect": [a, b, a+w, b+h],
             "cost": math.hypot(a+w/2-x, b+h/2-y)} for key, (a, b) in origins.items()]


def solve_layout(spec, max_nodes=50000):
    """Bounded branch-and-bound; report whether the finite search completed."""
    if isinstance(max_nodes, bool) or not isinstance(max_nodes, int) or max_nodes < 1:
        raise ValueError("max_nodes must be a positive integer")
    canvas = rectangle(spec["canvas"])
    clearance = spec.get("clearance", 0)
    if isinstance(clearance, bool) or not isinstance(clearance, (int, float)) or not math.isfinite(clearance) or clearance < 0:
        raise ValueError("clearance must be finite and nonnegative")
    obstacles = [rectangle(r) for r in spec.get("obstacles", [])]
    labels = spec["labels"]
    if not labels or len({label["id"] for label in labels}) != len(labels):
        raise ValueError("Require nonempty labels with unique IDs")
    if len(labels) > 128:
        raise ValueError("This bounded search supports at most 128 labels; solve crowded panels separately")
    options = {}
    for label in labels:
        supplied = label.get("candidates")
        if supplied is None:
            supplied = candidates_around(label["anchor"], label["size"], label.get("gap", 2))
        if not supplied or len({c["id"] for c in supplied}) != len(supplied):
            raise ValueError("Require nonempty candidates with unique IDs per label")
        valid = []
        for candidate in supplied:
            rect = rectangle(candidate["rect"])
            cost = candidate.get("cost", 0)
            if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
                raise ValueError("Candidate costs must be finite and nonnegative")
            if inside(rect, canvas, clearance) and not any(intersects(rect, o, clearance) for o in obstacles):
                valid.append({"id": candidate["id"], "rect": list(rect), "cost": cost})
        options[label["id"]] = sorted(valid, key=lambda c: (c["cost"], c["id"]))
    order = sorted(options, key=lambda key: (len(options[key]), key))
    if any(not options[key] for key in order):
        return {"status": "infeasible", "optimal": False, "nodes": 0, "placements": {},
                "reason": "A label has no candidate satisfying canvas and obstacle constraints"}
    suffix_minimum = [0.0] * (len(order)+1)
    for i in range(len(order)-1, -1, -1):
        suffix_minimum[i] = suffix_minimum[i+1] + options[order[i]][0]["cost"]
    if not math.isfinite(sum(max(c["cost"] for c in options[key]) for key in order)):
        raise ValueError("Total candidate cost exceeds the finite numeric range")
    best, best_cost, nodes, exhausted = None, math.inf, 0, False

    def visit(index, chosen, cost):
        nonlocal best, best_cost, nodes, exhausted
        if nodes >= max_nodes:
            exhausted = True
            return
        nodes += 1
        if cost + suffix_minimum[index] >= best_cost:
            return
        if index == len(order):
            best, best_cost = dict(chosen), cost
            return
        key = order[index]
        for candidate in options[key]:
            if any(intersects(candidate["rect"], other["rect"], clearance) for other in chosen.values()):
                continue
            chosen[key] = candidate
            visit(index+1, chosen, cost+candidate["cost"])
            del chosen[key]
            if exhausted:
                return

    visit(0, {}, 0)
    return {"status": "feasible" if best is not None else ("budget_exhausted" if exhausted else "infeasible"),
            "optimal": best is not None and not exhausted, "nodes": nodes,
            "cost": best_cost if best is not None else None, "placements": best or {},
            "reason": "Search budget exhausted" if exhausted else "Finite candidate search completed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("layout", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-nodes", type=int, default=50000)
    args = parser.parse_args()
    try:
        if args.output.resolve() == args.layout.resolve():
            raise ValueError("Output must not overwrite the input layout")
        result = solve_layout(json.loads(args.layout.read_text()), args.max_nodes)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
        print(result["status"])
        return 0 if result["status"] == "feasible" else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"ERROR: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
