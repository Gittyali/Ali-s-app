"""PDF export.

Combines every page's rich text into a single ``QTextDocument`` (separated
by hard page breaks) and lets Qt's paged renderer lay it out onto A4 pages
via ``QPdfWriter``.  Because the same rich-text engine renders the editor
and the PDF, the export matches what the user sees.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import (
    QPageLayout,
    QPageSize,
    QPdfWriter,
    QTextBlockFormat,
    QTextCursor,
    QTextDocument,
)

logger = logging.getLogger(__name__)

_MARGIN_MM = 20.0


def _combine_pages(page_htmls: list[str]) -> QTextDocument:
    """Merge page HTML fragments into one document with page breaks."""
    combined = QTextDocument()
    cursor = QTextCursor(combined)
    for index, html in enumerate(page_htmls):
        if index > 0:
            break_format = QTextBlockFormat()
            break_format.setPageBreakPolicy(
                QTextBlockFormat.PageBreakFlag.PageBreak_AlwaysBefore
            )
            cursor.insertBlock(break_format)
        fragment_document = QTextDocument()
        fragment_document.setHtml(html)
        fragment_cursor = QTextCursor(fragment_document)
        fragment_cursor.select(QTextCursor.SelectionType.Document)
        cursor.insertFragment(fragment_cursor.selection())
    return combined


def export_pdf(page_htmls: list[str], output_path: Path) -> Path:
    """Write all pages to *output_path* as a paginated A4 PDF.

    Raises ``RuntimeError`` with a readable message on failure.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = QPdfWriter(str(output_path))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(
        QMarginsF(_MARGIN_MM, _MARGIN_MM, _MARGIN_MM, _MARGIN_MM),
        QPageLayout.Unit.Millimeter,
    )
    writer.setTitle(output_path.stem)

    document = _combine_pages(page_htmls)
    paint_rect = writer.pageLayout().paintRectPixels(writer.resolution())
    document.setPageSize(paint_rect.size().toSizeF())

    try:
        document.print_(writer)
    except Exception as exc:  # QPdfWriter reports odd error types
        raise RuntimeError(f"Could not create PDF file: {exc}") from exc

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(
            f"PDF export produced no output at '{output_path}'. Check that "
            "the folder is writable and the disk has space."
        )
    logger.info("Exported %d pages to %s", len(page_htmls), output_path)
    return output_path
