"""Text helpers for the built-in PDF writers (standard Helvetica fonts, WinAnsi encoding)."""

from __future__ import annotations

# Advance widths (1/1000 em) of the standard Helvetica fonts for the printable ASCII range
# 32..126, from the Adobe core font metrics. Other characters use the average width.
_HELVETICA_WIDTHS = (
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
)  # fmt: skip
_HELVETICA_BOLD_WIDTHS = (
    278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611,
    975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556,
    333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611,
    611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584,
)  # fmt: skip
_DEFAULT_WIDTH = 556

# Font resource dictionaries for the standard fonts. WinAnsiEncoding makes accented Latin
# letters (for example "ü" in "Zürich") and typographic quotes print as the same characters.
PDF_STANDARD_FONT_OBJECTS = {
    "F1": b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    "F2": (
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    ),
    "F3": b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>",
    "F4": (
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>"
    ),
    "F5": (
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-BoldOblique "
        b"/Encoding /WinAnsiEncoding >>"
    ),
}
BOLD_FONTS = frozenset({"F2", "F5"})


def pdf_text_width(text: str, *, size: float, font: str = "F1") -> float:
    """Printed width of ``text`` in points for a standard Helvetica font."""
    table = _HELVETICA_BOLD_WIDTHS if font in BOLD_FONTS else _HELVETICA_WIDTHS
    units = 0
    for character in text:
        code = ord(character)
        units += table[code - 32] if 32 <= code <= 126 else _DEFAULT_WIDTH
    return units * size / 1000.0


def pdf_literal(text: str) -> str:
    """Escape ``text`` for a PDF string literal in a WinAnsi-encoded content stream.

    The result holds only characters 0-255, so the content stream can be written with
    ``latin-1``. Characters outside WinAnsi print as "?". Control characters become spaces.
    """
    cleaned = "".join(" " if ord(character) < 32 else character for character in text)
    win_ansi = cleaned.encode("cp1252", errors="replace").decode("latin-1")
    return win_ansi.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
