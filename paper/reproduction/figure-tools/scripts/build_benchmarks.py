#!/usr/bin/env python3
"""Build six reproducible toy figure cases; never treat toy values as evidence."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL_NAMES = ("build_benchmarks.py", "render_tikz.py", "render_context.py",
              "figure_spec.py", "figure_audit.py", "build_profile.py")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def copy_file(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)


def region_status(x, y, upper=1):
    if x < -1e-10 or y < -1e-10 or x + y > upper + 1e-10:
        return "outside"
    if abs(x) <= 1e-10 or abs(y) <= 1e-10 or abs(x + y - upper) <= 1e-10:
        return "boundary"
    return "inside"


def paired_summary(rows, coverage=0.95):
    from scipy.stats import t
    differences = [float(row["after"]) - float(row["before"]) for row in rows]
    n = len(differences)
    if n < 2:
        raise ValueError("Student t interval requires at least two paired differences")
    mean = statistics.mean(differences)
    sd = statistics.stdev(differences)
    critical = float(t.ppf((1 + coverage) / 2, n - 1))
    margin = critical * sd / math.sqrt(n)
    return {"n": n, "difference_definition": "after - before", "differences": differences,
            "mean_difference": mean, "sample_sd": sd, "coverage": coverage,
            "degrees_of_freedom": n - 1, "t_critical": critical,
            "lower": mean - margin, "upper": mean + margin,
            "assumptions": "Independent, normally distributed paired differences; numerical illustration only",
            "evidential_status": "Illustrative constructed data; no empirical experiment"}


def source(name, body, *, x="1cm", y="1cm"):
    return ("% Required packages: tikz\n% Required TikZ libraries: none\n"
            "% Target width: 120 mm\n% Minimum text size: 8 pt\n"
            "% Colour/greyscale intent: greyscale\n"
            "\\begingroup\n" + rf"\begin{{tikzpicture}}[x={x},y={y},line width=0.4pt," +
            "every node/.style={font=\\fontsize{8pt}{9.6pt}\\selectfont,inner sep=1pt}]\n" +
            f"% Benchmark: {name}; values are derived, simulated or illustrative as declared.\n" +
            body + "\n\\end{tikzpicture}\n\\endgroup\n")


def cross(x, y, dx=0.018, dy=0.018):
    return (rf"\draw[line width=0.55pt] ({x-dx:.6f},{y-dy:.6f}) -- ({x+dx:.6f},{y+dy:.6f});" + "\n" +
            rf"\draw[line width=0.55pt] ({x-dx:.6f},{y+dy:.6f}) -- ({x+dx:.6f},{y-dy:.6f});")


def coordinates(points):
    return " -- ".join(f"({float(x):.8f},{float(y):.8f})" for x, y in points)


def xy_axes():
    return r"""\draw (0,0) -- (1.15,0);
\draw (0,0) -- (0,1.15);
\node[below] at (1.15,0) {$x$};
\node[left] at (0,1.15) {$y$};
\node[below left] at (0,0) {0};
\draw (1,-0.015) -- (1,0.015); \node[below] at (1,-0.015) {1};
\draw (-0.015,1) -- (0.015,1); \node[left] at (-0.015,1) {1};"""


def input_record(output, identifier, path, status, reference):
    return {"id": identifier, "path": path, "status": status, "source_reference": reference,
            "sha256": hashlib.sha256((output / path).read_bytes()).hexdigest()}


def quantity(identifier, label, inputs, transformation, *, unit="dimensionless", uncertainty=None, sample=None):
    result = {"id": identifier, "label": label, "unit": unit, "definition": label,
              "input_ids": inputs, "transformation": transformation,
              "missingness": {"state": "complete", "treatment": "All declared toy values retained"},
              "uncertainty": uncertainty or {"kind": "not_applicable", "definition": "Deterministic toy construction"}}
    if sample:
        result["sample"] = sample
        result["statistical_role"] = "estimate"
    return result


def encoding(identifier, marks, represents, *, quantity_ids=None, construction_ids=None,
             domain=None, channel="position", definition="Direct Cartesian coordinates",
             mark_role="data_mark", interpretation=None, mapping_type=None):
    result = {"id": identifier, "marks": marks, "mark_role": mark_role, "channel": channel,
              "represents": represents, "interpretation": interpretation or ("quantitative" if domain else "relational"),
              "scale_or_mapping": {"type": mapping_type or ("linear" if domain else "explicit"), "definition": definition}}
    if domain:
        result["scale_or_mapping"]["domain"] = domain
    result["quantity_ids" if quantity_ids else "construction_ids"] = quantity_ids or construction_ids
    return result


def emit(output, identifier, tikz, inputs, quantities, encodings, question, claim, labels,
         *, constructions=None, profile=False):
    (output / f"{identifier}.tikz.tex").write_text(tikz, encoding="utf-8")
    dependencies = ([f"tools/{name}" for name in TOOL_NAMES] + ["assets/figure-spec.schema.json", f"{identifier}.caption.txt"] +
                    [f"assets/benchmarks/{name}" for name in
                     ("region.json", "intervention.json", "mixed.json", "paired.csv", "missing.csv")])
    target = {"width_mm": 120, "width_mode": "maximum", "min_text_pt": 8,
              "min_stroke_pt": 0.4, "colour_intent": "greyscale", "expected_labels": labels,
              "prohibit_block_circle_diagrams": True}
    build = {"renderer": "tikz", "source": f"{identifier}.tikz.tex",
             "recipe": [["python3", "tools/build_benchmarks.py", "--output", "."],
                        ["python3", "tools/render_tikz.py", f"{identifier}.tikz.tex",
                         "--spec", f"{identifier}.spec.json", "--qa-dir", f"qa/{identifier}"]],
             "outputs": {"pdf": f"{identifier}.pdf", "preview": f"{identifier}.png",
                         "audit": f"{identifier}.audit.json"}, "dependencies": dependencies}
    if profile:
        target["manuscript_profile"] = "profiles/book.json"
        build["profile"] = "profiles/book.json"
        dependencies += ["profiles/book-preamble.tex"]
    spec = {"schema_version": "1.0", "figure_id": identifier,
            "purpose": {"reader_question": question, "expected_reading": claim, "claim": claim,
                        "scope": "Bounded toy benchmark; no empirical or agency assessment",
                        "permitted_inferences": [claim],
                        "prohibited_inferences": ["Toy values establish empirical population effects",
                                                  "Displayed dynamics establish agency"]},
            "inputs": inputs, "quantities": quantities, "encodings": encodings,
            "target": target, "build": build}
    if constructions:
        spec["constructions"] = constructions
    destination = output / f"{identifier}.spec.json"
    write_json(destination, spec)
    return destination


def build_cases(output_dir: str | Path) -> list[Path]:
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    for name in TOOL_NAMES:
        tool = ROOT / "scripts" / name
        if not tool.is_file():
            tool = ROOT / "tools" / name
        copy_file(tool, output / "tools" / name)
    copy_file(ROOT / "assets/figure-spec.schema.json", output / "assets/figure-spec.schema.json")
    for name in ("book.json", "book-preamble.tex"):
        profile = ROOT / "assets/profiles" / name
        if not profile.is_file():
            profile = ROOT / "profiles" / name
        copy_file(profile, output / "profiles" / name)
    for fixture in sorted((ROOT / "assets/benchmarks").iterdir()):
        if fixture.is_file():
            copy_file(fixture, output / "assets/benchmarks" / fixture.name)
    models = {name: json.loads((output / f"assets/benchmarks/{name}.json").read_text())
              for name in ("region", "intervention", "mixed")}
    for name, model in models.items():
        write_json(output / f"data/{name}.json", model)
    for name in ("paired", "missing"):
        copy_file(output / f"assets/benchmarks/{name}.csv", output / f"data/{name}.csv")
    specs, captions = [], {}
    region = models["region"]
    points = [{**point, "computed_status": region_status(point["x"], point["y"], region["upper_sum"])}
              for point in region["points"]]
    if any(point["computed_status"] != point["expected"] for point in points):
        raise ValueError("Region fixture point classifications do not match computed inequalities")
    write_csv(output / "data/region-points.csv", points)
    vertices = [(0, 0), (region["upper_sum"], 0), (0, region["upper_sum"])]
    write_json(output / "data/region-vertices.json", vertices)
    region_construction = {"id": "feasible_region", "kind": "constraint_region",
                           "definition": region["definition"],
                           "method": "Intersect three declared half-planes; vertices (0,0),(1,0),(0,1)",
                           "input_ids": ["region_model"]}
    region_input = input_record(output, "region_model", "data/region.json", "derived", "Declared toy inequalities")
    body = "\\fill[black!8] " + coordinates(vertices) + " -- cycle;\n" + xy_axes()
    body += "\n" + r"\draw[line width=0.55pt] (0,1) -- (1,0);" + "\n"
    for point in points:
        body += cross(point["x"], point["y"]) + "\n"
    body += r"""\node[below] at (0.25,0.21) {inside};
\node[above right] at (0.53,0.52) {boundary};
\node[right] at (0.83,0.8) {outside};
\node at (0.2,0.68) {feasible};"""
    claim = "The computed triangle admits the inside and boundary points and excludes the outside point."
    specs.append(emit(output, "feasible-region", source("feasible-region", body, x="5cm", y="5cm"),
                      [region_input, input_record(output, "points", "data/region-points.csv", "derived", "Computed membership table")],
                      [quantity("point_coordinates", "Declared test point x and y coordinates", ["points"], "Identity coordinates; classify by declared inequalities")],
                      [encoding("region", "Shaded triangular region and linear boundary", "Membership in the declared inequalities",
                                construction_ids=["feasible_region"]),
                       encoding("test_points", "Crosses with direct membership labels", "Test point coordinates and classifications",
                                quantity_ids=["point_coordinates"], domain=[0, 1.15])], "Which points satisfy the declared constraints?", claim,
                      ["inside", "boundary", "outside", "feasible"], constructions=[region_construction], profile=True))
    captions["feasible-region"] = claim + " Shading represents x ≥ 0, y ≥ 0 and x + y ≤ 1 in dimensionless coordinates. The sloping boundary follows x + y = 1."

    model = models["intervention"]
    baseline = intervention = model["initial_state"]
    trajectories = [{"time": 0, "baseline": baseline, "intervention": intervention, "input": model["baseline_input"]}]
    for time in range(1, model["last_time"] + 1):
        control = model["baseline_input"] if time < model["intervention_time"] else model["intervention_input"]
        baseline = model["state_retention"] * baseline + model["baseline_input"]
        intervention = model["state_retention"] * intervention + control
        trajectories.append({"time": time, "baseline": baseline, "intervention": intervention, "input": control})
    write_csv(output / "data/trajectories.csv", trajectories)
    body = r"\draw (0,0) -- (10.3,0); \draw (0,0) -- (0,1.25);" + "\n"
    for time in (0, 2, 4, 6, 8, 10):
        body += rf"\draw ({time},-0.02) -- ({time},0.02); \node[below] at ({time},-0.02) {{{time}}};" + "\n"
    for value in (0.4, 0.8, 1.2):
        body += rf"\draw (-0.1,{value}) -- (0.1,{value}); \node[left] at (-0.1,{value}) {{{value}}};" + "\n"
    body += r"\node[below] at (5,-0.2) {Time step}; \node[rotate=90] at (-1.1,0.65) {State value};" + "\n"
    body += "\\draw[dashed,line width=0.55pt] " + coordinates((row["time"], row["baseline"]) for row in trajectories) + ";\n"
    body += "\\draw[line width=0.65pt] " + coordinates((row["time"], row["intervention"]) for row in trajectories) + ";\n"
    for row in trajectories:
        for series in ("baseline", "intervention"):
            body += cross(row["time"], row[series], .09, .015) + "\n"
    body += rf"\draw[densely dotted] ({model['intervention_time']},0.05) -- ({model['intervention_time']},1.2);" + "\n"
    body += r"""\node[above left] at (5,1.2) {Input changes};
\node[right] at (10.2,0.41) {Baseline};
\node[right] at (10.2,1.08) {Changed input};"""
    claim = "Changing the declared input at step 5 changes this deterministic simulated trajectory."
    specs.append(emit(output, "intervention-trajectories", source("intervention-trajectories", body, x="0.6cm", y="3.5cm"),
                      [input_record(output, "model", "data/intervention.json", "simulated", "Declared recurrence parameters"),
                       input_record(output, "values", "data/trajectories.csv", "simulated", "Deterministic recurrence output")],
                      [quantity("state", "Simulated state value", ["model", "values"],
                                "y(t)=0.75 y(t-1)+u(t), y(0)=0.5; changed input u(t)=0.3 from update t=5, baseline u(t)=0.1")],
                      [encoding("state_paths", "Solid and dashed guide polylines with diagonal crosses at each integer update", "Discrete states under changed and baseline input",
                                quantity_ids=["state"], domain=[0, 1.25],
                                definition="Discrete integer-step coordinates; joining segments guide comparison between sampled states and specify no intervening continuous dynamics")],
                      "How does the declared input change affect the simulated state?", claim,
                      ["Baseline", "Changed input", "Input changes", "Time step"]))
    captions["intervention-trajectories"] = (claim +
        " The recurrence is y(t)=0.75 y(t−1)+u(t), with y(0)=0.5. The solid path changes input from 0.1 to 0.3 for the first time in update t=5; the dashed baseline retains input 0.1. Crosses identify states at integer updates and the dotted guide locates that first changed update. Joining segments guide comparisons between discrete states; scope is the specified recurrence.")

    with (output / "data/paired.csv").open() as stream:
        pairs = list(csv.DictReader(stream))
    summary = paired_summary(pairs)
    write_json(output / "data/paired-summary.json", summary)
    inputs = [input_record(output, "pairs", "data/paired.csv", "illustrative", "Constructed pairs, not experimental measurements"),
              input_record(output, "summary", "data/paired-summary.json", "derived", "Student t calculation on constructed pairs")]
    interval = {"kind": "interval", "coverage": .95, "method": "Student t mean interval, df=4",
                "definition": summary["assumptions"]}
    quantities = [quantity("pair_values", "Constructed before and after values", ["pairs"], "Identity values from constructed pairs", unit="toy units"),
                  quantity("difference", "Mean paired difference after minus before", ["pairs", "summary"],
                           "Subtract within each pair; arithmetic mean and sample standard deviation", unit="toy units",
                           uncertainty=interval, sample={"denominator": 5, "unit": "constructed pair", "inclusion": "All five pairs"})]
    claim = "Constructed pairs have zero mean difference and a 95% Student t confidence interval for the mean paired difference containing zero and mean differences of either sign."
    body = r"\draw (0,1.8) -- (0,10.5);" + "\n"
    for value in (2, 4, 6, 8, 10):
        body += rf"\draw (-0.03,{value}) -- (0.03,{value}); \node[left] at (-0.03,{value}) {{{value}}};" + "\n"
    for row in pairs:
        before, after = float(row["before"]), float(row["after"])
        body += rf"\draw[black!60,line width=0.5pt] (0.8,{before}) -- (3.5,{after});" + "\n"
        body += cross(.8, before, .04, .08) + "\n" + cross(3.5, after, .04, .08) + "\n"
        body += rf"\node[right] at (3.6,{after}) {{{row['pair']}}};" + "\n"
    body += r"""\node[below] at (0.8,1.5) {Before}; \node[below] at (3.5,1.5) {After};
\node[rotate=90] at (-0.65,6) {Toy units};
\node[above] at (2,11) {Illustrative pairs; n = 5};
\node[below] at (2,0.4) {Mean paired difference = 0};"""
    specs.append(emit(output, "paired-raw", source("paired-raw", body, x="1.5cm", y="0.45cm"), inputs, quantities,
                      [encoding("pairs", "Paired diagonal endpoint crosses joined by segments", "Within-pair values before and after",
                                quantity_ids=["pair_values"], domain=[2, 10])], "How do the constructed within-pair changes differ?",
                      "Constructed paired changes have differing signs and a zero arithmetic mean.",
                      ["Before", "After", "Mean paired difference = 0", "P1", "P5"]))
    captions["paired-raw"] = "Five constructed pairs produce changes -2, -1, 0, 1 and 2 toy units and a zero mean paired difference. Crosses encode values; segments retain pair identity."
    body = r"\draw (-3,0) -- (3,0); \draw[dashed] (0,0.15) -- (0,0.82);" + "\n"
    for value in range(-3, 4):
        body += rf"\draw ({value},-0.04) -- ({value},0.04); \node[below] at ({value},-0.04) {{{value}}};" + "\n"
    body += rf"\draw[line width=0.7pt] ({summary['lower']:.8f},1) -- ({summary['upper']:.8f},1);" + "\n"
    for value in (summary["lower"], summary["upper"]):
        body += rf"\draw[line width=0.6pt] ({value:.8f},0.9) -- ({value:.8f},1.1);" + "\n"
    body += cross(0, 1, .06, .1) + "\n"
    body += r"""\node[above] at (0,1.6) {Mean paired difference = 0};
\node[above] at (0,1.18) {95\% Student t interval};
\node[below] at (0,-0.5) {After minus before (toy units)};
\node[below] at (0,-1) {Illustrative data; n = 5};"""
    specs.append(emit(output, "paired-interval", source("paired-interval", body, x="1.15cm", y="1.6cm"), inputs, quantities,
                      [encoding("mean_interval", "Diagonal mean cross and capped interval segment with shortened zero reference below the interval", "Toy mean and confidence interval for the mean paired difference",
                                quantity_ids=["difference"], domain=[-3, 3])], "Which mean paired differences are compatible with the illustrative confidence interval?", claim,
                      ["Mean paired difference = 0", "95% Student t interval", "Illustrative data; n = 5"]))
    captions["paired-interval"] = (f"The five constructed paired differences have mean zero and a 95% Student t confidence interval for the mean paired difference [{summary['lower']:.3f}, {summary['upper']:.3f}] toy units under independent normal-difference assumptions. The diagonal cross marks the estimated mean; the interval represents uncertainty about the mean paired difference. Compatibility with zero leaves mean differences of either sign within the interval.")

    with (output / "data/missing.csv").open() as stream:
        observations = list(csv.DictReader(stream))
    body = r"\draw (0,0) -- (4.3,0); \draw (0,0) -- (0,1.1);" + "\n"
    for time in range(5):
        body += rf"\draw ({time},-0.02) -- ({time},0.02); \node[below] at ({time},-0.02) {{{time}}};" + "\n"
    for value in (0.5, 1):
        body += rf"\draw (-0.05,{value}) -- (0.05,{value}); \node[left] at (-0.05,{value}) {{{value}}};" + "\n"
    segments, segment = [], []
    for row in observations:
        if row["value"] == "NA":
            if segment:
                segments.append(segment)
            segment = []
        else:
            segment.append((float(row["time"]), float(row["value"])))
    if segment:
        segments.append(segment)
    for segment in segments:
        body += "\\draw[line width=0.6pt] " + coordinates(segment) + ";\n"
        for x, y in segment:
            body += cross(x, y, .035, .025) + "\n"
    body += r"""\node at (2,-0.25) {NA};
\node at (1,-0.25) {Measured zero};
\node[left] at (-0.1,-0.25) {Status};
\node[below] at (2,-0.65) {Observation time};
\node[rotate=90] at (-0.55,0.6) {Toy value};"""
    missing_quantity = quantity("values", "Illustrative observations with explicit missingness", ["observations"],
                                "Retain numeric zero; retain NA and break the path at missing rows", unit="toy units")
    missing_quantity["missingness"] = {"state": "partial", "treatment": "Retain NA; no substitution or interpolation across missing observation"}
    claim = "A measured zero remains numeric while the missing observation is labelled NA and breaks the path."
    specs.append(emit(output, "missing-versus-zero", source("missing-versus-zero", body, x="1.4cm", y="3.5cm"),
                      [input_record(output, "observations", "data/missing.csv", "illustrative", "Constructed missingness fixture")],
                      [missing_quantity], [encoding("observations", "Diagonal crosses and separate observed path segments",
                                                   "Numeric observations", quantity_ids=["values"], domain=[0, 1]),
                                           encoding("missing_status", "NA and measured-zero text in a status row below the axes",
                                                    "Observation status aligned with time; status-row height carries no numeric value",
                                                    quantity_ids=["values"], channel="text",
                                                    domain=["measured zero", "missing"], mark_role="annotation",
                                                    interpretation="categorical", mapping_type="nominal",
                                                    definition="Measured zero labels a retained numeric zero; NA labels a missing value. The non-quantitative status row is aligned horizontally with observation time; vertical placement encodes no number")],
                      "How does the figure distinguish zero from a missing observation?", claim, ["NA", "Measured zero", "Observation time"]))
    captions["missing-versus-zero"] = claim + " Diagonal crosses distinguish numeric observations from axis ticks. The separate status row aligns NA with time 2 and measured zero with time 1; its height carries no numeric value. Values are constructed. Segments join only adjacent available observations."

    model = models["mixed"]
    mixed = [{"time": time, "x": model["initial_x"] + model["x_increment"] * time,
              "y": model["initial_y"] + model["y_increment"] * time}
             for time in range(model["last_time"] + 1)]
    for row in mixed:
        row["status"] = region_status(row["x"], row["y"], region["upper_sum"])
    write_csv(output / "data/mixed-trajectory.csv", mixed)
    body = r"\fill[black!8] (0,0) -- (1,0) -- (0,1) -- cycle;" + "\n" + xy_axes() + "\n"
    body += r"\draw[line width=0.55pt] (0,1) -- (1,0);" + "\n"
    body += "\\draw[line width=0.65pt] " + coordinates((row["x"], row["y"]) for row in mixed) + ";\n"
    for time in (0, 6, 7, 10):
        body += cross(mixed[time]["x"], mixed[time]["y"]) + "\n"
    body += r"""\node[below right] at (0.1,0.12) {t = 0};
\node[anchor=east] at (0.32,0.48) {t = 6};
\draw[black!60,line width=0.4pt] (0.35,0.48) -- (0.50,0.48);
\node[right] at (0.64,0.535) {t = 7 (first outside)};
\node[above right] at (0.83,0.75) {t = 10};
\node at (0.16,0.68) {admissible};"""
    claim = "Among displayed simulated states t=0 through t=10, state 6 lies on the declared constraint boundary and state 7 is the first outside state."
    specs.append(emit(output, "mixed-constraints-trajectory", source("mixed-constraints-trajectory", body, x="5cm", y="5cm"),
                      [region_input, input_record(output, "simulation_model", "data/mixed.json", "simulated", "Declared increment model"),
                       input_record(output, "trajectory", "data/mixed-trajectory.csv", "simulated", "Computed deterministic trajectory")],
                      [quantity("trajectory_values", "Simulated x and y", ["simulation_model", "trajectory"], model["definition"])],
                      [encoding("region", "Shaded triangle and linear boundary", "Declared admissible set", construction_ids=["feasible_region"]),
                       encoding("trajectory", "Simulated guide polyline with diagonal crosses at steps 0, 6, 7 and 10", "Modelled discrete state coordinates",
                                quantity_ids=["trajectory_values"], domain=[0, 1.15],
                                definition="Cartesian positions for displayed integer states 0 through 10; joining segments guide comparison")],
                      "When does this specified simulated trajectory leave the declared admissible set?", claim,
                      ["t = 0", "t = 6", "t = 7 (first outside)", "t = 10", "admissible"], constructions=[region_construction]))
    captions["mixed-constraints-trajectory"] = claim + " Displayed states 7 through 10 lie outside. Shading represents the mathematically derived set x ≥ 0, y ≥ 0 and x + y ≤ 1 in dimensionless coordinates. The states are deterministic simulation; joining segments guide comparisons between discrete states. The admissibility comparison establishes membership relative to these chosen inequalities over the displayed t=0 through t=10 range."
    for identifier, caption in captions.items():
        (output / f"{identifier}.caption.txt").write_text(caption + "\n", encoding="utf-8")
    write_json(output / "captions.json", captions)
    (output / "requirements.txt").write_text("PyMuPDF\nPillow\nNumPy\nSciPy\njsonschema\n", encoding="utf-8")
    (output / "README.md").write_text(
        "# Toy figure benchmarks\n\nAll values are derived, simulated or illustrative.\n\n"
        "Run `python3 tools/build_benchmarks.py --output .` from this directory to regenerate sources and tables. "
        "Each `.spec.json` records the rendering command and required inputs. Each `<id>.caption.txt` is its figure's declared caption dependency; `captions.json` is a convenience aggregate. "
        "Install `requirements.txt` plus a TeX installation with latexmk and Poppler before rendering. "
        "Mechanical checks and independent semantic/visual review remain separate.\n", encoding="utf-8")
    return specs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        for path in build_cases(args.output):
            print(path)
        return 0
    except (OSError, ValueError, ImportError) as exc:
        print(f"benchmark construction failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
