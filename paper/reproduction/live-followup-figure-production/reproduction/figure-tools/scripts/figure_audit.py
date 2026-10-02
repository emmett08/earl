#!/usr/bin/env python3
"""Measure a final PDF and create diagnostic previews, without judging its meaning.

Physical text/stroke sizes are reported in TeX points (72.27/in), whereas PDF
coordinates use big points (72/in). Bounding-box overlap and partial page-bound
violations are heuristics: font extents need not coincide with painted glyphs.
Straight path/text-bound intersections are warnings; curved paths still require
visual review. Neither bounds nor line segments establish glyph-ink intersection.

Colour previews apply the severity-1 matrices published by Machado, Oliveira
and Fernandes (2009) to linearised sRGB, then clamp to displayable sRGB. They are
approximate diagnostics, not individual perceptual simulations or accessibility
certification. Matrix source (authors' supplement):
https://www.inf.ufrgs.br/~oliveira/pubs_files/CVD_Simulation/CVD_Simulation.html
Linear-RGB implementation note (official colorspace documentation):
https://zeileis.codeberg.page/colorspace/reference/simulate_cvd.html
Paper: https://doi.org/10.1109/TVCG.2009.113
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

BP_TO_TEX_PT = 72.27 / 72.0
BP_TO_MM = 25.4 / 72.0
SIZE_TOLERANCE_PT = 0.005  # PDF numeric rounding, not a readability allowance.
BOUND_TOLERANCE_BP = 0.5
PATH_LABEL_INSET_BP = 0.5  # Inset font bounds to suppress incidental edge grazing.

COLOUR_VISION_MATRICES = {
    "protanopia": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deuteranopia": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
}


class AuditError(RuntimeError):
    """A diagnostic operation could not be completed."""


def _dependencies(*, previews: bool = False) -> tuple[Any, Any, Any]:
    try:
        import fitz
    except ImportError as exc:
        raise AuditError("PDF diagnostics require PyMuPDF (the fitz module)") from exc
    if not previews:
        return fitz, None, None
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise AuditError("Diagnostic previews require NumPy and Pillow") from exc
    return fitz, np, Image


def _normalise(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _number(target: dict[str, Any], key: str, default: float | None = None,
            *, zero: bool = False) -> float:
    value = target.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AuditError(f"Target {key} must be a finite number")
    value = float(value)
    if not math.isfinite(value) or value < 0 or (value == 0 and not zero):
        raise AuditError(f"Target {key} must be {'non-negative' if zero else 'positive'}")
    return value


def _issue(report: dict[str, Any], severity: str, code: str, message: str,
           **details: Any) -> None:
    report[severity].append({"code": code, "message": message, **details})


def _check(report: dict[str, Any], name: str, codes: tuple[str, ...],
           *, absent: bool = False) -> None:
    status = "not_measured" if absent else "pass"
    if any(item["code"] in codes for item in report["warnings"]):
        status = "warning"
    if any(item["code"] in codes for item in report["errors"]):
        status = "error"
    report["checks"].append({"name": name, "status": status})


def _contains_label(label: str, lines: list[str]) -> bool:
    # Word boundaries prevent an expected tick "1" from matching tick "10".
    label = _normalise(label)
    if not label:
        return False
    pattern = re.escape(label)
    if label[0].isalnum():
        pattern = r"(?<!\w)" + pattern
    if label[-1].isalnum():
        pattern += r"(?!\w)"
    return any(re.search(pattern, line) for line in lines)


def _straight_segments(item: Any) -> list[tuple[Any, Any]]:
    """Expand only actual line, rectangle and quadrilateral path edges."""
    if item[0] == "l":
        return [(item[1], item[2])]
    if item[0] == "re":
        rectangle = item[1]
        points = [rectangle.tl, rectangle.tr, rectangle.br, rectangle.bl, rectangle.tl]
    elif item[0] == "qu":
        quadrilateral = item[1]
        points = [quadrilateral.ul, quadrilateral.ur, quadrilateral.lr,
                  quadrilateral.ll, quadrilateral.ul]
    else:
        return []  # A curve's bounding rectangle never represents its path.
    return list(zip(points, points[1:]))


def _segment_crosses_interior(start: Any, end: Any, bbox: list[float]) -> bool:
    """Clip an actual straight segment to inset text bounds, excluding tangency.

    This tests centreline geometry only; dashes, clipping and painted glyphs can
    change visible contact. Curves are deliberately outside this heuristic.
    """
    x0, y0, x1, y1 = bbox
    inset = PATH_LABEL_INSET_BP
    if x1 - x0 <= 2 * inset or y1 - y0 <= 2 * inset or start == end:
        return False
    lower, upper = 0.0, 1.0
    for position, delta, minimum, maximum in (
        (start.x, end.x - start.x, x0 + inset, x1 - inset),
        (start.y, end.y - start.y, y0 + inset, y1 - inset),
    ):
        if delta == 0:
            if position <= minimum or position >= maximum:
                return False
            continue
        first, second = sorted(((minimum - position) / delta, (maximum - position) / delta))
        lower, upper = max(lower, first), min(upper, second)
        if upper <= lower:
            return False
    return upper > lower


def audit_pdf(pdf_path: str | Path, target: dict[str, Any],
              expected_labels: list[str] | None = None) -> dict[str, Any]:
    """Return JSON-serialisable mechanical findings for one final-size figure.

    Invalid PDF/target input produces a structured error report. Missing Python
    dependencies raise AuditError explicitly. Only extracted selectable text can
    be measured; no OCR or automatic semantic/readability verdict is supplied.
    """
    fitz, _, _ = _dependencies()
    report: dict[str, Any] = {
        "ok": False, "checks": [], "errors": [], "warnings": [],
        "measurements": {"pages": 0, "page_sizes": [], "text_spans": [],
                         "strokes": [], "rasters": []},
        "scope": ("Mechanical PDF measurements only. Potential overlap and clipping "
                  "are heuristic warnings. Meaning, reading accuracy and colour "
                  "accessibility require independent rendered review. Straight "
                  "path/text-bound crossings are heuristic; curved paths require "
                  "visual review."),
    }
    try:
        width = _number(target, "width_mm")
        tolerance = _number(target, "width_tolerance_mm", 0.5, zero=True)
        min_text = _number(target, "min_text_pt")
        min_script = _number(target, "min_math_script_pt", 6)
        min_stroke = _number(target, "min_stroke_pt", 0.35)
        min_raster = _number(target, "minimum_raster_dpi", 300)
        mode = target.get("width_mode", "maximum")
        if mode not in {"maximum", "exact"}:
            raise AuditError("Target width_mode must be maximum or exact")
        if min_text < 6 or min_script < 6 or min_stroke < 0.35:
            raise AuditError("Target floors are 6 pt text/scripts and 0.35 pt strokes")
        if target.get("colour_intent") not in {"greyscale", "colour_and_greyscale"}:
            raise AuditError("Target colour_intent must be greyscale or colour_and_greyscale")
        exceptions = target.get("font_exceptions", [])
        if not isinstance(exceptions, list):
            raise AuditError("Target font_exceptions must be a list")
        for exception in exceptions:
            if not isinstance(exception, dict):
                raise AuditError("Each font exception must be a record")
            exception_min = _number(exception, "min_text_pt")
            if (not isinstance(exception.get("text"), str) or not _normalise(exception["text"])
                    or not isinstance(exception.get("reason"), str) or not exception["reason"].strip()
                    or exception.get("role") != "mathematical_script"
                    or exception_min < min_script):
                raise AuditError("Font exceptions need exact text, reason, mathematical_script role "
                                 "and a minimum at least min_math_script_pt")
        labels = target.get("expected_labels", []) if expected_labels is None else expected_labels
        if not isinstance(labels, list) or any(not isinstance(label, str) or not _normalise(label)
                                               for label in labels):
            raise AuditError("expected_labels must be a list of non-empty strings")
    except (AuditError, TypeError, AttributeError) as exc:
        _issue(report, "errors", "invalid_target", str(exc))
        _check(report, "target", ("invalid_target",))
        return report

    try:
        document = fitz.open(str(pdf_path))
        if not document.is_pdf or document.needs_pass:
            document.close()
            raise AuditError("Input must be an accessible, unencrypted PDF")
    except Exception as exc:
        _issue(report, "errors", "unreadable_pdf", f"Could not inspect PDF: {exc}")
        _check(report, "pdf", ("unreadable_pdf",))
        return report

    with document:
        report["measurements"]["pages"] = len(document)
        if len(document) != 1:
            _issue(report, "errors", "page_count", f"Expected one figure page, found {len(document)}")
        all_lines: list[str] = []
        for page_number, page in enumerate(document, 1):
            bounds = page.rect
            text_bounds = bounds * page.derotation_matrix
            page_width = bounds.width * BP_TO_MM
            report["measurements"]["page_sizes"].append({
                "page": page_number, "width_mm": page_width,
                "height_mm": bounds.height * BP_TO_MM,
            })
            if page_width > width + tolerance or (mode == "exact" and page_width < width - tolerance):
                _issue(report, "errors", "width_mismatch",
                       f"Page width {page_width:.3f} mm does not meet {mode} target {width:g} mm",
                       page=page_number, measured_mm=page_width, target_mm=width,
                       tolerance_mm=tolerance)
            # Infinite clip retains labels outside the visible page rectangle.
            text = page.get_text("dict", clip=fitz.INFINITE_RECT())
            page_lines: list[dict[str, Any]] = []
            for block in text["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block["lines"]:
                    spans = [span for span in line["spans"] if span.get("text", "").strip()
                             and span.get("alpha", 255) > 0
                             and span.get("char_flags", 16) & 48]
                    if not spans:
                        continue
                    line_text = _normalise("".join(span["text"] for span in spans))
                    line_record = {"text": line_text, "bbox": list(line["bbox"])}
                    page_lines.append(line_record)
                    all_lines.append(line_text)
                    for span in spans:
                        size = span["size"] * BP_TO_TEX_PT
                        matching = [item for item in exceptions
                                    if _normalise(item["text"]) in {_normalise(span["text"]), line_text}]
                        # Apply the strictest match if selectors duplicate a text.
                        exception = max(matching, key=lambda item: item["min_text_pt"]) if matching else None
                        minimum = exception["min_text_pt"] if exception else min_text
                        record = {"page": page_number, "text": span["text"], "line_text": line_text,
                                  "font": span["font"], "size_pt": size, "bbox": list(span["bbox"]),
                                  "minimum_pt": minimum}
                        if exception:
                            record["exception"] = dict(exception)
                        report["measurements"]["text_spans"].append(record)
                        if size + SIZE_TOLERANCE_PT < minimum:
                            _issue(report, "errors", "undersized_text",
                                   f"Text {span['text']!r} is {size:.3f} TeX pt; required {minimum:g} pt",
                                   page=page_number, text=span["text"], size_pt=size,
                                   minimum_pt=minimum, bbox=record["bbox"])
                        box = fitz.Rect(span["bbox"])
                        padded = fitz.Rect(text_bounds.x0 - BOUND_TOLERANCE_BP,
                                           text_bounds.y0 - BOUND_TOLERANCE_BP,
                                           text_bounds.x1 + BOUND_TOLERANCE_BP,
                                           text_bounds.y1 + BOUND_TOLERANCE_BP)
                        if not padded.intersects(box):
                            _issue(report, "errors", "text_outside_page",
                                   f"Selectable text {span['text']!r} lies wholly outside the page",
                                   page=page_number, text=span["text"], bbox=record["bbox"])
                        elif not padded.contains(box):
                            _issue(report, "warnings", "text_clipping_risk",
                                   "Text font bounds extend beyond the page; inspect painted glyphs",
                                   page=page_number, text=span["text"], bbox=record["bbox"])
            for index, first in enumerate(page_lines):
                first_box = fitz.Rect(first["bbox"])
                for second in page_lines[index + 1:]:
                    second_box = fitz.Rect(second["bbox"])
                    overlap = first_box & second_box
                    area = min(first_box.get_area(), second_box.get_area())
                    # Small incidental font-extents intersections are suppressed.
                    if (not overlap.is_empty and overlap.width > 1 and overlap.height > 1
                            and area > 0 and overlap.get_area() / area > 0.10):
                        _issue(report, "warnings", "potential_label_overlap",
                               "Extracted line bounds overlap; equations or rotated labels may be legitimate",
                               page=page_number, texts=[first["text"], second["text"]],
                               bboxes=[first["bbox"], second["bbox"]])

            for drawing in page.get_drawings():
                if drawing.get("type") not in {"s", "fs"} or drawing.get("stroke_opacity", 1) <= 0:
                    continue
                stroke = float(drawing.get("width") or 0) * BP_TO_TEX_PT
                record = {"page": page_number, "width_pt": stroke,
                          "bbox": list(drawing["rect"])}
                report["measurements"]["strokes"].append(record)
                # Only actual straight drawing segments are tested. A curve's
                # bounding rectangle is not an approximation of its path.
                for item in drawing["items"]:
                    for start, end in _straight_segments(item):
                        for label in page_lines:
                            if _segment_crosses_interior(start, end, label["bbox"]):
                                _issue(report, "warnings", "potential_path_label_crossing",
                                       "Straight stroked segment intersects inset text-line bounds; "
                                       "inspect painted marks for visible contact",
                                       page=page_number, text=label["text"], bbox=label["bbox"],
                                       segment=[list(start), list(end)], inset_bp=PATH_LABEL_INSET_BP)
                if stroke + SIZE_TOLERANCE_PT < min_stroke:
                    _issue(report, "errors", "thin_stroke",
                           f"Stroke is {stroke:.3f} TeX pt; required {min_stroke:g} pt",
                           **record, minimum_pt=min_stroke)
            for image in page.get_image_info(xrefs=True):
                a, b, c, d, _, _ = image["transform"]
                display_x, display_y = math.hypot(a, b), math.hypot(c, d)
                if not display_x or not display_y:
                    _issue(report, "warnings", "raster_resolution_unknown",
                           "Raster placement has a degenerate transform", page=page_number)
                    continue
                dpi_x = image["width"] * 72 / display_x
                dpi_y = image["height"] * 72 / display_y
                record = {"page": page_number, "xref": image.get("xref", 0),
                          "pixels": [image["width"], image["height"]],
                          "dpi_x": dpi_x, "dpi_y": dpi_y, "bbox": list(image["bbox"])}
                report["measurements"]["rasters"].append(record)
                if min(dpi_x, dpi_y) < min_raster:
                    _issue(report, "warnings", "low_raster_resolution",
                           f"Raster effective resolution is {min(dpi_x, dpi_y):.1f} dpi; target {min_raster:g}",
                           **record, minimum_dpi=min_raster)
        for label in labels:
            if not _contains_label(label, all_lines):
                _issue(report, "errors", "missing_label",
                       f"Expected label {label!r} was not found in extracted text; check font encoding or rasterised text",
                       text=label)
        if labels and not all_lines:
            _issue(report, "warnings", "no_selectable_text", "No selectable labels could be measured")

    _check(report, "page_count", ("page_count",))
    _check(report, "final_width", ("width_mismatch",))
    _check(report, "text_size", ("undersized_text",), absent=not report["measurements"]["text_spans"])
    _check(report, "text_bounds", ("text_outside_page", "text_clipping_risk"))
    _check(report, "label_overlap", ("potential_label_overlap",))
    _check(report, "path_label_crossing", ("potential_path_label_crossing",))
    _check(report, "stroke_size", ("thin_stroke",), absent=not report["measurements"]["strokes"])
    _check(report, "raster_resolution", ("low_raster_resolution", "raster_resolution_unknown"),
           absent=not report["measurements"]["rasters"])
    _check(report, "expected_labels", ("missing_label", "no_selectable_text"), absent=not labels)
    for unmeasured in ("semantic_fidelity", "reading_accuracy", "colour_accessibility"):
        _check(report, unmeasured, (), absent=True)
    report["ok"] = not report["errors"]
    return report


def _srgb_to_linear(values: Any, np: Any) -> Any:
    return np.where(values <= 0.04045, values / 12.92,
                    ((values + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(values: Any, np: Any) -> Any:
    values = np.clip(values, 0, 1)
    return np.where(values <= 0.0031308, 12.92 * values,
                    1.055 * values ** (1 / 2.4) - 0.055)


def _save_image(image: Any, destination: Path, *, dpi: float) -> None:
    # Atomic replacement prevents reporting an old preview after a failed write.
    descriptor, temporary = tempfile.mkstemp(prefix=".preview-", suffix=".png", dir=destination.parent)
    os.close(descriptor)
    try:
        image.save(temporary, format="PNG", dpi=(dpi, dpi))
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def create_previews(pdf_path: str | Path, output_dir: str | Path,
                    dpi: float = 150) -> dict[str, Path]:
    """Render colour, greyscale, thumbnail and approximate dichromacy PNGs.

    PNG DPI preserves the PDF's physical size. The thumbnail is a 240-pixel
    overview; its lettering is not a final-size legibility test. RGB output is
    assumed sRGB, with a white background and no calibrated display/print model.
    """
    fitz, np, Image = _dependencies(previews=True)
    if isinstance(dpi, bool) or not isinstance(dpi, (int, float)) or not math.isfinite(dpi) or dpi <= 0:
        raise AuditError("Preview DPI must be a positive finite number")
    with fitz.open(str(pdf_path)) as document:
        if not document.is_pdf or document.needs_pass or len(document) != 1:
            raise AuditError("Previews require one accessible PDF page")
        pixmap = document[0].get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72),
                                      colorspace=fitz.csRGB, alpha=False)
        colour = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = Path(pdf_path).stem
    paths = {name: output_dir / f"{prefix}.preview-{name}.png"
             for name in ("colour", "greyscale", "thumbnail", "protanopia", "deuteranopia")}
    _save_image(colour, paths["colour"], dpi=dpi)
    linear = _srgb_to_linear(np.asarray(colour, dtype=float) / 255, np)
    luminance = linear @ np.array((0.2126, 0.7152, 0.0722))
    grey = np.rint(_linear_to_srgb(luminance, np) * 255).astype(np.uint8)
    _save_image(Image.fromarray(grey), paths["greyscale"], dpi=dpi)
    thumbnail = colour.copy()
    thumbnail.thumbnail((240, 240), Image.Resampling.LANCZOS)
    _save_image(thumbnail, paths["thumbnail"], dpi=dpi)
    for name, matrix in COLOUR_VISION_MATRICES.items():
        transformed = linear @ np.asarray(matrix).T
        rgb = np.rint(_linear_to_srgb(transformed, np) * 255).astype(np.uint8)
        _save_image(Image.fromarray(rgb), paths[name], dpi=dpi)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--target", type=Path, required=True, help="Target JSON or figure specification JSON")
    parser.add_argument("--report", type=Path, help="Write JSON report; otherwise print it")
    parser.add_argument("--previews", type=Path, help="Directory for diagnostic PNGs")
    parser.add_argument("--dpi", type=float, default=150)
    args = parser.parse_args()
    try:
        configuration = json.loads(args.target.read_text(encoding="utf-8"))
        target = configuration.get("target", configuration)
        report = audit_pdf(args.pdf, target)
        if args.previews and not any(item["code"] in {"unreadable_pdf", "page_count"} for item in report["errors"]):
            report["previews"] = {key: str(path) for key, path in create_previews(args.pdf, args.previews, args.dpi).items()}
        output = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
        return 0 if report["ok"] else 1
    except (AuditError, OSError, ValueError, TypeError, AttributeError) as exc:
        print(f"figure audit failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
