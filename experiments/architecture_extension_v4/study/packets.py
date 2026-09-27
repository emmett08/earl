"""Matched plain/formal packets from one bounded, public source observation.

The intervention changes only the presentation of an argument route. Both
arms obtain the same facts, scope, guidance, premise status and selected
action. The formal arm includes an EAL/2 evaluation and a bounded ASPIC+
compilation of the exact same source-inspection evidence. This collector
does not infer behaviour from the mere presence of a Python method.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any
from uuid import uuid4


HERE = Path(__file__).resolve().parent
PREMISE = HERE / "premise.eal"
TIMEOUT_PREMISE = HERE / "timeout-premise.eal"
EXCLUDED = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
            ".venv", "node_modules"}
MAX_FILES = 512
MAX_TREE_BYTES = 16 * 1024 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024
NAME = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z", re.ASCII)
STAGES = {"B", "C", "D"}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def formal_excerpt(path: Path) -> str:
    """Literal source declarations used for agent notation, not a new theory.

    Environment/tool/reasoning declarations are available in the pinned host
    source; the packet shows the relevant claim, evidence, route and attack.
    EAL parsing and compilation always consume the complete file.
    """
    blocks = []
    current = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not current and line.startswith(("evidence ", "claim ", "argument ", "objection ")):
            current = [line]
        elif current:
            current.append(line)
        if current and line == "}":
            blocks.append(" ".join(current))
            current = []
    if current or not blocks:
        raise ValueError("pinned EAL source has incomplete visible declarations")
    return "\n".join(blocks)


def inference_status_text(formal: dict[str, Any], status: str) -> str:
    evidence = ", ".join(f"{name} {'available' if row['available'] else 'unavailable'}"
                         for name, row in formal["evidence_availability"].items())
    routes = ", ".join(f"{row['id']} {row['status']}" for row in formal["routes"])
    objections = ", ".join(f"{row['id']} {row['status']}" for row in formal["objections"])
    return (f"Evidence: {evidence}. Route: {routes}. Objection: {objections}. "
            f"Claim {status}; grounded {formal['grounded_status']}; "
            f"defeat {'active' if formal['defeats'] else 'absent'}.")


def _source_manifest(source: Path) -> dict[str, Any]:
    if not source.is_dir() or source.is_symlink():
        raise ValueError("packet source must be a regular directory")
    files: dict[str, str] = {}
    total = 0
    for item in sorted(source.rglob("*")):
        relative = item.relative_to(source)
        if any(part in EXCLUDED for part in relative.parts) or item.suffix == ".pyc":
            continue
        if item.is_symlink():
            raise ValueError(f"source symlink: {relative}")
        if item.is_dir():
            continue
        if not item.is_file():
            raise ValueError(f"irregular source entry: {relative}")
        data = item.read_bytes()
        total += len(data)
        if len(data) > MAX_FILE_BYTES or total > MAX_TREE_BYTES or len(files) >= MAX_FILES:
            raise ValueError("packet source exceeds inspection bounds")
        files[relative.as_posix()] = _sha(data)
    if not files:
        raise ValueError("packet source is empty")
    # Identical to the runner's input-source identity. A JSON-map digest is
    # separately useful, but cannot be compared with its newline framing.
    framed = b"".join((path + "\0" + files[path] + "\n").encode("utf-8")
                      for path in sorted(files))
    return {"files": files, "tree_sha256": _sha(framed)}


def _target(schema: dict[str, Any]) -> dict[str, str] | None:
    selected = schema.get("target")
    if selected is None:
        return None
    if not isinstance(selected, dict) or set(selected) != {"path", "class", "method"}:
        raise ValueError("evidence_schema.target requires path, class and method")
    path = selected["path"]
    if not isinstance(path, str) or not path.endswith(".py"):
        raise ValueError("premise source path must name a Python file")
    relative = PurePosixPath(path)
    if (relative.is_absolute() or str(relative) != path or
            any(part in {"..", "."} for part in relative.parts)):
        raise ValueError("premise source path must be a canonical relative path")
    if any(not isinstance(selected[key], str) or not NAME.fullmatch(selected[key])
           for key in ("class", "method")):
        raise ValueError("premise target needs Python class and method identifiers")
    return {key: selected[key] for key in ("path", "class", "method")}


def _effect_timeout(function: ast.FunctionDef | ast.AsyncFunctionDef,
                    effect_attribute: str) -> dict[str, Any]:
    """Inspect the order of a direct append and direct TimeoutError raises.

    A nested raise is assigned the index of its enclosing top-level statement.
    This says nothing about dynamic branches, aliasing, or whether append is an
    externally durable effect. It is a controlled public source pattern.
    """
    append_sites = []
    timeout_sites = []
    for index, statement in enumerate(function.body):
        for node in ast.walk(statement):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "append" and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == effect_attribute
                    and isinstance(node.func.value.value, ast.Name)
                    and node.func.value.value.id == "self"):
                append_sites.append((index, node.lineno))
            if isinstance(node, ast.Raise):
                exception = node.exc
                if isinstance(exception, ast.Call):
                    exception = exception.func
                if isinstance(exception, ast.Name) and exception.id == "TimeoutError":
                    timeout_sites.append((index, node.lineno))
    after = [line for index, line in timeout_sites
             if any(effect_index < index for effect_index, _ in append_sites)]
    before = [line for index, line in timeout_sites
              if not any(effect_index < index for effect_index, _ in append_sites)]
    return {"effect_attribute": effect_attribute,
            "direct_append_lines": sorted(line for _, line in append_sites),
            "after_effect_timeout_lines": sorted(after),
            "before_effect_timeout_lines": sorted(before),
            "scope": "AST source-order patterns only; dynamic reachability, applied effects and external durability remain unverified."}


def _direct_stub(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    statements = list(function.body)
    if (statements and isinstance(statements[0], ast.Expr)
            and isinstance(statements[0].value, ast.Constant)
            and isinstance(statements[0].value.value, str)):
        statements.pop(0)  # docstring is not implementation
    if len(statements) != 1:
        return False
    statement = statements[0]
    if isinstance(statement, ast.Pass):
        return True
    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
        return statement.value.value is Ellipsis
    if isinstance(statement, ast.Raise):
        exception = statement.exc
        if isinstance(exception, ast.Call):
            exception = exception.func
        return isinstance(exception, ast.Name) and exception.id == "NotImplementedError"
    return False


def _inspect(source: Path, target: dict[str, str] | None,
             manifest: dict[str, Any], *, mode: str,
             effect_attribute: str | None) -> dict[str, Any]:
    if target is None:
        return {"observation": "unconfigured", "target": None, "present": None,
                "direct_stub": None, "source_file_sha256": None, "line": None,
                "scope": "No public source premise was configured; its status is unknown."}
    relative = target["path"]
    if relative not in manifest["files"]:
        return {"observation": "file_absent", "target": target, "present": False,
                "direct_stub": False, "source_file_sha256": None, "line": None,
                "scope": "The named source file is absent; no runtime conclusion follows."}
    path = source / relative
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
    except (SyntaxError, UnicodeError) as exc:
        return {"observation": "unparseable", "target": target, "present": None,
                "direct_stub": None, "source_file_sha256": manifest["files"][relative],
                "line": None, "scope": f"Source parsing failed ({type(exc).__name__}); premise unknown."}
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == target["class"]]
    methods = [node for cls in classes for node in cls.body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name == target["method"]]
    if len(classes) > 1 or len(methods) > 1:
        return {"observation": "ambiguous_declaration", "target": target,
                "present": None, "direct_stub": None,
                "source_file_sha256": manifest["files"][relative], "line": None,
                "scope": "Duplicate class or method declarations make the premise ambiguous."}
    method = methods[0] if methods else None
    finding = {"observation": "method_found" if method else "method_absent",
            "target": target, "present": method is not None,
            "direct_stub": _direct_stub(method) if method else False,
            "source_file_sha256": manifest["files"][relative],
            "line": method.lineno if method else None,
            "scope": ("The AST identifies the named method and a directly visible stub. "
                      "It does not verify runtime behaviour, atomicity or external effects.")}
    if mode == "effect_before_timeout" and method is not None:
        finding["effect_order"] = _effect_timeout(method, effect_attribute or "")
        finding["scope"] = finding["effect_order"]["scope"]
    return finding


def _record(program: Any, name: str, value: dict[str, bool],
            context: dict[str, Any], instant: str, binding_digest: str) -> dict[str, Any]:
    from eal.evaluator import canonical_digest, environment_fingerprint

    declaration = program.evidence[name]
    tool = program.tools[declaration.tool]
    acquisition = {"tool": tool.name, "tool_version": tool.version,
                   "input": declaration.input, "context": context}
    full_request = {"evidence_id": name, "environment": declaration.environment,
                    **acquisition}
    return {"evidence_id": name, "source_digest": program.source_digest,
            "tool": tool.name, "tool_version": tool.version,
            "evidence_kind": declaration.kind, "environment": declaration.environment,
            "environment_fingerprint": environment_fingerprint(declaration.environment, context),
            "input_digest": canonical_digest(declaration.input), "input": declaration.input,
            "context": context, "status": "ok", "collected_at": instant,
            "run_id": str(uuid4()), "tool_binding_digest": binding_digest,
            "request_digest": canonical_digest(full_request),
            "acquisition_request": acquisition,
            "acquisition_request_digest": canonical_digest(acquisition),
            "value": value, "data_digest": canonical_digest(value)}


def _formal(fact: dict[str, Any], source_sha: str, system: str,
            stage: str, mode: str) -> tuple[str, dict[str, Any]]:
    from eal.aspic_compiler import compile_eal_aspic
    from eal.evaluator import canonical_digest, evaluate
    from eal.parser import parse

    premise_path = TIMEOUT_PREMISE if mode == "effect_before_timeout" else PREMISE
    eal_source = premise_path.read_text(encoding="utf-8")
    programme = parse(eal_source)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    context = {"study": "architecture-extension-v4", "system": system,
               "stage": stage, "source_tree_sha256": source_sha}
    binding = _sha(_canonical({"probe_code_sha256": _sha(Path(__file__).read_bytes()),
                               "source_tree_sha256": source_sha}))
    records = {}
    if fact["present"] is not None and fact["direct_stub"] is not None:
        if mode == "effect_before_timeout":
            ordered = fact.get("effect_order", {})
            value = {"positive": bool(ordered.get("after_effect_timeout_lines")),
                     "counter": bool(ordered.get("before_effect_timeout_lines"))}
        else:
            value = {"present": fact["present"], "stub": fact["direct_stub"]}
        for name in programme.evidence:
            records[name] = _record(programme, name, value, context, now, binding)
    assessment = evaluate(programme, records, now=now, context=context)
    if assessment["valid"] is not True:
        raise ValueError("the v4 EAL source failed semantic validation")
    compiled = compile_eal_aspic(eal_source, records, goal="probe_candidate",
                                 now=now, context=context).to_dict()
    status = compiled["claim_status"]
    if status != assessment["claims"]["probe_candidate"]["status"]:
        raise ValueError("EAL and ASPIC+ disagree on the bounded premise")
    if status not in {"supported", "contested", "unsupported"}:
        raise ValueError("bounded premise has an unexpected status")
    origin = compiled["source_map"]["evidence"]
    routes = [{"id": name, "status": entry["status"]}
              for name, entry in sorted(compiled["routes"].items())]
    objections = [{"id": name, "status": entry["status"]}
                  for name, entry in sorted(assessment["objections"].items())]
    formal = {"language": "EAL/2", "claim": "probe_candidate",
              "mode": mode,
              "eal_source_sha256": programme.source_digest,
              "authored_status": assessment["claims"]["probe_candidate"]["status"],
              "profile": compiled["profile"],
              "aspic_snapshot_digest": compiled["snapshot_digest"],
              "grounded_status": compiled["formal"]["grounded_status"],
              "routes": routes, "objections": objections,
              "defeats": [{"kind": event["kind"], "attacker": event["attacker"],
                           "target": event["target"],
                           "subargument": event["subargument"]}
                          for event in compiled["formal"]["defeats"]],
              "evidence_availability": {name: {"available": entry["available"],
                                                  "issues": entry["availability_issues"]}
                                        for name, entry in sorted(origin.items())}}
    provenance = {"evidence_record_digest": canonical_digest(records),
                  "eal_source_sha256": programme.source_digest,
                  "formal_snapshot_digest": compiled["snapshot_digest"],
                  "probe_code_sha256": _sha(Path(__file__).read_bytes()),
                  "observed_at": now,
                  "observation_basis": "bounded local AST inspection; no behavioural certification"}
    return status, {"formal": formal, "provenance": provenance}


def generate(source: Path, system: str, stage: str, arm: str,
             evidence_schema: dict[str, Any]) -> dict[str, Any]:
    """Generate a single arm packet; P1/P2 differ only in formal explanation.

    `evidence_schema.target` names a public source method. This is an
    operator-authored review hypothesis, not an independent test oracle.
    Omission or undecidable source is reported as unknown.
    """
    if arm not in {"P0", "P1", "P2"} or stage not in STAGES:
        raise ValueError("unknown arm or stage")
    if not isinstance(system, str) or not system or not isinstance(evidence_schema, dict):
        raise ValueError("system and evidence_schema must be specified")
    if arm == "P0":
        return {"schema": "architecture-v4-no-packet/1", "arm": "P0",
                "packet_text": None, "shared_material_digest": None}
    manifest = _source_manifest(Path(source))
    mode = evidence_schema.get("mode", "method_inspectability")
    if mode not in {"method_inspectability", "effect_before_timeout"}:
        raise ValueError("unknown source premise mode")
    attribute = evidence_schema.get("effect_attribute")
    if mode == "effect_before_timeout" and (
            not isinstance(attribute, str) or not NAME.fullmatch(attribute)):
        raise ValueError("effect_before_timeout requires an effect_attribute identifier")
    target = _target(evidence_schema)
    fact = _inspect(Path(source), target, manifest, mode=mode,
                    effect_attribute=attribute)
    status, result = _formal(fact, manifest["tree_sha256"], system, stage, mode)
    if _source_manifest(Path(source)) != manifest:
        raise ValueError("packet source changed during inspection and assessment")
    if mode == "effect_before_timeout":
        decision = {
            "supported": "An after-effect timeout is visible; inspect reconciliation before any retry.",
            "contested": "Both pre-effect and after-effect timeout paths are visible; inspect their separate recovery obligations before retry.",
            "unsupported": "Source inspection does not establish an after-effect timeout route; inspect outcome semantics before retry.",
        }[status]
    elif status == "supported":
        decision = "The named method is a candidate for inspection; verify its behaviour before relying on it."
    elif status == "contested":
        decision = "The named method is stubbed; design or implement a reconciliation path before relying on it."
    else:
        decision = "The premise remains unresolved; inspect the public source and establish a reconciliation path."
    action_key = ("action_if_supported" if status == "supported" else
                  "action_if_contested" if status == "contested" else "action_if_unknown")
    action = evidence_schema.get(action_key, decision)
    if not isinstance(action, str) or not action.strip():
        raise ValueError(f"{action_key} must be nonempty prose")
    guidance = evidence_schema.get("guidance",
                                   "Inspect source, verify effects and recovery with tests, and keep one coherent path per operation.")
    if not isinstance(guidance, str) or not guidance.strip():
        raise ValueError("guidance must be nonempty prose")
    statement = evidence_schema.get(
        "statement", "The named method is a structural candidate for an inspection path; its behaviour is unverified.")
    if not isinstance(statement, str) or not statement.strip():
        raise ValueError("statement must be nonempty prose")
    plain_conclusion = (
        ("A direct append precedes a later direct TimeoutError in the pinned source; "
         "runtime outcomes remain unverified.") if status == "supported" else
        ("The pinned source contains both an after-effect timeout pattern and "
         "a pre-effect timeout pattern; the earlier inference is challenged.")
         if status == "contested" else
        "The pinned source does not establish an after-effect timeout pattern."
    ) if mode == "effect_before_timeout" else (
        "The named method exists in the pinned source. Its behaviour remains unverified."
        if status == "supported" else
        "The named method exists, but a direct stub defeats its use as an inspection path."
        if status == "contested" else
        "The named source does not establish an inspectable method. The premise is unresolved.")
    formal = result["formal"]
    # The inferential content and every available/blocked premise are in the
    # shared material. P2's EAL syntax is an alternative representation of
    # these propositions, not an additional source of task facts.
    argument_content = {
        "claim": formal["claim"], "claim_status": status,
        "grounded_status": formal["grounded_status"],
        "evidence_availability": formal["evidence_availability"],
        "routes": formal["routes"], "objections": formal["objections"],
        "defeats": formal["defeats"],
    }
    shared = {"source_tree_sha256": manifest["tree_sha256"],
              "system": system, "stage": stage,
              "facts": {"premise": statement, **fact}, "guidance": guidance,
              "status": status, "plain_conclusion": plain_conclusion,
              "selected_action": action,
              "argument_content": argument_content}
    digest = _sha(_canonical(shared))
    visible = {"schema": "architecture-v4-packet/1", "arm": arm,
               **shared, "shared_material_digest": digest,
               "evidence_provenance": result["provenance"]}
    if arm == "P2":
        visible["formal"] = result["formal"]
    # Host material keeps the full canonical argument, but each agent view
    # renders it exactly once. The common source facts, guidance, status and
    # action have identical bytes; plain prose and actual EAL source syntax
    # are the sole presentation contrast.
    common_view = {key: value for key, value in shared.items() if key != "argument_content"}
    common_text = json.dumps(common_view, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"))
    labels = inference_status_text(formal, status)
    if mode == "effect_before_timeout":
        plain = ("An after_effect_timeout observation requires a direct append before a later "
                 "TimeoutError in the named method. A before_effect_timeout observation requires "
                 "a direct TimeoutError without an earlier append. The first supports the bounded "
                 "source-order claim via declared_route; the second attacks that route via "
                 "stubbed_route. Both are source_probe version 1 inspection results in the "
                 "current_source environment, with a 3600-second freshness bound. The claim "
                 "concerns a possible after-effect timeout path, qualified by any pre-effect "
                 "path. source_order uses structured/1 reasoning; it does not infer the truth "
                 "of that rationale from prose. The objection targets only declared_route; "
                 "missing observations stay unavailable rather than false. Static ordering "
                 "cannot establish reachability or durable external effects.")
    else:
        plain = ("declared_method requires a named method declaration in pinned Python source. "
                 "direct_stub requires its sole effective statement to be pass, ellipsis or "
                 "NotImplementedError. declared_route uses the first to support a qualified "
                 "inspection candidate; stubbed_route targets that route when the second is "
                 "available. Both are source_probe version 1 inspection results in the "
                 "current_source environment, with a 3600-second freshness bound. The claim "
                 "is only that a named public method is a candidate for inspection. "
                 "structural_inspection uses structured/1 reasoning; source syntax does "
                 "not verify its behaviour. A missing observation remains unavailable, "
                 "rather than a negative finding. The targeted objection defeats only "
                 "the tentative route; other behaviour still needs testing.")
    representation = (plain if arm == "P1" else
                      formal_excerpt(TIMEOUT_PREMISE if mode == "effect_before_timeout" else PREMISE))
    packet_text = common_text + "\n" + labels + "\n" + representation
    return {**visible, "packet_text": packet_text}
