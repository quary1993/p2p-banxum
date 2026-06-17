#!/usr/bin/env python3
"""Merge chunk PDFs into the final manual and drop fully-blank pages.
Usage: uv run --with pypdf --with pymupdf python merge.py out.pdf part1.pdf part2.pdf ...
"""
import os
import sys

from pypdf import PdfReader, PdfWriter
import fitz  # PyMuPDF

out = sys.argv[1]
parts = sys.argv[2:]

writer = PdfWriter()
for p in parts:
    for page in PdfReader(p).pages:
        writer.add_page(page)
tmp = out + ".merged.tmp"
with open(tmp, "wb") as f:
    writer.write(f)

doc = fitz.open(tmp)


def visually_blank(page: fitz.Page) -> bool:
    """Treat whitespace-only Chrome print artifacts as blank pages.

    Chrome can emit empty pages with a handful of background/vector drawing
    instructions, so a structural "no drawings" check misses them. Render at a
    tiny scale and allow only a negligible number of non-paper pixels.
    """

    if page.get_text().strip() or page.get_images():
        return False
    pix = page.get_pixmap(matrix=fitz.Matrix(0.05, 0.05), alpha=False)
    data = pix.samples
    non_paper = 0
    pixels = pix.width * pix.height
    for i in range(0, len(data), pix.n):
        r, g, b = data[i], data[i + 1], data[i + 2]
        if r < 244 or g < 244 or b < 238:
            non_paper += 1
    return non_paper / max(pixels, 1) < 0.001


blanks = [i for i in range(doc.page_count) if visually_blank(doc[i])]
for i in reversed(blanks):
    doc.delete_page(i)
doc.save(out)
doc.close()
os.remove(tmp)
print(f"merged {len(parts)} parts -> {out}: {len(PdfReader(out).pages)} pages (removed {len(blanks)} blank)")
