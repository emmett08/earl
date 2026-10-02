#!/usr/bin/env python3
"""Build report figures solely from final sanitized endpoint rows.

No response, coder-output, rubric-key or task/scorer/plan file is opened.  The
input contract intentionally excludes answer text.  Run from any directory:
python3 reproduction/build_report_figures.py --render
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

if not __debug__:
    raise RuntimeError("Run the figure builder without Python optimization so all declared calculation checks remain active.")

ROOT = Path(__file__).resolve().parents[1]
CONTEXTS = [("facts", "Facts"), ("eal", "EAL"), ("conventional", "Conventional")]
POSITIONS = [2, 4, 6, 8, 10]
CONDITIONS = ["complete", "critical_gap", "restored_positive", "restored_negative", "noncritical_gap"]
FAMILIES = ["all_of", "any_of"]
CAUSES = ["missing", "stale", "invalidated", "version_mismatch"]
ROW_KEYS = {"task_id", "family", "cause", "position", "condition", "context", "reference_decision", "canonical_match", "whole_verdict_match", "explanation_consistency", "primary_state"}
STATES = {"success": ("+", "successblue"), "failure": (r"$-$", "failureorange"), "unresolved": ("?", "neutralgrey")}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def safe_data(path: Path) -> dict:
    data = json.loads(path.read_text())
    assert set(data) == {"schema", "source", "rows"}, "Use the sanitized figure export, not an annotated response/coder file."
    assert data["schema"] == "EARL/followup-final-figure-data/1"
    assert isinstance(data["source"], dict) and all(isinstance(v, (str, int, bool)) for v in data["source"].values())
    forbidden = {"answer", "answer_text", "output", "output_text", "response", "response_text", "coder", "calibration", "gold"}
    assert not any(k.lower() in forbidden for k in data["source"])
    rows = data["rows"]
    assert len(rows) == 120
    for row in rows:
        assert set(row) == ROW_KEYS, "Figure rows may contain only the declared endpoint/condition fields."
        assert row["context"] in dict(CONTEXTS)
        assert row["family"] in FAMILIES and row["cause"] in CAUSES
        assert row["position"] in POSITIONS
        assert row["condition"] == CONDITIONS[POSITIONS.index(row["position"])]
        assert row["reference_decision"] in {"ready", "not_ready", "undetermined"}
        expected_reference = {"complete": "ready", "critical_gap": "undetermined", "restored_positive": "ready", "restored_negative": "not_ready", "noncritical_gap": "not_ready" if row["family"] == "all_of" else "ready"}[row["condition"]]
        assert row["reference_decision"] == expected_reference, "Final cell reference must retain the declared authored control pattern."
        assert row["primary_state"] in STATES
        assert (type(row["canonical_match"]) is bool or row["canonical_match"] is None) and (type(row["whole_verdict_match"]) is bool or row["whole_verdict_match"] is None)
        assert row["explanation_consistency"] in {"consistent", "contradictory", "ambiguous", "no_explanation", "missing"}
        assert (row["primary_state"] == "success") == (row["whole_verdict_match"] is True and row["explanation_consistency"] == "consistent"), "Final primary-state and endpoint fields disagree."
    keys = [(r["context"], r["task_id"], r["position"]) for r in rows]
    assert len(set(keys)) == 120
    task_sets = {(family, cause): {r["task_id"] for r in rows if r["family"] == family and r["cause"] == cause} for family in FAMILIES for cause in CAUSES}
    assert all(len(ids) == 1 for ids in task_sets.values()), "Each family/cause task identity must stay fixed across positions and contexts."
    tasks = {key: next(iter(ids)) for key, ids in task_sets.items()}
    assert len(tasks) == len(set(tasks.values())) == 8
    for family in FAMILIES:
        for cause in CAUSES:
            assert (family, cause) in tasks
    reference_rows = {}
    for context, _ in CONTEXTS:
        subset = [r for r in rows if r["context"] == context]
        assert len(subset) == 40
        lookup = {(r["task_id"], r["position"]): r for r in subset}
        assert len(lookup) == 40
        reference_rows[context] = {(key, r["reference_decision"]) for key, r in lookup.items()}
        assert Counter(r["reference_decision"] for r in subset) == {"ready": 20, "not_ready": 12, "undetermined": 8}
    assert reference_rows["facts"] == reference_rows["eal"] == reference_rows["conventional"]
    return data


def tex_label(family: str, cause: str) -> str:
    return ("All" if family == "all_of" else "Any") + " / " + {"missing": "missing", "stale": "stale", "invalidated": "invalidated", "version_mismatch": "version"}[cause]


def picture(body: str) -> str:
    return r"""% Required packages: tikz, lmodern
% Required TikZ libraries: none
% Target width: 160 mm maximum
% Minimum text size: 9 pt
% Colour/greyscale intent: colour_and_greyscale; direct symbols and text carry all meaning
\begin{tikzpicture}[x=1mm,y=1mm,font=\fontsize{9}{11}\selectfont]
\definecolor{successblue}{HTML}{165D81}
\definecolor{failureorange}{HTML}{AD5920}
\definecolor{neutralgrey}{HTML}{616970}
""" + body + "\\end{tikzpicture}\n"


def quantity(qid: str, label: str, unit: str, definition: str, transformation: str) -> dict:
    return {"id": qid, "label": label, "unit": unit, "definition": definition,
            "input_ids": ["final_endpoints", "collection_provenance"], "transformation": transformation,
            "statistical_role": "derived", "status": "available",
            "sample": {"denominator": 40, "unit": "matched recipient positions per context", "inclusion": "All five scheduled positions for each of eight common-donor task blocks; one repeat. Donors excluded. The forty positions are clustered within eight tasks and are not forty independent cases."},
            "missingness": {"state": "complete", "treatment": "All 120 planned recipient cells retained. Unresolved primary coding has its own symbol; missing/unparseable endpoint fields remain missing and are not counted as confirmed matches."},
            "uncertainty": {"kind": "unquantified", "definition": "Exact finite tabulation conditional on final AI coding. No population confidence interval, independent human coder validation, measured resolved-code error or stochastic repeatability estimate is available; factual grounding is unassessed."}}


def specification(fid: str, purpose: dict, quantities: list[dict], encodings: list[dict], data_path: Path) -> dict:
    expected_labels = ["Facts", "EAL", "Conventional"] + (["Primary outcomes at all forty matched positions per context", "Success", "Failure", "Unresolved coding", "All / missing"] if fid == "01-primary-outcome-cells" else ["Canonical fields and whole-answer endpoints remain distinct", "Canonical match", "Known verdict matches", "Primary success"])
    tool_dependencies = ["reproduction/figure-tools/scripts/" + name for name in ["render_tikz.py", "render_context.py", "figure_audit.py", "figure_spec.py", "build_profile.py", "figure_review.py"]] + ["reproduction/figure-tools/assets/figure-spec.schema.json", "reproduction/figure-tools/assets/figure-review.schema.json", "inputs/final-analysis.schema.json"]
    return {"schema_version": "1.0", "figure_id": "fig-" + fid, "purpose": purpose,
            "inputs": [
                {"id": "final_endpoints", "path": str(data_path.relative_to(ROOT)), "status": "derived", "source_reference": "Final sanctioned sanitized analysis export. Endpoint labels derive from retained live model outputs and final whole-answer AI coding; references derive from the AI-authored fictional tasks. No response text or participant coding by the figure author.", "sha256": digest(data_path)},
                {"id": "collection_provenance", "path": "inputs/collection-audit-excerpt.json", "status": "derived", "source_reference": "Independent live collection audit of 128 actual API attempts, 8 donors/120 recipients, 40 matched position groups and 40 identical EAL/conventional model-visible packets. Exact raw rows hash retained; preliminary canonical counts excluded from the excerpt.", "sha256": digest(ROOT / "inputs/collection-audit-excerpt.json")},
            ], "quantities": quantities, "encodings": encodings,
            "target": {"width_mm": 160, "width_mode": "maximum", "min_text_pt": 9, "min_math_script_pt": 9, "min_stroke_pt": 0.4, "colour_intent": "colour_and_greyscale", "expected_labels": expected_labels, "prohibit_block_circle_diagrams": True, "manuscript_profile": "reproduction/manuscript-profile.json"},
            "build": {"renderer": "tikz", "engine": "pdflatex", "profile": "reproduction/manuscript-profile.json", "source": fid + ".tikz.tex",
                      "recipe": [["python3", "reproduction/build_report_figures.py", "--input", str(data_path.relative_to(ROOT))], ["python3", "reproduction/figure-tools/scripts/render_tikz.py", fid + ".tikz.tex", "--spec", fid + ".spec.json", "--output", fid + ".pdf", "--audit", fid + ".audit.json", "--preview", fid + ".png", "--qa-dir", "qa/" + fid]],
                      "outputs": {"pdf": fid + ".pdf", "preview": fid + ".png", "audit": fid + ".audit.json", "review": fid + ".review.json"},
                      "dependencies": ["reproduction/build_report_figures.py", "captions/" + fid + ".caption.txt", "captions/" + fid + ".alt.txt"] + tool_dependencies}}


def write_figure(fid: str, body: str, caption: str, alt: str, spec: dict) -> None:
    (ROOT / (fid + ".tikz.tex")).write_text(picture(body))
    (ROOT / "captions" / (fid + ".caption.txt")).write_text(caption + "\n")
    (ROOT / "captions" / (fid + ".alt.txt")).write_text(alt + "\n")
    write_json(ROOT / (fid + ".spec.json"), spec)


def primary_cells(rows: list[dict], path: Path) -> str:
    fid = "01-primary-outcome-cells"
    ordered = [(f, c) for f in FAMILIES for c in CAUSES]
    body = r"\node[anchor=west,inner sep=0pt,font=\fontsize{10}{12}\selectfont] at (0,83) {Primary outcomes at all forty matched positions per context};" + "\n"
    body += r"\node[anchor=west,inner sep=0pt] at (0,76) {+ Success\qquad $-$ Failure\qquad ? Unresolved coding};" + "\n"
    for context_index, (context, title) in enumerate(CONTEXTS):
        x0 = 44 + context_index * 37
        body += rf"\node[inner sep=0pt,font=\fontsize{{10}}{{12}}\selectfont] at ({x0+12},67) {{{title}}};" + "\n"
        for col, position in enumerate(POSITIONS):
            body += rf"\node[inner sep=0pt] at ({x0+col*6},60) {{{position}}};" + "\n"
        for index, (family, cause) in enumerate(ordered):
            y = 52 - index * 6
            if context_index == 0:
                body += rf"\node[anchor=west,inner sep=0pt] at (0,{y}) {{{tex_label(family,cause)}}};" + "\n"
            for col, position in enumerate(POSITIONS):
                subset = [r for r in rows if r["context"] == context and r["family"] == family and r["cause"] == cause and r["position"] == position]
                assert len(subset) == 1
                mark, colour = STATES[subset[0]["primary_state"]]
                body += rf"\node[text={colour},inner sep=0pt,font=\fontsize{{10}}{{12}}\selectfont] at ({x0+col*6},{y}) {{{mark}}};" + "\n"
    body += r"\node[anchor=west,inner sep=0pt] at (0,0) {Positions: 2 complete; 4 critical gap; 6 positive restoration;};" + "\n"
    body += r"\node[anchor=west,inner sep=0pt] at (0,-6) {8 negative restoration; 10 noncritical gap.};" + "\n"
    body += r"\node[anchor=west,inner sep=0pt] at (0,-14) {Eight common-donor task blocks; one repeat; grounding unassessed.};" + "\n"
    caption = ("Primary outcomes for all 120 live recipient outputs: 40 matched positions in each context, clustered within 8 common-donor task blocks and collected once. A success requires both a whole-answer communicated verdict matching the authored reference and an internally consistent explanation. Failure and unresolved primary coding remain distinct. An ambiguous communicated verdict can determinately fail the conjunctive endpoint when the explanation is contradictory. A success can match an undetermined reference; the question mark denotes unresolved coding, not an undetermined task reference. Columns are scheduled artificial snapshot positions; recipients are fresh clones of their common donor, not a serial answer trajectory. All/Any denotes the authored all_of/any_of logic family; rows distinguish four purposive task instances per family, with availability cause confounded with domain wording; version denotes version-mismatched evidence. EAL and conventional supplied identical model-visible packets at all 40 matched positions. Labels derive from final AI coding of observed outputs; references are authored synthetic states. Factual grounding, human validation and stochastic repeatability are unassessed. These finite counts establish no superiority or population reliability.")
    totals = {context: dict(Counter(r["primary_state"] for r in rows if r["context"] == context)) for context, _ in CONTEXTS}
    alt = "A three-panel categorical outcome matrix shows all 8 tasks by 5 scheduled positions for facts, EAL and conventional. Plus means primary success, minus failure and question mark unresolved coding. Finite primary-state totals by context: " + json.dumps(totals, sort_keys=True) + ". Each context has 40 positions in 8 common-donor blocks with 1 repeat; EAL/conventional packets were identical."
    scope = "120 live recipient outputs over 8 purposive AI-authored fictional tasks, 5 positions and 3 contexts; 40 matched positions/context, 8 common-donor clusters, 1 repeat. EAL/conventional packets equal at 40 positions."
    purpose = {"reader_question": "Which scheduled cells meet the communicated-verdict-and-consistency primary endpoint, and where are failure or unresolved coding retained?", "expected_reading": "Each cell has one final primary state under the fixed rubric; the complete 120-cell crossing is visible without dropping ambiguities or pooling away task/condition structure.", "claim": "The matrix is an exact finite display of final coded primary outcomes, not an inferred context advantage or population success rate.", "scope": scope, "permitted_inferences": ["Recover the final primary state of every fixed task/position/context cell.", "Compare matched finite cells while retaining common-donor clustering and identical EAL/conventional packet delivery."], "prohibited_inferences": ["Forty independent trials/context or 120 independent task cases.", "A live model state of undetermined equals unresolved coding.", "Superiority, population reliability, factual explanation grounding, human-task benefit or pure reasoning ability."]}
    quantities = [quantity("primary_state", "Final primary outcome", "category", "Success iff reference-matching whole communicated verdict and consistent explanation; final failure and unresolved states retained separately.", "Use final sanctioned primary_state directly; no answer interpretation or relabelling by the figure builder."), quantity("cell_identity", "Matched cell", "category", "Context, task family/cause and scheduled evidence position.", "Order rows by all_of then any_of and the four declared causes; retain scheduled positions 2, 4, 6, 8, 10 as categorical columns.")]
    encodings = [{"id": "states", "marks": "plus, minus and question-mark data glyphs", "mark_role": "data_mark", "channel": "shape", "represents": "Final primary success, failure or unresolved coding.", "interpretation": "categorical", "quantity_ids": ["primary_state"], "scale_or_mapping": {"type": "nominal", "definition": "Plus and blue denote success; minus and orange denote failure; question mark and grey denote unresolved coding. Meaning survives greyscale through the glyph.", "domain": ["success", "failure", "unresolved"]}}, {"id": "cells", "marks": "aligned categorical data glyphs", "mark_role": "data_mark", "channel": "position", "represents": "Task identity, condition position and context; distances are not effects or elapsed times.", "interpretation": "categorical", "quantity_ids": ["cell_identity"], "scale_or_mapping": {"type": "nominal", "definition": "Eight task rows crossed with five scheduled position columns in each of three explicitly named context panels.", "domain": ["facts", "eal", "conventional", "all_of", "any_of", "missing", "stale", "invalidated", "version_mismatch", "2", "4", "6", "8", "10"]}}]
    write_figure(fid, body, caption, alt, specification(fid, purpose, quantities, encodings, path))
    return fid


def endpoint_separation(rows: list[dict], path: Path) -> str:
    fid = "02-endpoint-separation"
    counts = {}
    for context, _ in CONTEXTS:
        subset = [r for r in rows if r["context"] == context]
        counts[context] = {"canonical": sum(r["canonical_match"] is True for r in subset), "whole_verdict": sum(r["whole_verdict_match"] is True for r in subset), "primary": sum(r["primary_state"] == "success" for r in subset), "contradictory": sum(r["explanation_consistency"] == "contradictory" for r in subset), "correct_canonical_and_contradictory": sum(r["canonical_match"] is True and r["explanation_consistency"] == "contradictory" for r in subset), "whole_verdict_unresolved": sum(r["whole_verdict_match"] is None for r in subset), "unresolved_primary": sum(r["primary_state"] == "unresolved" for r in subset)}
        assert counts[context]["primary"] <= counts[context]["whole_verdict"]
        assert counts[context]["correct_canonical_and_contradictory"] <= min(counts[context]["canonical"], counts[context]["contradictory"])
    body = r"\node[anchor=west,inner sep=0pt,font=\fontsize{10}{12}\selectfont] at (0,74) {Canonical fields and whole-answer endpoints remain distinct};" + "\n"
    methods = [("canonical", "Canonical match", 53, "neutralgrey"), ("whole_verdict", "Known verdict matches", 43, "failureorange"), ("primary", "Primary success", 33, "successblue")]
    for _, label, y, _ in methods:
        body += rf"\node[anchor=west,inner sep=0pt] at (0,{y}) {{{label}}};" + "\n"
    for context_index, (context, title) in enumerate(CONTEXTS):
        origin = 40 + context_index * 36
        body += rf"\node[inner sep=0pt,font=\fontsize{{10}}{{12}}\selectfont] at ({origin+14},63) {{{title}}};" + "\n"
        for method, _, y, colour in methods:
            count = counts[context][method]
            x = origin + 0.55 * count
            body += rf"\draw[{colour},line width=1pt] ({x:.3f},{y-1.5}) -- ({x:.3f},{y+1.5});" + "\n"
            body += rf"\node[anchor=west,inner sep=0pt] at ({x+2:.3f},{y}) {{{count}}};" + "\n"
        body += rf"\draw[black,line width=0.5pt] ({origin},26) -- ({origin+22},26);" + "\n"
        for value in [0, 20, 40]:
            x = origin + 0.55 * value
            body += rf"\draw[black,line width=0.5pt] ({x:.3f},26) -- ({x:.3f},24.6);\node[anchor=north,inner sep=0pt] at ({x:.3f},23.5) {{{value}}};" + "\n"
        body += rf"\node[inner sep=0pt] at ({origin+14},15) {{Contradictory: {counts[context]['contradictory']}}};" + "\n"
        body += rf"\node[inner sep=0pt] at ({origin+14},9) {{With enum match: {counts[context]['correct_canonical_and_contradictory']}}};" + "\n"
        body += rf"\node[inner sep=0pt] at ({origin+14},3) {{Verdict unresolved: {counts[context]['whole_verdict_unresolved']}}};" + "\n"
        body += rf"\node[inner sep=0pt] at ({origin+14},-3) {{Primary unresolved: {counts[context]['unresolved_primary']}}};" + "\n"
    body += r"\node[anchor=west,inner sep=0pt] at (0,-12) {Counts out of 40 per context; endpoint and contradiction counts overlap.};" + "\n"
    caption = ("Separate endpoint counts among the same 40 live recipient outputs per context. Canonical match compares the parsed designated field with the authored reference; known verdict matches counts only confirmed true whole-verdict matches from the final AI-coded communicated whole-answer verdict. Null whole-verdict judgments are shown separately and are not counted as known matches. Primary success additionally requires an internally consistent explanation. Counts overlap and are not components to add. Contradictory gives the number with a contradictory explanation; the following line, 'With enum match', counts the contradictory subset whose canonical field nevertheless matches. Verdict unresolved counts null whole-verdict matching fields; Primary unresolved counts unresolved conjunctive endpoint codes. An ambiguous verdict can determinately fail the primary endpoint when its explanation is contradictory. All remain in the 40-cell denominator. Eight common-donor task clusters and one repeat preclude a population precision or repeatability claim. EAL/conventional model-visible packets were identical at all 40 matched positions. These endpoints derive from actual model outputs and final AI coding, while references are authored synthetic states; they do not measure explanation factual grounding, human benefit or superiority.")
    alt = "Three context panels use identical 0–40 positional scales for canonical matches, known whole-verdict matches and primary successes. Contradictions, the canonical-correct contradictory subset, unresolved whole-verdict matches and unresolved primary outcomes are separately labelled overlapping diagnostics. Exact finite counts: " + json.dumps(counts, sort_keys=True) + "."
    purpose = {"reader_question": "How do canonical field matching, whole-verdict matching and the primary consistency requirement differ in the same finite outputs?", "expected_reading": "The three separately named endpoints have common forty-output denominators; a correct enum can coexist with contradiction, so endpoint counts and diagnostics overlap.", "claim": "Endpoint separation and contradictions are retained exactly; a canonical match alone does not establish the primary endpoint.", "scope": "40 matched recipient positions per context in 8 common-donor task clusters and 1 repeat; all three contexts retained, equal EAL/conventional model-visible packets.", "permitted_inferences": ["Recover each finite endpoint count and contradictory canonical-correct subset.", "Check primary successes are a subset of whole-verdict matches."], "prohibited_inferences": ["Add endpoint counts or contradiction diagnostics as disjoint classes.", "Superiority, population precision, repeatability, human validation, factual explanation grounding or pure reasoning advantage."]}
    quantities = [quantity("matches", "Endpoint matching count", "recipient outputs", "Count of canonical field matches, known true final whole-verdict matches or primary successes among 40 outputs in a named context.", "Sum only true endpoint booleans, and primary success states, separately; retain all planned recipients and do not equate the three definitions."), quantity("diagnostics", "Contradiction and unresolved-code diagnostics", "recipient outputs", "Contradictory explanation count, its canonical-correct subset, null whole-verdict matching count, and unresolved primary coding count.", "Tabulate consistency=='contradictory'; intersect with canonical_match==true for the subset; count whole_verdict_match==null and primary_state=='unresolved' separately."), quantity("endpoint", "Endpoint/context identity", "category", "Three separately named endpoints and three context panels.", "Retain fixed facts/EAL/conventional panel order; no outcome-based sorting.")]
    encodings = [{"id": "positions", "marks": "short vertical tick data marks with exact count labels", "mark_role": "data_mark", "channel": "position", "represents": "Each endpoint count on a common 0–40 linear scale in each panel.", "interpretation": "quantitative", "quantity_ids": ["matches"], "scale_or_mapping": {"type": "linear", "definition": "Within each panel x=panel origin+0.55mm×count; zero, twenty, forty are labelled and every mark has its exact count.", "domain": [0, 40]}}, {"id": "diagnostic_text", "marks": "direct numeric text", "mark_role": "annotation", "channel": "text", "represents": "Contradiction total, canonical-correct contradictory subset, unresolved whole-verdict count, and unresolved primary count; not an additional disjoint population.", "interpretation": "quantitative", "quantity_ids": ["diagnostics"], "scale_or_mapping": {"type": "explicit", "definition": "Print exact integers under each named panel without area/length encoding."}}, {"id": "rows_panels", "marks": "labelled metric rows and context panels", "mark_role": "annotation", "channel": "position", "represents": "Categorical endpoint and context identities.", "interpretation": "categorical", "quantity_ids": ["endpoint"], "scale_or_mapping": {"type": "nominal", "definition": "Named rows canonical/known whole-verdict/primary and panels facts/EAL/conventional; spacing encodes no time or effect.", "domain": ["canonical", "whole_verdict", "primary", "facts", "eal", "conventional"]}}]
    write_figure(fid, body, caption, alt, specification(fid, purpose, quantities, encodings, path))
    write_json(ROOT / "validation/endpoint-counts.json", counts)
    return fid


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "inputs/final-analysis-for-figures.json")
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    path = args.input.resolve()
    if not path.exists():
        raise SystemExit("Final sanitized analysis input is awaited; no mock or preliminary outcome figure will be produced.")
    assert path.is_relative_to(ROOT), "Retain sanctioned sanitized input within the figure staging root."
    data = safe_data(path)
    ids = [primary_cells(data["rows"], path), endpoint_separation(data["rows"], path)]
    with (ROOT / "validation/plotted-cells.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted(ROW_KEYS));writer.writeheader();writer.writerows(data["rows"])
    write_json(ROOT / "validation/calculation-checks.json", {"input_sha256": digest(path), "rows": 120, "matched_positions_per_context": 40, "task_clusters": 8, "repeats": 1, "checks": ["No duplicate context/task/position cells.", "Exactly 8 logic/cause task instances and 5 scheduled positions in each context.", "Reference keys coincide across contexts and sum to 20 ready / 12 not_ready / 8 undetermined per context.", "Primary success requires whole-verdict match and consistent explanation.", "Endpoint diagnostics retain overlapping counts and all planned recipients."], "source": data["source"], "choice_rationale": "The complete fixed crossing calls for one categorical outcome matrix; the endpoint-separation question calls for directly labelled comparable positional counts. No unresolved encoding choice warrants invented prototypes; no measured human interpretation benefit is claimed."})
    for fid in ids:
        subprocess.run([sys.executable, str(ROOT / "reproduction/figure-tools/scripts/figure_spec.py"), str(ROOT / (fid + ".spec.json")), "--check-files"], check=True)
        if args.render:
            subprocess.run([sys.executable, str(ROOT / "reproduction/figure-tools/scripts/render_tikz.py"), str(ROOT / (fid + ".tikz.tex")), "--spec", str(ROOT / (fid + ".spec.json")), "--output", str(ROOT / (fid + ".pdf")), "--audit", str(ROOT / (fid + ".audit.json")), "--preview", str(ROOT / (fid + ".png")), "--qa-dir", str(ROOT / "qa" / fid)], check=True)
    print("Built", ", ".join(ids))


if __name__ == "__main__":
    main()
