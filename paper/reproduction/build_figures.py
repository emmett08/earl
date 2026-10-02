#!/usr/bin/env python3
"""Build audit-ready PGFPlots figures from the retained two-run pilot tables.

Resource figures retain their original finite descriptive calculations. Quality
figures distinguish conditional coding ranges from frozen statistical bounds;
the plot generator does not estimate new sampling intervals. Reasoning tokens
remain a subset of provider output.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reproduction/figure-tools/scripts"
FIGURES = ROOT / "figures"
CAPTIONS = ROOT / "captions"
TABLES = ROOT / "tables"
BLUE = "ealblue"
ORANGE = "ordinaryorange"
GREY = "neutralgrey"
TEMPORAL_SNAPSHOT_FIGURES = {
    "08-measurement-status", "12-recipient-decisions",
    "13-recipient-match-bounds", "14-frozen-endpoint-bounds",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tex(text: str) -> str:
    for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("_", r"\_")]:
        text = text.replace(a, b)
    return text


def coords(xs, ys) -> str:
    return " ".join(f"({float(x):.10g},{float(y):.10g})" for x, y in zip(xs, ys))


def plot(xs, ys, options: str) -> str:
    return f"\\addplot[{options}] coordinates {{{coords(xs,ys)}}};\n"


def ecdf(values, domain=None) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(values, dtype=float)
    assert len(values) and np.isfinite(values).all()
    unique, counts = np.unique(values, return_counts=True)
    cumulative = 100.0 * np.cumsum(counts) / len(values)
    if domain is not None:
        lower, upper = domain
        assert lower <= unique[0] and upper >= unique[-1]
        unique = np.r_[lower, unique, upper]
        cumulative = np.r_[0.0, cumulative, 100.0]
    return unique, cumulative


def picture(body: str) -> str:
    return r"""% Required packages: pgfplots, lmodern
% Required TikZ libraries: none
% Target width: 160 mm maximum
% Minimum text size: 9 pt
% Colour/greyscale intent: colour_and_greyscale, direct labels and line styles
\begin{tikzpicture}
\definecolor{ealblue}{HTML}{165D81}
\definecolor{ordinaryorange}{HTML}{C27021}
\definecolor{neutralgrey}{HTML}{616970}
\pgfplotsset{compat=1.18,
  every axis/.append style={
    width=148mm,height=66mm,
    font=\fontsize{9}{11}\selectfont,
    tick label style={font=\fontsize{9}{11}\selectfont},
    label style={font=\fontsize{9}{11}\selectfont},
    title style={font=\fontsize{10}{12}\selectfont},
    legend style={font=\fontsize{9}{11}\selectfont,draw=none,fill=none},
    axis lines=left,axis line style={line width=0.5pt},
    tick style={line width=0.5pt},
    grid style={line width=0.4pt,black!12},
    scaled ticks=false,clip=false}}
""" + body + "\\end{tikzpicture}\n"


def quantity(qid, label, unit, definition, transformation, input_ids,
             denominator=None, observational_unit="recorded session", inclusion=None):
    q = {
        "id": qid, "label": label, "unit": unit, "definition": definition,
        "input_ids": input_ids, "transformation": transformation,
        "statistical_role": "derived", "status": "available",
        "missingness": {"state": "complete", "treatment": "All selected recorded resource observations retained; correctness labels excluded from resource calculations."},
        "uncertainty": {"kind": "unquantified", "definition": "Descriptive values for the retained finite selection. No sampling interval or population effect is asserted; provider accounting and clock measurement limitations remain."}
    }
    if denominator is not None:
        q["sample"] = {"denominator": int(denominator), "unit": observational_unit,
                       "inclusion": inclusion or "Recorded pilot sessions in the explicitly stated arm, role and stratum; complete resource accounting."}
    return q


def encoding(eid, qids, channel, definition, domain, marks="positions and connecting line", interpretation="quantitative", mapping="linear"):
    return {"id": eid, "marks": marks, "mark_role": "data_mark", "channel": channel,
            "represents": definition, "interpretation": interpretation,
            "quantity_ids": qids,
            "scale_or_mapping": {"type": mapping, "definition": definition, "domain": domain}}


def coded_quantity(qid, label, unit, definition, transformation, input_ids,
                   denominator, observational_unit, inclusion, ambiguity=True):
    q = quantity(qid, label, unit, definition, transformation, input_ids,
                 denominator, observational_unit, inclusion)
    q["missingness"] = {"state": "partial" if ambiguity else "complete",
                        "treatment": "Every retained coding entry is counted. Ambiguous communicated decisions remain a separate category or define sharp conditional bounds; resolved AI codes are held fixed, without measured assessor-error correction."}
    q["uncertainty"] = {"kind": "interval" if ambiguity else "unquantified",
                        "definition": "Conditional ambiguity range only, not a sampling confidence interval or a bound on errors in resolved AI codes. No independent human validation or measured assessor error is available."}
    return q


def write_figure(fid, source, caption, claim, question, expected, inputs, quantities, encodings, dependencies=None, expected_labels=None, quality=False):
    FIGURES.mkdir(exist_ok=True)
    CAPTIONS.mkdir(exist_ok=True)
    p = FIGURES / f"{fid}.tikz.tex"
    p.write_text(picture(source))
    cp = CAPTIONS / f"{fid}.caption.txt"
    cp.write_text(caption + "\n")
    input_records = []
    for iid, rel, desc in inputs:
        ip = ROOT / rel
        input_records.append({"id": iid, "path": rel, "status": "derived", "source_reference": desc,
                              "sha256": digest(ip)})
    spec = {
        "schema_version": "1.0", "figure_id": "fig-" + fid,
        "purpose": {"reader_question": question, "expected_reading": expected,
                    "claim": claim,
                    "scope": "Original resources from GitHub Actions run 36985062352, with AI-only decision coding added by finish run 36997861629 to the same 192 paired trajectories across six selected authored cases, two donor profiles, two recipient profiles and two tool modes; no additional experimental observations or independently validated assessor accuracy.",
                    "permitted_inferences": (["Decision agreement with authored references conditional on retained AI communication codes.", "Conditional ambiguity ranges and frozen statistical bounds under their explicitly audited assumptions."] if quality else ["Descriptive resource contrasts for the explicitly included recorded sessions."]) + ["Comparison of recorded quantities under the declared denominators and transformations."],
                    "prohibited_inferences": ["Population-wide or causal superiority of EAL.", "Independent answer correctness, explanation quality, assessor accuracy or reliability from these records.", "Net lifecycle cost savings after unmeasured authoring, review, maintenance or acquisition costs."]},
        "inputs": input_records,
        "quantities": quantities, "encodings": encodings,
        "target": {"width_mm": 160, "width_mode": "maximum", "min_text_pt": 9,
                   "min_math_script_pt": 9, "min_stroke_pt": 0.4,
                   "colour_intent": "colour_and_greyscale", "expected_labels": expected_labels or [],
                   "prohibit_block_circle_diagrams": True},
        "build": {"renderer": "pgfplots", "engine": "pdflatex", "source": f"figures/{fid}.tikz.tex",
                  "recipe": [["python3", "reproduction/build_figures.py"],
                             ["python3", "reproduction/figure-tools/scripts/render_tikz.py", f"figures/{fid}.tikz.tex",
                              "--spec", f"{fid}.spec.json", "--output", f"figures/{fid}.pdf",
                              "--audit", f"figures/{fid}.audit.json", "--preview", f"figures/{fid}.png",
                              "--qa-dir", f"qa/{fid}"]],
                  "outputs": {"pdf": f"figures/{fid}.pdf", "preview": f"figures/{fid}.png", "audit": f"figures/{fid}.audit.json", "review": f"figures/{fid}.review.json"},
                  "dependencies": [f"captions/{fid}.caption.txt"] + (dependencies or [])}
    }
    if fid in TEMPORAL_SNAPSHOT_FIGURES:
        spec["purpose"]["scope"] += " This figure retains the original finish AI-coding snapshot, before the supplemental review; supplemental coding ambiguities do not enter its displayed values or frozen inference."
        spec["build"]["dependencies"].append(f"captions/{fid}.alt.txt")
    (ROOT / f"{fid}.spec.json").write_text(json.dumps(spec, indent=2) + "\n")


def update_temporal_alternative_text():
    """Retain numerical descriptions while explicitly dating four coding views."""
    path = FIGURES / "alternative-text.json"
    content = json.loads(path.read_text())
    replacements = {
        "08-measurement-status": [("Five rows count the same 4,224 sessions after the finish run.", "Five rows count the same 4,224 sessions in the original finish recording and AI-coding snapshot, before the supplemental review.")],
        "12-recipient-decisions": [("Two count matrices compare authored reference decisions with AI-coded communicated decisions for 1,920 recipient sessions per arm.", "Two count matrices compare authored reference decisions with AI-coded communicated decisions in the original finish coding snapshot, for 1,920 recipient sessions per arm.")],
        "13-recipient-match-bounds": [("Four recipient model/tool groups compare ordinary and EAL reference-match ambiguity ranges,", "Four recipient model/tool groups in the original finish coding snapshot compare ordinary and EAL reference-match ambiguity ranges,")],
        "14-frozen-endpoint-bounds": [("Three separately scaled panels distinguish", "Three separately scaled panels retain the original finish coding snapshot and distinguish"), ("and planning remains blocked by only two fully scored paired reruns in the least-complete cell.", "and the original finish allocation report remains blocked by only two fully scored paired reruns in the least-complete cell.")],
    }
    for fid, changes in replacements.items():
        for old, new in changes:
            if old in content[fid]:
                assert content[fid].count(old) == 1
                content[fid] = content[fid].replace(old, new)
            else:
                assert new in content[fid], (fid, old)
        (CAPTIONS / f"{fid}.alt.txt").write_text(content[fid] + "\n")
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n")


def render(fid: str):
    subprocess.run([sys.executable, str(TOOLS / "figure_spec.py"), str(ROOT / f"{fid}.spec.json"), "--check-files"], check=True)
    subprocess.run([sys.executable, str(TOOLS / "render_tikz.py"), str(FIGURES / f"{fid}.tikz.tex"),
                    "--spec", str(ROOT / f"{fid}.spec.json"), "--output", str(FIGURES / f"{fid}.pdf"),
                    "--audit", str(FIGURES / f"{fid}.audit.json"), "--preview", str(FIGURES / f"{fid}.png"),
                    "--qa-dir", str(ROOT / "qa" / fid)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", action="store_true", help="Also render and mechanically audit every figure")
    ap.add_argument("--only", help="Render only one named figure after regenerating exact sources")
    args = ap.parse_args()
    ids = build()
    if args.render:
        for fid in ids:
            if args.only is None or args.only == fid:
                render(fid)


def build():
    update_temporal_alternative_text()
    pair = pd.read_csv(ROOT / "analysis/paired_resources.csv")
    cum = pd.read_csv(ROOT / "analysis/cumulative_resources.csv")
    sessions = pd.read_csv(ROOT / "analysis/session_resources.csv")
    totals = pd.read_csv(ROOT / "analysis/arm_phase_totals.csv")
    summary = json.loads((ROOT / "analysis/resource_summary.json").read_text())
    completion = json.loads((ROOT / "analysis/completion-outcomes.json").read_text())
    assert len(pair) == 192 and pair.pair_id.nunique() == 192
    assert len(sessions) == 4224 and sessions.sequence_id.nunique() == 384
    assert np.all(sessions.reasoning_tokens <= sessions.output_tokens)
    assert np.all(sessions.cached_input_tokens <= sessions.input_tokens)
    assert np.all(sessions.total_tokens == sessions.input_tokens + sessions.output_tokens)
    all_totals = totals[totals.phase == "all"].set_index("arm")
    ordinary = all_totals.loc["ordinary"]
    eal = all_totals.loc["eal"]
    assert np.isclose(pair.ordinary_total_tokens.sum(), ordinary.total_tokens)
    assert np.isclose(pair.eal_total_tokens.sum(), eal.total_tokens)
    TABLES.mkdir(exist_ok=True)
    ids = []
    pp = [("pairs", "analysis/paired_resources.csv", "Whole-sequence matched resources derived from export rows.json and calls.json for run 36985062352.")]
    cc = [("horizons", "analysis/cumulative_resources.csv", "Recorded resource sums including donor session 0 and recipient sessions 1 through each shown horizon.")]
    tt = [("totals", "analysis/arm_phase_totals.csv", "Finite arm and role totals derived from retained provider accounting and session event records.")]
    ss = [("sessions", "analysis/session_resources.csv", "Resource records for all 4,224 selected live sessions, derived from provider usage and local measured times.")]

    # 1. Empirical distribution of paired whole-sequence changes.
    fid = "01-token-distribution"; ids.append(fid)
    reduction = 100.0 * (1 - pair.eal_total_tokens / pair.ordinary_total_tokens)
    xs, ys = ecdf(reduction, (-10, 60))
    pd.DataFrame({"reduction_pct": xs, "cumulative_pct": ys}).to_csv(TABLES / f"{fid}.csv", index=False)
    median = float(np.median(reduction)); lower_count = int((reduction > 0).sum())
    body = r"\begin{axis}[xmin=-10,xmax=60,ymin=0,ymax=100,xtick={-10,0,10,20,30,40,50,60},ytick={0,25,50,75,100},xlabel={Reduction in total tokens per matched trajectory (\%)},ylabel={Trajectories at or below (\%)},ymajorgrids=true]" + "\n"
    body += plot([0, 0], [0, 100], "neutralgrey,dashed,line width=0.5pt,no marks")
    body += plot(xs, ys, "ealblue,line width=0.9pt,no marks,const plot")
    body += f"\\node[anchor=west,font=\\fontsize{{9}}{{11}}\\selectfont] at (rel axis cs:0.22,0.9) {{{lower_count}/192 use fewer tokens}};\n"
    body += f"\\node[anchor=west,font=\\fontsize{{9}}{{11}}\\selectfont] at (rel axis cs:0.22,0.82) {{Median reduction: {median:.1f}\\%}};\n"
    body += "\\end{axis}\n"
    caption = (f"Empirical cumulative distribution of total-token reductions in 192 matched whole trajectories, each containing one donor and ten recipient sessions. A positive reduction denotes fewer EAL tokens. {lower_count} trajectories use fewer tokens; two use more. The median paired reduction is {median:.2f}%; the pooled ratio-of-sums reduction is {100*(1-eal.total_tokens/ordinary.total_tokens):.2f}%. These are distinct summaries of the selected cases. Token reductions alone do not establish decision quality; completed AI-coded decision matches are shown separately.")
    qs = [quantity("reduction", "Paired total-token reduction", "%", "100 times (1 minus EAL whole-trajectory total divided by ordinary whole-trajectory total).", "Input plus output tokens summed within each arm and paired block, then paired ratio calculated.", ["pairs"], 192, "matched whole trajectory"),
          quantity("ecdf", "Empirical cumulative proportion", "%", "Percentage of the 192 paired reductions at or below the horizontal coordinate.", "Sorted, tie-collapsed right-continuous empirical distribution; each of 192 recorded pairs carries equal weight. Zero and unity tails span the declared plotting domain.", ["pairs"], 192, "matched whole trajectory")]
    write_figure(fid, body, caption, f"190 of the 192 recorded paired trajectories use fewer total tokens with EAL, with a median reduction of {median:.2f}%.", "How heterogeneous are paired token changes?", "The empirical step distribution retains two increased-token trajectories and the observed spread.", pp, qs, [encoding("horizontal", ["reduction"], "position", "Horizontal position is the signed paired percentage reduction in total tokens.", [-10,60]), encoding("vertical", ["ecdf"], "position", "Vertical position is the fraction at or below that recorded reduction.", [0,100])], expected_labels=["Median reduction", "Trajectories at or below"])

    # One genuine comparison: a fixed-bin histogram of the identical reductions.
    proto = "01-token-distribution-histogram"
    edges = np.arange(-10, 65, 5)
    counts, _ = np.histogram(reduction, edges)
    assert counts.sum() == 192
    centres = (edges[:-1] + edges[1:]) / 2
    hbody = r"\begin{axis}[xmin=-10,xmax=60,ymin=0,ymax=70,xtick={-10,0,10,20,30,40,50,60},xlabel={Reduction in total tokens per matched trajectory (\%)},ylabel={Recorded trajectories},ymajorgrids=true]" + "\n"
    hbody += plot(centres, counts, "ybar,bar width=8.1mm,ealblue,fill=ealblue!35,line width=0.5pt")
    hbody += "\\end{axis}\n"
    write_figure(proto, hbody, "Histogram prototype of the same 192 paired whole-trajectory token reductions, in fixed five-percentage-point bins from -10% through 60%. The bins reveal local frequency but introduce a binning choice.", "The paired token reductions occupy a finite, heterogeneous observed range.", "Does a histogram or ECDF better retain the observed distribution?", "Histogram reveals local frequency; ECDF permits cumulative lookup without choosing bins.", pp, [qs[0], quantity("count", "Recorded count per bin", "trajectories", "Number of recorded reductions in each declared five-point bin.", "Fixed edges -10,-5,...,60; final upper edge included by NumPy histogram convention.", ["pairs"], 192, "matched whole trajectory")], [encoding("horizontal", ["reduction"], "position", "Fixed bin position on paired percentage reduction.", [-10,60]), encoding("bar", ["count"], "length", "Bar height is the count in the fixed bin; baseline zero.", [0,70], marks="rectangular data bars")])
    ids.append(proto)

    # 2. Distinguish assigned recipient groups from the donor-inclusive endpoint.
    fid = "02-token-subgroups"; ids.append(fid)
    groups = []
    for receiver in ["plain", "reasoning"]:
        for native in [False, True]:
            g = pair[(pair.receiver == receiver) & (pair.native_tools == native)]
            assert len(g) == 48
            recipients = sessions[(sessions.phase == "recipient") & (sessions.receiver == receiver) & (sessions.native_tools == native)]
            assert len(recipients) == 960
            recipient_totals = recipients.groupby("arm").total_tokens.sum()
            groups.append({"receiver": receiver, "native_tools": native, "pairs": len(g),
                           "whole_sessions_per_arm": 528, "recipient_sessions_per_arm": 480,
                           "ordinary_tokens": g.ordinary_total_tokens.sum(), "eal_tokens": g.eal_total_tokens.sum(),
                           "reduction_pct": 100*(1-g.eal_total_tokens.sum()/g.ordinary_total_tokens.sum()),
                           "ordinary_recipient_tokens": recipient_totals["ordinary"], "eal_recipient_tokens": recipient_totals["eal"],
                           "recipient_reduction_pct": 100*(1-recipient_totals["eal"]/recipient_totals["ordinary"])})
    gd = pd.DataFrame(groups); gd.to_csv(TABLES / f"{fid}.csv", index=False)
    labels = [f"{r.receiver.capitalize()} / {'tools' if r.native_tools else 'no tools'}" for r in gd.itertuples()]
    def subgroup_picture(offset):
        body = r"\begin{axis}[width=138mm,height=77mm,xmin=0,xmax=55,ymin=0.5,ymax=4.5,ytick={1,2,3,4},yticklabels={" + ",".join("{"+x+"}" for x in labels) + r"},xlabel={Pooled total-token reduction (\%)},xtick={0,10,20,30,40,50},xmajorgrids=false,legend columns=2,legend style={at={(0.5,1.06)},anchor=south,column sep=4mm}]" + "\n"
        for role, col, mark, shift, label in [("reduction_pct",BLUE,"square*",offset,"Donor + ten recipients"),("recipient_reduction_pct",ORANGE,"triangle*",-offset,"Ten recipients only")]:
            for y, row in enumerate(gd.itertuples(), 1):
                value = float(getattr(row, role))
                body += plot([value], [y+shift], f"forget plot,only marks,mark={mark},mark size=2pt,{col},line width=0.5pt")
                if offset:
                    body += f"\\node[anchor=west,font=\\fontsize{{9}}{{11}}\\selectfont] at (axis cs:{value+0.7},{y+shift}) {{{value:.1f}\\%}};\n"
            body += f"\\addlegendimage{{only marks,mark={mark},mark size=2pt,{col},line width=0.5pt}}\\addlegendentry{{{label}}}\n"
        return body + "\\end{axis}\n"
    body = subgroup_picture(0.18)
    caption = r"Pooled total-token reductions in four assigned recipient-model/tool groups. Squares include the donor and ten recipients; triangles include only ten recipients. Each group contains 48 paired trajectories, corresponding to 528 donor-inclusive or 480 recipient-only sessions per arm. Both estimators use $100(1 - \mathrm{summed\ EAL\ tokens}/\mathrm{summed\ ordinary\ tokens})$, with role-specific denominators. Donors with native tools are pooled across both donor models in the inclusive result; the recipient-only result refers to the actual recipient model. Native tools are permitted in the enabled mode, alongside EAL host assessment."
    inputs = pp + ss
    quantities = [quantity("whole", "Donor-inclusive pooled token reduction", "%", "100 times one minus the ratio of donor-plus-ten-recipient EAL and ordinary token sums within the assigned recipient group.", "Group matched whole trajectories by assigned recipient model and native-tool permission, pooling donors, cases and repeats.", ["pairs"],48,"matched trajectories per group",inclusion="48 complete matched trajectories in each assigned recipient-model/tool group; donor plus ten recipients gives 528 sessions per arm and group."),quantity("recipients", "Recipient-only pooled token reduction", "%", "100 times one minus the ratio of recipient-only EAL and ordinary token sums within the assigned recipient group.", "Select phase=recipient and the named recipient-model/native-tool group; sum input plus output tokens separately by arm before forming the ratio.", ["sessions"],48,"matched trajectories per group",inclusion="The same 48 matched trajectories in each assigned recipient-model/tool group, retaining only ten recipients: 480 sessions per arm and group."),quantity("stratum","Assigned recipient model and tool permission","category","Ordered pair of assigned recipient model and native-tool permission, as printed in the row labels.","Project matched-block identities onto assigned receiver and native_tools, retaining all donor profiles within the group.",["pairs"]),quantity("role","Included session role","category","Donor plus ten recipients, or ten recipients only.","Retain the explicit role inclusion when comparing the two pooled estimators.",["pairs","sessions"])]
    encodings = [encoding("horizontal", ["whole","recipients"], "position", "The horizontal value is the explicitly role-specific pooled percentage reduction.", [0,55],marks="square and triangle data markers"),encoding("group", ["stratum"], "position", "Each named recipient-model/tool group contains 48 matched trajectories; vertical offsets distinguish role inclusion within that category.",labels,marks="square and triangle data markers in categorical rows",interpretation="categorical",mapping="nominal"),encoding("rolemarks",["role"],"shape","Squares denote donor plus ten recipients; triangles denote ten recipients only.",["Donor + ten recipients","Ten recipients only"],marks="square and triangle data markers",interpretation="categorical",mapping="nominal")]
    write_figure(fid,body,caption,"All four assigned recipient groups show lower EAL token sums in both donor-inclusive and recipient-only comparisons, with different role-specific magnitudes.","How does retaining the donor affect the assigned-recipient-group token contrast?","Distinct role markers expose the inclusive primary endpoint and the recipient-only decomposition without attributing donor usage to the recipient model.",inputs,quantities,encodings)
    prototype = "02-token-subgroups-overlaid"
    ids.append(prototype)
    prototype_encodings=json.loads(json.dumps(encodings))
    for e in prototype_encodings:
        if e["id"]=="group":
            e["represents"]="Each named recipient-model/tool group contains 48 matched trajectories; both role markers share the category row centre."
            e["scale_or_mapping"]["definition"]=e["represents"]
    write_figure(prototype,subgroup_picture(0),"Comparison prototype using the same role-specific values as the selected recipient-group comparison, with both role markers on one row centre. The square denotes donor plus ten recipients and triangle denotes recipients only.","The same two role-specific pooled contrasts can be compared with coincident nominal row positions.","Do coincident or vertically separated role markers permit clearer recovery of two close reductions?","This rendered alternative removes the within-row role offsets while retaining the common numerical scale.",inputs,quantities,prototype_encodings)

    # 3. Cumulative totals retain the donor at horizon zero.
    fid = "03-cumulative-tokens"; ids.append(fid)
    body = r"\begin{axis}[width=140mm,height=66mm,xmin=0,xmax=10.9,ymin=0,ymax=3.25,xtick={0,2,4,6,8,10},ytick={0,0.5,1,1.5,2,2.5,3},xlabel={Recipient horizon after the donor},ylabel={Cumulative total tokens (millions)},ymajorgrids=false]" + "\n"
    for arm, col, dash in [("ordinary", ORANGE, "dashed"), ("eal", BLUE, "solid")]:
        g = cum[cum.arm == arm].sort_values("recipient_horizon")
        body += plot(g.recipient_horizon, g.total_tokens/1e6, f"{col},{dash},line width=0.9pt,mark={'triangle*' if arm=='ordinary' else 'square*'},mark size=1.6pt")
        last = g.iloc[-1]
        body += f"\\node[anchor=west,font=\\fontsize{{9}}{{11}}\\selectfont] at (axis cs:10.1,{last.total_tokens/1e6}) {{{'Ordinary' if arm=='ordinary' else 'EAL'}}};\n"
    body += "\\end{axis}\n"
    caption = "Cumulative total input plus output tokens across all 192 trajectories per arm. The horizontal coordinate is recipient session position. Position zero includes the donor; each later point adds the indicated number of recipients. At horizon ten, ordinary uses 2,982,385 tokens and EAL 1,980,029, a pooled reduction of 33.61%. The smaller 47.46% donor reduction becomes 33.61% after ten recipients; the lines describe observed finite trajectories, without extrapolation."
    # Correct the wording: 47.46 is the larger initial relative reduction.
    caption = caption.replace("The smaller 47.46% donor reduction", "The 47.46% donor reduction")
    write_figure(fid, body, caption, "EAL uses fewer cumulative total tokens at each observed horizon, including the donor cost.", "How does the token difference evolve when donor cost is retained?", "Two cumulative curves include the full donor at zero and all recorded recipients through horizon ten.", cc, [quantity("cumtokens", "Cumulative total tokens", "million tokens", "Sum of provider input plus output tokens through donor session zero and each recipient horizon.", "Aggregate all 192 trajectories separately by arm and divide tokens by one million for axis labelling.", ["horizons"], 192, "trajectory per arm", inclusion="All 192 donor-inclusive trajectories within each arm; the input table contains 384 arm-specific trajectories overall."),quantity("horizon","Recipient horizon","recipients","Number of recipient sessions included after donor session zero, from zero through ten.","Use the retained integer recipient_horizon field; zero includes only the donor.",["horizons"])], [encoding("horizontal", ["horizon"], "position", "Horizontal order names the number of recipients included after the donor.", [0,10.9]), encoding("vertical", ["cumtokens"], "position", "Vertical position encodes cumulative input plus output tokens in millions; donor included.", [0,3.25])], expected_labels=["EAL", "Ordinary", "Recipient horizon after the donor"])

    # 4. Token composition uses a disjoint partition of accounting categories.
    fid = "04-token-composition"; ids.append(fid)
    recipient_rows = sessions[sessions.phase == "recipient"]
    assert len(recipient_rows) == 3840
    assert (recipient_rows[recipient_rows.receiver == "plain"].reasoning_tokens == 0).all()
    assert (recipient_rows.groupby(["receiver", "native_tools", "arm"]).size() == 480).all()
    comp = recipient_rows.groupby(["receiver", "native_tools", "arm"])[["input_tokens","output_tokens","reasoning_tokens"]].sum().reset_index()
    comp["other_output_tokens"] = comp.output_tokens-comp.reasoning_tokens
    comp["total_tokens"] = comp.input_tokens+comp.output_tokens
    comp.to_csv(TABLES / f"{fid}.csv", index=False)
    rows = []
    for receiver in ["plain", "reasoning"]:
        for native in [False, True]:
            for arm in ["ordinary", "eal"]:
                rows.append(comp[(comp.receiver == receiver)&(comp.native_tools == native)&(comp.arm==arm)].iloc[0])
    labels = [f"{r.receiver.capitalize()} / {'tools' if r.native_tools else 'no tools'} / {'O' if r.arm=='ordinary' else 'E'}" for r in rows]
    maxval = max(r.total_tokens for r in rows)/1e6
    body = r"\begin{axis}[width=110mm,height=89mm,xmin=0,xmax=1.25,ymin=0.3,ymax=8.7,ytick={1,2,3,4,5,6,7,8},yticklabels={" + ",".join("{"+x+"}" for x in labels) + r"},title={Recipient sessions only},title style={at={(0.5,1.16)},anchor=south},xlabel={Recipient tokens (millions)},xtick={0,0.2,0.4,0.6,0.8,1,1.2},xmajorgrids=false,legend columns=3,legend style={at={(0.5,1.05)},anchor=south,column sep=3mm}]" + "\n"
    # Draw stacks explicitly so every extent is an additive accounting category.
    for y,r in enumerate(rows,1):
        left = 0.0
        for name, colour in [("input_tokens",GREY),("other_output_tokens",BLUE),("reasoning_tokens",ORANGE)]:
            right = left+float(r[name])/1e6
            if right > left:
                body += f"\\path[fill={colour}!65,draw={colour},line width=0.5pt] (axis cs:{left:.10g},{y-0.27}) rectangle (axis cs:{right:.10g},{y+0.27});\n"
            left = right
        body += f"\\node[anchor=west,font=\\fontsize{{9}}{{11}}\\selectfont] at (axis cs:{left+0.01},{y}) {{{left:.2f}}};\n"
    for name,colour in [("Input",GREY),("Other output",BLUE),("Reasoning output",ORANGE)]:
        body += f"\\addlegendimage{{area legend,fill={colour}!65,draw={colour},line width=0.5pt}}\\addlegendentry{{{name}}}\n"
    body += "\\end{axis}\n"
    caption = "Disjoint token-accounting components for recipient sessions only, grouped by actual recipient model and native-tool permission. Donor sessions are intentionally excluded from this decomposition; the primary endpoint retains donors. O denotes ordinary and E denotes EAL. Input includes cached input; other output is output minus provider-reported reasoning output. Reasoning is already contained in output and is shown once. Bar endpoints therefore equal input plus output, with no double counting. Each recipient-model/tool/arm group contains 480 recipient sessions from 48 trajectories. Provider-reported reasoning output is zero for plain recipients."
    write_figure(fid, body, caption, "Input-token use supplies most of the recorded recipient-only token difference; the disjoint output partition refers to actual recipient models.", "Which accounting components contribute to the recipient-only token contrast?", "Aligned stacked bars retain mutually exclusive token categories and explicit arm/profile labels.", ss, [quantity("input", "Provider input tokens", "million tokens", "Recipient input usage, including cached input, from provider records.", "Select phase=recipient; sum in recipient-model/tool/arm group and divide by one million.", ["sessions"], 480,"recipient sessions per bar",inclusion="Ten recipient sessions from each of 48 trajectories in the named model/tool/arm group; all donor sessions excluded."), quantity("otheroutput", "Other provider output tokens", "million tokens", "Provider output minus provider-reported reasoning output.", "Select phase=recipient; subtract reasoning once within recipient session, aggregate within group, then divide by one million.", ["sessions"], 480,"recipient sessions per bar",inclusion="Ten recipient sessions from each of 48 trajectories in the named model/tool/arm group; all donor sessions excluded."), quantity("reasoning", "Reasoning output tokens", "million tokens", "Provider-reported reasoning subset of output usage.", "Select phase=recipient; sum in recipient-model/tool/arm group divided by one million; not added again to total output.", ["sessions"], 480,"recipient sessions per bar",inclusion="Ten recipient sessions from each of 48 trajectories in the named model/tool/arm group; all donor sessions excluded."),quantity("rowgroup","Receiver, tool and arm identity","category","Receiver profile, permission for native tools and arm jointly identify each labelled row; O is ordinary and E is EAL.","Select phase=recipient before grouping on actual recipient model/native_tools/arm, pooling over donor assignment, selected cases and repeats.",["sessions"])], [encoding("stack", ["input","otheroutput","reasoning"], "length", "Disjoint accounting components add from zero to provider input plus output.", [0,1.25], marks="stacked rectangular data bars"), encoding("category", ["input","otheroutput","reasoning"], "colour", "Tone and explicit legend identify the three accounting components.", ["Input","Other output","Reasoning output"], marks="stacked rectangular data bars", interpretation="categorical", mapping="nominal"),encoding("rows",["rowgroup"],"position","Each row is the named actual recipient-model/tool/arm group, with 480 recipient sessions from 48 trajectories; donor sessions excluded.",labels,marks="stacked rectangular data bars in categorical rows",interpretation="categorical",mapping="nominal")])

    # 5. A shared ratio scale exposes the resource boundary.
    fid = "05-resource-ratios"; ids.append(fid)
    metric_rows = [("total_tokens", "Total tokens"), ("known_cost_usd", "API price subtotal"), ("api_attempts", "API attempts"), ("api_elapsed_seconds", "API-call time"), ("elapsed_with_setup_seconds", "Session + setup time"), ("native_tool_calls", "Native acquisitions"), ("total_collector_calls", "All acquisitions")]
    rr=[]
    body=r"\begin{axis}[width=138mm,height=79mm,xmin=0,xmax=3.15,ymin=0.4,ymax=7.6,xtick={0,0.5,1,1.5,2,2.5,3},ytick={1,2,3,4,5,6,7},yticklabels={"+",".join("{"+label+"}" for _,label in metric_rows)+r"},xlabel={EAL / ordinary recorded resource ratio},xmajorgrids=false]"+"\n"
    body += plot([1,1],[0.4,7.6],"neutralgrey,dashed,line width=0.5pt,no marks")
    for y,(metric,label) in enumerate(metric_rows,1):
        ratio=float(eal[metric]/ordinary[metric]); rr.append({"metric":metric,"ordinary":float(ordinary[metric]),"eal":float(eal[metric]),"ratio":ratio})
        col=BLUE if ratio<1 else ORANGE
        body += plot([1,ratio],[y,y],f"{col},line width=0.7pt,no marks")
        body += plot([ratio],[y],f"{col},only marks,mark=square*,mark size=2pt,line width=0.5pt")
        anchor = "east" if ratio < 1 else "west"
        label_x = ratio - 0.04 if ratio < 1 else ratio + 0.04
        body += f"\\node[anchor={anchor},font=\\fontsize{{9}}{{11}}\\selectfont] at (axis cs:{label_x},{y}) {{{100*(ratio-1):+.1f}\\%}};\n"
    body += "\\end{axis}\n"
    pd.DataFrame(rr).to_csv(TABLES / f"{fid}.csv",index=False)
    caption = "Whole-run ratios include donors, recipients and measured sequence setup where stated. Unity denotes equal recorded use. EAL reduces total tokens, the recorded API price subtotal and client-observed API-call time, while increasing summed session/setup duration and total acquisitions. Client-observed API request duration is nested inside session duration; it is not provider-internal computation time and these durations are not added. The price subtotal applies recorded plan rates, excludes cache discounts and remains unreconciled with an invoice. Authoring, maintenance, review and infrastructure costs remain unmeasured. Decision-match evidence is reported separately from these unchanged resource ratios and is conditional on AI coding."
    qs=[quantity("ratios","Whole-run resource ratios","dimensionless","EAL all-session resource total divided by ordinary all-session total for each named metric.","Form ratio separately for seven explicitly different recorded resources; never add their units.",["totals"],384,"whole trajectory")]
    qs.append(quantity("metric","Recorded resource identity","category","One of the seven named resource measures, with its own unit before normalisation.","Retain explicit metric identity when each separately computed EAL/ordinary ratio is plotted.",["totals"]))
    write_figure(fid,body,caption,"The selected EAL trajectories have lower recorded total tokens and API price subtotal, with greater summed session/setup duration and more total evidence acquisitions.","Does the apparent saving persist across resource boundaries?","Ratios on a common dimensionless scale reveal adverse as well as favourable resource contrasts.",tt,qs,[encoding("ratio","ratios".split(),"position","Each position is a ratio for the specifically named resource; one is equality.",[0,3.15]),encoding("metricrow",["metric"],"position","Vertical row labels name distinct resources rather than a shared dimensional quantity.",[label for _,label in metric_rows],marks="square data markers with horizontal comparison segments in categorical rows",interpretation="categorical",mapping="nominal")],expected_labels=["All acquisitions","API price subtotal"])

    # 6. Whole-trajectory latency contrasts retain adverse tails.
    fid="06-latency-distribution";ids.append(fid)
    delay=pair.difference_elapsed_with_setup_seconds.to_numpy()
    lx,ly=ecdf(delay, (-20, 25))
    pd.DataFrame({"difference_seconds":lx,"cumulative_pct":ly}).to_csv(TABLES/f"{fid}.csv",index=False)
    median_delay=float(np.median(delay)); slower=int((delay>0).sum())
    body=r"\begin{axis}[xmin=-20,xmax=25,ymin=0,ymax=100,xtick={-20,-10,0,10,20},ytick={0,25,50,75,100},xlabel={Difference in summed session + setup time (s)},ylabel={Trajectories at or below (\%)},ymajorgrids=true]"+"\n"
    body+=plot([0,0],[0,100],"neutralgrey,dashed,line width=0.5pt,no marks")
    body+=plot(lx,ly,"ordinaryorange,line width=0.9pt,no marks,const plot")
    body+=f"\\node[anchor=west,font=\\fontsize{{9}}{{11}}\\selectfont] at (rel axis cs:0.03,0.89) {{Median: {median_delay:+.2f} s}};\n"
    body+=f"\\node[anchor=west,font=\\fontsize{{9}}{{11}}\\selectfont] at (rel axis cs:0.03,0.82) {{{slower}/192 have higher summed time}};\n"
    body+="\\end{axis}\n"
    caption=f"Empirical distribution of the EAL-minus-ordinary difference in summed session times plus measured sequence setup in 192 matched pairs. Positive differences mean a higher EAL accumulated-time sum; {slower} of 192 pairs have a positive difference and the median difference is {median_delay:+.2f} seconds. The measured range is ${delay.min():.2f}$ to ${delay.max():.2f}$ seconds. Concurrent session sums describe accumulated activity, not workflow wall-clock time; context and client-observed API-attempt times are already nested within session duration."
    qs=[quantity("delay","Paired summed session and setup time difference","seconds","EAL summed donor/recipient session time plus sequence setup minus the corresponding ordinary accumulated-time sum.","Sum within each whole trajectory, retain measured sequence setup, subtract within matched pair.",["pairs"],192,"matched whole trajectory"),quantity("ecdf","Empirical cumulative proportion","%","Percentage of the 192 paired duration differences at or below the horizontal coordinate.","Sort differences with equal weight per matched trajectory.",["pairs"],192,"matched whole trajectory")]
    write_figure(fid,body,caption,f"{slower} of 192 paired trajectories have higher EAL summed session and setup time; the median difference is {median_delay:+.2f} seconds.","How variable are whole-trajectory timing changes?","The empirical distribution exposes faster pairs and slower pairs with a signed zero reference.",pp,qs,[encoding("horizontal",["delay"],"position","Horizontal position is EAL minus ordinary summed session time plus measured sequence setup.",[-20,25]),encoding("vertical",["ecdf"],"position","Vertical position is the empirical percentage at or below the recorded difference.",[0,100])])

    # 7. Snapshot reuse is a separate event type, not an acquisition.
    fid="07-acquisition-horizon";ids.append(fid)
    body=r"\begin{axis}[height=72mm,xmin=0,xmax=10,ymin=0,ymax=1800,xtick={0,2,4,6,8,10},ytick={0,400,800,1200,1600},xlabel={Recipient horizon after the donor},ylabel={Recorded events, summed trajectories},ymajorgrids=true,legend columns=2,legend style={at={(0.5,1.06)},anchor=south,column sep=4mm}]"+"\n"
    series=[("eal","total_collector_calls",BLUE,"solid","square*","EAL acquisitions"),("ordinary","total_collector_calls",ORANGE,"dashed","triangle*","Ordinary acquisitions"),("eal","host_collections",GREY,"dash dot","x","EAL host acquisitions"),("eal","host_reuses",GREY,"dotted","+","Host reuses (excluded)")]
    for arm,metric,col,dash,mark,label in series:
        g=cum[cum.arm==arm].sort_values("recipient_horizon")
        body+=plot(g.recipient_horizon,g[metric],f"{col},{dash},line width=0.8pt,mark={mark},mark size=1.7pt")
        body+=f"\\addlegendentry{{{label}}}\n"
    body+="\\end{axis}\n"
    caption="Cumulative recorded acquisitions and EAL snapshot reuses include donor session zero. At horizon ten, EAL has 1,724 acquisitions: 1,152 host acquisitions and 572 native acquisitions. Ordinary has 646 native acquisitions and zero host acquisitions. EAL's 960 host reuses are shown separately and excluded from the acquisition total. Reusing snapshots therefore coexists with more total acquisitions in this selected run; a reuse is neither an API cache hit nor a fresh acquisition. An acquisition counts one snapshot collector invocation. The fixture deliberately places recipient assessments at and beyond the inclusive 60-second snapshot-validity boundary, specifying opportunities for host reuse and refresh; native probes remain recorded model behaviour."
    qs=[quantity("acquisitions","Evidence acquisitions","recorded events","Native probe events plus EAL host collected_count, excluding reused_count.","Sum all recorded acquisition events through each donor-inclusive horizon separately by arm; show EAL host subset separately.",["horizons"],192,"trajectory per arm",inclusion="All 192 donor-inclusive trajectories within each arm; the input table contains 384 arm-specific trajectories overall."),quantity("reuses","Host snapshot reuses","recorded events","Recorded EAL host reused_count; not a fresh collection.","Sum host reused_count through each donor-inclusive horizon, keeping separate from acquisitions.",["horizons"],192,"trajectory per arm",inclusion="All 192 donor-inclusive trajectories within each arm; the input table contains 384 arm-specific trajectories overall.")]
    qs.append(quantity("horizon","Recipient horizon","recipients","Number of recipient sessions included after donor session zero, from zero through ten.","Use retained integer recipient_horizon; zero includes the donor only.",["horizons"]))
    write_figure(fid,body,caption,"Recorded EAL host snapshot reuse accompanies more total evidence acquisitions than ordinary at the final horizon.","How do evidence acquisition and snapshot reuse change with repeated handovers?","Solid/dashed acquisition totals and separately labelled host events prevent treating reuse as an acquisition reduction.",cc,qs,[encoding("horizontal",["horizon"],"position","Horizontal order is the number of recipient sessions completed after the donor.",[0,10]),encoding("vertical",["acquisitions","reuses"],"position","Vertical position counts the precisely named recorded event type; host reuses are excluded from all acquisitions.",[0,1800])])

    # 8. Complete coding entries retain unresolved communication decisions.
    fid="08-measurement-status";ids.append(fid)
    n=int(summary["audit"]["session_rows"])
    resolved=int(completion["counts"]["coded_resolved"])
    ambiguous=int(completion["counts"]["coded_ambiguous"])
    assert n==4224 and resolved==4199 and ambiguous==25 and resolved+ambiguous==n
    labels=["Completed sessions","Resource records","AI-coded entries","Resolved decisions","Ambiguous decisions"]
    vals=[n,n,n,resolved,ambiguous]
    body=r"\begin{axis}[width=134mm,height=68mm,xmin=0,xmax=4900,ymin=0.5,ymax=5.5,xtick={0,1000,2000,3000,4224},ytick={1,2,3,4,5},yticklabels={"+",".join("{"+x+"}" for x in labels)+r"},xlabel={Recorded session count},xmajorgrids=false]"+"\n"
    for y,(label,value) in enumerate(zip(labels,vals),1):
        body+=plot([value],[y],f"{GREY},only marks,mark=square*,mark size=2.2pt,line width=0.5pt")
        body+=f"\\node[anchor=west,font=\\fontsize{{9}}{{11}}\\selectfont] at (axis cs:{value+80},{y}) {{{value:,}}};\n"
    body+="\\end{axis}\n"
    caption="Original finish recording and AI-coding snapshot for the same 4,224 sessions, before the supplemental review. Completed-session, resource-record and coded-entry rows overlap and must not be added. Resolved and ambiguous decisions partition the coded entries: 4,199 are resolved and 25 remain ambiguous, with 12 ordinary and 13 EAL ambiguities. Every answer has a coding entry; this does not establish a resolved decision for every answer or independent adjudication. AI-coded agreement with authored references is analysed separately, without independent human validation or a measured assessor-error rate."
    inputs=[("status","analysis/resource_summary.json","Independent resource audit of the original recorded sessions."),("coding","analysis/completion-outcomes.json","Independently reproduced AI coding and joins from finish run 36997861629; the underlying recorded sessions are unchanged.")]
    qs=[coded_quantity("counts","Recording or AI-coding count","sessions","Number of sessions satisfying each named recording/coding status.","Use the audited original session count and independently reconstructed resolved/ambiguous coding counts; retain overlapping rows and their one disjoint partition.",["status","coding"],4224,"recorded sessions","All 4,224 original sessions with a coding entry in the finish run.",ambiguity=False),coded_quantity("recordingstatus","Recording or AI-coding status","category","Completion, resource record, AI coding entry, resolved communication or ambiguous communication.","Retain explicit condition identity; only resolved plus ambiguous is an additive partition.",["coding"],4224,"recorded sessions","All original sessions, including donor and recipients in both arms.",ambiguity=False)]
    write_figure(fid,body,caption,"All 4,224 recorded sessions have AI-coded entries, with 4,199 resolved communications and 25 ambiguities.","Which recording and coding stages are complete, and which decisions remain unresolved?","Complete entry coverage is distinct from resolved communication and independent adjudication.",inputs,qs,[encoding("horizontal",["counts"],"position","Each horizontal position counts the named condition, not correct answers.",[0,4900],marks="square point data markers"),encoding("statusrow",["recordingstatus"],"position","Named recording/coding conditions overlap except for the resolved-versus-ambiguous partition.",labels,marks="square point data markers in categorical rows",interpretation="categorical",mapping="nominal")],quality=True)
    # 9. A joint paired view retains the trade-off obscured by separate marginals.
    fid="09-paired-tradeoff";ids.append(fid)
    joint=pair[["pair_id","receiver","native_tools"]].copy()
    joint["token_reduction_pct"]=reduction
    joint["summed_time_difference_seconds"]=delay
    quadrant_counts={"fewer_higher":int(((reduction>0)&(delay>0)).sum()),"fewer_lower":int(((reduction>0)&(delay<0)).sum()),"more_higher":int(((reduction<0)&(delay>0)).sum()),"more_lower":int(((reduction<0)&(delay<0)).sum())}
    assert quadrant_counts == {"fewer_higher":136,"fewer_lower":54,"more_higher":2,"more_lower":0}
    assert (reduction!=0).all() and (delay!=0).all()
    joint.to_csv(TABLES/f"{fid}.csv",index=False)
    body=r"\begin{axis}[width=146mm,height=85mm,xmin=-10,xmax=60,ymin=-20,ymax=27,xtick={-10,0,10,20,30,40,50,60},ytick={-20,-10,0,10,20},xlabel={Paired total-token reduction (\%)},ylabel={Difference in summed session + setup time (s)},legend columns=2,legend style={at={(0.5,1.05)},anchor=south,column sep=4mm}]"+"\n"
    body+=plot([0,0],[-20,27],"forget plot,neutralgrey,dashed,line width=0.5pt,no marks")
    body+=plot([-10,60],[0,0],"forget plot,neutralgrey,dashed,line width=0.5pt,no marks")
    for profile,mark,fill in [("plain","square*","neutralgrey!45"),("reasoning","triangle*","neutralgrey")]:
        g=joint[joint.receiver==profile]
        assert len(g)==96
        body+=plot(g.token_reduction_pct,g.summed_time_difference_seconds,f"only marks,mark={mark},mark size=1.8pt,neutralgrey,line width=0.5pt,mark options={{fill={fill}}}")
        body+=f"\\addlegendentry{{Assigned recipient: {profile}}}\n"
    for x,y,key in [(-5,24,"more_higher"),(50,24,"fewer_higher"),(-5,-18,"more_lower"),(50,-18,"fewer_lower")]:
        body+=f"\\node[font=\\fontsize{{9}}{{11}}\\selectfont] at (axis cs:{x},{y}) {{{quadrant_counts[key]} pairs}};\n"
    body+="\\end{axis}\n"
    caption=r"Joint resource contrasts in all 192 matched whole trajectories, including the donor, ten recipients and measured sequence setup in the time sum. The horizontal percentage is computed per matched trajectory as $100(1 - \mathrm{EAL\ total\ tokens}/\mathrm{ordinary\ total\ tokens})$. Positive horizontal values mean fewer EAL tokens; positive vertical values mean higher EAL summed time. The quadrants contain 136 fewer-token/higher-time pairs, 54 fewer-token/lower-time pairs, two more-token/higher-time pairs and zero more-token/lower-time pairs. Square and triangle data marks distinguish assigned recipient model, while the totals retain both donor and recipient phases. Repeated fixed-case observations support this descriptive joint comparison; no causal relation or fitted trend is asserted."
    qs=[quantity("reduction","Paired whole-trajectory token reduction","%","100(1 - EAL whole-trajectory total tokens / ordinary whole-trajectory total tokens).","Sum input plus output within each arm and matched trajectory; form the paired ratio.",["pairs"],192,"matched whole trajectories",inclusion="All 192 matched trajectories, donor plus ten recipients in each arm."),quantity("time","Difference in summed session and setup time","seconds","EAL summed donor/recipient session time and setup minus the corresponding ordinary sum.","Use the retained matched whole-trajectory accumulated-time difference, retaining measured sequence setup.",["pairs"],192,"matched whole trajectories",inclusion="All 192 matched trajectories, including all eleven session durations and measured setup in each arm."),quantity("recipient","Assigned recipient model","category","The recipient model assignment of the paired trajectory, even though both donor and recipient costs are included.","Retain receiver identity from the matched-block table.",["pairs"])]
    write_figure(fid,body,caption,"136 of 192 matched trajectories combine fewer EAL tokens with higher summed session and setup time, while 54 combine fewer tokens with lower summed time.","Do the token and accumulated-time contrasts occur in the same paired trajectories?","All 192 paired positions retain both numerical contrasts, zero boundaries and observed quadrant counts; model markers identify assignment without reattributing donor usage.",pp,qs,[encoding("horizontal",["reduction"],"position","Signed paired total-token reduction; positive means fewer EAL tokens.",[-10,60],marks="square and triangle point data markers"),encoding("vertical",["time"],"position","EAL minus ordinary summed session and setup time; positive means a higher EAL accumulated-time sum.",[-20,27],marks="square and triangle point data markers"),encoding("recipientmarks",["recipient"],"shape","Squares denote assigned plain recipients and triangles assigned reasoning recipients; these are data marks.",["plain","reasoning"],marks="square and triangle data markers",interpretation="categorical",mapping="nominal")])

    # 10. Disjoint phases reveal sign reversals hidden by whole-run aggregation.
    fid="10-phase-contrasts";ids.append(fid)
    metric_rows=[("total_tokens","Total tokens"),("api_attempts","API attempts"),("native_tool_calls","Native probe calls"),("elapsed_seconds","Summed session time")]
    phase_rows=[("initial","Donor",BLUE,"square*",0.22),("recipient","Ten recipients",ORANGE,"triangle*",0),("all","Whole (1 + 10)",GREY,"x",-0.22)]
    phase_values=[]
    body=r"\begin{axis}[width=132mm,height=86mm,xmin=-25,xmax=65,ymin=0.45,ymax=4.55,xtick={-20,0,20,40,60},ytick={1,2,3,4},yticklabels={Total tokens,API attempts,Native probe calls,Summed session time},xlabel={Pooled resource reduction: 100(1 - EAL / ordinary) (\%)},legend columns=3,legend style={at={(0.5,1.06)},anchor=south,column sep=2mm}]"+"\n"
    body+=plot([0,0],[0.45,4.55],"forget plot,neutralgrey,dashed,line width=0.5pt,no marks")
    for phase,label,col,mark,offset in phase_rows:
        phase_totals=totals[totals.phase==phase].set_index("arm")
        for y,(metric,_) in enumerate(metric_rows,1):
            o=float(phase_totals.loc["ordinary",metric]);e=float(phase_totals.loc["eal",metric]);value=100*(1-e/o)
            phase_values.append({"phase":phase,"metric":metric,"ordinary":o,"eal":e,"reduction_pct":value,"sessions_per_arm":int(phase_totals.loc["ordinary","sessions"])})
            body+=plot([value],[y+offset],f"forget plot,only marks,mark={mark},mark size=2pt,{col},line width=0.6pt")
            anchor="east" if value<0 else "west"
            label_x=value-0.9 if value<0 else value+0.9
            body+=f"\\node[anchor={anchor},font=\\fontsize{{9}}{{11}}\\selectfont] at (axis cs:{label_x},{y+offset}) {{{value:+.1f}\\%}};\n"
        body+=f"\\addlegendimage{{only marks,mark={mark},mark size=2pt,{col},line width=0.6pt}}\\addlegendentry{{{label}}}\n"
    body+="\\end{axis}\n"
    pd.DataFrame(phase_values).to_csv(TABLES/f"{fid}.csv",index=False)
    for metric,_ in metric_rows:
        for arm in ["ordinary","eal"]:
            phase=totals[totals.arm==arm].set_index("phase")
            assert np.isclose(phase.loc["all",metric],phase.loc["initial",metric]+phase.loc["recipient",metric])
    caption=r"Pooled resource reductions for the donor, ten recipients and their whole-trajectory sum, computed separately as $100(1 - \mathrm{EAL}/\mathrm{ordinary})$. Positive means lower EAL use; negative means higher EAL use. The donor includes 192 sessions per arm, recipients 1,920 and whole 2,112, covering the same 192 matched trajectories. Sequence setup is excluded from every timing value so the donor and recipient timing phases add exactly to the whole session-time sum. Recipient API attempts increase from 2,386 to 2,406 and native probe calls from 466 to 486, although both whole-run counts decrease. Native probes are counts, not acquisition costs; the whole is the sum of the two disjoint phases rather than an additional phase."
    qs=[]
    for phase,label,_,_,_ in phase_rows:
        phase_sessions={"initial":192,"recipient":1920,"all":2112}[phase]
        qs.append(quantity(phase,f"{label} pooled resource reductions","%","100(1 - EAL phase resource sum / ordinary phase resource sum), separately for tokens, API attempts, native probes and summed session time.",f"Select phase={phase}; form each ratio after aggregation. Exclude sequence setup from session-time contrasts.",["totals"],192,"matched trajectories per phase",inclusion=f"The same 192 matched trajectories contribute {phase_sessions} sessions per arm to this phase-specific aggregate; sequence setup excluded."))
    qs.append(quantity("metric","Recorded resource identity","category","Four explicitly named metrics, each separately normalised rather than added across units.","Retain metric names and explicit denominator for each phase ratio.",["totals"]))
    qs.append(quantity("phase","Included session phase","category","Donor, ten recipients, or their donor-inclusive whole-trajectory sum.","Retain phase inclusion identity after each resource is aggregated.",["totals"]))
    write_figure(fid,body,caption,"The recipient-only API-attempt and native-probe contrasts have opposite signs to the donor-inclusive whole-run contrasts.","Which resource contrasts change when the donor and recipient phases are separated?","Three phase markers on a common signed reduction scale expose recipient count increases alongside whole-run count decreases; session setup is consistently excluded.",tt,qs,[encoding("horizontal",["initial","recipient","all"],"position","Each x coordinate is a phase-specific ratio-of-sums reduction; positive means lower EAL use.",[-25,65],marks="square, triangle and cross point data markers"),encoding("metricrow",["metric"],"position","Rows name distinct resource metrics; within-row offsets distinguish phase inclusion, not metric magnitude.",[label for _,label in metric_rows],marks="square, triangle and cross point data markers in categorical rows",interpretation="categorical",mapping="nominal"),encoding("phasemarks",["phase"],"shape","Blue squares denote donor, orange triangles ten recipients, and grey crosses their whole-trajectory sum; vertical offsets separate phase markers within each metric row.",["Donor","Ten recipients","Whole (1 + 10)"],marks="square, triangle and cross data markers",interpretation="categorical",mapping="nominal")])

    # 11. Recorded synchronous boundaries support a disjoint duration partition.
    fid="11-time-partition";ids.append(fid)
    residual=sessions.elapsed_seconds-sessions.api_elapsed_seconds-sessions.context_seconds
    assert (residual>0).all(), "Every recorded session must have positive residual time."
    duration_rows=[]
    for arm in ["ordinary","eal"]:
        g=sessions[sessions.arm==arm]
        row={"arm":arm,"sessions":len(g),"client_api_attempt_seconds":g.api_elapsed_seconds.sum(),"context_seconds":g.context_seconds.sum(),"residual_seconds":(g.elapsed_seconds-g.api_elapsed_seconds-g.context_seconds).sum(),"session_seconds":g.elapsed_seconds.sum(),"sequence_setup_seconds":float(all_totals.loc[arm,"setup_seconds"])}
        assert np.isclose(row["session_seconds"],row["client_api_attempt_seconds"]+row["context_seconds"]+row["residual_seconds"])
        duration_rows.append(row)
    pd.DataFrame(duration_rows).to_csv(TABLES/f"{fid}.csv",index=False)
    body=r"\begin{axis}[name=sessionpanel,width=137mm,height=48mm,xmin=0,xmax=6100,ymin=0.5,ymax=2.5,ytick={1,2},yticklabels={Ordinary,EAL},xtick={0,1000,2000,3000,4000,5000,6000},xlabel={Summed session time (s)},legend columns=3,legend style={at={(0.5,1.07)},anchor=south,column sep=2mm}]"+"\n"
    for y,row in enumerate(duration_rows,1):
        left=0.0
        for key,col in [("client_api_attempt_seconds",GREY),("context_seconds",BLUE),("residual_seconds",ORANGE)]:
            right=left+row[key]
            body+=f"\\path[fill={col}!65,draw={col},line width=0.5pt] (axis cs:{left:.10g},{y-0.22}) rectangle (axis cs:{right:.10g},{y+0.22});\n"
            left=right
        body+=f"\\node[anchor=west,font=\\fontsize{{9}}{{11}}\\selectfont] at (axis cs:{left+60},{y}) {{{left:,.1f}}};\n"
    for label,col in [("Client API attempts",GREY),("Context",BLUE),("Residual",ORANGE)]:
        body+=f"\\addlegendimage{{area legend,fill={col}!65,draw={col},line width=0.5pt}}\\addlegendentry{{{label}}}\n"
    body+="\\end{axis}\n"
    body+=r"\begin{axis}[at={(sessionpanel.south west)},yshift=-22mm,anchor=north west,width=137mm,height=37mm,xmin=0,xmax=12,ymin=0.5,ymax=2.5,ytick={1,2},yticklabels={Ordinary,EAL},xtick={0,2,4,6,8,10,12},xlabel={Sequence setup time (s), separate scale}]"+"\n"
    for y,row in enumerate(duration_rows,1):
        value=row["sequence_setup_seconds"]
        body+=plot([0,value],[y,y],"black,line width=2pt,no marks")
        body+=f"\\node[anchor=west,font=\\fontsize{{9}}{{11}}\\selectfont] at (axis cs:{value+0.15},{y}) {{{value:.3f}}};\n"
    body+="\\end{axis}\n"
    caption="Partition of all recorded donor and recipient session-time sums, with measured sequence setup shown separately on its own explicitly labelled scale. Client API attempts are observed from immediately before synchronous transport through response decoding and accounting; they are not provider-internal compute time. Context construction finishes before the synchronous API loop. Residual time is defined as session time minus the two recorded components and is positive in all 4,224 sessions. The three components add exactly to session time; setup is then added once. Across 2,112 sessions per arm, EAL has 875.147 seconds of context construction, while ordinary has 0.005 seconds. Residuals are 6.846 and 7.492 seconds for EAL and ordinary respectively; the component names describe operational timing boundaries rather than infrastructure costs."
    qs=[quantity("components","Disjoint session-time components","seconds","Client-observed API-attempt time, context-construction time and the arithmetic residual partition each recorded session time.","Subtract API-attempt and context durations from each session duration; verify every residual is positive, then sum within arm.",["sessions"],2112,"sessions per arm",inclusion="All 192 donor plus 1,920 recipient sessions within each arm; setup is excluded from these session components."),quantity("setup","Measured sequence setup time","seconds","Sum of measured sequence setup, retained separately from all session durations.","Read whole-arm sequence setup sum from the phase resource table; the lower panel uses a distinct linear scale.",["totals"],192,"sequences per arm",inclusion="All 192 sequence-setup records per arm; included once per sequence and excluded from session components.")]
    qs.append(quantity("arm","Comparison arm","category","Ordinary or EAL recorded trajectory arm.","Retain the arm identity of each session and sequence aggregate.",["sessions","totals"]))
    qs.append(quantity("component","Recorded timing boundary","category","Client API attempts, context construction, and the residual of recorded session time.","Retain component identity in the disjoint timing partition.",["sessions"]))
    write_figure(fid,body,caption,"The higher EAL session-time sum includes recorded context construction despite lower client-observed API-attempt time; the disjoint components and separate setup reconcile exactly.","Which recorded timing boundaries contribute to accumulated session and setup time?","The upper panel partitions session time without double counting, and the lower panel displays setup on its separate declared scale.",ss+tt,qs,[encoding("sessioncomponents",["components"],"length","Disjoint component lengths add from zero to summed session time on the upper scale.",[0,6100],marks="stacked rectangular data bars"),encoding("setupscale",["setup"],"length","Black setup segments begin at zero on the separate lower scale, explicitly labelled as a different scale; the upper component legend does not apply to this panel.",[0,12],marks="horizontal data segments"),encoding("armrows",["arm"],"position","The two panels use the same named rows: ordinary below and EAL above.",["Ordinary","EAL"],marks="stacked rectangular bars and horizontal segments in categorical rows",interpretation="categorical",mapping="nominal"),encoding("componentcolours",["component"],"colour","Grey denotes client-observed API-attempt time, blue context construction, and orange arithmetic residual; stacked order and caption retain the same identity in greyscale.",["Client API attempts","Context","Residual"],marks="stacked rectangular data bars",interpretation="categorical",mapping="nominal")])

    ids.extend(build_completion_figures(completion))
    (ROOT/"figures/figure-calculation-checks.json").write_text(json.dumps({"paired_trajectories":192,"session_rows":4224,"total_tokens_ordinary":int(ordinary.total_tokens),"total_tokens_eal":int(eal.total_tokens),"ratio_of_sums_reduction_pct":float(100*(1-eal.total_tokens/ordinary.total_tokens)),"median_paired_reduction_pct":median,"token_saving_pairs":lower_count,"latency_slower_pairs":slower,"joint_quadrant_counts":quadrant_counts,"recipient_only_group_reductions":gd.recipient_reduction_pct.tolist(),"positive_timing_residuals":bool((residual>0).all()),"minimum_session_residual_seconds":float(residual.min()),"no_reasoning_double_count":True,"no_cached_input_double_count":True,"resource_plots_are_descriptive":True,"frozen_endpoint_bounds_imported_without_reestimation":True,"coding_resolved":resolved,"coding_ambiguous":ambiguous,"files":ids},indent=2)+"\n")
    return ids


def build_completion_figures(completion):
    """Use frozen, independently reconstructed coding counts and endpoint bounds."""
    confusion=pd.read_csv(TABLES/"completion-confusion.csv")
    confusion=confusion[confusion.role=="recipients"].copy()
    groups=pd.read_csv(TABLES/"completion-correctness-groups.csv")
    groups=groups[groups.dimension=="recipient_model_tools"].copy()
    endpoints=pd.read_csv(TABLES/"completion-endpoints.csv")
    assert len(groups)==8 and (groups.n==480).all()
    assert np.allclose(groups.lower,groups.known_correct/groups.n)
    assert np.allclose(groups.upper,(groups.known_correct+groups.ambiguous)/groups.n)
    assert np.all(groups.known_correct+groups.known_incorrect+groups.ambiguous==groups.n)
    assert (confusion[confusion.communicated=="no_answer"]["count"]==0).all()
    references=["ready","not_ready","undetermined"]
    decisions=["ready","not_ready","undetermined","ambiguous"]
    reference_counts={"ready":768,"not_ready":512,"undetermined":640}
    confusion=confusion[confusion.communicated.isin(decisions)].copy()
    assert len(confusion)==24
    for arm in ["ordinary","eal"]:
        for ref in references:
            g=confusion[(confusion.arm==arm)&(confusion.reference==ref)]
            assert len(g)==4 and g["count"].sum()==reference_counts[ref]
            assert (g.reference_n==reference_counts[ref]).all()
            assert np.allclose(g.fraction_of_reference,g["count"]/reference_counts[ref])
        expected=739 if arm=="ordinary" else 1866
        diagonal=confusion[(confusion.arm==arm)&(confusion.reference==confusion.communicated)]["count"].sum()
        assert diagonal==expected
        assert groups[groups.arm==arm].known_correct.sum()==expected
    coding_input=("coding","analysis/completion-outcomes.json","Independent reconstruction of frozen AI communication codes joined to authored decision references in finish run 36997861629; all original session observations retained.")
    ids=[]

    # 12. An explicit matrix retains false-ready routes and ambiguous coding.
    fid="12-recipient-decisions";ids.append(fid)
    confusion.to_csv(TABLES/f"{fid}.csv",index=False)
    body=r"\begin{scope}[x=14.5mm,y=12mm,every node/.style={font=\fontsize{9}{11}\selectfont}]"+"\n"
    body+=r"\node[font=\fontsize{10}{12}\selectfont] at (4.2,5.05) {AI-coded communicated decision};"+"\n"
    body+=r"\node[anchor=east] at (-0.12,3.85) {Reference};"+"\n"
    col_labels=["Ready",r"Not\\ready","Undet.","Ambig."]
    ref_labels={"ready":"Ready","not_ready":"Not ready","undetermined":"Undetermined"}
    for arm,offset,title in [("ordinary",0,"Ordinary"),("eal",4.45,"EAL")]:
        body+=f"\\node[font=\\fontsize{{10}}{{12}}\\selectfont] at ({offset+2},4.4) {{{title}}};\n"
        for j,label in enumerate(col_labels):
            body+=f"\\node[align=center,text width=13.5mm] at ({offset+j+0.5},3.75) {{{label}}};\n"
        for i,ref in enumerate(references):
            y=3-i
            if arm=="ordinary":
                body+=f"\\node[anchor=east,align=right,text width=27mm] at (-0.12,{y}) {{{ref_labels[ref]}\\\\$N={reference_counts[ref]}$}};\n"
            for j,decision in enumerate(decisions):
                row=confusion[(confusion.arm==arm)&(confusion.reference==ref)&(confusion.communicated==decision)].iloc[0]
                x=offset+j+0.5;shade=78*float(row.fraction_of_reference)
                colour="white" if shade>45 else "black"
                body+=f"\\path[fill=black!{shade:.6f},draw=black!30,line width=0.4pt] ({x-0.5},{y-0.43}) rectangle ({x+0.5},{y+0.43});\n"
                body+=f"\\node[text={colour}] at ({x},{y}) {{{int(row['count'])}}};\n"
    body+=r"\node at (4.2,0.1) {Tone: percentage within each reference row};"+"\n"
    for j,pct in enumerate([0,25,50,75,100]):
        x=2.2+j
        body+=f"\\path[fill=black!{0.78*pct},draw=black!30,line width=0.4pt] ({x-0.25},-0.65) rectangle ({x+0.25},-0.35);\n"
        body+=f"\\node at ({x},-1) {{{pct}\\%}};\n"
    body+="\\end{scope}\n"
    caption="Original finish recipient reference decisions versus AI-coded communicated decisions, excluding donors. Cells print counts; tone is the within-reference percentage on the same scale in both arms. Each arm has 1,920 recipients, with reference-row counts 768 ready, 512 not_ready and 640 undetermined. Undet. and Ambig. abbreviate undetermined and ambiguous communication. The ambiguous column retains all ten ordinary and thirteen EAL recipient ambiguities; no-answer counts are zero throughout and that column is omitted. Ready communications against not_ready or undetermined references total 653 ordinary and eight EAL. The matrix measures agreement and disagreement with authored references conditional on AI communication coding, not independently human-validated factual or explanation correctness."
    inputs=[("matrix","tables/completion-confusion.csv","Frozen reconstructed recipient confusion counts; original code/reference join verified for every session."),coding_input]
    qs=[coded_quantity("count","Reference/communication cell count","recipient sessions","Count of each AI-coded communication category within each authored reference decision and arm.","Select role=recipients; retain ambiguous as a separate communication category; omit only the verified all-zero no_answer column.",["matrix","coding"],1920,"recipient sessions per arm","Ten recipient positions from each of192 paired trajectories, with768/512/640 sessions in the three reference rows.",ambiguity=False),coded_quantity("share","Reference-conditional communication share","%","100 times cell count divided by the count of the named reference row in its arm.","Normalise each reference row by its own 768, 512 or 640 observed sessions; use a shared 0--100% tone mapping.",["matrix"],1920,"recipient sessions per arm","All recipient sessions; every within-row percentage uses the explicitly printed reference-row denominator.",ambiguity=False),coded_quantity("reference","Authored reference decision","category","Ready, not_ready or undetermined, computed from the authored fixture rules.","Retain reference category from the independently verified coding join.",["matrix"],1920,"recipient sessions per arm","All recipients, excluding donor sessions.",ambiguity=False),coded_quantity("communication","AI-coded communicated decision","category","Ready, not_ready, undetermined, or an ambiguous communication code.","Retain all communication codes as distinct categories; ambiguity is not a fourth reference class.",["matrix"],1920,"recipient sessions per arm","All recipients, including unresolved AI communication codes.",ambiguity=False),coded_quantity("arm","Recorded workflow arm","category","Ordinary or EAL, containing the same assigned reference-position mixture.","Retain arm identity in two explicitly labelled panels.",["matrix"],1920,"recipient sessions per arm","All 1920recipients in each arm.",ambiguity=False)]
    encs=[encoding("cellcounts",["count"],"text","Printed integer in each matrix cell is the complete reference/communication count.",[0,1920],marks="printed counts in rectangular matrix data cells"),encoding("celltone",["share"],"tone","Black percentage is 0.78 times within-reference percentage; white is 0% and black!78 is 100%, shared across arms.",[0,100],marks="rectangular matrix data cells"),encoding("rows",["reference"],"position","Rows align the same authored reference classes in both panels.",references,marks="rectangular matrix data cells in reference rows",interpretation="categorical",mapping="nominal"),encoding("columns",["communication"],"position","Columns identify AI-coded communication, including an explicit ambiguous column.",decisions,marks="rectangular matrix data cells in communication columns",interpretation="categorical",mapping="nominal"),encoding("armpanels",["arm"],"position","Separate labelled panels identify ordinary and EAL, without making panel distance quantitative.",["ordinary","eal"],marks="two labelled matrix panels",interpretation="categorical",mapping="nominal")]
    write_figure(fid,body,caption,"AI-coded ready communications against non-ready references number653 ordinary versus8 EAL recipients, while ambiguous coding remains visible.","Which communicated decisions account for the recipient reference mismatches?","Exact cell counts, shared within-reference tone and retained ambiguity reveal specific reference/communication routes without dropping unresolved codes.",inputs,qs,encs,quality=True)

    # Actual alternative: 100% decision profiles sacrifice rare-route count lookup.
    proto="12-recipient-decision-profiles";ids.append(proto)
    pbody=r"\begin{axis}[width=126mm,height=78mm,xmin=0,xmax=100,ymin=0.4,ymax=6.6,ytick={1,2,3,4,5,6},yticklabels={Undet. / EAL,Undet. / ordinary,Not ready / EAL,Not ready / ordinary,Ready / EAL,Ready / ordinary},xtick={0,25,50,75,100},xlabel={AI-coded communication within reference row (\%)},legend columns=4,legend style={at={(0.5,1.07)},anchor=south,column sep=3mm}]"+"\n"
    tones={"ready":75,"not_ready":50,"undetermined":25,"ambiguous":5}
    for y,(ref,arm) in enumerate([(r,a) for r in reversed(references) for a in ["eal","ordinary"]],1):
        left=0
        for decision in decisions:
            row=confusion[(confusion.arm==arm)&(confusion.reference==ref)&(confusion.communicated==decision)].iloc[0]
            right=left+100*float(row.fraction_of_reference)
            if right>left:
                pbody+=f"\\path[fill=black!{tones[decision]},draw=black!30,line width=0.4pt] (axis cs:{left:.10g},{y-0.28}) rectangle (axis cs:{right:.10g},{y+0.28});\n"
                if right-left>=12:
                    colour="white" if tones[decision]>=50 else "black"
                    pbody+=f"\\node[text={colour},font=\\fontsize{{9}}{{11}}\\selectfont] at (axis cs:{(left+right)/2:.10g},{y}) {{{int(row['count'])}}};\n"
            left=right
        assert np.isclose(left,100)
    for decision,label in zip(decisions,["Ready","Not ready","Undet.","Ambig."]):
        pbody+=f"\\addlegendimage{{area legend,fill=black!{tones[decision]},draw=black!30,line width=0.4pt}}\\addlegendentry{{{label}}}\n"
    pbody+="\\end{axis}\n"
    pe=[encoding("sharelength",["share"],"length","Each stacked rectangular segment is the conditional communication share within its named reference row; all four segments total 100%.",[0,100],marks="stacked rectangular profile data bars"),encoding("profiletone",["communication"],"tone","Fixed categorical tones identify ready 75%,not_ready 50%,undetermined 25%andambiguous 5%black. Tone identifies category rather than magnitude in this alternative.",decisions,marks="stacked rectangular profile data bars",interpretation="categorical",mapping="nominal"),encoding("profilerows",["reference","arm"],"position","Each row jointly identifies an authored reference and workflow arm; paired rows share the same reference denominator.",["Undet. / EAL","Undet. / ordinary","Not ready / EAL","Not ready / ordinary","Ready / EAL","Ready / ordinary"],marks="stacked rectangular profile data bars in categorical rows",interpretation="categorical",mapping="nominal")]
    write_figure(proto,pbody,"Comparison prototype: conditional communication profiles from the same recipient confusion counts as the selected count matrix. Bars total 100% within each authored reference class and arm. Tones identify communication categories; printed counts are limited to segments at least 12 percentage points wide, while all smaller categories including ambiguities remain in the bars and retained data. AI-code validity remains independently unmeasured.","The profile alternative retains reference-specific communication shares but makes rare routes harder to enumerate.","Do decision-profile bars or a count matrix better preserve exact false-ready and ambiguous routes?","The profiles show conditional composition while the retained matrix makes every rare cell count directly recoverable.",inputs,qs,pe,quality=True)

    # 13. Two arms share fixed denominators; tiny ambiguity ranges remain explicit.
    fid="13-recipient-match-bounds";ids.append(fid)
    order=[("plain",False),("plain",True),("reasoning",False),("reasoning",True)]
    rowlabels=[f"{receiver.capitalize()} / {'tools' if native else 'no tools'}" for receiver,native in order]
    body=r"\begin{axis}[width=136mm,height=76mm,xmin=0,xmax=101,ymin=0.5,ymax=4.5,xtick={0,20,40,60,80,100},ytick={1,2,3,4},yticklabels={"+",".join("{"+x+"}" for x in rowlabels)+r"},xlabel={Recipient reference-match bounds (\%)},title={AI-coded decisions; ambiguity only},title style={at={(0.5,1.19)},anchor=south},legend columns=2,legend style={at={(0.5,1.06)},anchor=south,column sep=4mm}]"+"\n"
    for arm,col,mark,offset,title in [("ordinary",ORANGE,"triangle*",-0.18,"Ordinary"),("eal",BLUE,"square*",0.18,"EAL")]:
        for y,(receiver,native) in enumerate(order,1):
            g=groups[(groups.arm==arm)&(groups.receiver==receiver)&(groups.native_tools.astype(str).str.lower()==str(native).lower())]
            assert len(g)==1;row=g.iloc[0];lower=100*float(row.lower);upper=100*float(row.upper);yy=y+offset
            body+=plot([lower,upper],[yy,yy],f"forget plot,{col},line width=0.8pt,no marks")
            for bound in [lower,upper]:
                body+=plot([bound,bound],[yy-0.045,yy+0.045],f"forget plot,{col},line width=0.6pt,no marks")
            body+=plot([lower],[yy],f"forget plot,only marks,mark={mark},mark size=1.5pt,{col},line width=0.5pt")
            label=f"{lower:.2f}" if np.isclose(lower,upper) else f"{lower:.2f}--{upper:.2f}"
            anchor="east" if arm=="eal" else "west";labelx=lower-1 if arm=="eal" else upper+1
            body+=f"\\node[anchor={anchor},font=\\fontsize{{9}}{{11}}\\selectfont] at (axis cs:{labelx},{yy}) {{{label}\\%}};\n"
        body+=f"\\addlegendimage{{only marks,mark={mark},mark size=1.7pt,{col},line width=0.5pt}}\\addlegendentry{{{title}}}\n"
    body+="\\end{axis}\n"
    caption="Recipient agreement in the original finish coding snapshot with authored reference decisions in four actual recipient-model/native-tool groups, with 480 sessions per arm/group from 48 matched trajectories. A range runs from known matching AI codes divided by 480 to known matches plus all ambiguous codes divided by 480. Single values indicate no ambiguous codes in that arm/group; they do not imply statistical certainty. These are finite-record ambiguity envelopes conditional on all resolved AI codes, not confidence intervals or bounds on assessor error. Both donor model assignments and all six selected cases are pooled within each recipient group; independent human validation and explanation correctness remain unavailable."
    qmatch=coded_quantity("match","Recipient reference-match ambiguity bounds","%","Known matching communicated decisions divided by all 480 recipient sessions, through known matches plus ambiguous decisions divided by 480.","Select dimension=recipient_model_tools; retain fixed per-arm denominator, including every unresolved code; multiply lower/upper proportions by 100.",["groups","coding"],480,"recipient sessions per arm/group","Ten recipients from each of48 matched trajectories in the named actual recipient-model/tool group; donors excluded.")
    qgroup=coded_quantity("group","Actual recipient model/tool group","category","Actual recipient profile and native-tool permission in each of four groups.","Retain actual recipient-model/tool categories, pooling selected cases and donor assignments.",["groups"],480,"recipient sessions per arm/group","All480recipients in each named arm/group.",ambiguity=False)
    qarm=coded_quantity("arm","Workflow arm","category","Ordinary or EAL, with the same recipient-condition denominator.","Retain arm identity; marker shape and direct labels supplement colour.",["groups"],480,"recipient sessions per arm/group","Both arms retain all selected recipient positions.",ambiguity=False)
    inp=[("groups","tables/completion-correctness-groups.csv","Frozen independently verified AI-coded decision agreement and ambiguity counts by recipient condition."),coding_input]
    write_figure(fid,body,caption,"EAL recipient reference-match ambiguity bounds exceed ordinary bounds in all four actual model/tool groups, conditional on the retained AI codes.","Does the AI-coded reference-match contrast persist across recipient model and tool groups?","Both arms retain equal denominators and explicit ambiguity widths; close or degenerate bounds do not imply quantified coder validity or sampling certainty.",inp,[qmatch,qgroup,qarm],[encoding("matchposition",["match"],"position","Horizontal endpoints delimit conditional ambiguity envelopes; markers locate the lower known-match share, not a midpoint estimate.",[0,101],marks="capped horizontal ranges with lower-endpoint square/triangle data marks"),encoding("grouprows",["group"],"position","Four named actual recipient groups; small role offsets distinguish arms within a category.",rowlabels,marks="range data marks in categorical rows",interpretation="categorical",mapping="nominal"),encoding("armmarkers",["arm"],"shape","Orange triangles denote ordinary and blue squares EAL, consistently with explicit arm legend.",["ordinary","eal"],marks="triangle and square lower-endpoint data marks",interpretation="categorical",mapping="nominal")],quality=True)

    # 14. Frozen family intervals and component decision bounds answer different questions.
    fid="14-frozen-endpoint-bounds";ids.append(fid)
    assert len(endpoints)==3 and endpoints.endpoint.nunique()==3
    assert endpoints.one_sided_criterion_met.all()
    endpoint_config=[("quality_difference","Recipient reference-match difference (EAL $-$ ordinary)","Percentage points",(-10,100),[-5,0,20,40,60,80,100]),("eal_correctness","EAL recipient reference-match rate","Percent; restricted 80--100 axis",(80,100),[80,85,90,95,100]),("token_reduction","Donor-inclusive pooled total-token reduction","Percent; restricted 15--40 axis",(15,40),[15,20,25,30,35,40])]
    body=""
    qlist=[];encs=[]
    for panel,(endpoint,title,unit,domain,ticks) in enumerate(endpoint_config):
        row=endpoints[endpoints.endpoint==endpoint].iloc[0]
        lo,hi=domain
        at="" if panel==0 else f"at={{(panel{panel-1}.south west)}},yshift=-16mm,anchor=north west,"
        body+=f"\\begin{{axis}}[name=panel{panel},{at}width=139mm,height=42mm,xmin={lo},xmax={hi},ymin=0.5,ymax=3.65,ytick={{1,2,3}},yticklabels={{IUT 1-sided,Family 2-sided,Observed}},xtick={{{','.join(map(str,ticks))}}},xlabel={{{unit}}},title={{{title}}},title style={{font=\\fontsize{{10}}{{12}}\\selectfont}},axis lines=left]\n"
        threshold=100*float(row.threshold)
        body+=plot([threshold,threshold],[0.5,3.65],"forget plot,ordinaryorange,dashed,line width=0.6pt,no marks")
        for y,lower,upper,col,dash in [(3,100*row.observation_lower,100*row.observation_upper,"black","solid"),(2,100*row.family_interval_lower,100*row.family_interval_upper,GREY,"dashed")]:
            body+=plot([lower,upper],[y,y],f"forget plot,{col},{dash},line width=0.8pt,no marks")
            for value in [lower,upper]:
                body+=plot([value,value],[y-0.07,y+0.07],f"forget plot,{col},line width=0.6pt,no marks")
            if y==3:body+=plot([lower],[y],"forget plot,black,only marks,mark=square*,mark size=1.3pt,line width=0.5pt")
            label=f"{lower:.2f}" if np.isclose(lower,upper) else f"{lower:.2f}--{upper:.2f}"
            body+=f"\\node[font=\\fontsize{{9}}{{11}}\\selectfont,anchor=south] at (axis cs:{(lower+upper)/2},{y+0.08}) {{{label}}};\n"
        lower=100*float(row.one_sided_decision_lower)
        body+=plot([lower,hi-0.025*(hi-lo)],[1,1],f"forget plot,{BLUE},line width=0.8pt,no marks,->")
        body+=plot([lower],[1],f"forget plot,{BLUE},only marks,mark=triangle*,mark size=1.7pt,line width=0.5pt")
        body+=f"\\node[font=\\fontsize{{9}}{{11}}\\selectfont,anchor=south west] at (axis cs:{lower+0.02*(hi-lo)},1.08) {{Lower {lower:.2f}}};\n"
        body+="\\end{axis}\n"
        unit_name="percentage points" if endpoint=="quality_difference" else "%"
        inclusion="All 192 planned paired trajectories across 48 fixed strata, with four reruns per stratum and every ambiguous recipient code retained. Quality averages ten recipients within each trajectory; the token endpoint retains donor plus ten recipients."
        obs=coded_quantity(endpoint+"observed",title+": finite-record range",unit_name,"Frozen lower and upper endpoints of this pilot's conditional coding envelope; the observed token reduction is a single recorded ratio.","Read observation_lower and observation_upper; multiply proportions by 100 without changing their denominators.",["endpoints","coding"],192,"paired trajectories",inclusion,ambiguity=endpoint!="token_reduction")
        if endpoint=="token_reduction":
            obs["uncertainty"]={"kind":"unquantified","definition":"The recorded pooled token ratio has no communication-code ambiguity; provider accounting limitations are separate from its sampling interval."}
        family=coded_quantity(endpoint+"family",title+": family component interval",unit_name,"Two-sided nominal 98.333% component interval contributing to the three-endpoint nominal 95% simultaneous family.","Read family_interval_lower and family_interval_upper from the frozen independently reconstructed report; scale by 100.",["endpoints","inference"],192,"paired trajectories",inclusion,ambiguity=endpoint!="token_reduction")
        family["statistical_role"]="estimate"
        family["uncertainty"]={"kind":"interval","coverage":0.9833333333333333,"definition":"Nominal marginal component coverage within a three-endpoint 95% family. The token component is an approximation. These intervals concern expected independent reruns of the fixed configuration mixture; resolved AI communication codes are held fixed, and their error is not bounded.","method":"Frozen empirical-Bernstein quality envelopes for independent, potentially non-identical trajectory means; stratified delta/Welch approximation for the resource ratio. Independently audited, not re-estimated by the figure script."}
        decision=coded_quantity(endpoint+"decision",title+": one-sided decision lower bound",unit_name,"Frozen component-alpha=0.05 one-sided lower bound used in the intersection-union conjunction, not a simultaneous family bound.","Read one_sided_decision_lower; scale by 100. A ray points towards greater admissible values within the endpoint support.",["endpoints","inference"],192,"paired trajectories",inclusion,ambiguity=endpoint!="token_reduction")
        decision["statistical_role"]="estimate"
        decision["uncertainty"]={"kind":"interval","coverage":0.95,"definition":"One-sided component coverage conditional on valid trajectory-independence and frozen-coding assumptions, with an approximate token test. Conjoining three valid component tests controls the intersection-union false-support event; the three bounds do not have simultaneous 95% coverage.","method":"Frozen one-sided empirical-Bernstein quality bound or approximate resource delta/Welch bound at component alpha=0.05."}
        criterion=quantity(endpoint+"criterion",title+": engineering criterion",unit_name,"The declared frozen engineering threshold for this endpoint, with no validated developer-utility mapping.","Read threshold from the frozen report and scale by 100.",["endpoints"])
        criterion["statistical_role"]="parameter"
        criterion["missingness"]={"state":"not_applicable","treatment":"A declared criterion, rather than a measured outcome."}
        criterion["uncertainty"]={"kind":"not_applicable","definition":"Fixed report threshold, not a confidence bound."}
        qlist.extend([obs,family,decision,criterion])
        encs.append(encoding(endpoint+"position",[obs["id"],family["id"],decision["id"]],"position","Each separately labelled panel has its declared units/domain. Observed black capped ranges, grey dashed family ranges and blue triangular one-sided lower bounds/rays answer distinct questions.",[lo,hi],marks="capped ranges and lower-bound triangle/ray data marks"))
        boundary=encoding(endpoint+"threshold",[criterion["id"]],"position","The orange dashed vertical boundary is the fixed endpoint criterion; comparing the blue lower bound to it applies the declared one-sided test.",[lo,hi],marks="vertical criterion reference boundary")
        boundary["mark_role"]="boundary"
        encs.append(boundary)
    kind=quantity("boundkind","Inferential question","category","Finite-record observed range, two-sided family component interval, or one-sided component decision lower bound.","Retain the frozen report's three distinct inferential roles in each separately scaled panel.",["endpoints"])
    kind["missingness"]={"state":"not_applicable","treatment":"These are explicit method labels, not missing outcomes."}
    kind["uncertainty"]={"kind":"not_applicable","definition":"A method/category label does not itself encode a confidence level."}
    qlist.append(kind)
    encs.append(encoding("boundrows",["boundkind"],"position","Rows identify distinct inferential questions; observed is top, family middle, and one-sided intersection-union component lower bound bottom.",["Observed","Family 2-sided","IUT 1-sided"],marks="capped ranges and triangular lower-bound rays in named method rows",interpretation="categorical",mapping="nominal"))
    caption="Frozen pilot endpoints retain the original finish coding snapshot and distinguish three questions. Inference uses 192 matched whole trajectories in 48 fixed strata, with four reruns per stratum; quality averages ten recipients, while tokens include the donor and ten recipients. Observed black quality ranges enclose unresolved AI communication codes in this finite record; the black token point is the exact recorded reduction. Grey two-sided intervals concern expected independent reruns of the fixed task/model/tool mixture: a nominal 95% three-endpoint family with 98.333% marginal components and an approximate token component. Blue triangles/rays show lower bounds for separate one-sided component tests at alpha=0.05; their conjunction is an intersection-union decision, not simultaneous 95% coverage of the three bounds. Orange reference lines mark the frozen thresholds: minus 5 percentage points for the EAL-minus-ordinary recipient match difference, 90% for EAL match, and 20% token reduction. All one-sided criteria pass under those assumptions. The EAL family interval extends below 90%, illustrating the different inferential targets. Inference does not bound errors in resolved AI codes and trajectory independence is unverified. The original finish allocation report remains blocked by unresolved labels and a minimum of two fully scored paired reruns per cell against a requirement of four; these criteria do not establish practical adoption. Panels use explicitly different positional scales."
    inp=[("endpoints","tables/completion-endpoints.csv","Frozen independently reproduced report endpoints, preserving descriptive/family/one-sided distinctions."),coding_input,("inference","analysis/completion-inference-audit.json","Independent audit of fixed-mixture inference, empirical-Bernstein theorem applicability and approximate resource component.")]
    write_figure(fid,body,caption,"All three one-sided frozen endpoint criteria pass conditionally, while family intervals answer a different question and the original finish allocation report remains blocked.","How do finite-record ambiguity, simultaneous family inference and one-sided engineering criteria differ?","Three separately scaled panels retain distinct glyphs and thresholds; conditional support for the one-sided conjunction does not establish independently validated quality or planning eligibility.",inp,qlist,encs,quality=True)
    return ids


if __name__ == "__main__":
    main()
