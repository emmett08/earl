"""Check manuscript references, generated results and PDF build diagnostics."""
from pathlib import Path
import json
import re
import subprocess

PAPER = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    text = (PAPER / "manuscript.tex").read_text()
    labels = re.findall(r"\\label\{([^}]+)\}", text)
    labels += re.findall(r"label=\{([^}]+)\}", text)
    refs = re.findall(r"\\ref\{([^}]+)\}", text)
    require(len(labels) == len(set(labels)), "Duplicate manuscript label")
    require(set(refs) <= set(labels), "Unresolved source reference")
    cited = {key.strip() for group in re.findall(r"\\cite\w*\{([^}]+)\}", text)
             for key in group.split(",")}
    bibliography = (PAPER / "references.bib").read_text()
    entries = re.findall(r"@\w+\{([^,]+),", bibliography)
    require(len(entries) == len(set(entries)), "Duplicate bibliography key")
    require(cited == set(entries), "Missing or unused bibliography entry")
    figures = re.findall(r"\\includegraphics\[[^\]]*\]\{([^}]+)\}", text)
    require(len(figures) == len(set(figures)) == 3, "Expected exactly three figures")
    for filename in figures:
        path = PAPER / filename
        require(path.exists(), f"Missing figure: {filename}")
        require(path.with_suffix(".tikz.tex").exists(), "Missing editable TikZ source")
    require(not re.search(r"\b(TODO|TBD|FIXME|INSERT HERE)\b", text), "Manuscript placeholder")
    log = (PAPER / "build/manuscript.log").read_text()
    for pattern in (r"Overfull \\hbox", r"Overfull \\vbox", r"undefined",
                    r"multiply defined", r"Missing character", r"^! "):
        require(not re.search(pattern, log, re.MULTILINE), f"Build issue: {pattern}")
    summary = json.loads((PAPER / "results/summary.json").read_text())
    require(len(summary["cells"]) == 30, "Expected 6 by 5 result cells")
    for row in summary["cells"]:
        require(row["assigned"] == 40, "Assignment denominator changed")
    components = json.loads((PAPER / "results/error-components.json").read_text())
    full_json = [row for row in components["complete_incorrect"]
                 if row["model"] == "gpt-4.1-2025-04-14" and row["arm"] == "json_prompt"]
    require(len(full_json) == 4 and all(row["family"] == "corrupt" and
            row["failed_components"] == ["failed_checks_correct"] for row in full_json),
            "Full-model JSON error interpretation changed")
    mini_eal = [row for row in components["complete_incorrect"]
                if row["model"] == "gpt-4.1-mini-2025-04-14" and row["arm"] == "eal_mcp"]
    require(len(mini_eal) == 8 and sum("status_correct" in row["failed_components"]
                                     for row in mini_eal) == 7,
            "Mini-model EAL error interpretation changed")
    require(components["recorded_host_agreement_flags"] == {"True": 141}, "Host flags changed")
    highlights = (PAPER / "highlights.txt").read_text().splitlines()
    require(len(highlights) == 4 and all(len(line) <= 85 for line in highlights), "Highlights length")
    # The publication includes vector PDF graphics with embedded fonts.
    for path in [PAPER / "manuscript.pdf", *(PAPER / name for name in figures)]:
        info = subprocess.check_output(["pdfinfo", str(path)], text=True)
        require("Pages:" in info, f"Unreadable PDF: {path.name}")
        fonts = subprocess.check_output(["pdffonts", str(path)], text=True).splitlines()[2:]
        require(fonts and all(re.search(r"\s+yes\s+(yes|no)\s+(yes|no)\s+\d+\s+\d+\s*$", row)
                             for row in fonts), f"Unembedded font: {path.name}")
    print("PASS: 3 figures; references resolved; no overflow; all fonts embedded; "
          "30 result cells; component interpretations verified")


if __name__ == "__main__":
    main()
