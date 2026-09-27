"""Regenerate the five vector evidence figures from a retained Actions ZIP.

Usage: python3 analysis/make_figures.py --zip /path/to/api-experiment-36275725154-1.zip
The sources contain direct TikZ primitives and text; the render step is separate.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile


BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "figures"
MODELS = (
    ("gpt-4.1-2025-04-14", "4.1"),
    ("gpt-4.1-mini-2025-04-14", "4.1 mini"),
    ("gpt-4.1-nano-2025-04-14", "4.1 nano"),
    ("gpt-5.4-2026-03-05", "5.4"),
    ("gpt-5.4-mini-2026-03-17", "5.4 mini"),
    ("gpt-5.4-nano-2026-03-17", "5.4 nano"),
)
ARMS = (
    ("eal_mcp", "EAL"),
    ("json_prompt", "JSON"),
    ("plain_brief", "brief"),
    ("plain_explicit", "explicit"),
    ("plain_review", "review"),
    ("plain_validator", "validator"),
)


def document(height: int, body: list[str]) -> str:
    head = [
        "% Required packages: tikz, xcolor, amsmath",
        "% Required TikZ libraries: none",
        "% Target width: 161 mm",
        "% Minimum text size: 7 pt at final reproduction",
        "% Colour/greyscale intent: dark ink and one restrained accent; orientations and direct labels are redundant.",
        r"\begingroup",
        r"\definecolor{runInk}{RGB}{38,44,51}%",
        r"\definecolor{runQuiet}{RGB}{95,104,109}%",
        r"\definecolor{runAccent}{RGB}{146,65,36}%",
        r"\begin{tikzpicture}[x=1mm,y=1mm,inner sep=0pt,outer sep=0pt]",
        rf"\useasboundingbox (0,0) rectangle (160,{height});",
    ]
    tail = [r"\end{tikzpicture}", r"\endgroup\ignorespaces"]
    return "\n".join(head + body + tail) + "\n"


def txt(x: float, y: float, s: str, *, anchor: str = "west", font: str = "8", colour: str = "runInk") -> str:
    return (rf"\node[anchor={anchor},text={colour},font=\fontsize{{{font}}}{{9}}\selectfont] "
            rf"at ({x:.3f},{y:.3f}) {{{s}}};")


def line(x1: float, y1: float, x2: float, y2: float, *, colour: str = "runQuiet", width: str = "0.45pt") -> str:
    return rf"\draw[{colour},line width={width}] ({x1:.3f},{y1:.3f}) -- ({x2:.3f},{y2:.3f});"


def fig1(cells: dict[tuple[str, str], dict], summary: dict) -> str:
    b = [txt(0, 54, "Model snapshot"), txt(104, 54, "Completed / assigned", anchor="center", font="8")]
    xs = (52, 72, 91, 110, 129, 149)
    for x, (_, label) in zip(xs, ARMS):
        b.append(txt(x, 46, label, anchor="center", font="7.2"))
    for i, (model, label) in enumerate(MODELS):
        y = 40 - i * 5.8
        b.append(txt(1, y, label))
        for x, (arm, _) in zip(xs, ARMS):
            c = cells[model, arm]
            assert c["assigned"] == c["completed"] == 40
            b.append(txt(x, y, "40/40", anchor="center", font="7.5"))
    b.append(line(1, 6.2, 159, 6.2))
    b.append(txt(1, 2.3, rf"$40\,\times\,6\,\times\,6={summary['assigned']}$ assigned", font="7.5"))
    b.append(txt(86, 2.3, rf"{summary['completed']} complete; {summary['failed']} failed; {summary['not_attempted']} not attempted", font="7.5"))
    return document(58, b)


def fig2(rows: dict[tuple[str, str], dict[str, dict]]) -> str:
    b = [txt(0, 158, "Same 40 cases in each row; case IDs in lexical order", font="7.5"),
         txt(151, 158, "Correct", anchor="east", font="7.5")]
    for i, (model, mlab) in enumerate(MODELS):
        top = 151 - 24.0 * i
        b.append(txt(1, top, mlab, font="8"))
        for j, (arm, alab) in enumerate(ARMS):
            y = top - 3.4 - 3.10 * j
            b.append(txt(1, y, alab, font="7.1"))
            cases = sorted(rows[model, arm])
            assert len(cases) == 40
            for k, case_id in enumerate(cases):
                r = rows[model, arm][case_id]
                x = 37 + k * 2.40
                if r["state"] == "complete" and r["outcome"]["correct"]:
                    b.append(line(x, y - .72, x, y + .72, colour="runInk", width="0.65pt"))
                else:
                    b.append(line(x - .60, y - .65, x + .60, y + .65,
                                  colour="runAccent", width="0.8pt"))
            n = sum(r["state"] == "complete" and r["outcome"]["correct"]
                    for r in rows[model, arm].values())
            b.append(txt(139.2, y, f"{n}/40", font="7.4"))
    b.extend([line(7, 4.8, 7, 6.2, colour="runInk", width="0.65pt"),
              txt(15, 5.5, "upright tick: correct", font="7"),
              line(90, 4.8, 91.2, 6.2, colour="runAccent", width="0.8pt"),
              txt(94, 5.5, "slanted tick: incorrect answer", font="7")])
    return document(161, b)


def fig3(contrasts: dict[str, dict]) -> str:
    b = [txt(0, 77, "Rows: EAL correct / incorrect; columns: validator correct / incorrect", font="7.8")]
    for i, (model, label) in enumerate(MODELS):
        col, row = i % 3, i // 3
        x, y = col * 54, 54 - row * 35
        c = contrasts[model]
        assert sum(c[k] for k in ("both_correct", "reference_only_correct",
                                   "comparator_only_correct", "both_incorrect")) == 40
        b.append(txt(x + 1, y + 13, label, font="8"))
        matrix = (rf"$\left(\begin{{array}}{{rr}}"
                  rf"{c['both_correct']}&{c['reference_only_correct']}\\"
                  rf"{c['comparator_only_correct']}&{c['both_incorrect']}"
                  rf"\end{{array}}\right)$")
        b.append(txt(x + 2.5, y + 2, matrix, font="10"))
        if c["reference_only_correct"] or c["comparator_only_correct"]:
            b.append(txt(x + 29, y + 1, rf"discordant: {c['reference_only_correct']} : {c['comparator_only_correct']}",
                         font="7", colour="runAccent"))
        else:
            b.append(txt(x + 29, y + 1, "no discordance", font="7", colour="runQuiet"))
    b.append(txt(0, 2, "Each matrix contains 40 paired case outcomes; row and column totals are arm accuracies.", font="7.2"))
    return document(81, b)


def fig4(rows: dict[tuple[str, str], dict[str, dict]]) -> str:
    b = [txt(1, 61, "Among the 19 reference-unavailable cases per model", font="8"),
         txt(57, 53, "reported unavailable", anchor="center", font="7.1"),
         txt(102, 53, "reported unsupported", anchor="center", font="7.1"),
         txt(145, 53, "reported supported", anchor="center", font="7.1")]
    x0s = {"unavailable": 42, "unsupported": 85, "supported": 128}
    designs = [("gpt-4.1-nano-2025-04-14", "4.1 nano", 40),
               ("gpt-5.4-nano-2026-03-17", "5.4 nano", 20)]
    for model, mlab, top in designs:
        b.append(txt(1, top + 3.8, mlab, font="8"))
        for j, (arm, alab) in enumerate((("eal_mcp", "EAL"), ("plain_validator", "validator"))):
            y = top - j * 7
            b.append(txt(3, y, alab, font="7.6"))
            fate = Counter(r["answer"]["status"] for r in rows[model, arm].values()
                           if r["reference"]["status"] == "unavailable")
            assert sum(fate.values()) == 19
            for status in ("unavailable", "unsupported", "supported"):
                start = x0s[status]
                for k in range(fate[status]):
                    x = start + k * 1.40
                    if status == "supported":
                        b.append(line(x-.35, y-.76, x+.35, y+.76,
                                      colour="runAccent", width="0.8pt"))
                    elif status == "unsupported":
                        b.append(line(x-.35, y+.76, x+.35, y-.76,
                                      colour="runInk", width="0.55pt"))
                    else:
                        b.append(line(x, y-.75, x, y+.75,
                                      colour="runInk", width="0.55pt"))
                b.append(txt(start + 25, y, str(fate[status]), font="7.5",
                             colour="runAccent" if status == "supported" and fate[status] else "runInk"))
    b.append(txt(1, 2.4, "Each stroke is one case; orientations distinguish reported statuses.", font="7.2"))
    return document(65, b)


def fig5(cells: dict[tuple[str, str], dict]) -> str:
    b = [txt(1, 54, "Model snapshot", font="8"),
         txt(46, 54, "Median trial seconds", font="8"),
         txt(103, 54, "Known cost (mUSD / trial)", font="8"),
         txt(46, 49, r"EAL / validator = ratio of medians", font="7", colour="runQuiet"),
         txt(103, 49, r"EAL / validator = ratio of totals", font="7", colour="runQuiet")]
    for i, (model, label) in enumerate(MODELS):
        e, v = cells[model, "eal_mcp"], cells[model, "plain_validator"]
        assert e["assigned"] == v["assigned"] == 40
        assert e["unknown_cost_calls"] == v["unknown_cost_calls"] == 0
        se, sv = e["median_seconds_attempted"], v["median_seconds_attempted"]
        ce, cv = e["estimated_usd_known"] * 1000 / 40, v["estimated_usd_known"] * 1000 / 40
        y = 42 - i * 6.6
        b.append(txt(1, y, label, font="8"))
        b.append(txt(46, y, rf"{se:.2f} / {sv:.2f} $\approx {se/sv:.2f}\times$", font="7.6"))
        b.append(txt(103, y, rf"{ce:.2f} / {cv:.2f} $\approx {ce/cv:.2f}\times$", font="7.6"))
    b.append(txt(1, 2, "Observed paired arms; 40 completed trials in each cell, with no unknown-cost calls.", font="7.2"))
    return document(58, b)


def render(source: Path) -> Path:
    """Compile the exact include-ready source using standard TeX tools."""
    wrapper = (r"\documentclass[10pt,border=1pt]{standalone}" + "\n"
               r"\usepackage[T1]{fontenc}" + "\n"
               r"\usepackage{lmodern,tikz,amsmath,xcolor}" + "\n"
               r"\begin{document}" + "\n"
               rf"\input{{{source.resolve()}}}" + "\n"
               r"\end{document}" + "\n")
    with tempfile.TemporaryDirectory(prefix="earl-fig-") as temporary:
        build = Path(temporary)
        (build / "wrapper.tex").write_text(wrapper)
        proc = subprocess.run(["latexmk", "-pdf", "-halt-on-error", "-interaction=nonstopmode",
                               "-file-line-error", "wrapper.tex"], cwd=build,
                              capture_output=True, text=True)
        if proc.returncode:
            raise RuntimeError(f"Cannot render {source.name}:\n" + "\n".join(proc.stdout.splitlines()[-30:]))
        pdf = build / "wrapper.pdf"
        info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
        if not any(line.startswith("Pages:") and line.split()[-1] == "1" for line in info.splitlines()):
            raise RuntimeError(f"Expected one page for {source.name}")
        fonts = subprocess.run(["pdffonts", str(pdf)], capture_output=True, text=True, check=True).stdout.splitlines()[2:]
        if not fonts or any(line.split()[4].lower() != "yes" for line in fonts):
            raise RuntimeError(f"Unembedded or absent fonts for {source.name}")
        output = source.with_suffix("").with_suffix(".pdf")
        shutil.copyfile(pdf, output)
        return output


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--zip", type=Path, required=True, help="retained GitHub Actions experiment ZIP")
    p.add_argument("--no-render", action="store_true", help="generate TikZ without compiling PDFs")
    args = p.parse_args()
    with zipfile.ZipFile(args.zip) as z:
        summary = json.loads(z.read("run/summary.json"))
        trial_paths = [name for name in z.namelist() if name.startswith("run/trials/") and name.endswith("/trial.json")]
        rows: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
        for name in trial_paths:
            row = json.loads(z.read(name))
            key = row["model"], row["arm"]
            assert row["case_id"] not in rows[key]
            rows[key][row["case_id"]] = row
    assert len(trial_paths) == summary["assigned"] == summary["completed"] == 1440
    assert summary["failed"] == summary["not_attempted"] == 0
    assert len(rows) == 36 and all(len(v) == 40 for v in rows.values())
    cells = {(v["model"], v["arm"]): v for v in summary["cells"]}
    contrasts = {v["model"]: v for v in summary["contrasts"]
                 if v["reference_arm"] == "eal_mcp" and v["comparator"] == "plain_validator"}
    assert len(contrasts) == 6
    output = {
        "fig1-assignment.tikz.tex": fig1(cells, summary),
        "fig2-correctness.tikz.tex": fig2(rows),
        "fig3-paired.tikz.tex": fig3(contrasts),
        "fig4-false-support.tikz.tex": fig4(rows),
        "fig5-resource.tikz.tex": fig5(cells),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for filename, content in output.items():
        (OUT / filename).write_text(content)
        print(OUT / filename)
    if not args.no_render:
        for filename in output:
            print(render(OUT / filename))


if __name__ == "__main__":
    main()
