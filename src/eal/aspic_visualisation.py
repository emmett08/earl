"""Offline, read-only view of one bounded ASPIC+ result and its EAL origins.

This renders a supplied result; it never reruns collection or changes the
evaluator. The formal theory digest and graph references are checked before
any untrusted text is embedded in the standalone page.
"""
from __future__ import annotations

import base64
import hashlib
from html import escape
import json

from .aspic import OUTPUT_SCHEMA, _validate
from .evaluator import canonical_digest
from .methods import schema_errors


def build_aspic_view(result: dict) -> dict:
    """Make a bounded, source-aware graph from compiled or explicit theory output."""
    if not isinstance(result, dict) or not isinstance(result.get("theory"), dict):
        raise ValueError("Visualisation requires a theory and its formal result")
    theory, formal = result["theory"], result.get("formal")
    _validate(theory)
    errors = schema_errors(formal, OUTPUT_SCHEMA)
    if errors:
        raise ValueError("Invalid ASPIC+ result: " + "; ".join(errors[:4]))
    if canonical_digest(theory) != formal["theory_sha256"]:
        raise ValueError("Formal result does not match the supplied theory digest")
    arguments = formal["arguments"]
    by_id = {arg["id"]: arg for arg in arguments}
    if len(by_id) != len(arguments) or len(arguments) != formal["argument_count"]:
        raise ValueError("Argument IDs and argument_count must agree")
    premises = {item["atom"]: item for item in theory["premises"]}
    rules = {item["id"]: item for item in theory["rules"]}
    for arg in arguments:
        children = arg["direct_subarguments"]
        if len(set(children)) != len(children) or any(child not in by_id for child in children):
            raise ValueError("Direct subarguments must reference distinct constructed arguments")
        if "rule_id" in arg:
            rule = rules.get(arg["rule_id"])
            if (rule is None or arg["conclusion"] != rule["consequent"]
                    or arg["top"] != rule["kind"]
                    or [by_id[child]["conclusion"] for child in children] != rule["antecedents"]):
                raise ValueError("An argument does not match its source rule or direct antecedents")
        elif (children or arg["conclusion"] not in premises
              or arg["top"] != premises[arg["conclusion"]]["kind"]):
            raise ValueError("An argument does not match a declared premise")
    # Reconstruct closure from direct edges, so a forged transitive-only link
    # cannot appear as a legitimate derivation in the view.
    closures: dict[str, set[str]] = {}
    visiting: set[str] = set()

    def closure(identifier: str) -> set[str]:
        if identifier in visiting:
            raise ValueError("Argument derivation contains a cycle")
        if identifier not in closures:
            visiting.add(identifier)
            ancestors = set()
            for child in by_id[identifier]["direct_subarguments"]:
                ancestors.add(child)
                ancestors.update(closure(child))
            visiting.remove(identifier)
            closures[identifier] = ancestors
        return closures[identifier]

    for arg in arguments:
        if set(arg["subarguments"]) != closure(arg["id"]) or len(arg["subarguments"]) != len(closure(arg["id"])):
            raise ValueError("Transitive subarguments disagree with direct derivation edges")
    defeats = formal["defeats"]
    for event in defeats:
        if (event["attacker"] not in by_id or event["target"] not in by_id
                or event["subargument"] not in closure(event["target"]) | {event["target"]}):
            raise ValueError("Defeat witness must reference an attacker and an attacked subargument")
    if len({(event["attacker"], event["target"]) for event in defeats}) != formal["defeat_count"]:
        raise ValueError("Defeat edge count does not match defeat witnesses")

    source = result.get("source_map")
    if source is not None:
        if (not isinstance(source, dict) or not isinstance(source.get("goal"), dict)
                or source.get("theory_digest") != formal["theory_sha256"]
                or source["goal"].get("atom") != theory["goal"]):
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
        for kind in ("arguments", "assumptions", "objections"):
            for name, item in origins(kind).items():
                if item.get("emitted"):
                    rule_id = item.get("rule_id")
                    if (rule_id not in rules or rule_id in origin_by_rule
                            or (kind == "arguments" and
                                (not isinstance(item.get("reasoning"), str)
                                 or not isinstance(item.get("rationale"), str)))):
                        raise ValueError("Source map rule identity is inconsistent")
                    origin_by_rule[rule_id] = {"kind": kind[:-1], "name": name,
                                               "span": item.get("span"),
                                               **({"rationale": item.get("rationale"),
                                                   "reasoning": item.get("reasoning")}
                                                  if kind == "arguments" else {})}
        for name, item in origins("evidence").items():
            if item.get("available"):
                atom = item.get("atom")
                if (atom not in premises or premises[atom]["kind"] != "ordinary"
                        or atom in origin_by_atom):
                    raise ValueError("Source map evidence identity is inconsistent")
                origin_by_atom[atom] = {"kind": "evidence", "name": name,
                                        "span": item.get("span"),
                                        "observation": item.get("identity")}
            else:
                if (not isinstance(item.get("reasons", []), list)
                        or any(not isinstance(reason, str)
                               for reason in item.get("reasons", []))):
                    raise ValueError("Unavailable evidence reasons must be text")
                missing.append({"name": name, "reasons": item.get("reasons", []),
                                "span": item.get("span")})
        basis = source.get("structural_basis")
        if basis is not None and not isinstance(basis, dict):
            raise ValueError("Source map structural basis is invalid")
        if basis and basis.get("atom") in premises:
            origin_by_atom[basis["atom"]] = {"kind": "structural basis", "name": "compiler_basis",
                                                     "meaning": basis["meaning"]}

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
    return {"profile": result.get("profile", "supplied-formal-result"),
            "goal": theory["goal"], "goal_claim": result.get("claim"),
            "formal_status": formal["grounded_status"],
            "claim_status": result.get("claim_status"),
            "authored_claim_status": result.get("authored_claim_status"),
            "source_digest": result.get("source_digest"),
            "snapshot_digest": source.get("snapshot_digest") if source else None,
            "arguments": nodes, "defeats": defeats,
            "unavailable_evidence": missing}


_SCRIPT = r"""
"use strict";
const view = JSON.parse(document.getElementById("view-data").textContent);
const byId = new Map(view.arguments.map(arg => [arg.id, arg]));
const picker = document.getElementById("argument-picker");
const search = document.getElementById("argument-search");
const summary = document.getElementById("summary");
const detail = document.getElementById("detail");
const graph = document.getElementById("derivation");
const attacks = document.getElementById("defeats");
const missing = document.getElementById("missing");
const NS = "http://www.w3.org/2000/svg";
const label = {in: "in", out: "out", undecided: "undecided"};

function element(tag, parent, content, className) {
  const el = document.createElement(tag);
  if (content !== undefined) el.textContent = String(content);
  if (className) el.className = className;
  parent.append(el);
  return el;
}
function linkArg(parent, id) {
  const item = element("button", parent, id + " · " + byId.get(id).conclusion, "link-button");
  item.type = "button";
  item.addEventListener("click", () => select(id));
}
function renderList() {
  picker.replaceChildren();
  const term = search.value.toLowerCase().trim();
  let count = 0;
  for (const arg of view.arguments) {
    const caption = arg.id + "  " + arg.display_conclusion + "  " + arg.origin.name + "  " + arg.label;
    if (!caption.toLowerCase().includes(term)) continue;
    const button = element("button", picker, caption, "picker-item " + arg.label);
    button.type = "button";
    button.dataset.argumentId = arg.id;
    button.addEventListener("click", () => select(arg.id));
    count += 1;
  }
  document.getElementById("picker-count").textContent = count + " of " + view.arguments.length + " arguments";
}
function renderGraph(focus) {
  graph.replaceChildren();
  const depths = new Map([[focus, 0]]);
  function walk(id, depth) {
    for (const child of byId.get(id).direct_subarguments) {
      if (depth + 1 > (depths.get(child) ?? -1)) {
        depths.set(child, depth + 1);
        walk(child, depth + 1);
      }
    }
  }
  walk(focus, 0);
  const levels = [];
  for (const [id, depth] of depths) (levels[depth] ??= []).push(id);
  const width = Math.max(440, ...levels.map(group => group.length * 220 + 32));
  const height = levels.length * 106 + 24;
  graph.setAttribute("viewBox", `0 0 ${width} ${height}`);
  graph.setAttribute("width", width);
  graph.setAttribute("height", height);
  graph.setAttribute("role", "img");
  graph.setAttribute("aria-label", "Direct subarguments of " + focus + "; derivation edges point upwards");
  const defs = document.createElementNS(NS, "defs");
  const marker = document.createElementNS(NS, "marker");
  for (const [key, value] of Object.entries({id: "arrow", markerWidth: "9", markerHeight: "9",
      refX: "7", refY: "4", orient: "auto", markerUnits: "userSpaceOnUse"})) {
    marker.setAttribute(key, value);
  }
  const arrow = document.createElementNS(NS, "path");
  arrow.setAttribute("d", "M 0 0 L 8 4 L 0 8 z");
  arrow.setAttribute("fill", "#64748b");
  marker.append(arrow);
  defs.append(marker);
  graph.append(defs);
  const positions = new Map();
  levels.forEach((group, depth) => group.forEach((id, index) => {
    positions.set(id, {x: (index + 0.5) * width / group.length, y: depth * 106 + 52});
  }));
  for (const [id, position] of positions) {
    for (const child of byId.get(id).direct_subarguments) {
      const below = positions.get(child);
      const path = document.createElementNS(NS, "path");
      path.setAttribute("d", `M ${below.x} ${below.y - 29} L ${position.x} ${position.y + 29}`);
      path.setAttribute("class", "edge");
      path.setAttribute("marker-end", "url(#arrow)");
      graph.append(path);
    }
  }
  for (const [id, position] of positions) {
    const arg = byId.get(id);
    const group = document.createElementNS(NS, "g");
    group.setAttribute("class", "node " + arg.label);
    group.setAttribute("tabindex", "0");
    group.setAttribute("role", "button");
    group.setAttribute("aria-label", id + ": " + arg.display_conclusion + ", " + label[arg.label]);
    group.addEventListener("click", () => select(id));
    group.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(id); }
    });
    const rect = document.createElementNS(NS, "rect");
    rect.setAttribute("x", position.x - 94);
    rect.setAttribute("y", position.y - 30);
    rect.setAttribute("width", "188");
    rect.setAttribute("height", "60");
    rect.setAttribute("rx", "8");
    group.append(rect);
    for (const [line, content] of [[-5, id + " · " + arg.display_conclusion], [17, label[arg.label] + " · " + arg.origin.name]]) {
      const title = document.createElementNS(NS, "text");
      title.setAttribute("x", position.x);
      title.setAttribute("y", position.y + line);
      title.setAttribute("text-anchor", "middle");
      title.textContent = content.length > 26 ? content.slice(0, 25) + "…" : content;
      group.append(title);
    }
    graph.append(group);
  }
}
function select(id) {
  const arg = byId.get(id);
  if (!arg) return;
  detail.replaceChildren();
  element("h2", detail, id + " · " + arg.display_conclusion);
  if (arg.display_conclusion !== arg.conclusion) element("p", detail, "Formal atom: " + arg.conclusion);
  if (arg.authored_statement) element("p", detail, "Authored claim: " + arg.authored_statement);
  element("p", detail, "Grounded label: " + label[arg.label] + " · " + arg.top +
    " · strength " + arg.strength, "status " + arg.label);
  element("p", detail, "Origin: " + arg.origin.kind + " " + arg.origin.name);
  if (arg.rule_id) element("p", detail, "Rule: " + arg.rule_id + (arg.rule_name ? " · applicability: " + arg.rule_name : ""));
  if (arg.origin.span) element("p", detail, "Source location: " + JSON.stringify(arg.origin.span));
  if (arg.origin.rationale) element("p", detail, "Authored rationale: " + arg.origin.rationale);
  if (arg.origin.observation) element("p", detail, "Checked observation identity: " + JSON.stringify(arg.origin.observation));
  if (arg.origin.meaning) element("p", detail, arg.origin.meaning);
  element("h3", detail, "Direct subarguments (premises first)");
  if (!arg.direct_subarguments.length) element("p", detail, "Premise; no subarguments.");
  for (const child of arg.direct_subarguments) linkArg(detail, child);
  element("p", detail, arg.subarguments.length + " transitive subarguments in this derivation.");
  renderGraph(id);
  attacks.replaceChildren();
  const incoming = view.defeats.filter(item => item.target === id);
  const outgoing = view.defeats.filter(item => item.attacker === id);
  element("h3", attacks, "Incoming defeats · " + incoming.length + " witnesses");
  if (!incoming.length) element("p", attacks, "No recorded defeat witness for this argument.");
  for (const item of incoming) {
    const row = element("p", attacks, item.kind + " at " + item.subargument + " from ");
    linkArg(row, item.attacker);
  }
  element("h3", attacks, "Outgoing defeats · " + outgoing.length + " witnesses");
  if (!outgoing.length) element("p", attacks, "No recorded outgoing defeat witness.");
  for (const item of outgoing) {
    const row = element("p", attacks, item.kind + " at " + item.subargument + " against ");
    linkArg(row, item.target);
  }
  for (const button of picker.querySelectorAll("button")) {
    button.setAttribute("aria-current", button.dataset.argumentId === id ? "true" : "false");
  }
}
summary.textContent = "Goal " + (view.goal_claim || view.goal) + " · formal " + view.formal_status +
  (view.claim_status ? " · compiled claim " + view.claim_status : "") +
  (view.authored_claim_status ? " · authored EAL " + view.authored_claim_status : "") +
  " · " + view.arguments.length + " arguments · " + view.defeats.length + " defeat witnesses";
for (const item of view.unavailable_evidence) {
  const row = element("li", missing);
  element("strong", row, item.name + ": ");
  row.append(document.createTextNode(item.reasons.join("; ") || "Unavailable at this snapshot"));
}
if (!view.unavailable_evidence.length) element("li", missing, "No unavailable declared evidence in this snapshot.");
search.addEventListener("input", renderList);
renderList();
const requested = new URLSearchParams(location.search).get("argument");
const initial = document.body.dataset.focus || requested;
const goal = view.arguments.find(arg => arg.conclusion === view.goal && arg.label === "in") ||
             view.arguments.find(arg => arg.conclusion === view.goal);
select(byId.has(initial) ? initial : goal?.id || view.arguments[0].id);
"""


def render_aspic_html(result: dict, *, focus: str | None = None) -> str:
    """Return a standalone interactive HTML page; no network assets or writes."""
    view = build_aspic_view(result)
    if focus is not None and focus not in {arg["id"] for arg in view["arguments"]}:
        raise ValueError(f"Unknown formal argument ID {focus!r}")
    encoded = json.dumps(view, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    # A JSON script element still terminates at a literal </script>. Escape
    # markup delimiters before embedding, even though the data is inert JSON.
    encoded = (encoded.replace("&", "\\u0026").replace("<", "\\u003c")
              .replace(">", "\\u003e").replace("\u2028", "\\u2028")
              .replace("\u2029", "\\u2029"))
    script_hash = base64.b64encode(hashlib.sha256(_SCRIPT.encode("utf-8")).digest()).decode("ascii")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'sha256-{script_hash}'; style-src 'unsafe-inline'">
<title>ASPIC+ argument view</title>
<style>
:root {{ font: 16px/1.5 system-ui,sans-serif; color: #17243a; background: #f5f7fa }}
body {{ margin: 0 }} header {{ padding: 1rem 2rem; background: #14233e; color: white }}
h1 {{ font-size: 1.4rem; margin: 0 }} h2 {{ font-size: 1.15rem }} h3 {{ font-size: 1rem }}
.notice {{ background: #fff2d4; padding: .7rem 2rem; margin: 0 }}
main {{ display: grid; grid-template-columns: minmax(240px,300px) minmax(0,1fr); gap: 1rem; padding: 1rem }}
aside, section {{ background: white; border-radius: .6rem; padding: 1rem; box-shadow: 0 1px 4px #bbc6d4 }}
aside {{ align-self: start; max-height: 85vh; overflow: auto }}
input {{ box-sizing: border-box; width: 100%; padding: .5rem; font: inherit }}
button {{ font: inherit; cursor: pointer }} button:focus-visible, g:focus-visible {{ outline: 3px solid #b36b00 }}
.picker-item {{ display: block; width: 100%; text-align: left; border: 1px solid #cbd5df; background: #fff;
  padding: .45rem; margin: .3rem 0; overflow-wrap: anywhere }}
.picker-item[aria-current=true] {{ border-width: 2px; border-color: #1d579d }}
.link-button {{ color: #155397; border: 0; background: transparent; text-decoration: underline; padding: .15rem }}
.graph-wrap {{ max-width: 100%; overflow: auto; border: 1px solid #d9e0e8; margin: 1rem 0 }}
svg {{ font: 12px system-ui,sans-serif }} .edge {{ stroke: #64748b; stroke-width: 2; fill: none }}
.node {{ cursor: pointer }} .node rect {{ stroke: #25364a; stroke-width: 2 }}
.node.in rect {{ fill: #d7f2df }} .node.out rect {{ fill: #f9e1e1 }}
.node.undecided rect {{ fill: #fff0c7 }} .node text {{ fill: #17243a; pointer-events: none }}
.status.in {{ color: #145d30 }} .status.out {{ color: #993232 }} .status.undecided {{ color: #7f5700 }}
.meta {{ overflow-wrap: anywhere }}
@media(max-width:750px) {{ main {{ display: block }} aside {{ max-height: 30vh; margin-bottom: 1rem }} }}
</style></head>
<body data-focus="{escape(focus or '', quote=True)}">
<header><h1>ASPIC+ arguments</h1><p id="summary"></p></header>
<p class="notice">Labels are supplied solver output for this bounded theory; rendering does not recompute them. Missing evidence is unresolved, not false. Source names are supplied provenance, not proof of semantic correspondence.</p>
<main><aside><label for="argument-search">Search arguments</label><input id="argument-search" type="search">
<p id="picker-count"></p><nav id="argument-picker" aria-label="Arguments"></nav></aside>
<section><div id="detail" class="meta"></div><h3>Direct derivation · premises below conclusions</h3>
<div class="graph-wrap"><svg id="derivation" aria-label="Argument derivation"></svg></div>
<div id="defeats"></div><h3>Unavailable declared evidence</h3><ul id="missing" class="meta"></ul>
<details class="meta"><summary>Snapshot identifiers</summary>
<p>Source digest: {escape(str(view['source_digest'] or 'not supplied'))}</p>
<p>Snapshot digest: {escape(str(view['snapshot_digest'] or 'not supplied'))}</p></details>
</section></main><script type="application/json" id="view-data">{encoded}</script>
<script>{_SCRIPT}</script></body></html>'''
