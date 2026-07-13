"""DOCX export.

Walks the Qt rich-text structure of every page (blocks, inline fragments,
lists, tables, page breaks) and rebuilds it with ``python-docx`` so the
result opens as a native, editable Word document.
"""

from __future__ import annotations

import logging
from pathlib import Path

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Pt
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextBlock, QTextBlockFormat, QTextDocument, QTextFrame
from PySide6.QtGui import QTextTable  # noqa: F401 (isinstance target)

logger = logging.getLogger(__name__)

_ALIGNMENT_MAP = {
    Qt.AlignmentFlag.AlignLeft: WD_ALIGN_PARAGRAPH.LEFT,
    Qt.AlignmentFlag.AlignCenter: WD_ALIGN_PARAGRAPH.CENTER,
    Qt.AlignmentFlag.AlignHCenter: WD_ALIGN_PARAGRAPH.CENTER,
    Qt.AlignmentFlag.AlignRight: WD_ALIGN_PARAGRAPH.RIGHT,
    Qt.AlignmentFlag.AlignJustify: WD_ALIGN_PARAGRAPH.JUSTIFY,
}


def _docx_alignment(block_format: QTextBlockFormat) -> int:
    alignment = block_format.alignment() & Qt.AlignmentFlag.AlignHorizontal_Mask
    for qt_flag, docx_value in _ALIGNMENT_MAP.items():
        if alignment & qt_flag:
            return docx_value
    return WD_ALIGN_PARAGRAPH.LEFT


def _paragraph_style(block: QTextBlock) -> str | None:
    """Word style name for a block, or None for default body text."""
    heading_level = block.blockFormat().headingLevel()
    if heading_level > 0:
        return f"Heading {min(heading_level, 9)}"
    text_list = block.textList()
    if text_list is not None:
        style = text_list.format().style()
        from PySide6.QtGui import QTextListFormat

        numbered_styles = (
            QTextListFormat.Style.ListDecimal,
            QTextListFormat.Style.ListLowerAlpha,
            QTextListFormat.Style.ListUpperAlpha,
            QTextListFormat.Style.ListLowerRoman,
            QTextListFormat.Style.ListUpperRoman,
        )
        return "List Number" if style in numbered_styles else "List Bullet"
    return None


def _write_block(docx_doc: DocxDocument, block: QTextBlock, force_page_break: bool) -> bool:
    """Append one text block; returns False when the block was skipped."""
    text = block.text()
    style = _paragraph_style(block)
    needs_break = force_page_break or bool(
        block.blockFormat().pageBreakPolicy()
        & QTextBlockFormat.PageBreakFlag.PageBreak_AlwaysBefore
    )
    if not text.strip() and style is None and not needs_break:
        # Preserve intentional blank lines but collapse trailing noise.
        docx_doc.add_paragraph("")
        return True

    paragraph = (
        docx_doc.add_paragraph(style=style) if style else docx_doc.add_paragraph()
    )
    paragraph.alignment = _docx_alignment(block.blockFormat())

    if needs_break:
        paragraph.add_run().add_break(WD_BREAK.PAGE)

    iterator = block.begin()
    while not iterator.atEnd():
        fragment = iterator.fragment()
        if fragment.isValid():
            char_format = fragment.charFormat()
            # Qt marks soft line breaks with U+2028; python-docx renders "\n"
            # as an in-paragraph line break.
            text_content = fragment.text().replace("\u2028", "\n")
            run = paragraph.add_run(text_content)
            run.bold = char_format.fontWeight() >= 600
            run.italic = char_format.fontItalic()
            run.underline = char_format.fontUnderline()
            point_size = char_format.fontPointSize()
            if point_size > 0:
                run.font.size = Pt(point_size)
            family = char_format.fontFamilies()
            if isinstance(family, list) and family:
                run.font.name = str(family[0])
        iterator += 1
    return True


def _write_table(docx_doc: DocxDocument, table: QTextTable) -> None:
    rows, cols = table.rows(), table.columns()
    if rows == 0 or cols == 0:
        return
    docx_table = docx_doc.add_table(rows=rows, cols=cols)
    docx_table.style = "Table Grid"
    for row in range(rows):
        for col in range(cols):
            cell = table.cellAt(row, col)
            fragments: list[str] = []
            frame_iterator = cell.begin()
            while not frame_iterator.atEnd():
                block = frame_iterator.currentBlock()
                if block.isValid() and block.text():
                    fragments.append(block.text())
                frame_iterator += 1
            docx_table.cell(row, col).text = "\n".join(fragments)
    docx_doc.add_paragraph("")


def _walk_frame(docx_doc: DocxDocument, frame: QTextFrame, force_first_break: bool) -> None:
    pending_break = force_first_break
    iterator = frame.begin()
    while not iterator.atEnd():
        child_frame = iterator.currentFrame()
        if child_frame is not None:
            if isinstance(child_frame, QTextTable):
                _write_table(docx_doc, child_frame)
            else:
                _walk_frame(docx_doc, child_frame, force_first_break=False)
        else:
            block = iterator.currentBlock()
            if block.isValid():
                if _write_block(docx_doc, block, force_page_break=pending_break):
                    pending_break = False
        iterator += 1


def export_docx(page_htmls: list[str], output_path: Path) -> Path:
    """Write all pages to *output_path* as one Word document.

    Each entry of *page_htmls* is one page's rich text (HTML); pages are
    separated by page breaks.  Raises ``RuntimeError`` with a readable
    message on failure.
    """
    docx_doc = DocxDocument()
    try:
        for index, html in enumerate(page_htmls):
            qt_document = QTextDocument()
            qt_document.setHtml(html)
            _walk_frame(docx_doc, qt_document.rootFrame(), force_first_break=index > 0)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        docx_doc.save(str(output_path))
    except PermissionError as exc:
        raise RuntimeError(
            f"Cannot write '{output_path.name}': the file is open in another "
            "application or the folder is read-only."
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"Could not save DOCX file: {exc}") from exc

    logger.info("Exported %d pages to %s", len(page_htmls), output_path)
    return output_path
