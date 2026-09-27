#!/usr/bin/env python3
"""Collect Python control-flow cognitive complexity for the architecture trial.

The implementation follows the SonarSource white paper (version 1.7) and the
SonarPython visitor at commit 6be3971f. It is independent code, not a copy of
SonarSource's source-available implementation. The exact measurement contract
and limits are recorded in README.md next to this file.

With a positional path, emit a bare JSON report. With no positional path, read
the EAL command-tool JSON request from stdin and emit its observation envelope.
Collection and parsing failures are errors; exceeding a descriptive threshold
is not an error or a release decision.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterator

SCHEMA = "python-cognitive-complexity/1"
_NEUTRAL_STATEMENTS = (
    ast.Expr, ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Return,
    ast.Delete, ast.Assert, ast.Raise, ast.Pass, ast.Break, ast.Continue,
    ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.With,
    ast.AsyncWith, ast.TypeAlias,
)


def _subtree(node: ast.AST) -> Iterator[ast.AST]:
    """Visit a function's own code, excluding definitions it contains."""
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield from _subtree(child)


def _definitions(tree: ast.AST) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef, str | None]]:
    definitions: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef, str | None]] = []

    def visit(node: ast.AST, parents: tuple[str, ...], containing: str | None) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = ".".join((*parents, child.name))
                definitions.append((name, child, containing))
                visit(child, (*parents, child.name), name)
            elif isinstance(child, ast.ClassDef):
                visit(child, (*parents, child.name), containing)
            else:
                visit(child, parents, containing)

    visit(tree, (), None)
    return definitions


def _recursion_cycle_nodes(tree: ast.AST) -> set[int]:
    """Resolve statically named local calls and find direct or mutual cycles.

    Python can rebind functions and dispatch dynamically. These cases have no
    statically justified edge here; neither a missing edge nor a score of zero
    establishes absence of runtime recursion.
    """
    definitions = _definitions(tree)
    class_paths: set[str] = set()

    def class_names(node: ast.AST, parents: tuple[str, ...] = ()) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                nested = (*parents, child.name)
                if isinstance(child, ast.ClassDef):
                    class_paths.add(".".join(nested))
                class_names(child, nested)
            else:
                class_names(child, parents)

    class_names(tree)
    multiplicity = Counter(name for name, _, _ in definitions)
    # A repeated lexical name could refer to either definition after runtime
    # rebinding. Keep both scores but infer no recursion edge through that name.
    by_name = {name: node for name, node, _ in definitions if multiplicity[name] == 1}
    edges: dict[str, set[str]] = {name: set() for name in by_name}

    for caller, node, _ in definitions:
        if caller not in by_name:
            continue
        class_name = max((name for name in class_paths if caller.startswith(name + ".")),
                         key=len, default="")
        first_arg = (node.args.posonlyargs + node.args.args)
        receiver = first_arg[0].arg if first_arg and first_arg[0].arg in {"self", "cls"} else None
        shadows = {argument.arg for argument in first_arg}
        shadows.update(descendant.id for descendant in _subtree(node)
                       if isinstance(descendant, ast.Name) and isinstance(descendant.ctx, ast.Store))
        for descendant in _subtree(node):
            if not isinstance(descendant, ast.Call):
                continue
            callee: str | None = None
            if isinstance(descendant.func, ast.Name):
                bare = descendant.func.id
                if bare in shadows:
                    continue
                scopes = caller.split(".")[:-1]
                candidates = [".".join((*scopes[:i], bare)) for i in range(len(scopes), -1, -1)
                              if ".".join(scopes[:i]) not in class_paths]
                callee = next((candidate for candidate in candidates if candidate in by_name), None)
            elif isinstance(descendant.func, ast.Attribute) and class_name:
                target = descendant.func.value
                if isinstance(target, ast.Name) and target.id in {receiver, class_name.rsplit(".", 1)[-1]}:
                    candidate = f"{class_name}.{descendant.func.attr}"
                    if candidate in by_name:
                        callee = candidate
            if callee is not None:
                edges[caller].add(callee)

    index = 0
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    cyclic: set[str] = set()

    def strongconnect(name: str) -> None:
        nonlocal index
        indices[name] = index
        lowlink[name] = index
        index += 1
        stack.append(name)
        on_stack.add(name)
        for successor in sorted(edges[name]):
            if successor not in indices:
                strongconnect(successor)
                lowlink[name] = min(lowlink[name], lowlink[successor])
            elif successor in on_stack:
                lowlink[name] = min(lowlink[name], indices[successor])
        if lowlink[name] == indices[name]:
            component: list[str] = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == name:
                    break
            if len(component) > 1 or name in edges[name]:
                cyclic.update(component)

    for name in sorted(edges):
        if name not in indices:
            strongconnect(name)
    return {id(by_name[name]) for name in cyclic}


class _Scorer:
    def __init__(self, source: str, recursive: set[int]) -> None:
        self.lines = source.splitlines()
        self.recursive = recursive

    def _is_elif(self, node: ast.If) -> bool:
        return bool(re.match(r"elif(?:\s|\()", self.lines[node.lineno - 1].lstrip()))

    @staticmethod
    def _wrapper(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        # SonarPython's decorator exception: one nested function and returns
        # naming a function. Other statements, including an assignment, end it.
        definitions = [stmt for stmt in node.body if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))]
        return len(definitions) == 1 and all(
            isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
            or (isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Name))
            for stmt in node.body
        )

    def score(self, node: ast.AST) -> int:
        return self._visit(node, 0, False)

    def _children(self, node: ast.AST, depth: int, in_function: bool) -> int:
        return sum(self._visit(child, depth, in_function) for child in ast.iter_child_nodes(node))

    def _suite(self, nodes: list[ast.stmt], depth: int, in_function: bool) -> int:
        return sum(self._visit(child, depth, in_function) for child in nodes)

    @staticmethod
    def _bool_ops(node: ast.BoolOp) -> list[type[ast.boolop]]:
        """Flatten the maximal adjacent and/or expression in source order."""
        result: list[type[ast.boolop]] = []
        for index, value in enumerate(node.values):
            if isinstance(value, ast.BoolOp):
                result.extend(_Scorer._bool_ops(value))
            if index < len(node.values) - 1:
                result.append(type(node.op))
        return result

    def _boolean(self, node: ast.BoolOp, depth: int, in_function: bool) -> int:
        operators = self._bool_ops(node)
        runs = sum(index == 0 or operator is not operators[index - 1]
                   for index, operator in enumerate(operators))

        def non_boolean_descendants(value: ast.AST) -> int:
            # Boolean children were already flattened into this run. A unary
            # `not` ends the run; its Boolean child starts a separate one.
            if isinstance(value, ast.BoolOp):
                return sum(non_boolean_descendants(part) for part in value.values)
            return self._visit(value, depth, in_function)

        return runs + sum(non_boolean_descendants(value) for value in node.values)

    def _if(self, node: ast.If, depth: int, in_function: bool, elif_chain: bool = False) -> int:
        score = 1 if elif_chain else 1 + depth
        score += self._visit(node.test, depth, in_function)
        score += self._suite(node.body, depth + 1, in_function)
        if node.orelse:
            next_if = node.orelse[0] if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If) else None
            if next_if is not None and self._is_elif(next_if):
                score += self._if(next_if, depth, in_function, True)
            else:
                score += 1 + self._suite(node.orelse, depth + 1, in_function)
        return score

    def _visit(self, node: ast.AST, depth: int, in_function: bool) -> int:
        if isinstance(node, ast.If):
            return self._if(node, depth, in_function)
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            score = 1 + depth
            expressions = (node.test,) if isinstance(node, ast.While) else (node.target, node.iter)
            score += sum(self._visit(expression, depth, in_function) for expression in expressions)
            score += self._suite(node.body, depth + 1, in_function)
            if node.orelse:
                score += 1 + self._suite(node.orelse, depth + 1, in_function)
            return score
        if isinstance(node, (ast.Try, ast.TryStar)):
            score = self._suite(node.body, depth, in_function)
            for handler in node.handlers:
                score += 1 + depth
                if handler.type is not None:
                    score += self._visit(handler.type, depth, in_function)
                score += self._suite(handler.body, depth + 1, in_function)
            if node.orelse:
                score += 1 + self._suite(node.orelse, depth + 1, in_function)
            score += self._suite(node.finalbody, depth, in_function)
            return score
        if isinstance(node, ast.Match):
            # Python 3.10 match is one switch-like branch. Guards are an
            # additional conditional nested inside that branch.
            score = 1 + depth + self._visit(node.subject, depth, in_function)
            for case in node.cases:
                score += self._visit(case.pattern, depth + 1, in_function)
                if case.guard is not None:
                    score += 2 + depth + self._visit(case.guard, depth + 1, in_function)
                score += self._suite(case.body, depth + 1, in_function)
            return score
        if isinstance(node, ast.IfExp):
            return 1 + depth + self._children(node, depth + 1, in_function)
        if isinstance(node, ast.BoolOp):
            return self._boolean(node, depth, in_function)
        if isinstance(node, ast.Lambda):
            return self._children(node, depth + 1, in_function)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            recursion = int(id(node) in self.recursive)
            child_depth = depth + int(not self._wrapper_parent(node)) if in_function else 0
            score = recursion
            score += self._suite(node.decorator_list, child_depth, True)
            score += self._visit(node.args, child_depth, True)
            if node.returns:
                score += self._visit(node.returns, child_depth, True)
            score += self._suite(node.body, child_depth, True)
            return score
        if isinstance(node, ast.ClassDef):
            # SonarPython resets depth on entering a class.
            return self._children(node, 0, False)
        if isinstance(node, ast.stmt) and not isinstance(node, _NEUTRAL_STATEMENTS):
            raise ValueError(f"unsupported Python statement {type(node).__name__} at line {node.lineno}")
        # Comprehension for/if clauses are readable shorthand, as in the
        # SonarPython visitor. Ternaries or Boolean expressions inside them
        # still count. Ordinary break, continue, return and raise cost zero.
        return self._children(node, depth, in_function)

    def _wrapper_parent(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        return id(node) in self._wrapped_children

    @property
    def _wrapped_children(self) -> set[int]:
        # The set is set by score_source; its empty default keeps score()
        # useful for small independent snippets.
        return getattr(self, "wrapped_children", set())


def score_source(source: str, filename: str = "<source>") -> dict[str, Any]:
    tree = ast.parse(source, filename=filename)
    definitions = _definitions(tree)
    scorer = _Scorer(source, _recursion_cycle_nodes(tree))
    scorer.wrapped_children = {
        id(child)
        for _, parent, _ in definitions if scorer._wrapper(parent)
        for child in parent.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    total = scorer.score(tree)
    functions = [
        {
            "qualname": name,
            "line": node.lineno,
            "score": scorer.score(node),
            "included_in": containing,
            "recursive": id(node) in scorer.recursive,
        }
        for name, node, containing in definitions
    ]
    return {"total": total, "functions": functions}


def collect(path: str | Path, max_function_score: int = 15) -> dict[str, Any]:
    if isinstance(max_function_score, bool) or not isinstance(max_function_score, int) or max_function_score < 0:
        raise ValueError("max_function_score must be a nonnegative integer")
    root = Path(path)
    if not root.exists():
        raise ValueError(f"path does not exist: {root}")
    files = [root] if root.is_file() else sorted(
        file for file in root.rglob("*.py")
        if not any(part.startswith(".") or part == "__pycache__" for part in file.relative_to(root).parts)
    )
    if not files or any(file.suffix != ".py" for file in files):
        raise ValueError("path must be a Python source file or a directory containing Python files")
    results: list[dict[str, Any]] = []
    functions: list[dict[str, Any]] = []
    for file in files:
        raw = file.read_bytes()
        source = raw.decode("utf-8-sig")
        result = score_source(source, str(file))
        name = file.name if root.is_file() else file.relative_to(root).as_posix()
        results.append({"file": name, "sha256": sha256(raw).hexdigest(), "score": result["total"]})
        functions.extend({"file": name, **function} for function in result["functions"])
    functions.sort(key=lambda item: (item["file"], item["line"], item["qualname"]))
    scores = [row["score"] for row in functions]
    return {
        "schema": SCHEMA,
        "scope": "Python AST control-flow complexity; descriptive partial technical-debt indicator",
        "static_recursion_scope": "unambiguous named calls within each Python file; dynamic rebinding and imported cycles unmeasured",
        "threshold": max_function_score,
        "files": results,
        "total": sum(file["score"] for file in results),
        "maximum": max(scores, default=0),
        "function_count": len(functions),
        "threshold_breaches": sum(score > max_function_score for score in scores),
        "functions": functions,
    }


def compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Partition change by matched names, newly added and removed functions.

    File plus qualified name is a stable key for ordinary edits. Duplicate
    definitions with the same key are ambiguous and excluded from matching.
    """
    def index(rows: list[dict[str, Any]]) -> tuple[dict[tuple[str, str], dict[str, Any]], set[tuple[str, str]]]:
        keys = Counter((row["file"], row["qualname"]) for row in rows)
        unique = {(row["file"], row["qualname"]): row for row in rows
                  if keys[(row["file"], row["qualname"])] == 1}
        ambiguous = {key for key, count in keys.items() if count > 1}
        return unique, ambiguous

    old, old_ambiguous = index(before["functions"])
    new, new_ambiguous = index(after["functions"])
    ambiguous = old_ambiguous | new_ambiguous
    shared = sorted((old.keys() & new.keys()) - ambiguous)
    added = sorted(new.keys() - old.keys() - ambiguous)
    removed = sorted(old.keys() - new.keys() - ambiguous)
    old_files = {row["file"]: row["sha256"] for row in before["files"]}
    new_files = {row["file"]: row["sha256"] for row in after["files"]}
    return {
        "before_total": before["total"],
        "after_total": after["total"],
        "total_delta": after["total"] - before["total"],
        "same_file_set": old_files.keys() == new_files.keys(),
        "changed_files": sorted(name for name in old_files.keys() & new_files.keys()
                                if old_files[name] != new_files[name]),
        "matched_function_count": len(shared),
        "matched_score_delta": sum(new[key]["score"] - old[key]["score"] for key in shared),
        "matched": [{"file": file, "qualname": name,
                     "before": old[(file, name)]["score"], "after": new[(file, name)]["score"]}
                    for file, name in shared],
        "added": [{"file": file, "qualname": name, "score": new[(file, name)]["score"]}
                  for file, name in added],
        "removed": [{"file": file, "qualname": name, "score": old[(file, name)]["score"]}
                    for file, name in removed],
        "ambiguous_keys": [{"file": file, "qualname": name} for file, name in sorted(ambiguous)],
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="Python file or source tree; omit for EAL JSON stdin mode")
    parser.add_argument("--max-function-score", type=int, default=15)
    parser.add_argument("--compare-before", help="optional earlier tree for a descriptive matched-function delta")
    args = parser.parse_args()
    try:
        if args.path is not None:
            output = collect(args.path, args.max_function_score)
            if args.compare_before is not None:
                output["comparison"] = compare(collect(args.compare_before, args.max_function_score), output)
        else:
            if args.compare_before is not None:
                raise ValueError("--compare-before is only available with a positional path")
            request = json.load(sys.stdin)
            if not isinstance(request, dict) or not isinstance(request.get("input"), dict):
                raise ValueError("EAL request must contain an input object")
            if request.get("tool") != "cognitive_complexity" or request.get("tool_version") != "1":
                raise ValueError("tool name/version mismatch")
            parameters = request["input"]
            if not isinstance(parameters.get("path"), str):
                raise ValueError("input.path must be a string")
            value = collect(parameters["path"], parameters.get("max_function_score", 15))
            if "compare_before" in parameters:
                if not isinstance(parameters["compare_before"], str):
                    raise ValueError("input.compare_before must be a string")
                value["comparison"] = compare(
                    collect(parameters["compare_before"], parameters.get("max_function_score", 15)), value
                )
            output = {
                "value": value,
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "context": request.get("context"),
                "request": {key: request.get(key) for key in ("tool", "tool_version", "input", "context")},
            }
        json.dump(output, sys.stdout, sort_keys=True, separators=(",", ":"))
        sys.stdout.write("\n")
        return 0
    except (OSError, UnicodeError, ValueError, SyntaxError, RecursionError, json.JSONDecodeError) as exc:
        print(f"cognitive complexity collection failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
