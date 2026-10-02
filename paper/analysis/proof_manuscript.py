#!/usr/bin/env python3
"""Bind a journal PDF proof to the current source and exact reviewed figures."""
from pathlib import Path
import argparse
import hashlib
import json
import re

import fitz
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--render", action="store_true", help="Render all pages and contact sheets for placement review")
    ap.add_argument("--accept-visual-review", action="store_true", help="Record completed inspection of the current rendered pages")
    args = ap.parse_args()
    source = (ROOT / "manuscript.tex").read_text()
    manifest = json.loads((ROOT / "review/article-import.json").read_text())
    log = (ROOT / "manuscript.log").read_text(errors="replace")
    assert not any(w in log for w in ["Overfull", "undefined references", "undefined citations"])
    included = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{figures/([^}]+)\.pdf\}", source)
    assert included == manifest["figure_ids"]
    document = fitz.open(ROOT / "manuscript.pdf")
    text = "\n".join(page.get_text() for page in document)
    normalized_text = re.sub(r"\s+", " ", text)
    for required in ["EAL/3", "4,224", "5,442", "25 ambiguous", "1,980,029", "2,982,385", "33.61%", "36985062352", "36997861629"]:
        assert required in normalized_text, required
    if "15-reference-undetermined-profiles" in included:
        for required in ["Constructed reference-undetermined mixture", "Supplemental answer-measurement review", "1,871", "169"]:
            assert required in normalized_text, required
    for obsolete in ["EAL/2", "5,453", "1,943,638", "2,992,739", "35.05%", "36477862213", "36492423435"]:
        assert obsolete not in text, obsolete
    live_followup = any(name.startswith("16-followup-") for name in included)
    if live_followup:
        assert len(included) == 17 and "17-followup-endpoint-separation" in included, "Current follow-up figure pair is incomplete"
        assert "37023431850" in text, "Current follow-up collection identity missing"
        assert "128" in text and "120" in text, "Current follow-up session counts missing"
        assert "factual grounding" in normalized_text.lower(), "Unassessed endpoint qualification missing"
    followup_size_checks = []
    for name in included:
        if not name.startswith(("16-followup-", "17-followup-")):
            continue
        options = re.search(r"\\includegraphics\[([^\]]*)\]\{figures/" + re.escape(name) + r"\.pdf\}", source)
        assert options and any(width in options.group(1) for width in ["width=\\linewidth", "width=160mm"]), name
        figure = fitz.open(ROOT / f"figures/{name}.pdf")
        width_mm = figure[0].rect.width * 25.4 / 72
        height_mm = figure[0].rect.height * 25.4 / 72
        scale = min(160 / width_mm, (.84 * (297 - 50)) / height_mm)
        assert scale >= 1, f"Follow-up figure shrinks below its natural text-size contract: {name}"
        followup_size_checks.append({"id": name, "natural_width_mm": width_mm,
                                     "natural_height_mm": height_mm, "journal_width_mm": 160,
                                     "minimum_scale_under_wrapper_limits": scale,
                                     "natural_text_size_contract_preserved": True})
    caption_pages = {}
    for index, page in enumerate(document):
        for match in re.finditer(r"\bFigure\s+(\d+):", page.get_text()):
            number = int(match.group(1))
            assert number not in caption_pages, f"Duplicate figure caption {number}"
            caption_pages[number] = index + 1
    assert set(caption_pages) == set(range(1, len(included) + 1)), "Figure caption count or numbering differs"
    out_of_page = []
    for index, page in enumerate(document):
        for word in page.get_text("words"):
            x0, y0, x1, y1 = word[:4]
            if x0 < 0 or y0 < 0 or x1 > page.rect.width + .2 or y1 > page.rect.height + .2:
                out_of_page.append({"page": index + 1, "word": word[4], "bbox": list(word[:4])})
    assert not out_of_page, out_of_page
    normalized_pages = [re.sub(r"\s+", "", page.get_text()) for page in document]
    listing_pages = [index + 1 for index, page in enumerate(normalized_pages)
                     if "reasoningtask_rules" in page or "argumentresult" in page]
    assert len(listing_pages) == 1, "Retained source listing is missing or split across pages"
    listing_text = normalized_pages[listing_pages[0] - 1]
    assert "reasoningtask_rules" in listing_text and "argumentresult" in listing_text
    qa = ROOT / "qa/journal-proof"
    contact_sheets = []
    if args.render:
        qa.mkdir(parents=True, exist_ok=True)
        thumbnails = []
        for index, page in enumerate(document):
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False)
            pixmap.save(qa / f"page-{index+1:02}.png")
            im = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
            im.thumbnail((420, 594))
            tile = Image.new("RGB", (440, 624), "#e4e4e4")
            tile.paste(im, ((440-im.width)//2, 20))
            ImageDraw.Draw(tile).text((12, 606), f"Page {index+1}", fill="black")
            thumbnails.append(tile)
        for start in range(0, len(thumbnails), 6):
            sheet = Image.new("RGB", (880, 1872), "#e4e4e4")
            for offset, tile in enumerate(thumbnails[start:start+6]):
                sheet.paste(tile, ((offset % 2)*440, (offset//2)*624))
            path = qa / f"contact-{start//6+1:02}.png"
            sheet.save(path)
            contact_sheets.append(str(path.relative_to(ROOT)))
    proof = {"schema": "eal-jss-manuscript-proof/2", "pdf_sha256": digest(ROOT / "manuscript.pdf"),
             "source_sha256": digest(ROOT / "manuscript.tex"), "pages": len(document),
             "figure_ids": included, "import_manifest_sha256": digest(ROOT / "review/article-import.json"),
             "checks": {"no_overfull_boxes": True, "no_undefined_references_or_citations": True,
                        "current_pilot_values_present": True, "obsolete_pilot_values_absent": True,
                        "every_text_word_within_page": True, "figure_inclusion_matches_import_manifest": True,
                        "figure_caption_numbering_complete_and_unique": True,
                        "live_followup_identity_and_qualifications_present": live_followup,
                        "retained_listing_present_on_one_page": True},
             "figure_placements": [{"id": name, "caption_number": index + 1,
                                     "caption_page": caption_pages[index + 1]}
                                    for index, name in enumerate(included)],
             "out_of_page_word_count": len(out_of_page), "listing_pages": listing_pages,
             "live_followup_size_checks": followup_size_checks,
             "visual_review": "accepted after inspection of current page renders" if args.accept_visual_review else "pending rendered inspection",
             "visual_review_scope": "Journal page layout and placement only; standalone semantic reviews retain their exact imported file bindings, and scientific coding validity remains conditional.",
             "rendered_page_count": len(document) if args.render else 0,
             "contact_sheet_count": len(contact_sheets),
             "underfull_hbox_count": log.count("Underfull \\hbox"),
             "underfull_review": "accepted after rendered inspection" if args.accept_visual_review else "pending rendered inspection",
             "review_assets": "Transient page renders and contact sheets are not publication assets and are not required by the paper checks."}
    (ROOT / "review/manuscript-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"pages": len(document), "figures": len(included), "checks": "passed", "visual_review": proof["visual_review"]}))


if __name__ == "__main__":
    main()
