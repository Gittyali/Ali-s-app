"""Heuristic layout reconstruction from OCR geometry.

Turns an :class:`~app.ocr.base.OCRResult` (positioned text lines) into a
:class:`~app.document.model.StructuredDocument` by reasoning about font
sizes, indentation, horizontal position and list markers.  This is the
fallback path when no AI vision provider is configured; with a provider the
richer AI reconstruction is used instead.

Design notes for the paragraph assembly:

* Scanned paragraphs are usually justified: every line except the last runs
  to the right margin, the first line is often indented, and the last line
  is short.  Naive per-line alignment guessing therefore misreads first
  lines as right-aligned and last lines as centered, shattering the
  paragraph.  The assembler treats a line as a *continuation* whenever the
  previous line fills the width or the left edges agree, and only honours
  an alignment change when the line genuinely starts a new block.
* Numbered headings ("4. MEANING OF MAXIM:") must remain headings with
  their original number — never list items renumbered from 1.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.document.model import (
    Block,
    BlockType,
    InlineSpan,
    ListBlock,
    ParagraphBlock,
    StructuredDocument,
    TextAlignment,
)
from app.ocr.base import OCRLine, OCRResult

logger = logging.getLogger(__name__)

_BULLET_MARKER_RE = re.compile(r"^\s*[•▪◦‣●○*·—-]\s+(.+)$")
_NUMBERED_MARKER_RE = re.compile(r"^\s*(\d{1,3})[.)]\s+(.+)$")
_FOOTNOTE_RE = re.compile(r"^\s*(\*|\d{1,2}[.)]?)\s+\S")

# Lines below this mean confidence are treated as noise (watermarks, stamps,
# scanner artifacts, bleed-through) and excluded from the document.
_MIN_LINE_CONFIDENCE = 0.35

# A line is "large" (heading candidate) when its height exceeds the page
# median by this factor.
_HEADING_HEIGHT_RATIO = 1.25
_SUBHEADING_HEIGHT_RATIO = 1.12
# Vertical gap (in median line heights) that separates paragraphs.
_PARAGRAPH_GAP_RATIO = 1.6
# A line whose right edge reaches this fraction of the text region "fills"
# the width — its successor is a wrapped continuation of the same paragraph.
# Only meaningful when the text region itself spans most of the page;
# otherwise (e.g. a page of short centered lines) every line would
# trivially "fill" its own extent.
_FILL_RIGHT_RATIO = 0.92
_MIN_TEXT_REGION_RATIO = 0.75
# Left edges within this fraction of the page width count as "aligned".
_LEFT_EDGE_TOLERANCE_RATIO = 0.04


@dataclass
class _Classified:
    """One OCR line with the semantic role assigned by the heuristics."""

    line: OCRLine
    role: BlockType
    alignment: TextAlignment
    list_text: str = ""
    list_number: int = 0
    gap_before: float = 0.0
    fills_width: bool = False


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return float(ordered[len(ordered) // 2])


def _detect_alignment(line: OCRLine, image_width: int, right_extent: int) -> TextAlignment:
    """Best-effort alignment guess for a single line.

    Lines that run to the right edge of the text region are body text
    (LEFT), regardless of indentation — indented first lines of justified
    paragraphs must not read as right-aligned.
    """
    if image_width <= 0:
        return TextAlignment.LEFT
    left_margin = line.left
    right_margin = image_width - line.right
    line_width = max(1, line.right - line.left)

    wide_region = right_extent >= image_width * _MIN_TEXT_REGION_RATIO
    if wide_region and line.right >= right_extent * _FILL_RIGHT_RATIO:
        return TextAlignment.LEFT
    if (
        line_width < image_width * 0.6
        and abs(left_margin - right_margin) < image_width * 0.06
        and left_margin > image_width * 0.14
    ):
        return TextAlignment.CENTER
    if (
        line_width < image_width * 0.5
        and left_margin > image_width * 0.45
        and right_margin < image_width * 0.08
    ):
        return TextAlignment.RIGHT
    return TextAlignment.LEFT


def _looks_like_heading_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped or len(stripped) > 90:
        return False
    # Headings frequently end with a colon ("MEANING OF MAXIM:"); only
    # sentence punctuation rules a heading out.
    if stripped.endswith((".", ",", ";")):
        return False
    words = stripped.split()
    if len(words) > 12:
        return False
    return True


def _uppercase_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if c.isupper()) / len(letters)


def _classify_lines(result: OCRResult, filter_noise: bool) -> list[_Classified]:
    median_height = _median([line.height for line in result.lines if line.height > 0])
    right_extent = max((line.right for line in result.lines), default=0)
    classified: list[_Classified] = []
    previous_bottom: int | None = None

    for line in result.lines:
        text = line.text.strip()
        if not text:
            continue
        if filter_noise and line.confidence < _MIN_LINE_CONFIDENCE:
            # Watermarks, stamps and bleed-through recognise as garbled,
            # low-confidence lines; dropping them keeps the document clean.
            logger.debug("Dropping low-confidence line: %r", text[:50])
            continue
        gap = 0.0
        if previous_bottom is not None and median_height > 0:
            gap = max(0.0, (line.top - previous_bottom) / median_height)
        previous_bottom = max(previous_bottom or 0, line.bottom)

        alignment = _detect_alignment(line, result.image_width, right_extent)
        fills = (
            right_extent >= result.image_width * _MIN_TEXT_REGION_RATIO
            and line.right >= right_extent * _FILL_RIGHT_RATIO
        )

        bullet = _BULLET_MARKER_RE.match(text)
        numbered = _NUMBERED_MARKER_RE.match(text)
        is_bottom_zone = (
            result.image_height > 0 and line.top > result.image_height * 0.88
        )
        size_ratio = (line.height / median_height) if median_height else 1.0

        # A numbered line that reads like a title ("4. MEANING OF MAXIM:")
        # is a heading — with its number kept — not a list item.
        numbered_heading = bool(
            numbered
            and _looks_like_heading_text(text)
            and (
                size_ratio >= _SUBHEADING_HEIGHT_RATIO
                or _uppercase_ratio(numbered.group(2)) >= 0.7
                or numbered.group(2).rstrip().endswith(":")
            )
        )

        if numbered_heading:
            role = (
                BlockType.HEADING
                if size_ratio >= _HEADING_HEIGHT_RATIO
                else BlockType.SUBHEADING
            )
            classified.append(
                _Classified(
                    line=line,
                    role=role,
                    alignment=alignment,
                    gap_before=gap,
                    fills_width=fills,
                )
            )
            continue

        if bullet:
            role, list_text, list_number = (
                BlockType.BULLET_LIST,
                bullet.group(1).strip(),
                0,
            )
        elif numbered and len(numbered.group(2).split()) <= 30:
            role, list_text, list_number = (
                BlockType.NUMBERED_LIST,
                numbered.group(2).strip(),
                int(numbered.group(1)),
            )
        elif size_ratio >= _HEADING_HEIGHT_RATIO and _looks_like_heading_text(text):
            role, list_text, list_number = BlockType.HEADING, "", 0
        elif size_ratio >= _SUBHEADING_HEIGHT_RATIO and _looks_like_heading_text(text):
            role, list_text, list_number = BlockType.SUBHEADING, "", 0
        elif (
            is_bottom_zone
            and line.height < median_height * 0.9
            and _FOOTNOTE_RE.match(text)
        ):
            role, list_text, list_number = BlockType.FOOTNOTE, "", 0
        else:
            role, list_text, list_number = BlockType.PARAGRAPH, "", 0

        classified.append(
            _Classified(
                line=line,
                role=role,
                alignment=alignment,
                list_text=list_text,
                list_number=list_number,
                gap_before=gap,
                fills_width=fills,
            )
        )
    return classified


def reconstruct_document(
    result: OCRResult, filter_noise: bool = True
) -> StructuredDocument:
    """Build a structured document from an OCR result.

    *filter_noise* drops low-confidence lines (watermarks, stamps,
    bleed-through); it maps to Settings > Reading > Ignore watermarks.
    """
    classified = _classify_lines(result, filter_noise)
    image_width = max(1, result.image_width)
    blocks: list[Block] = []

    paragraph_lines: list[str] = []
    paragraph_alignment = TextAlignment.LEFT
    paragraph_left = 0
    previous_fills = False
    list_items: list[list[InlineSpan]] = []
    list_type: BlockType | None = None
    list_start = 1

    def flush_paragraph() -> None:
        nonlocal paragraph_lines, paragraph_alignment
        if paragraph_lines:
            blocks.append(
                ParagraphBlock(
                    block_type=BlockType.PARAGRAPH,
                    alignment=paragraph_alignment,
                    spans=[InlineSpan(text=" ".join(paragraph_lines))],
                )
            )
            paragraph_lines = []
            paragraph_alignment = TextAlignment.LEFT

    def flush_list() -> None:
        nonlocal list_items, list_type, list_start
        if list_items and list_type is not None:
            blocks.append(
                ListBlock(block_type=list_type, items=list_items, start=list_start)
            )
            list_items = []
            list_type = None
            list_start = 1

    for item in classified:
        text = item.line.text.strip()

        if item.role in (BlockType.BULLET_LIST, BlockType.NUMBERED_LIST):
            flush_paragraph()
            if list_type is not None and list_type != item.role:
                flush_list()
            if not list_items and item.role is BlockType.NUMBERED_LIST:
                list_start = item.list_number or 1
            list_type = item.role
            list_items.append([InlineSpan(text=item.list_text)])
            previous_fills = item.fills_width
            continue

        if item.role in (BlockType.HEADING, BlockType.SUBHEADING):
            flush_paragraph()
            flush_list()
            blocks.append(
                ParagraphBlock(
                    block_type=item.role,
                    alignment=item.alignment,
                    spans=[InlineSpan(text=text, bold=True)],
                    level=1 if item.role is BlockType.HEADING else 2,
                )
            )
            previous_fills = item.fills_width
            continue

        if item.role is BlockType.FOOTNOTE:
            flush_paragraph()
            flush_list()
            blocks.append(
                ParagraphBlock(
                    block_type=BlockType.FOOTNOTE,
                    alignment=TextAlignment.LEFT,
                    spans=[InlineSpan(text=text)],
                )
            )
            previous_fills = item.fills_width
            continue

        # Plain text. A line continues the open paragraph when the previous
        # line filled the width (wrapped text) or the left edges agree —
        # only a real block boundary (big gap, or an alignment change on a
        # non-continuation line) starts a new paragraph.
        flush_list()
        is_continuation = bool(paragraph_lines) and (
            previous_fills
            or abs(item.line.left - paragraph_left)
            <= image_width * _LEFT_EDGE_TOLERANCE_RATIO
        )
        if paragraph_lines and (
            item.gap_before > _PARAGRAPH_GAP_RATIO
            or (item.alignment != paragraph_alignment and not is_continuation)
        ):
            flush_paragraph()
        if not paragraph_lines:
            paragraph_alignment = item.alignment
            paragraph_left = item.line.left
        paragraph_lines.append(text)
        previous_fills = item.fills_width

    flush_paragraph()
    flush_list()
    logger.info(
        "Layout analysis: %d OCR lines -> %d blocks", len(classified), len(blocks)
    )
    return StructuredDocument(blocks=blocks)
