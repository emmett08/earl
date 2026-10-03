"""Generate editable LaTeX from the maintained argument and its numbered references."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "engineering-argumentation-ai-agents.md"


def latex(text: str) -> str:
    return subprocess.run(
        ["pandoc", "--from=markdown+raw_tex", "--to=latex", "--wrap=preserve"],
        input=text, text=True, capture_output=True, check=True,
    ).stdout.strip()


def externalise_links(text: str) -> str:
    def resolve(match: re.Match) -> str:
        target = match[1]
        if "://" in target or target.startswith("#"):
            return match[0]
        resolved = (SOURCE.parent / target).resolve().relative_to(ROOT.parents[1])
        return "](" + "https://github.com/emmett08/earl/blob/main/" + str(resolved) + ")"
    return re.sub(r"\]\(([^)]+)\)", resolve, text)


source = SOURCE.read_text()
source = re.sub(r"<!-- article-navigation:start -->.*?<!-- article-navigation:end -->", "", source, flags=re.S)
references = dict(re.findall(r"^\[\^([^\]]+)\]: (.*)$", source, re.M))
body = re.sub(r"^\[\^[^\]]+\]: .*\n?", "", source, flags=re.M)
body = "\n".join(body.splitlines()[1:]).strip()
order = list(dict.fromkeys(re.findall(r"\[\^([^\]]+)\]", body)))
assert set(order) == set(references), "Unresolved or unused reference"
body = body.replace("The [figure](engineering-argumentation/figures/decision-sufficiency.pdf)", r"Figure~\ref{fig:decision-sufficiency}")
body = externalise_links(body)
body = body.replace("<!-- figure:decision-sufficiency -->", r"""
\begin{figure}[htbp]
\centering
\input{figures/decision-sufficiency.tikz.tex}
\caption[Evidence sufficiency for a bounded choice]{\input{figures/decision-sufficiency.caption.tex}}
\label{fig:decision-sufficiency}
\end{figure}
""")
body = re.sub(r"\[\^([^\]]+)\]", lambda m: r"\cite{" + m[1] + "}", body)
body = re.sub(r"(?:\\cite\{[^}]+\}){2,}", lambda m: r"\cite{" + ",".join(re.findall(r"\\cite\{([^}]+)\}", m[0])) + "}", body)
body = latex(body)
body = body.replace(r"Figure\textasciitilde{}\ref{fig:decision-sufficiency}", r"Figure~\ref{fig:decision-sufficiency}")
body = body.replace("A simple illustrative calculation makes this stopping condition visible.", r"\Needspace{16\baselineskip}\begin{samepage}" + "\nA simple illustrative calculation makes this stopping condition visible.", 1)
body = body.replace(r"\begin{figure}[htbp]", r"\end{samepage}" + "\n" + r"\begin{figure}[htbp]", 1)

# Tables retain the comparison, with widths chosen for their different reading tasks.
tables = list(re.finditer(r"\\begin\{longtable\}.*?\\end\{longtable\}", body, re.S))
assert len(tables) == 2, "Review table layout after changing the source structure"
settings = [
    (["0.26", "0.29", "0.45"], "Established engineering practices", "Established engineering practices and their contribution to AI-assisted decisions.", "tab:practices"),
    (["0.15", "0.425", "0.425"], "Toulmin reconstruction of the two claims", "The connected arguments for explicit justification and proportionate inquiry.", "tab:toulmin"),
]
for match, (widths, short, caption, label) in reversed(list(zip(tables, settings))):
    table = match[0]
    for width in widths:
        table = table.replace(r"\real{0.3333}", r"\real{" + width + "}", 1)
    table = table.replace(r"\begin{longtable}[]", r"\begin{tabular}", 1)
    table = table.replace("\\endhead\n\\bottomrule\\noalign{}\n\\endlastfoot\n", "")
    table = table.replace(r"\end{longtable}", r"\bottomrule" + "\n" + r"\end{tabular}")
    # Visible row spacing preserves the distinct assertions without vertical rules.
    table = table.replace(" \\\\\n", " \\\\[4pt]\n")
    table = "\\begin{table}[htbp]\n\\small\n\\centering\n" + r"\caption[" + short + "]{" + caption + r"}\label{" + label + "}\n" + table + "\n\\end{table}"
    body = body[:match.start()] + table + body[match.end():]

references_tex = "\n\n".join(r"\bibitem{" + key + "}\n" + latex(references[key]) for key in order)
preamble = r"""% Generated from ../engineering-argumentation-ai-agents.md by reproduction/typeset.py.
% Edit the maintained prose there; regenerate this complete, editable LaTeX source.
\documentclass[11pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{lmodern,microtype}
\usepackage[a4paper,textwidth=155mm,top=24mm,bottom=24mm]{geometry}
\usepackage{amsmath,amssymb,booktabs,longtable,array,calc}
\usepackage{graphicx,xcolor,tikz,pgfplots}
\pgfplotsset{compat=1.18}
\usepackage{xurl,caption,placeins,flafter,needspace}
\usepackage[colorlinks=true,linkcolor=black,citecolor=black,urlcolor=teal!65!black]{hyperref}
\hypersetup{pdftitle={Engineering argumentation with AI agents},pdfsubject={Explicit justification and minimum sufficient evidence for engineering decisions}}
\captionsetup{font=small,labelfont=bf,skip=8pt}
\setlength{\parindent}{0pt}
\setlength{\parskip}{5.5pt plus 1pt minus 1pt}
\setlength{\emergencystretch}{2em}
\setlength{\LTpre}{8pt}
\setlength{\LTpost}{8pt}
\setlength{\tabcolsep}{5pt}
\renewcommand{\arraystretch}{1.12}
\clubpenalty=10000
\widowpenalty=10000
\displaywidowpenalty=10000
\postdisplaypenalty=10000
\raggedbottom
\begin{document}
{\fontsize{22}{26}\selectfont\bfseries Engineering argumentation\\with AI agents\par}
\vspace{4pt}
{\large Justification and minimum sufficient evidence\par}
\vspace{5pt}
{\small 3 October 2026\par}
\vspace{10pt}
"""
(ROOT / "engineering-argumentation.tex").write_text(
    preamble + body + "\n\n\\FloatBarrier\n\\begin{thebibliography}{99}\n\\small\n"
    + "\\raggedright\n\\interlinepenalty=10000\n\\setlength{\\parskip}{0pt}\n\\setlength{\\itemsep}{4pt}\n"
    + references_tex + "\n\\end{thebibliography}\n\\end{document}\n"
)
print(f"Generated LaTeX with {len(order)} numbered references and two comparison tables.")
