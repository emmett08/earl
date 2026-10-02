#!/usr/bin/env python3
"""Rasterise the two canonical PDFs at their physical size using 96 dpi."""
from pathlib import Path
import fitz
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
for stem in ("01-primary-outcome-cells", "02-endpoint-separation"):
    output = ROOT / "qa" / stem
    output.mkdir(parents=True, exist_ok=True)
    colour = output / (stem + ".final-size-96dpi.png")
    with fitz.open(ROOT / (stem + ".pdf")) as document:
        document[0].get_pixmap(matrix=fitz.Matrix(96 / 72, 96 / 72)).save(colour)
    with Image.open(colour) as image:
        image.convert("L").save(output / (stem + ".final-size-96dpi-greyscale.png"))
