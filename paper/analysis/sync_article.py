#!/usr/bin/env python3
"""Sync the completed article into the preserved Elsevier review wrapper.

This is an explicit local import, never an archive lookup or a network action.
The standalone figure reviews bind copied, byte-identical figure files. They
do not certify the newly typeset journal manuscript; its proof is separate.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]

PREAMBLE = r"""\documentclass[preprint,11pt]{elsarticle}
\usepackage[a4paper,margin=25mm]{geometry}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{lmodern,microtype,amsmath,amssymb,booktabs,array,longtable,calc}
\usepackage{xcolor,listings,graphicx,placeins,xurl,float,etoolbox}
\usepackage[hidelinks]{hyperref}
\input{eal3-listings.tex}
\definecolor{teal}{HTML}{176D74}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\setlength{\emergencystretch}{3em}
\setcounter{secnumdepth}{5}
\clubpenalty=10000
\widowpenalty=10000
\displaywidowpenalty=10000
\journal{Journal of Systems and Software}
\date{2 October 2026}
\myfooter[L]{Review draft for Journal of Systems and Software\hfill 2 October 2026}
\begin{document}
\begin{frontmatter}
\title{Resource use and decision correctness in a live EAL/3 handover pilot}
\author{Anonymous review manuscript}
"""

DECLARATIONS = r"""
\FloatBarrier
\appendix
\section{Retained executable source}
The following excerpt is derived from the actual EAL/3 cutover source retained
in the finished archive. The repository parser validates the source with the
registered \texttt{experiment/task-rules/1} method; formatting preserves its
semantic representation. The complete source and its archive hash are retained
in the compact replication snapshot. This syntax check establishes consistency
with the implemented language contract, rather than model comprehension or
independently validated engineering correctness.

\noindent\begin{minipage}{\linewidth}
\lstinputlisting[style=ealcode,caption={Reasoning declaration and argument from the retained EAL/3 cutover source.},label={lst:retained}]{listings/method-excerpt.eal}
\end{minipage}

\section{Research materials and declarations for author review}
The repository's \texttt{paper/data} snapshot retains byte-preserved annotated
rows, cases, frozen design contracts and reports. API calls are projected to
their accounting and configuration fields; duplicated provider payloads are
omitted. The original finish ZIP has SHA-256
\nolinkurl{491df25b38bd22554143c0e146a7ac547d0686ea1022b1c9bf87b6093482b69a}.
The separate full research package retains the six original archives. The
flat journal source ZIP contains manuscript sources and figures, rather than
all research data. Repository and artefact links identify the project even
though this review copy omits author names.

OpenAI ChatGPT/Codex assisted with corpus construction, answer coding,
analysis, figure preparation and manuscript preparation. The retained
assessor provenance describes that assistance and its measurement limitations.
Author responsibility, oversight actually performed, authorship, affiliations,
funding, competing interests and a durable public data-availability statement
must be supplied by the authors before submission. This draft does not assert
that those declarations or human review have been completed.

\end{document}
"""


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("article", type=Path, help="Directory containing article.md and article.tex")
    args = ap.parse_args()
    article = args.article.resolve()
    tex = (article / "article.tex").read_text()
    body = tex.split(r"\begin{document}", 1)[1].split(r"\end{document}", 1)[0]
    body = body.replace(r"\maketitle", "", 1).strip()
    abstract, body = body.split(r"\end{abstract}", 1)
    assert abstract.startswith(r"\begin{abstract}")
    body = body.replace(r"\includegraphics[width=160mm,height=\textheight]",
                        r"\includegraphics[width=\linewidth,height=.84\textheight,keepaspectratio]")
    for model in ["gpt-4.1-nano-2025-04-14", "gpt-5-nano-2025-08-07"]:
        body = body.replace(r"\texttt{" + model + "}", r"\nolinkurl{" + model + "}")
    # The full research package and this compact repository package have
    # different inclusion boundaries, stated in the journal appendix.
    body = body.replace("The accompanying package retains all six source archives",
                        "The accompanying research package retains all six source archives")
    keywords = r"""
\begin{keyword}
Engineering evidence \sep executable arguments \sep language models \sep context transfer \sep empirical software engineering \sep reproducibility
\end{keyword}
\end{frontmatter}
"""
    (ROOT / "manuscript.tex").write_text(PREAMBLE + abstract + "\\end{abstract}\n" + keywords + body + DECLARATIONS)
    shutil.copyfile(article / "article.md", ROOT / "article.md")
    shutil.copyfile(article / "article.tex", ROOT / "article-source.tex")

    figure_names = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{figures/([^}]+)\.pdf\}", body)
    assert len(figure_names) == len(set(figure_names)) and len(figure_names) >= 14
    imported = ["article.md", "article-source.tex"]
    required = {"reproduction/build_figures.py", "reproduction/build_followup_figures.py", "figures/alternative-text.json",
                "analysis/paired_resources.csv", "analysis/cumulative_resources.csv",
                "analysis/session_resources.csv", "analysis/arm_phase_totals.csv",
                "analysis/resource_summary.json", "analysis/completion-outcomes.json",
                "analysis/completion-inference-audit.json",
                "analysis/completion-figure-numerical-audit.json",
                "analysis/completion-fresh-reader-review.json"}
    required.update(str(p.relative_to(article)) for p in (article / "tables").glob("*.csv"))
    required.update(str(p.relative_to(article)) for p in (article / "analysis").glob("temporal-caption*")
                    if p.is_file())
    required.update(str(p.relative_to(article)) for p in (article / "reproduction/figure-tools").rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts)
    for name in figure_names:
        for suffix in [".tikz.tex", ".pdf", ".png", ".audit.json", ".review.json"]:
            required.add("figures/" + name + suffix)
        required.add("captions/" + name + ".caption.txt")
        required.add(name + ".spec.json")
        spec = json.loads((article / (name + ".spec.json")).read_text())
        required.update(item["path"] for item in spec["inputs"] if "path" in item)
        required.update(spec["build"].get("dependencies", []))
        for profile in [spec["target"].get("manuscript_profile"), spec["build"].get("profile")]:
            if profile:
                required.add(profile)
        review = json.loads((article / ("figures/" + name + ".review.json")).read_text())
        required.update(item["path"] for item in review["artifacts"])
        if "test_evidence" in review["reviewer"]:
            required.add(review["reviewer"]["test_evidence"]["path"])
    for rel in sorted(required):
        source = article / rel
        assert source.is_file(), source
        target = ROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        imported.append(rel)
    # Remove the previous pilot's five unrelated plot files and their reviews.
    for name in ["case-correctness", "session-profiles", "paired-token-ratios", "cumulative-tokens", "coding-sensitivity"]:
        for path in (ROOT / "figures").glob(name + ".*"):
            path.unlink()
    manifest = {"schema": "eal-jss-article-import/1", "figure_ids": figure_names,
                "article_md_sha256": digest(article / "article.md"),
                "article_tex_sha256": digest(article / "article.tex"),
                "files": {name: digest(ROOT / name) for name in sorted(imported)},
                "review_scope": "Copied standalone figure files retain their exact reviewed bytes. New journal PDF placement requires a separate proof."}
    if (article / "eal-handover-data-story.pdf").exists():
        manifest["source_article_pdf_sha256"] = digest(article / "eal-handover-data-story.pdf")
    (ROOT / "review/article-import.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Imported completed article and {len(figure_names)} exact reviewed figures; generated elsarticle manuscript.")


if __name__ == "__main__":
    main()
