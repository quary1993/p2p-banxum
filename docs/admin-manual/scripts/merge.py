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
blanks = [
    i for i in range(doc.page_count)
    if not doc[i].get_text().strip() and len(doc[i].get_images()) == 0 and len(doc[i].get_drawings()) <= 1
]
for i in reversed(blanks):
    doc.delete_page(i)
doc.save(out)
doc.close()
os.remove(tmp)
print(f"merged {len(parts)} parts -> {out}: {len(PdfReader(out).pages)} pages (removed {len(blanks)} blank)")
