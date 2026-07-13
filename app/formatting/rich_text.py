"""Render a :class:`StructuredDocument` into a ``QTextDocument``.

The editor's native representation is Qt rich text; this module is the only
place that translates the neutral document model into it, so the mapping
(heading sizes, list styles, table styling) stays consistent everywhere.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QFont,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextListFormat,
    QTextTableFormat,
)

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

BODY_POINT_SIZE = 11.0
HEADING_POINT_SIZES = {1: 18.0, 2: 15.0, 3: 13.0, 4: 12.0, 5: 11.5, 6: 11.0}
FOOTNOTE_POINT_SIZE = 9.0

_ALIGNMENT_MAP = {
    TextAlignment.LEFT: Qt.AlignmentFlag.AlignLeft,
    TextAlignment.CENTER: Qt.AlignmentFlag.AlignCenter,
    TextAlignment.RIGHT: Qt.AlignmentFlag.AlignRight,
    TextAlignment.JUSTIFY: Qt.AlignmentFlag.AlignJustify,
}


def _char_format(
    span: InlineSpan, point_size: float, base_bold: bool = False
) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setFontPointSize(point_size)
    fmt.setFontWeight(
        QFont.Weight.Bold if (span.bold or base_bold) else QFont.Weight.Normal
    )
    fmt.setFontItalic(span.italic)
    fmt.setFontUnderline(span.underline)
    return fmt


def _block_format(alignment: TextAlignment, heading_level: int = 0) -> QTextBlockFormat:
    fmt = QTextBlockFormat()
    fmt.setAlignment(_ALIGNMENT_MAP[alignment])
    fmt.setBottomMargin(6.0)
    if heading_level:
        fmt.setHeadingLevel(heading_level)
        fmt.setTopMargin(10.0)
    return fmt


def _insert_spans(
    cursor: QTextCursor, spans: list[InlineSpan], point_size: float, bold: bool = False
) -> None:
    for span in spans:
        cursor.insertText(span.text, _char_format(span, point_size, base_bold=bold))


def _insert_paragraph(cursor: QTextCursor, block: ParagraphBlock) -> None:
    if block.block_type in (BlockType.HEADING, BlockType.SUBHEADING):
        level = block.level if 1 <= block.level <= 6 else (
            1 if block.block_type is BlockType.HEADING else 2
        )
        cursor.insertBlock(_block_format(block.alignment, heading_level=level))
        _insert_spans(cursor, block.spans, HEADING_POINT_SIZES[level], bold=True)
    elif block.block_type is BlockType.FOOTNOTE:
        cursor.insertBlock(_block_format(block.alignment))
        _insert_spans(cursor, block.spans, FOOTNOTE_POINT_SIZE)
    else:
        cursor.insertBlock(_block_format(block.alignment))
        _insert_spans(cursor, block.spans, BODY_POINT_SIZE)


def _insert_list(cursor: QTextCursor, block: ListBlock) -> None:
    list_format = QTextListFormat()
    list_format.setStyle(
        QTextListFormat.Style.ListDisc
        if block.block_type is BlockType.BULLET_LIST
        else QTextListFormat.Style.ListDecimal
    )
    list_format.setIndent(1)

    cursor.insertBlock(_block_format(block.alignment))
    text_list = cursor.insertList(list_format)
    for index, item in enumerate(block.items):
        if index > 0:
            cursor.insertBlock()
            text_list.add(cursor.block())
        _insert_spans(cursor, item, BODY_POINT_SIZE)
    # Leave the list scope so following blocks are not swallowed into it.
    exit_format = QTextBlockFormat()
    exit_format.setObjectIndex(-1)
    cursor.insertBlock(exit_format)
    cursor.setBlockFormat(_block_format(TextAlignment.LEFT))


def _insert_table(cursor: QTextCursor, block: TableBlock) -> None:
    if not block.rows or block.column_count == 0:
        return
    table_format = QTextTableFormat()
    table_format.setCellPadding(4.0)
    table_format.setCellSpacing(0.0)
    table_format.setBorder(0.5)
    table_format.setBorderCollapse(True)
    if block.header_row:
        table_format.setHeaderRowCount(1)

    cursor.insertBlock(_block_format(TextAlignment.LEFT))
    table = cursor.insertTable(len(block.rows), block.column_count, table_format)
    for row_index, row in enumerate(block.rows):
        for col_index in range(block.column_count):
            cell = table.cellAt(row_index, col_index)
            cell_cursor = cell.firstCursorPosition()
            text = row[col_index] if col_index < len(row) else ""
            is_header = block.header_row and row_index == 0
            spans = [InlineSpan(text=text, bold=is_header)]
            _insert_spans(cell_cursor, spans, BODY_POINT_SIZE)
    # Move the working cursor past the table.
    cursor.setPosition(table.lastCursorPosition().position())
    cursor.movePosition(QTextCursor.MoveOperation.NextBlock)


def insert_structured_document(
    cursor: QTextCursor, document: StructuredDocument
) -> None:
    """Insert *document* at *cursor* as one undoable edit."""
    cursor.beginEditBlock()
    try:
        for block in document.blocks:
            _insert_block(cursor, block)
    finally:
        cursor.endEditBlock()
    logger.debug("Inserted %d blocks into editor", len(document.blocks))


def _insert_block(cursor: QTextCursor, block: Block) -> None:
    if isinstance(block, ParagraphBlock):
        _insert_paragraph(cursor, block)
    elif isinstance(block, ListBlock):
        _insert_list(cursor, block)
    elif isinstance(block, TableBlock):
        _insert_table(cursor, block)
    else:  # Defensive: unknown block types must never crash the editor.
        logger.warning("Skipping unknown block type: %r", block)


def append_structured_document(
    target: QTextDocument,
    document: StructuredDocument,
    separator_text: str = "",
) -> None:
    """Append *document* to the END of *target* as one undoable edit.

    Used by single-document ("append") output mode: page after page is
    added to one continuous document.  A blank line separates pages; when
    *separator_text* is given (e.g. ``"— Page 3 —"``) a small centered
    marker line is inserted before the new content.
    """
    cursor = QTextCursor(target)
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.beginEditBlock()
    try:
        has_content = bool(target.toPlainText().strip())
        if has_content:
            # Blank line between the previous page and the new one.
            cursor.insertBlock(_block_format(TextAlignment.LEFT))
        if separator_text:
            separator_block = _block_format(TextAlignment.CENTER)
            cursor.insertBlock(separator_block)
            marker_format = QTextCharFormat()
            marker_format.setFontPointSize(FOOTNOTE_POINT_SIZE)
            marker_format.setFontItalic(True)
            cursor.insertText(separator_text, marker_format)
        for block in document.blocks:
            _insert_block(cursor, block)
    finally:
        cursor.endEditBlock()
    logger.debug(
        "Appended %d blocks (separator=%r)", len(document.blocks), separator_text
    )
