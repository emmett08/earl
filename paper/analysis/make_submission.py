#!/usr/bin/env python3
"""Create and compile a flat, self-contained Elsevier source bundle."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import zipfile

import fitz

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="earl-submission-") as directory:
        work = Path(directory)
        source = (ROOT / "manuscript.tex").read_text()
        paths = re.findall(r"(?:\\input|\\includegraphics)(?:\[[^\]]*\])?\{([^}]+)\}", source)
        paths += re.findall(r"\\lstinputlisting(?:\[[^\]]*\])?\{([^}]+)\}", source)
        copied = set()
        for name in paths:
            original = ROOT / name
            if not original.exists():
                original = original.with_suffix(".tex")
            assert original.exists(), original
            assert original.name not in copied, "Flat filename collision"
            copied.add(original.name)
            shutil.copyfile(original, work / original.name)
            source = source.replace("{" + name + "}", "{" + original.name + "}")
        for name in ["elsarticle.cls", "elsarticle-num.bst", "highlights.txt"]:
            shutil.copyfile(ROOT / name, work / name)
        if "\\bibliography{" in source:
            shutil.copyfile(ROOT / "references.bib", work / "references.bib")
        for figure_source in sorted((ROOT / "figures").glob("*.tikz.tex")):
            shutil.copyfile(figure_source, work / figure_source.name)
        shutil.copyfile(ROOT / "vendor/SOURCE.md", work / "elsevier-source.md")
        for name in ["elsarticle.dtx", "elsarticle.ins", "README", "manifest.txt"]:
            shutil.copyfile(ROOT / "vendor" / name, work / ("elsevier-" + name if name in {"README", "manifest.txt"} else name))
        (work / "manuscript.tex").write_text(source)
        (work / "submission-notes.md").write_text((ROOT / "review/author-review.md").read_text())
        sources = sorted(p.name for p in work.iterdir())
        result = subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "manuscript.tex"],
                                cwd=work, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(result.stdout[-12000:])
        log = (work / "manuscript.log").read_text(errors="replace")
        for warning in ["undefined references", "undefined citations", "Overfull"]:
            assert warning not in log, warning
        retained = fitz.open(ROOT / "manuscript.pdf")
        rebuilt = fitz.open(work / "manuscript.pdf")
        assert len(retained) == len(rebuilt), "Flat build page count differs"
        render_hashes = []
        for page, (a, b) in enumerate(zip(retained, rebuilt), 1):
            assert a.get_text() == b.get_text(), f"Flat build text differs on page {page}"
            x = a.get_pixmap(matrix=fitz.Matrix(.5, .5), alpha=False)
            y = b.get_pixmap(matrix=fitz.Matrix(.5, .5), alpha=False)
            assert x.samples == y.samples, f"Flat build rendered page differs: {page}"
            render_hashes.append(hashlib.sha256(x.samples).hexdigest())
        sources += ["manuscript.pdf"]
        if (work / "manuscript.bbl").exists():
            sources.append("manuscript.bbl")
        hashes = {name: hashlib.sha256((work/name).read_bytes()).hexdigest() for name in sources}
        (work / "source-manifest.json").write_text(json.dumps(hashes, indent=2)+"\n")
        sources.append("source-manifest.json")
        destination = ROOT / "jss-submission.zip"
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(sources):
                archive.write(work / name, name)
        with zipfile.ZipFile(destination) as archive:
            assert archive.testzip() is None, "ZIP CRC verification failed"
            for name, sha in hashes.items():
                assert hashlib.sha256(archive.read(name)).hexdigest() == sha, name
        proof = {"schema": "eal-jss-submission-proof/1", "zip_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                 "files": len(sources), "pages": len(retained), "flat_source_compiles_independently": True,
                 "no_overfull_or_undefined_references": True, "zip_crc_and_manifest_hashes_verified": True,
                 "rendered_pages_equal_current_journal_pdf": True, "page_render_sha256": render_hashes,
                 "journal_pdf_sha256": hashlib.sha256((ROOT / "manuscript.pdf").read_bytes()).hexdigest()}
        (ROOT / "review/submission-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
        print(f"Built and compiled {destination.name}: {len(sources)} flat files.")


if __name__ == "__main__":
    main()
