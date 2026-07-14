"""Markdown to :class:`StructuredDocument` conversion.

AI vision providers are instructed to answer in a constrained Markdown
dialect (headings, paragraphs, ``-`` bullets, ``1.`` numbers, pipe tables,
``**bold**``/``*italic*``/``<u>underline</u>``, ``[^n]`` footnotes).  This
parser is intentionally tolerant: anything it does not recognise degrades to
a plain paragraph rather than being dropped.
"""

from __future__ import annotations

import logging
import re

from app.document.model import (
    Block,
    BlockType,
    InlineSpan,
    ListBlock,
    ParagraphBlock,
    StructuredDocument,
    TableBlock,
    TextAlignment,
)

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^\s*[-*+]\s+(.*)$")
_NUMBERED_RE = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")
_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")
_FOOTNOTE_RE = re.compile(r"^\[\^?\d+\][:.]?\s+(.*)$")
_CENTER_TAG_RE = re.compile(r"^<center>(.*)</center>$", re.IGNORECASE | re.DOTALL)

# Inline tokens: **bold**, __bold__, *italic*, _italic_, <u>underline</u>
_INLINE_TOKEN_RE = re.compile(
    r"(\*\*(?P<bold>.+?)\*\*"
    r"|__(?P<bold2>.+?)__"
    r"|\*(?P<italic>[^*]+)\*"
    r"|_(?P<italic2>[^_]+)_"
    r"|<u>(?P<underline>.+?)</u>)",
    re.DOTALL,
)


def parse_inline(text: str) -> list[InlineSpan]:
    """Split *text* into styled spans, resolving inline Markdown markers."""
    spans: list[InlineSpan] = []
    position = 0
    for match in _INLINE_TOKEN_RE.finditer(text):
        if match.start() > position:
            spans.append(InlineSpan(text=text[position : match.start()]))
        groups = match.groupdict()
        if groups["bold"] is not None or groups["bold2"] is not None:
            content = groups["bold"] if groups["bold"] is not None else groups["bold2"]
            spans.append(InlineSpan(text=content, bold=True))
        elif groups["italic"] is not None or groups["italic2"] is not None:
            content = (
                groups["italic"] if groups["italic"] is not None else groups["italic2"]
            )
            spans.append(InlineSpan(text=content, italic=True))
        elif groups["underline"] is not None:
            spans.append(InlineSpan(text=groups["underline"], underline=True))
        position = match.end()
    if position < len(text):
        spans.append(InlineSpan(text=text[position:]))
    return spans or [InlineSpan(text="")]


def _split_table_row(line: str) -> list[str]:
    inner = line.strip().strip("|")
    return [cell.strip() for cell in inner.split("|")]


def _looks_like_numbered_heading(remainder: str) -> bool:
    """True when a numbered line reads as a section heading.

    AI providers are inconsistent: the same document yields both
    ``## 13. POWERS OF AUDITOR:`` and a bare ``2. RELVANT PROVISION:``.
    Treating title-cased/uppercase/colon-terminated numbered lines as
    headings keeps every section bold and sized the same way.
    """
    stripped = remainder.strip()
    if not stripped or len(stripped) > 90 or len(stripped.split()) > 12:
        return False
    if stripped.endswith((".", ",", ";")):
        return False
    if stripped.endswith(":"):
        return True
    letters = [c for c in stripped if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if c.isupper()) / len(letters) >= 0.7


def parse_markdown(markdown: str) -> StructuredDocument:
    """Parse *markdown* into a structured document."""
    blocks: list[Block] = []
    lines = markdown.replace("\r\n", "\n").split("\n")
    index = 0
    total = len(lines)

    while index < total:
        raw_line = lines[index]
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        heading = _HEADING_RE.match(stripped)
        if heading:
            level = len(heading.group(1))
            block_type = BlockType.HEADING if level == 1 else BlockType.SUBHEADING
            blocks.append(
                ParagraphBlock(
                    block_type=block_type,
                    spans=parse_inline(heading.group(2).strip()),
                    level=level,
                )
            )
            index += 1
            continue

        if _BULLET_RE.match(stripped):
            items: list[list[InlineSpan]] = []
            while index < total:
                bullet = _BULLET_RE.match(lines[index].strip())
                if not bullet:
                    break
                items.append(parse_inline(bullet.group(1).strip()))
                index += 1
            blocks.append(ListBlock(block_type=BlockType.BULLET_LIST, items=items))
            continue

        first_numbered = _NUMBERED_RE.match(stripped)
        if first_numbered and _looks_like_numbered_heading(first_numbered.group(2)):
            # "17. REMOVAL OF AUDITOR:" is a section heading with its
            # number kept — not a list item silently renumbered from 1.
            blocks.append(
                ParagraphBlock(
                    block_type=BlockType.SUBHEADING,
                    spans=parse_inline(stripped),
                    level=2,
                )
            )
            index += 1
            continue
        if first_numbered:
            # Preserve the document's own numbering: a list starting at
            # "4." must not render as "1.".
            start = int(first_numbered.group(1))
            items = []
            while index < total:
                numbered = _NUMBERED_RE.match(lines[index].strip())
                if not numbered:
                    break
                items.append(parse_inline(numbered.group(2).strip()))
                index += 1
            blocks.append(
                ListBlock(
                    block_type=BlockType.NUMBERED_LIST, items=items, start=start
                )
            )
            continue

        if _TABLE_ROW_RE.match(stripped):
            rows: list[list[str]] = []
            while index < total and _TABLE_ROW_RE.match(lines[index].strip()):
                candidate = lines[index].strip()
                if not _TABLE_SEPARATOR_RE.match(candidate):
                    rows.append(_split_table_row(candidate))
                index += 1
            if rows:
                width = max(len(row) for row in rows)
                normalised = [row + [""] * (width - len(row)) for row in rows]
                blocks.append(
                    TableBlock(block_type=BlockType.TABLE, rows=normalised)
                )
            continue

        footnote = _FOOTNOTE_RE.match(stripped)
        if footnote:
            blocks.append(
                ParagraphBlock(
                    block_type=BlockType.FOOTNOTE,
                    spans=parse_inline(stripped),
                )
            )
            index += 1
            continue

        centered = _CENTER_TAG_RE.match(stripped)
        if centered:
            blocks.append(
                ParagraphBlock(
                    block_type=BlockType.PARAGRAPH,
                    alignment=TextAlignment.CENTER,
                    spans=parse_inline(centered.group(1).strip()),
                )
            )
            index += 1
            continue

        # Plain paragraph: merge soft-wrapped consecutive lines.
        paragraph_lines = [stripped]
        index += 1
        while index < total:
            follow = lines[index].strip()
            if (
                not follow
                or _HEADING_RE.match(follow)
                or _BULLET_RE.match(follow)
                or _NUMBERED_RE.match(follow)
                or _TABLE_ROW_RE.match(follow)
                or _FOOTNOTE_RE.match(follow)
            ):
                break
            paragraph_lines.append(follow)
            index += 1
        blocks.append(
            ParagraphBlock(
                block_type=BlockType.PARAGRAPH,
                spans=parse_inline(" ".join(paragraph_lines)),
            )
        )

    # Safety net: never silently drop a page. If nothing parsed but the
    # model returned text, keep it verbatim as a paragraph.
    if not blocks and markdown.strip():
        logger.warning("Markdown parse produced no blocks; keeping raw text")
        blocks.append(
            ParagraphBlock(
                block_type=BlockType.PARAGRAPH,
                spans=[InlineSpan(text=markdown.strip())],
            )
        )

    document = StructuredDocument(blocks=blocks)
    logger.debug("Parsed markdown into %d blocks", len(blocks))
    return document
