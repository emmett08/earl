"""Bound the article to the audited run and exactly five rendered figures."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "results/aggregate.json").read_text())
assert data["run_id"] == 36275725154
assert data["source_commit"] == "f8c629f49b5bef6c760de2029f6bc7db0e762a6f"
assert data["archive_sha256"] == "0d1286e661eabb78470a2283d160979d4aae7221f98a086189ee7495124de018"
assert (data["assigned"], data["distinct_cases"], data["transport"], data["finalisation"]) == (
    1440, 40, "native", "model")
assert len(data["cells"]) == 36 and len(data["pairs"]) == 30
by = {(x["model"], x["arm"]): x for x in data["cells"]}
assert sum(x["correct"] for x in data["cells"] if x["arm"] == "eal_mcp") == 223
assert sum(x["correct"] for x in data["cells"] if x["arm"] == "plain_validator") == 219
assert sum(x["false_support"] for x in data["cells"] if x["arm"] == "eal_mcp") == 0
assert sum(x["false_support"] for x in data["cells"] if x["arm"] == "plain_validator") == 7
assert all(x["unknown_cost_calls"] == 0 for x in data["cells"])
assert (ROOT / "results/assignments.csv").read_text().count("\n") == 1441
source = (ROOT / "manuscript.tex").read_text()
assert len(re.findall(r"\\begin\{figure\}", source)) == 5
assert len(re.findall(r"\\includegraphics", source)) == 5
assert len(set(re.findall(r"\\label\{fig:[^}]+\}", source))) == 5
assert len(re.findall(r"\\begin\{algorithm\}", source)) == 1
expected = ("fig1-assignment", "fig2-correctness", "fig3-paired",
            "fig4-false-support", "fig5-resource")
for stem in expected:
    assert (ROOT / "figures" / f"{stem}.tikz.tex").is_file()
    assert (ROOT / "figures" / f"{stem}.pdf").is_file()
pdf = ROOT / "manuscript.pdf"
assert pdf.is_file() and pdf.stat().st_size > 30_000
info = subprocess.check_output(["pdfinfo", str(pdf)], text=True)
assert int(re.search(r"^Pages:\s+(\d+)$", info, flags=re.MULTILINE).group(1)) >= 5
text = subprocess.check_output(["pdftotext", "-layout", str(pdf), "-"], text=True)
for phrase in ("1,440", "223", "219", "unavailable", "paired", "References"):
    assert phrase in text, phrase
print("Verified five figures, one algorithm, paired source data and rendered manuscript")
