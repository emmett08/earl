"""Generate three exact TikZ figures; statistical entries come from replayed data."""
from pathlib import Path
import json

PAPER = Path(__file__).resolve().parents[1]
HEADER = r"""% Required packages: amsmath, amssymb, xcolor, tikz
% Required TikZ libraries: none
% Target width: 160 mm
% Minimum text size: 8 pt
% Colour/greyscale intent: one teal accent; direct labels preserve all distinctions
\begingroup
\definecolor{ealfigaccent}{RGB}{15,91,103}
\begin{tikzpicture}[x=1mm,y=1mm,font=\fontsize{9}{11}\selectfont]
"""
END = "\\end{tikzpicture}\n\\endgroup\n"


def write(name, body):
    (PAPER / "figures" / (name + ".tikz.tex")).write_text(HEADER + body + END)


def main():
    write("typed-correspondence", r"""\path[use as bounding box] (0,0) rectangle (156,66);
\node[anchor=west,font=\bfseries] at (2,62) {Declared proposition};
\node[anchor=east,font=\bfseries] at (154,62) {Supplied observation};
\node[anchor=west] at (2,53) {$s=\texttt{pump-A}$};
\node[anchor=east] at (154,53) {$s'=\texttt{pump-A}$};
\node[anchor=west] at (2,44) {$q=\texttt{pressure},\quad u=\mathrm{kPa}$};
\node[anchor=east] at (154,44) {$q'=\texttt{pressure},\quad u'=\mathrm{Pa}$};
\node[anchor=west] at (2,35) {$\sigma=\texttt{trial-v1}$};
\node[anchor=east] at (154,35) {$\sigma'=\texttt{trial-v1}$};
\node[anchor=west] at (2,26) {$I=[t_0,t_1)$};
\node[anchor=east] at (154,26) {$I'=[t_0,t_1)$};
\node[anchor=west] at (2,17) {$Q:\ \texttt{assignment=randomised}$};
\node[anchor=east] at (154,17) {$v:\ \texttt{assignment=randomised}$};
\foreach \y in {53,44,35,26,17} {
  \draw[gray!55,line width=.45pt] (57,\y)--(70,\y);
  \draw[gray!55,line width=.45pt] (86,\y)--(99,\y);
}
\node[text=ealfigaccent] at (78,53) {$s=s'$};
\node[text=ealfigaccent] at (78,44) {$q=q'$};
\node[text=ealfigaccent] at (78,35) {$\sigma=\sigma'$};
\node[text=ealfigaccent] at (78,26) {$I\subseteq I'$};
\node[text=ealfigaccent] at (78,17) {$Q=v|_Q$};
\node[anchor=west,text=ealfigaccent] at (2,3) {Result conversion: $7500\,\mathrm{Pa}=7.5\,\mathrm{kPa}\geq5\,\mathrm{kPa}$};
\node[anchor=east] at (154,3) {Method: \texttt{causal/1}};
""")
    write("acceptance-region", r"""\path[use as bounding box] (0,0) rectangle (156,73);
\node[anchor=west,font=\bfseries] at (3,68) {Available evidence: $A=1$};
\draw[line width=.55pt] (14,13)--(91,13);
\draw[line width=.55pt] (14,13)--(14,59);
\node[anchor=north] at (53,5) {Sample p95 latency (ms)};
\node[anchor=west] at (3,62) {Error rate (\%)};
\foreach \x/\label in {14/0,39/100,64/200,89/300} {
 \draw[line width=.5pt] (\x,13)--(\x,11.5);
 \node[anchor=north,font=\fontsize{8}{10}\selectfont] at (\x,11) {\label};
}
\foreach \y/\label in {13/0,28/1,43/2,58/3} {
 \draw[line width=.5pt] (14,\y)--(12.5,\y);
 \node[anchor=east,font=\fontsize{8}{10}\selectfont] at (12,\y) {\label};
}
\draw[ealfigaccent,line width=.9pt] (14,28)--(64,28)--(64,13);
\node[text=ealfigaccent] at (36,20) {supported};
\node at (64,52) {unsupported};
\draw[line width=.8pt] (58,27)--(60,29) (58,29)--(60,27);
\node[anchor=south east,font=\fontsize{8}{10}\selectfont] at (57.5,30) {$(180,1)$};
\draw[line width=.8pt] (58,42)--(60,44) (58,44)--(60,42);
\node[anchor=west,font=\fontsize{8}{10}\selectfont] at (62,43) {$(180,2)$};
\node[anchor=west,font=\bfseries] at (103,61) {Unavailable: $A=0$};
\node[anchor=west] at (103,50) {wrong identity};
\node[anchor=west] at (103,42) {incomplete records};
\node[anchor=west] at (103,34) {stale observation};
\node[anchor=west] at (103,26) {invalid measurements};
\node[anchor=west] at (103,14) {Performance remains};
\node[anchor=west] at (103,8) {unresolved.};
""")
    summary = json.loads((PAPER / "results/summary.json").read_text())
    rows = {r["model"]: r for r in summary["contrasts"] if r["comparator"] == "json_prompt"}
    models = [("gpt-4.1-nano-2025-04-14", "4.1 nano"), ("gpt-4.1-mini-2025-04-14", "4.1 mini"),
              ("gpt-4.1-2025-04-14", "4.1 full"), ("gpt-5.4-nano-2026-03-17", "5.4 nano"),
              ("gpt-5.4-mini-2026-03-17", "5.4 mini"), ("gpt-5.4-2026-03-05", "5.4 full")]
    body = [r"\path[use as bounding box] (0,0) rectangle (156,94);",
            r"\node[anchor=west] at (2,90) {Rows: EAL/MCP correct, incorrect. Columns: JSON correct, incorrect.};"]
    for i, (model, label) in enumerate(models):
        r = rows[model]
        x, y = 26 + (i % 3) * 52, 73 - (i // 3) * 39
        a, b, c, d = [r[k] for k in ("both_correct", "eal_only_correct", "comparator_only_correct", "both_incorrect")]
        body.append(fr"\node[font=\bfseries] at ({x},{y+8}) {{{label}}};")
        body.append(fr"\node at ({x},{y-3}) {{$\displaystyle\begin{{bmatrix}}{a}&\color{{ealfigaccent}}{b}\\\color{{ealfigaccent}}{c}&{d}\end{{bmatrix}}$}};")
        delta = 100 * r["accuracy_difference"]
        body.append(fr"\node at ({x},{y-16}) {{$\Delta={delta:+g}$ percentage points}};")
        body.append(fr"\node[font=\fontsize{{8}}{{10}}\selectfont] at ({x},{y-23}) {{Completed pairs: {r['paired_completed']}/40}};")
    body.append(r"\node[anchor=west] at (2,3) {Each matrix retains all 40 assigned pairs. Off-diagonal counts determine $\Delta$.};")
    write("paired-outcomes", "\n".join(body) + "\n")


if __name__ == "__main__":
    main()
