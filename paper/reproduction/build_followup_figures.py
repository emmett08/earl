#!/usr/bin/env python3
"""Build new reference-state figures without changing the fourteen pilot figures.

Run from any directory: python3 article/reproduction/build_followup_figures.py
The reference-profile input is a calculation over authored synthetic cases.  It
is not a table of model outputs, communication codes or deployment failures.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FID = "15-reference-undetermined-profiles"
ORDER = [
    ("stale", "Stale"),
    ("missing_observation", "Missing observation"),
    ("invalidated", "Invalidated"),
    ("invalidated + stale", "Invalidated + stale"),
    ("scope_mismatch", "Scope/version mismatch"),
    ("scope_mismatch + stale", "Scope/version mismatch + stale"),
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, content: dict) -> None:
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n")


def quantity(qid: str, label: str, unit: str, definition: str, transformation: str) -> dict:
    return {
        "id": qid, "label": label, "unit": unit,
        "definition": definition,
        "input_ids": ["profile_summary", "point_table"],
        "transformation": transformation,
        "statistical_role": "derived", "status": "available",
        "missingness": {"state": "complete", "treatment": "All twenty reference-undetermined recipient task/time positions are retained exactly once; no model-output or communication-code rows enter the calculation."},
        "uncertainty": {"kind": "not_applicable", "definition": "Exact finite counts of constructed reference states. These are neither effect estimates nor population-frequency estimates, so no sampling interval is assigned."},
    }


def main() -> None:
    input_dir = ROOT / "followup-analysis"
    # The article is the faithful-staging root for the figure contracts. Retain
    # byte-identical copies here instead of using forbidden parent traversal.
    input_dir.mkdir(exist_ok=True)
    for name in ("reference-unknown-causes.json", "reference-unknown-points.csv"):
        original = ROOT.parent / "followup-analysis" / name
        retained = input_dir / name
        if original.exists():
            retained.write_bytes(original.read_bytes())
        if not retained.exists():
            raise FileNotFoundError(f"Missing retained reference-state input: {retained}")
    summary_path = input_dir / "reference-unknown-causes.json"
    points_path = input_dir / "reference-unknown-points.csv"
    summary = json.loads(summary_path.read_text())
    with points_path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    point_ids = [(r["case"], int(r["session"])) for r in rows]
    assert len(rows) == len(set(point_ids)) == 20
    assert all(1 <= session <= 10 for _, session in point_ids), "Recipients only"
    assert all(int(r["expanded_per_arm"]) == 32 and int(r["expanded_both_arms"]) == 64 for r in rows)
    counts = Counter(r["profile"] for r in rows)
    assert set(counts) == {profile for profile, _ in ORDER}
    profiles = []
    for profile, label in ORDER:
        unique = counts[profile]
        per_arm = sum(int(r["expanded_per_arm"]) for r in rows if r["profile"] == profile)
        both = sum(int(r["expanded_both_arms"]) for r in rows if r["profile"] == profile)
        assert summary["disjoint_blocker_profiles"][profile] == {"unique_points": unique, "per_arm": per_arm, "both_arms": both}
        assert per_arm == unique * 32 and both == per_arm * 2
        profiles.append({"profile": profile, "label": label, "unique_positions": unique, "per_arm": per_arm, "both_arms": both})
    assert sum(p["both_arms"] for p in profiles) == 1280
    assert sum(p["per_arm"] for p in profiles) == 640
    assert summary["unique_recipient_unknown_points"] == 20
    assert summary["replication"]["expanded_unknown_total"] == 1280
    assert summary["replication"]["unknown_per_arm"] == 640
    assert all(summary["reference_counts_recipient_by_arm"][arm]["undetermined"] == 640 for arm in ("ordinary", "eal"))
    assert all(sum(summary["reference_counts_recipient_by_arm"][arm].values()) == 1920 for arm in ("ordinary", "eal"))

    FIGURES, CAPTIONS, TABLES = ROOT / "figures", ROOT / "captions", ROOT / "tables"
    for directory in (FIGURES, CAPTIONS, TABLES):
        directory.mkdir(exist_ok=True)
    table_path = TABLES / f"{FID}.csv"
    with table_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(profiles[0]))
        writer.writeheader()
        writer.writerows(profiles)

    # One calibrated position channel and direct multiplicity labels suffice.
    # Category rows are an explanatory order, not a magnitude/causality ranking.
    origin_x, scale_mm, axis_y = 61.0, 0.20, -1.0
    body = [r"% Required packages: tikz, lmodern", r"% Required TikZ libraries: none",
            r"% Target width: 160 mm maximum", r"% Minimum text size: 9 pt",
            r"% Colour/greyscale intent: colour_and_greyscale; direct labels carry all meaning",
            r"\begin{tikzpicture}[x=1mm,y=1mm,font=\fontsize{9}{11}\selectfont]",
            r"\definecolor{referenceblue}{HTML}{165D81}",
            r"\node[anchor=west,inner sep=0pt,font=\fontsize{10}{12}\selectfont] at (0,70) {Constructed reference-undetermined mixture};",
            r"\node[anchor=west,inner sep=0pt] at (0,62) {20 task/time positions $\times$ 32 trajectories per arm $\times$ 2 arms = 1,280 references};"]
    for index, profile in enumerate(profiles):
        y = 51 - index * 9
        x = origin_x + scale_mm * profile["both_arms"]
        body += [
            rf"\node[anchor=west,inner sep=0pt] at (0,{y}) {{{profile['label']}}};",
            rf"\draw[referenceblue,line width=1pt] ({x:.3f},{y-1.5:.3f}) -- ({x:.3f},{y+1.5:.3f});",
            rf"\node[anchor=west,inner sep=0pt] at ({x+3:.3f},{y}) {{{profile['both_arms']} ({profile['unique_positions']} positions)}};",
        ]
    body.append(rf"\draw[black,line width=0.5pt] ({origin_x},{axis_y}) -- ({origin_x+scale_mm*320},{axis_y});")
    for value in range(0, 321, 64):
        x = origin_x + scale_mm * value
        body += [rf"\draw[black,line width=0.5pt] ({x:.3f},{axis_y}) -- ({x:.3f},{axis_y-1.4});",
                 rf"\node[anchor=north,inner sep=0pt] at ({x:.3f},{axis_y-2.3}) {{{value}}};"]
    body += [rf"\node[anchor=north,inner sep=0pt] at ({origin_x+scale_mm*160:.3f},-10) {{Recipient references, both arms}};",
             r"\end{tikzpicture}"]
    source = FIGURES / f"{FID}.tikz.tex"
    source.write_text("\n".join(body) + "\n")
    caption = (
        "The constructed mixture behind 1,280 reference-undetermined recipient references. "
        "The six disjoint profiles classify twenty task/time positions in the authored synthetic cases; "
        "each position is repeated across 32 trajectories per arm and two arms, yielding 640 references "
        "per arm and one third of all 3,840 recipient references. Direct labels give expanded references "
        "and unique positions. Profiles collect rejection reasons for decision-relevant unknown requirements "
        "on unrefuted routes, including historical fallback records; mixed profiles are not independent "
        "failures or causal-effect estimates. These counts describe the constructed reference mixture, "
        "not model outputs, communication-code ambiguities or deployment prevalence."
    )
    (CAPTIONS / f"{FID}.caption.txt").write_text(caption + "\n")
    alt = (
        "A directly labelled position plot of six disjoint profiles of authored synthetic reference states. "
        "Stale and invalidated each account for 128 recipient references from two unique task/time positions. "
        "Missing observation, invalidated plus stale, scope/version mismatch, and scope/version mismatch plus "
        "stale each account for 256 references from four unique positions. The twenty positions expand "
        "through 32 trajectories per arm and two arms to 1,280 references, 640 per arm. Mixed profiles "
        "include historical fallback reasons and do not estimate independent causes or deployment prevalence."
    )
    (CAPTIONS / f"{FID}.alt.txt").write_text(alt + "\n")
    profile_path = ROOT / "reproduction/followup-manuscript-profile.json"
    write_json(profile_path, {"schema_version": "1.0", "profile_id": "followup-article-latin-modern",
        "document_class": "article", "class_options": ["11pt"],
        "packages": [{"name": "fontenc", "options": ["T1"]}, {"name": "lmodern", "options": []},
                     {"name": "geometry", "options": ["a4paper", "margin=25mm"]}],
        "dependencies": [], "engine": "pdflatex"})
    quantities = [
        quantity("profile", "Disjoint rejection profile", "category", summary["profile_definition"], "Retain exactly one CSV profile per unique case/session pair; translate scope_mismatch to scope/version mismatch for display."),
        quantity("expanded_references", "Expanded reference-undetermined recipient references", "recipient references", "Number of recipient references in each disjoint profile, pooled across the two arms.", "Sum expanded_both_arms over each profile, equivalently multiply its unique-position count by 32 trajectories per arm and two arms."),
        quantity("unique_positions", "Unique reference-undetermined task/time positions", "task/time positions", "Number of unique case/session pairs in each disjoint profile before trajectory and arm expansion.", "Count CSV rows per profile after asserting unique case/session pairs."),
    ]
    spec = {
        "schema_version": "1.0", "figure_id": f"fig-{FID}",
        "purpose": {
            "reader_question": "Why do 1,280 recipient references have an undetermined reference decision in the retained pilot?",
            "expected_reading": "Six disjoint rejection profiles describe twenty authored task/time positions. Uniform replication produces 128 references for each two-position profile and 256 for each four-position profile, totalling 1,280 (640 per arm).",
            "claim": "The reference-undetermined total is an exact constructed mixture of six disjoint profiles, including combined historical rejection reasons, rather than 1,280 independent failures or observed model-output ambiguities.",
            "scope": "Reference states derived from the six authored synthetic cases, recipient session positions 1 through 10, with 32 trajectories per case per arm; one third of 3,840 recipient references. No model outputs are plotted.",
            "permitted_inferences": ["Exact profile counts and their uniform replication multiplicity within the constructed finite record.", "Mixed profiles record unions of rejection reasons, including historical fallback candidates, for unknown requirements on unrefuted routes."],
            "prohibited_inferences": ["Independent causal effects of rejection reasons.", "1,280 independent task failures or unknown factual fields.", "Model-output decisions or communication-code ambiguity counts.", "Deployment prevalence or an estimated task-population distribution."]
        },
        "inputs": [
            {"id": "profile_summary", "path": "followup-analysis/reference-unknown-causes.json", "status": "derived", "source_reference": "Independent fixture calculation over the authored six synthetic cases; disjoint_blocker_profiles and replication fields. The retained summary includes other model-output diagnostics, but none is used by this figure.", "sha256": digest(summary_path)},
            {"id": "point_table", "path": "followup-analysis/reference-unknown-points.csv", "status": "derived", "source_reference": "Twenty unique case/session reference-undetermined recipient positions with the union of rejection reasons on unrefuted routes; authored synthetic reference states, not model outputs.", "sha256": digest(points_path)},
            {"id": "plotted_table", "path": f"tables/{FID}.csv", "status": "derived", "source_reference": "Profile-wise exact counts regenerated by reproduction/build_followup_figures.py from the retained point table and checked against the independent summary.", "sha256": digest(table_path)},
        ],
        "quantities": quantities,
        "encodings": [
            {"id": "profile_rows", "marks": "directly labelled rows", "mark_role": "annotation", "channel": "position", "represents": "Six disjoint profile identities in explanatory order; rows are neither a timeline nor a causal ranking.", "interpretation": "categorical", "quantity_ids": ["profile"], "scale_or_mapping": {"type": "nominal", "definition": "Top to bottom: stale, missing observation, invalidated, invalidated plus stale, scope/version mismatch, scope/version mismatch plus stale.", "domain": [p["label"] for p in profiles]}},
            {"id": "reference_positions", "marks": "short vertical tick data marks", "mark_role": "data_mark", "channel": "position", "represents": "Exact expanded count of recipient references across both arms.", "interpretation": "quantitative", "quantity_ids": ["expanded_references"], "scale_or_mapping": {"type": "linear", "definition": "Horizontal position x = 61 mm + 0.20 mm times reference count; labelled axis spans zero through 320.", "domain": [0, 320]}},
            {"id": "direct_counts", "marks": "numeric text annotations", "mark_role": "annotation", "channel": "text", "represents": "Exact expanded count followed by the unique-position count in parentheses.", "interpretation": "quantitative", "quantity_ids": ["expanded_references", "unique_positions"], "scale_or_mapping": {"type": "explicit", "definition": "Each row prints the CSV-expanded count as an integer and its unique-position count as '(2 positions)' or '(4 positions)'; expanded count equals unique positions times 64."}},
        ],
        "target": {"width_mm": 160, "width_mode": "maximum", "min_text_pt": 9, "min_math_script_pt": 9, "min_stroke_pt": 0.4, "colour_intent": "colour_and_greyscale", "expected_labels": ["Constructed reference-undetermined mixture", "Stale", "Missing observation", "Invalidated", "Scope/version mismatch", "128 (2 positions)", "256 (4 positions)", "Recipient references, both arms"], "prohibit_block_circle_diagrams": True, "manuscript_profile": "reproduction/followup-manuscript-profile.json"},
        "build": {"renderer": "tikz", "engine": "pdflatex", "profile": "reproduction/followup-manuscript-profile.json", "source": f"figures/{FID}.tikz.tex",
            "recipe": [["python3", "reproduction/build_followup_figures.py"], ["python3", "reproduction/figure-tools/scripts/render_tikz.py", f"figures/{FID}.tikz.tex", "--spec", f"{FID}.spec.json", "--output", f"figures/{FID}.pdf", "--audit", f"figures/{FID}.audit.json", "--preview", f"figures/{FID}.png", "--qa-dir", f"qa/{FID}"]],
            "outputs": {"pdf": f"figures/{FID}.pdf", "preview": f"figures/{FID}.png", "audit": f"figures/{FID}.audit.json", "review": f"figures/{FID}.review.json"},
            "dependencies": ["reproduction/build_followup_figures.py", f"captions/{FID}.caption.txt", f"captions/{FID}.alt.txt"]},
    }
    write_json(ROOT / f"{FID}.spec.json", spec)
    write_json(ROOT / "analysis/followup-profile-numerical-checks.json", {
        "figure": FID, "source_status": "Derived from authored synthetic reference states; no model outputs or communication-code ambiguities are plotted.",
        "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in (summary_path, points_path, table_path)},
        "unique_case_session_pairs": len(point_ids), "no_duplicate_positions": len(set(point_ids)) == len(point_ids),
        "profiles": profiles, "total_both_arms": 1280, "total_per_arm": 640,
        "recipient_reference_denominator_both_arms": 3840, "constructed_fraction": "1/3",
        "checks": ["CSV profiles exactly match independent JSON summary.", "Every retained point expands to 32 per arm and 64 across both arms.", "Six disjoint profile counts sum to twenty unique recipient positions and 1,280 references.", "Each arm has 640 reference-undetermined entries among 1,920 recipient references."],
        "plot_choice": "One directly labelled calibrated positional plot is justified by the exact six-category count-comparison task. A companion exact table is retained. Additional prototypes would not resolve a live design ambiguity; no human comprehension improvement is claimed.",
    })
    print(f"Built {FID}: 20 positions, 640 references per arm, 1,280 both arms.")


if __name__ == "__main__":
    main()
