"""Heuristic layout reconstruction from OCR geometry.

Turns an :class:`~app.ocr.base.OCRResult` (positioned text lines) into a
:class:`~app.document.model.StructuredDocument` by reasoning about font
sizes, indentation, horizontal position and list markers.  This is the
fallback path when no AI vision provider is configured; with a provider the
richer AI reconstruction is used instead.
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

# A line is "large" (heading candidate) when its height exceeds the page
# median by this factor.
_HEADING_HEIGHT_RATIO = 1.25
_SUBHEADING_HEIGHT_RATIO = 1.12
# Vertical gap (in median line heights) that separates paragraphs.
_PARAGRAPH_GAP_RATIO = 1.6


@dataclass
class _Classified:
    """One OCR line with the semantic role assigned by the heuristics."""

    line: OCRLine
    role: BlockType
    alignment: TextAlignment
    list_text: str = ""
    gap_before: float = 0.0


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return float(ordered[len(ordered) // 2])


def _detect_alignment(line: OCRLine, image_width: int) -> TextAlignment:
    if image_width <= 0:
        return TextAlignment.LEFT
    left_margin = line.left
    right_margin = image_width - line.right
    line_width = max(1, line.right - line.left)
    # Narrow lines roughly centred on the page read as centered text.
    if (
        line_width < image_width * 0.7
        and abs(left_margin - right_margin) < image_width * 0.08
        and left_margin > image_width * 0.12
    ):
        return TextAlignment.CENTER
    if left_margin > image_width * 0.4 and right_margin < image_width * 0.1:
        return TextAlignment.RIGHT
    return TextAlignment.LEFT


def _looks_like_heading_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped or len(stripped) > 90:
        return False
    if stripped.endswith((".", ",", ";", ":")):
        return False
    words = stripped.split()
    if len(words) > 12:
        return False
    return True


def _classify_lines(result: OCRResult) -> list[_Classified]:
    median_height = _median([line.height for line in result.lines if line.height > 0])
    classified: list[_Classified] = []
    previous_bottom: int | None = None

    for line in result.lines:
        text = line.text.strip()
        if not text:
            continue
        gap = 0.0
        if previous_bottom is not None and median_height > 0:
            gap = max(0.0, (line.top - previous_bottom) / median_height)
        previous_bottom = max(previous_bottom or 0, line.bottom)

        alignment = _detect_alignment(line, result.image_width)

        bullet = _BULLET_MARKER_RE.match(text)
        numbered = _NUMBERED_MARKER_RE.match(text)
        is_bottom_zone = (
            result.image_height > 0 and line.top > result.image_height * 0.88
        )
        size_ratio = (line.height / median_height) if median_height else 1.0

        if bullet:
            role, list_text = BlockType.BULLET_LIST, bullet.group(1).strip()
        elif numbered and len(numbered.group(2).split()) <= 30:
            role, list_text = BlockType.NUMBERED_LIST, numbered.group(2).strip()
        elif size_ratio >= _HEADING_HEIGHT_RATIO and _looks_like_heading_text(text):
            role, list_text = BlockType.HEADING, ""
        elif size_ratio >= _SUBHEADING_HEIGHT_RATIO and _looks_like_heading_text(text):
            role, list_text = BlockType.SUBHEADING, ""
        elif is_bottom_zone and line.height < median_height * 0.9 and _FOOTNOTE_RE.match(text):
            role, list_text = BlockType.FOOTNOTE, ""
        else:
            role, list_text = BlockType.PARAGRAPH, ""

        classified.append(
            _Classified(
                line=line,
                role=role,
                alignment=alignment,
                list_text=list_text,
                gap_before=gap,
            )
        )
    return classified


def reconstruct_document(result: OCRResult) -> StructuredDocument:
    """Build a structured document from an OCR result."""
    classified = _classify_lines(result)
    blocks: list[Block] = []

    paragraph_lines: list[str] = []
    paragraph_alignment = TextAlignment.LEFT
    list_items: list[list[InlineSpan]] = []
    list_type: BlockType | None = None

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
        nonlocal list_items, list_type
        if list_items and list_type is not None:
            blocks.append(ListBlock(block_type=list_type, items=list_items))
            list_items = []
            list_type = None

    for item in classified:
        text = item.line.text.strip()

        if item.role in (BlockType.BULLET_LIST, BlockType.NUMBERED_LIST):
            flush_paragraph()
            if list_type is not None and list_type != item.role:
                flush_list()
            list_type = item.role
            list_items.append([InlineSpan(text=item.list_text)])
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
            continue

        # Plain text: start a new paragraph on a large vertical gap or an
        # alignment change, otherwise continue the current one.
        flush_list()
        if paragraph_lines and (
            item.gap_before > _PARAGRAPH_GAP_RATIO
            or item.alignment != paragraph_alignment
        ):
            flush_paragraph()
        if not paragraph_lines:
            paragraph_alignment = item.alignment
        paragraph_lines.append(text)

    flush_paragraph()
    flush_list()
    logger.info(
        "Layout analysis: %d OCR lines -> %d blocks", len(classified), len(blocks)
    )
    return StructuredDocument(blocks=blocks)
