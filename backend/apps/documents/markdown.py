"""Small Markdown reader for template bodies printed in document PDFs.

It reads the subset the web legal page shows: headings, paragraphs, bullet and numbered
lists, pipe tables, block quotes and rules, with bold and italic text inside them. Links and
images print as text. Nothing is interpreted as HTML: raw tags stay visible text, the same
as on the web page, which renders template text as plain text nodes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

ESCAPABLE_CHARACTERS = frozenset("\\`*_{}[]()#+-.!|>~")
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
RULE_RE = re.compile(r"^\s{0,3}([-*_])(?:\s*\1){2,}\s*$")
BULLET_RE = re.compile(r"^(\s*)[-*+]\s+(.*)$")
ORDERED_RE = re.compile(r"^(\s*)(\d{1,3})[.)]\s+(.*)$")
QUOTE_RE = re.compile(r"^\s{0,3}>\s?(.*)$")
TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-{2,}:?$")
LINK_RE = re.compile(r"!?\[([^\]\n]*)\]\(\s*<?([^)\s>]*)>?(?:\s+\"[^\"]*\")?\s*\)")
AUTOLINK_RE = re.compile(r"<((?:https?|mailto):[^>\s]+)>")


@dataclass(frozen=True, slots=True)
class InlineRun:
    text: str
    bold: bool = False
    italic: bool = False


@dataclass(frozen=True, slots=True)
class ListItem:
    marker: str
    depth: int
    runs: tuple[InlineRun, ...]


@dataclass(frozen=True, slots=True)
class MarkdownBlock:
    kind: str  # heading, paragraph, bullet_list, ordered_list, table, quote, rule
    level: int = 0
    runs: tuple[InlineRun, ...] = ()
    items: tuple[ListItem, ...] = ()
    rows: tuple[tuple[str, ...], ...] = field(default_factory=tuple)


def _delimiter_run_length(text: str, index: int) -> int:
    character = text[index]
    length = 1
    while index + length < len(text) and text[index + length] == character:
        length += 1
    return length


def _find_closing_delimiter(text: str, start: int, character: str, length: int) -> int:
    index = start
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == "`":
            closing = text.find("`", index + 1)
            index = closing + 1 if closing > index else index + 1
            continue
        if text[index] != character:
            index += 1
            continue
        run = _delimiter_run_length(text, index)
        after = text[index + run] if index + run < len(text) else ""
        before = text[index - 1] if index > 0 else ""
        closes = run == length and before and not before.isspace()
        if closes and character == "_" and after.isalnum():
            closes = False
        if closes:
            return index
        index += run
    return -1


def inline_runs(text: str, *, bold: bool = False, italic: bool = False) -> list[InlineRun]:
    """Split Markdown inline text into runs of plain, bold and italic text."""
    runs: list[InlineRun] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            runs.append(InlineRun("".join(buffer), bold=bold, italic=italic))
            buffer.clear()

    index = 0
    while index < len(text):
        character = text[index]
        if character == "\\" and index + 1 < len(text) and text[index + 1] in ESCAPABLE_CHARACTERS:
            buffer.append(text[index + 1])
            index += 2
            continue
        if character == "`":
            closing = text.find("`", index + 1)
            if closing > index + 1:
                buffer.append(text[index + 1 : closing])
                index = closing + 1
                continue
        if character in "[!":
            match = LINK_RE.match(text, index)
            if match is not None:
                label, target = match.group(1).strip(), match.group(2).strip()
                is_image = character == "!"
                flush()
                if label:
                    runs.extend(inline_runs(label, bold=bold, italic=italic))
                if target and not is_image and target != label:
                    runs.append(InlineRun(f" ({target})" if label else target, bold, italic))
                index = match.end()
                continue
        if character == "<":
            match = AUTOLINK_RE.match(text, index)
            if match is not None:
                buffer.append(match.group(1))
                index = match.end()
                continue
        if character in "*_":
            length = _delimiter_run_length(text, index)
            before = text[index - 1] if index > 0 else ""
            after = text[index + length] if index + length < len(text) else ""
            can_open = bool(after) and not after.isspace() and length <= 3
            if can_open and character == "_" and before.isalnum():
                can_open = False
            if can_open:
                closing = _find_closing_delimiter(text, index + length, character, length)
                if closing > index + length:
                    flush()
                    runs.extend(
                        inline_runs(
                            text[index + length : closing],
                            bold=bold or length >= 2,
                            italic=italic or length in {1, 3},
                        )
                    )
                    index = closing + length
                    continue
            buffer.append(character * length)
            index += length
            continue
        buffer.append(character)
        index += 1
    flush()
    merged: list[InlineRun] = []
    for run in runs:
        if merged and merged[-1].bold == run.bold and merged[-1].italic == run.italic:
            merged[-1] = InlineRun(merged[-1].text + run.text, run.bold, run.italic)
        elif run.text:
            merged.append(run)
    return merged


def plain_text(text: str) -> str:
    """Inline Markdown as plain text (markers removed, links as text)."""
    return " ".join("".join(run.text for run in inline_runs(text)).split())


def _table_cells(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    return [plain_text(cell.strip()) for cell in re.split(r"(?<!\\)\|", stripped)]


def _paragraph_runs(lines: list[str]) -> tuple[InlineRun, ...]:
    return tuple(inline_runs(" ".join(line.strip() for line in lines)))


def parse_markdown_blocks(text: str) -> list[MarkdownBlock]:
    """Read one blank-line separated block (or a whole body) into printable blocks."""
    blocks: list[MarkdownBlock] = []
    lines = [line.rstrip() for line in text.splitlines()]
    paragraph: list[str] = []
    list_kind = ""
    list_items: list[tuple[str, int, list[str]]] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(MarkdownBlock(kind="paragraph", runs=_paragraph_runs(paragraph)))
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_kind
        if list_items:
            blocks.append(
                MarkdownBlock(
                    kind=list_kind,
                    items=tuple(
                        ListItem(marker=marker, depth=depth, runs=_paragraph_runs(item_lines))
                        for marker, depth, item_lines in list_items
                    ),
                )
            )
            list_items.clear()
        list_kind = ""

    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            flush_paragraph()
            flush_list()
            index += 1
            continue
        heading = HEADING_RE.match(line)
        if heading is not None:
            flush_paragraph()
            flush_list()
            blocks.append(
                MarkdownBlock(
                    kind="heading",
                    level=len(heading.group(1)),
                    runs=tuple(inline_runs(heading.group(2))),
                )
            )
            index += 1
            continue
        if RULE_RE.match(line) and not paragraph:
            flush_list()
            blocks.append(MarkdownBlock(kind="rule"))
            index += 1
            continue
        if line.lstrip().startswith("|"):
            table_lines: list[str] = []
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                table_lines.append(lines[index])
                index += 1
            if len(table_lines) >= 2:
                flush_paragraph()
                flush_list()
                rows = [_table_cells(table_line) for table_line in table_lines]
                rows = [
                    row
                    for row in rows
                    if not all(TABLE_SEPARATOR_CELL_RE.match(cell.replace(" ", "")) for cell in row)
                ]
                width = max(len(row) for row in rows) if rows else 0
                blocks.append(
                    MarkdownBlock(
                        kind="table",
                        rows=tuple(tuple(row + [""] * (width - len(row))) for row in rows),
                    )
                )
            else:
                flush_list()
                paragraph.extend(table_lines)
            continue
        bullet = BULLET_RE.match(line)
        ordered = ORDERED_RE.match(line) if bullet is None else None
        if bullet is not None or ordered is not None:
            flush_paragraph()
            if bullet is not None:
                kind, indent, marker, content = "bullet_list", bullet.group(1), "", bullet.group(2)
            else:
                assert ordered is not None
                kind = "ordered_list"
                indent, marker, content = ordered.group(1), f"{ordered.group(2)}.", ordered.group(3)
            if list_items and kind != list_kind and not indent:
                flush_list()
            if not list_kind:
                list_kind = kind
            depth = min(2, len(indent.replace("\t", "    ")) // 2)
            list_items.append((marker, depth, [content]))
            index += 1
            continue
        if list_items and (line.startswith("  ") or line.startswith("\t")):
            list_items[-1][2].append(line.strip())
            index += 1
            continue
        quote = QUOTE_RE.match(line)
        if quote is not None:
            flush_paragraph()
            flush_list()
            quote_lines: list[str] = []
            while index < len(lines):
                quoted = QUOTE_RE.match(lines[index])
                if quoted is None:
                    break
                quote_lines.append(quoted.group(1))
                index += 1
            blocks.append(MarkdownBlock(kind="quote", runs=_paragraph_runs(quote_lines)))
            continue
        flush_list()
        paragraph.append(line)
        index += 1
    flush_paragraph()
    flush_list()
    return blocks
