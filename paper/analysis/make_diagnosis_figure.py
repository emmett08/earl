"""Render the later nano trial partition from the replayed diagnosis counts.

The resulting TikZ source uses arithmetic and grouping braces: positions do not
encode time, magnitude or a causal path. The manuscript supplies the caption.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]


def make_figure(data: dict) -> str:
    partition = data["eal_partition"]
    assigned = partition["assigned"]
    attempted = partition["attempted"]
    correct = partition["correct"]
    incorrect = partition["completed_incorrect"]
    failed = partition["model_call_limit"]
    skipped = partition["not_attempted"]
    completed = correct + incorrect
    status_errors = data["eal_completed_error_components"]["status_incorrect"]
    missing_operation = data["eal_failed_second_response_missing_operation"]
    stop = data["stop"]
    assert completed + failed == attempted
    assert attempted + skipped == assigned
    assert data["eal_first_assessment_success"] == attempted
    assert data["eal_failed_call_counts"] == {"6": failed}
    assert stop["eal_skipped"] == skipped
    assert stop["arm"] == "plain_validator"
    assert status_errors <= incorrect and missing_operation <= failed
    assert assigned == 40, "This layout describes the frozen 40-case nano study."

    source = r"""% Required packages: amsmath, amssymb, xcolor, tikz
% Required TikZ libraries: none
% Target width: 160 mm
% Minimum text size: 8 pt
% Colour/greyscale intent: one teal accent; grouping and direct labels survive greyscale
% Generated from paper/results/nano-diagnosis.json by analysis/make_diagnosis_figure.py.
\begingroup
\definecolor{ealnanoaccent}{RGB}{15,91,103}
\begin{tikzpicture}[x=1mm,y=1mm,font=\fontsize{9}{11}\selectfont]
\path[use as bounding box] (0,0) rectangle (156,83);
% Mathematical grouping braces; their extent identifies summands, not a time path.
\draw[line width=.6pt] (30,70) .. controls (30,73) and (36,73) .. (38,73)
 -- (66,73) .. controls (69,73) and (71,73) .. (73,76)
 .. controls (75,73) and (77,73) .. (80,73) -- (108,73)
 .. controls (111,73) and (116,73) .. (116,70);
\node at (77,81) {__ATTEMPTED__ attempted: all assessments matched the reference};
\draw[line width=.6pt] (30,56) .. controls (30,59) and (35,59) .. (37,59)
 -- (47,59) .. controls (50,59) and (52,59) .. (54,62)
 .. controls (56,59) and (58,59) .. (61,59) -- (71,59)
 .. controls (74,59) and (79,59) .. (79,56);
\node at (54,66) {__COMPLETED__ completed};
\node[font=\fontsize{22}{24}\selectfont] at (10,48) {$__ASSIGNED__$};
\node[font=\fontsize{18}{20}\selectfont] at (23,48) {$=$};
\node[font=\fontsize{22}{24}\selectfont,text=ealnanoaccent] at (38,48) {$__CORRECT__$};
\node[font=\fontsize{18}{20}\selectfont] at (54,48) {$+$};
\node[font=\fontsize{22}{24}\selectfont] at (71,48) {$__INCORRECT__$};
\node[font=\fontsize{18}{20}\selectfont] at (90,48) {$+$};
\node[font=\fontsize{22}{24}\selectfont] at (107,48) {$__FAILED__$};
\node[font=\fontsize{18}{20}\selectfont] at (125,48) {$+$};
\node[font=\fontsize{22}{24}\selectfont] at (143,48) {$__SKIPPED__$};
\node at (10,39) {assigned};
\node[text=ealnanoaccent] at (38,39) {correct};
\node at (71,39) {incorrect};
\node at (107,39) {failed};
\node at (143,39) {unattempted};
\node[align=center,font=\fontsize{8}{10}\selectfont] at (71,24)
  {__STATUS_ERRORS__/__INCORRECT__ wrong\\decision status};
\node[align=center,font=\fontsize{8}{10}\selectfont] at (107,22)
  {Six-call limit\\__MISSING__/__FAILED__ omitted\\\texttt{operation}*};
\node[align=center,font=\fontsize{8}{10}\selectfont] at (143,22)
  {Provider HTTP __HTTP__\\in plain-validator\\__GLOBAL_SKIPPED__ skipped overall};
\node[anchor=west,font=\fontsize{8}{10}\selectfont] at (2,4)
  {*First model response after a successful assessment.};
\end{tikzpicture}
\endgroup
"""
    replacements = {
        "ASSIGNED": assigned, "ATTEMPTED": attempted, "COMPLETED": completed,
        "CORRECT": correct, "INCORRECT": incorrect, "FAILED": failed,
        "SKIPPED": skipped, "STATUS_ERRORS": status_errors,
        "MISSING": missing_operation, "HTTP": stop["http_status"],
        "GLOBAL_SKIPPED": stop["skipped"],
    }
    for key, value in replacements.items():
        source = source.replace(f"__{key}__", str(value))
    return source


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path,
                        default=PAPER / "results" / "nano-diagnosis.json")
    parser.add_argument("--output", type=Path,
                        default=PAPER / "figures" / "nano-failure-diagnosis.tikz.tex")
    args = parser.parse_args()
    args.output.write_text(make_figure(json.loads(args.data.read_text())))
    print(args.output.relative_to(PAPER) if args.output.is_relative_to(PAPER) else args.output)


if __name__ == "__main__":
    main()
