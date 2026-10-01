"""Export a recomputed bounded ASPIC+ graph with supplied EAL provenance.

The solver owns formal semantics; the separate Vue application owns rendering.
This boundary checks source-map structure without authenticating source claims.
"""
from __future__ import annotations

from copy import deepcopy
import json

from jsonschema import Draft202012Validator

from .aspic import ASPIC_CONTRACT, OUTPUT_SCHEMA
from .evaluator import canonical_digest
from .methods import execute_extension, schema_errors
from .limits import ExecutionLimits, current_limits, using_limits, bounded

VIEW_VERSION = "aspic-view/3"
AVAILABILITY_ISSUES = ("predicate_not_met", "missing_observation",
                       "stale_observation", "tool_error", "invalid_observation",
                       "out_of_scope")
MAX_INPUT_BYTES = 4 * 1024 * 1024


@bounded
def export_aspic_view(result: dict, *, limits=None) -> dict:
    """Recompute and export one supplied theory/result, without collection.

    Equality is exact, including argument order, labels, ranks and every defeat
    witness. Older or edited results must be solved again before export.
    Authored source maps remain supplied assertions even when well formed.
    """
    try:
        encoded = json.dumps(result, allow_nan=False, ensure_ascii=False)
        if len(encoded.encode("utf-8")) > MAX_INPUT_BYTES:
            raise ValueError("ASPIC+ result exceeds the 4 MiB export input limit")
        # Detach from caller-owned mutable dictionaries and require JSON data.
        result = json.loads(encoded)
    except (TypeError, OverflowError, RecursionError, UnicodeError) as exc:
        raise ValueError("ASPIC+ export requires bounded JSON data") from exc
    if not isinstance(result, dict) or not isinstance(result.get("theory"), dict):
        raise ValueError("Export requires a theory and its formal result")
    theory, formal = result["theory"], result.get("formal")
    supplied_limits = result.get('source_map', {}).get('execution_limits', current_limits().describe())
    try:
        selected_limits = ExecutionLimits(**supplied_limits)
    except (ValueError, TypeError) as exc:
        raise ValueError('Invalid snapshot execution budgets') from exc
    if any(value > current_limits().describe()[key] for key, value in selected_limits.describe().items()):
        raise ValueError('Snapshot budgets exceed the exporter host policy; configure explicit host limits')
    errors = schema_errors(formal, OUTPUT_SCHEMA)
    if errors:
        raise ValueError("Invalid ASPIC+ result: " + "; ".join(errors[:4]))
    if canonical_digest(theory) != formal["theory_sha256"]:
        raise ValueError("Formal result does not match the supplied theory digest")
    with using_limits(selected_limits):
        computation = execute_extension(ASPIC_CONTRACT, {"theory": theory})
    if computation["status"] != "supported":
        raise ValueError("Bounded ASPIC recomputation failed: " +
                         "; ".join(computation["reasons"]))
    if canonical_digest(formal) != canonical_digest(computation["details"]):
        raise ValueError("Supplied formal result differs from bounded ASPIC recomputation")
    arguments, defeats = formal["arguments"], formal["defeats"]
    by_id = {arg["id"]: arg for arg in arguments}
    premises = {item["atom"]: item for item in theory["premises"]}
    rules = {item["id"]: item for item in theory["rules"]}
    source = result.get("source_map")
    if source is not None:
        source_errors = list(Draft202012Validator(_SOURCE_SCHEMA).iter_errors(source))
        if source_errors:
            raise ValueError("Invalid source map structure: " + source_errors[0].message)
        if (not isinstance(source, dict) or not isinstance(source.get("goal"), dict)
                or source.get("theory_digest") != formal["theory_sha256"]
                or source["goal"].get("atom") != theory["goal"]
                or result.get("claim", source["goal"].get("claim")) != source["goal"].get("claim")
                or result.get("source_digest", source.get("source_digest")) != source.get("source_digest")):
            raise ValueError("Source map does not match the supplied theory and goal")
        if (result.get("snapshot_digest", source.get("snapshot_digest"))
                != source.get("snapshot_digest")):
            raise ValueError("Snapshot digest disagrees with the source map")
    origin_by_rule = {}
    origin_by_atom = {}
    claim_by_atom = {}
    missing = []
    if source is not None:
        def origins(kind: str) -> dict:
            entries = source.get(kind, {})
            if (not isinstance(entries, dict) or any(not isinstance(name, str)
                    or not isinstance(item, dict) for name, item in entries.items())):
                raise ValueError(f"Source map {kind} must contain named declarations")
            return entries

        for name, item in origins("claims").items():
            atom = item.get("atom")
            if (atom in claim_by_atom or not isinstance(atom, str)
                    or not isinstance(item.get("statement"), str)):
                raise ValueError("Source map claim identity is inconsistent")
            claim_by_atom[atom] = {"name": name, "statement": item.get("statement")}
        if (not isinstance(source["goal"].get("claim"), str)
                or claim_by_atom.get(theory["goal"], {}).get("name") != source["goal"]["claim"]):
            raise ValueError("Source map goal claim does not name the formal goal atom")
        for kind in ("arguments", "assumptions", "objections"):
            for name, item in origins(kind).items():
                if item.get("emitted"):
                    rule_id = item.get("rule_id")
                    if (rule_id not in rules or rule_id in origin_by_rule
                            or (kind == "arguments" and
                                (not isinstance(item.get("reasoning"), str)
                                 or not isinstance(item.get("rationale"), str)))):
                        raise ValueError("Source map rule identity is inconsistent")
                    rule = rules[rule_id]
                    if (item.get("conclusion_atom", item.get("atom")) != rule["consequent"]
                            or item.get("rule_kind", rule["kind"]) != rule["kind"]
                            or item.get("applicability_atom") != rule.get("name")
                            or item.get("rank") != rule.get("rank")):
                        raise ValueError("Source map rule fields disagree with the formal theory")
                    origin_by_rule[rule_id] = {"kind": kind[:-1], "name": name,
                                               "span": item.get("span"),
                                               "formal_review": (item.get("strict_annotation")
                                                                 or item.get("rank_annotation")),
                                               **({"rationale": item.get("rationale"),
                                                   "reasoning": item.get("reasoning")}
                                                  if kind == "arguments" else {})}
                    for key in ('source_file', 'scope_transfer'):
                        if key in item:
                            origin_by_rule[rule_id][key] = item[key]
        for name, item in origins("evidence").items():
            if item.get("available"):
                atom = item.get("atom")
                if (atom not in premises or premises[atom]["kind"] != "ordinary"
                        or atom in origin_by_atom or item.get("rank") != premises[atom]["rank"]):
                    raise ValueError("Source map evidence identity is inconsistent")
                origin_by_atom[atom] = {"kind": "evidence", "name": name,
                                        "span": item.get("span"),
                                        "formal_review": item.get("rank_annotation"),
                                        "observation": item.get("identity")}
                if 'source_file' in item:
                    origin_by_atom[atom]['source_file'] = item['source_file']
            else:
                if (not isinstance(item.get("reasons", []), list)
                        or any(not isinstance(reason, str)
                               for reason in item.get("reasons", []))):
                    raise ValueError("Unavailable evidence reasons must be text")
                issues = item.get("availability_issues")
                if not issues:
                    raise ValueError("Unavailable evidence must have availability issues")
                missing.append({"name": name, "reasons": item.get("reasons", []),
                                "availability_issues": issues, "span": item.get("span")})
        basis = source.get("structural_basis")
        if basis is not None:
            if (basis["atom"] not in premises or premises[basis["atom"]]["kind"] != "axiom"
                    or basis["atom"] in origin_by_atom):
                raise ValueError("Source map structural basis must name an unmapped axiom")
            origin_by_atom[basis["atom"]] = {"kind": "structural basis", "name": "compiler_basis",
                                                     "meaning": basis["meaning"]}

    contrary_origins = {}
    contrary_pairs = {(item["attacker"], item["target"]) for item in theory["contraries"]}
    if source is not None:
        for item in source.get("contraries", []):
            if isinstance(item, dict):
                if (item["attacker"], item["target"]) not in contrary_pairs:
                    raise ValueError("Source map contrary is absent from the formal theory")
                contrary_origins[(item.get("attacker"), item.get("target"))] = {
                    "objection": item.get("objection"),
                    "annotation": item.get("annotation")}
    viewed_defeats = []
    for event in defeats:
        target = by_id[event["subargument"]]
        attacked_atom = target.get("rule_name") if event["kind"] == "undercut" else target["conclusion"]
        relation = contrary_origins.get((by_id[event["attacker"]]["conclusion"], attacked_atom))
        viewed_defeats.append({**event, **({"relation_origin": relation} if relation else {})})

    nodes = []
    for arg in arguments:
        node = dict(arg)
        node["origin"] = (origin_by_rule.get(arg.get("rule_id")) if "rule_id" in arg
                          else origin_by_atom.get(arg["conclusion"])) or {
                              "kind": "formal rule" if "rule_id" in arg else "formal premise",
                              "name": arg.get("rule_id", arg["conclusion"])}
        claim = claim_by_atom.get(arg["conclusion"])
        node["display_conclusion"] = claim["name"] if claim else (
            node["origin"]["name"] if node["origin"]["kind"] in
            ("evidence", "assumption", "objection") else arg["conclusion"])
        if claim:
            node["authored_statement"] = claim["statement"]
        nodes.append(node)
    view = {"schema": VIEW_VERSION, "theory_digest": formal["theory_sha256"],
            "evaluated_at": source.get("assessed_at") if source else None,
            "validation": {"formal_result": "recomputed", "provenance": "supplied"},
            "profile": result.get("profile", "supplied-formal-result"),
            "goal": theory["goal"], "goal_claim": source["goal"]["claim"] if source else result.get("claim"),
            "formal_status": formal["grounded_status"],
            **{key: formal[key] for key in ('semantics', 'query_mode', 'query_status', 'preference', 'extensions')},
            'execution_limits': selected_limits.describe(),
            'formal_directives': deepcopy(source.get('formal_directives', [])) if source else [],
            "claim_status": result.get("claim_status"),
            "authored_claim_status": result.get("authored_claim_status"),
            "source_digest": result.get("source_digest"),
            "snapshot_digest": source.get("snapshot_digest") if source else None,
            "arguments": nodes, "defeats": viewed_defeats,
            "unavailable_evidence": missing}

    errors = list(Draft202012Validator(VIEW_SCHEMA).iter_errors(view))
    if errors:
        error = errors[0]
        raise ValueError("Invalid ASPIC+ view metadata at " +
                         ".".join(map(str, error.absolute_path)) + ": " + error.message)
    return view


def _object(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required,
            "additionalProperties": False}


def _nullable(schema):
    return {"anyOf": [schema, {"type": "null"}]}


_TEXT = {"type": "string", "maxLength": 100_000}
_NAME = {"type": "string", "minLength": 1, "maxLength": 100_000}
_DIGEST = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
_SPAN = _object({name: {"type": "integer", "minimum": 1}
                 for name in ("line", "column", "end_line", "end_column")})
_REVIEW = _object({
    "kind": {"enum": ["strict", "rank", "contrary", "prefer"]}, "name": _NAME,
    "other": _nullable(_NAME),
    "rank": _nullable({"type": "integer", "minimum": 0, "maximum": 1000}),
    "review": _NAME, "span": _nullable(_SPAN),
    "target_kind": {"enum": ["argument", "assumption", "objection", "evidence", "claim"]},
    'source_file': _nullable(_NAME),
})
_TRANSFER = _object({key: _NAME for key in ('source', 'target', 'assumption', 'review')})
_OBSERVATION = _object({
    "run_id": _NAME, "data_digest": _DIGEST, "request_digest": _DIGEST,
    "collected_at": _NAME, "tool_binding_digest": _DIGEST,
})
_ORIGIN = _object({
    "kind": {"enum": ["argument", "assumption", "objection", "evidence",
                       "structural basis", "formal rule", "formal premise"]},
    "name": _NAME, "span": _nullable(_SPAN), "formal_review": _nullable(_REVIEW),
    "observation": _nullable(_OBSERVATION), "reasoning": _TEXT,
    "rationale": _TEXT, "meaning": _TEXT,
    'source_file': _NAME, 'scope_transfer': _TRANSFER,
}, required=["kind", "name"])
_NODE = deepcopy(OUTPUT_SCHEMA["properties"]["arguments"]["items"])
_NODE["properties"].update({"origin": _ORIGIN, "display_conclusion": _TEXT,
                             "authored_statement": _TEXT})
_NODE["required"].extend(["origin", "display_conclusion"])
_DEFEAT = deepcopy(OUTPUT_SCHEMA["properties"]["defeats"]["items"])
_DEFEAT["properties"]["relation_origin"] = _object({
    "objection": _nullable(_NAME), "annotation": _nullable(_REVIEW)})
_STATUS = _nullable({"enum": ["supported", "unsupported", "contested", "out_of_scope"]})
VIEW_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://github.com/emmett08/earl/blob/main/docs/aspic-view.schema.json",
    "title": "ASPIC+ graph export",
    "description": "The Python exporter recomputes the formal result. Source metadata is supplied, not authenticated. Importing this document alone does not independently verify these assertions.",
    **_object({
        "schema": {"const": VIEW_VERSION}, "profile": _NAME, "goal": _NAME,
        "goal_claim": _nullable(_NAME),
        "formal_status": deepcopy(OUTPUT_SCHEMA["properties"]["grounded_status"]),
        **{key: deepcopy(OUTPUT_SCHEMA['properties'][key]) for key in
           ('semantics', 'query_mode', 'query_status', 'preference', 'extensions')},
        'execution_limits': _object({key: {'type': 'integer', 'minimum': 1} for key in ExecutionLimits().describe()}),
        'formal_directives': {'type': 'array', 'items': _REVIEW},
        "claim_status": _STATUS, "authored_claim_status": _STATUS,
        "source_digest": _nullable(_DIGEST), "snapshot_digest": _nullable(_DIGEST),
        "theory_digest": _DIGEST, "evaluated_at": _nullable(_NAME),
        "validation": _object({"formal_result": {"const": "recomputed"},
                               "provenance": {"const": "supplied"}}),
        "arguments": {"type": "array", "items": _NODE, "minItems": 1},
        "defeats": {"type": "array", "items": _DEFEAT},
        "unavailable_evidence": {"type": "array", "items": _object({
            "name": _NAME, "reasons": {"type": "array", "items": _TEXT},
            "availability_issues": {"type": "array", "minItems": 1,
                                    "uniqueItems": True,
                                    "items": {"enum": list(AVAILABILITY_ISSUES)}},
            "span": _nullable(_SPAN)})},
    }),
}

# Source-map checks concern types and correspondence only. They deliberately
# cannot establish whether a statement, review or observation is authentic.
_SOURCE_ENTRY = {
    "type": "object", "properties": {
        "atom": _NAME, "rule_id": _NAME, "conclusion_atom": _NAME,
        "applicability_atom": _nullable(_NAME), "rule_kind": {"enum": ["strict", "defeasible"]},
        "statement": _TEXT, "reasoning": _TEXT, "rationale": _TEXT,
        "emitted": {"type": "boolean"}, "available": {"type": "boolean"},
        "span": _nullable(_SPAN), "rank_annotation": _nullable(_REVIEW),
        "strict_annotation": _nullable(_REVIEW), "identity": _nullable(_OBSERVATION),
        "reasons": {"type": "array", "items": _TEXT},
        "availability_issues": {"type": "array", "uniqueItems": True,
                                "items": {"enum": list(AVAILABILITY_ISSUES)}},
        'source_file': _NAME, 'scope_transfer': _TRANSFER,
    },
}
_SOURCE_SCHEMA = {"type": "object", "properties": {
    'formal_directives': {'type': 'array', 'items': _REVIEW},
    **{kind: {"type": "object", "additionalProperties": _SOURCE_ENTRY}
       for kind in ("claims", "arguments", "assumptions", "objections", "evidence")},
    "contraries": {"type": "array", "items": {"type": "object", "properties": {
        "attacker": _NAME, "target": _NAME, "objection": _NAME,
        "annotation": _nullable(_REVIEW)}, "required": ["attacker", "target"]}},
    "structural_basis": _object({"atom": _NAME, "meaning": _TEXT}),
}}
