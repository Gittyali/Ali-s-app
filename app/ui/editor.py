"""Rich text document editor.

A Word-like editing surface for the active page: bold/italic/underline,
font size, alignment, bullet/numbered lists, line spacing, page breaks,
undo/redo and free typing.  Voice commands from the dictation session are
applied through :meth:`DocumentEditor.apply_command` and dictated words
through :meth:`DocumentEditor.insert_dictation`.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QFont,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextListFormat,
    QTextOption,
)
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.document.model import StructuredDocument
from app.formatting.rich_text import (
    BODY_POINT_SIZE,
    HEADING_POINT_SIZES,
    insert_structured_document,
)
from app.speech.commands import CommandType, ParsedCommand

logger = logging.getLogger(__name__)

_FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36, 48]
_LINE_SPACINGS = {"1.0": 100, "1.15": 115, "1.5": 150, "2.0": 200}


class DocumentEditor(QWidget):
    """Editor pane bound to the active page's document.

    Signals:
        * ``content_edited()`` — any user/voice change to the document.
        * ``navigation_requested(str, int)`` — voice navigation that the
          editor cannot handle itself ("next", "previous", "goto" + number).
    """

    content_edited = Signal()
    navigation_requested = Signal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._edit = QTextEdit(self)
        self._edit.setAcceptRichText(True)
        self._edit.setUndoRedoEnabled(True)
        # Word wrap: break long lines at word boundaries within the widget
        # width so text never requires horizontal scrolling.
        self._edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._edit.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        default_font = QFont("Calibri", int(BODY_POINT_SIZE))
        self._edit.document().setDefaultFont(default_font)
        self._edit.textChanged.connect(self.content_edited)
        self._edit.cursorPositionChanged.connect(self._sync_toolbar_state)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._build_toolbar())
        layout.addWidget(self._edit, stretch=1)

    # -------------------------------------------------------------- toolbar
    def _build_toolbar(self) -> QWidget:
        bar = QWidget(self)
        row = QHBoxLayout(bar)
        row.setContentsMargins(4, 2, 4, 2)

        def tool(
            text: str, tooltip: str, slot, checkable: bool = False
        ) -> QToolButton:
            button = QToolButton(bar)
            button.setText(text)
            button.setToolTip(tooltip)
            button.setCheckable(checkable)
            button.clicked.connect(slot)
            row.addWidget(button)
            return button

        tool("↶", "Undo (Ctrl+Z)", self._edit.undo)
        tool("↷", "Redo (Ctrl+Y)", self._edit.redo)
        row.addSpacing(8)

        self._size_box = QComboBox(bar)
        self._size_box.setToolTip("Font size")
        for size in _FONT_SIZES:
            self._size_box.addItem(str(size), size)
        self._size_box.setCurrentText(str(int(BODY_POINT_SIZE)))
        self._size_box.activated.connect(self._on_font_size)
        row.addWidget(self._size_box)

        self._bold_button = tool("B", "Bold (Ctrl+B)", self.toggle_bold, True)
        self._bold_button.setStyleSheet("font-weight: bold;")
        self._italic_button = tool("I", "Italic", self.toggle_italic, True)
        self._italic_button.setStyleSheet("font-style: italic;")
        self._underline_button = tool("U", "Underline (Ctrl+U)", self.toggle_underline, True)
        self._underline_button.setStyleSheet("text-decoration: underline;")
        row.addSpacing(8)

        tool("H1", "Heading", lambda: self.apply_heading(1))
        tool("H2", "Subheading", lambda: self.apply_heading(2))
        tool("¶", "Normal paragraph", lambda: self.apply_heading(0))
        row.addSpacing(8)

        tool("⯇", "Align left", lambda: self.set_alignment(Qt.AlignmentFlag.AlignLeft))
        tool("≡", "Center", lambda: self.set_alignment(Qt.AlignmentFlag.AlignCenter))
        tool("⯈", "Align right", lambda: self.set_alignment(Qt.AlignmentFlag.AlignRight))
        row.addSpacing(8)

        tool("•", "Bullet list", self.toggle_bullet_list)
        tool("1.", "Numbered list", self.toggle_numbered_list)
        row.addSpacing(8)

        self._spacing_box = QComboBox(bar)
        self._spacing_box.setToolTip("Line spacing")
        for label in _LINE_SPACINGS:
            self._spacing_box.addItem(label)
        self._spacing_box.activated.connect(self._on_line_spacing)
        row.addWidget(self._spacing_box)

        tool("⤓", "Insert page break", self.insert_page_break)
        row.addStretch(1)
        return bar

    def _sync_toolbar_state(self) -> None:
        fmt = self._edit.currentCharFormat()
        self._bold_button.setChecked(fmt.fontWeight() >= 600)
        self._italic_button.setChecked(fmt.fontItalic())
        self._underline_button.setChecked(fmt.fontUnderline())
        size = int(fmt.fontPointSize() or BODY_POINT_SIZE)
        self._size_box.setCurrentText(str(size))

    # ------------------------------------------------------------- content
    def set_html(self, html: str) -> None:
        """Load a page's document without emitting content_edited."""
        self._edit.blockSignals(True)
        try:
            self._edit.setHtml(html)
        finally:
            self._edit.blockSignals(False)

    def to_html(self) -> str:
        return self._edit.toHtml()

    def is_empty(self) -> bool:
        return not self._edit.toPlainText().strip()

    def insert_document(self, document: StructuredDocument, replace: bool = True) -> None:
        """Insert recognised content (AI/OCR result) into the editor."""
        cursor = self._edit.textCursor()
        if replace:
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.removeSelectedText()
        insert_structured_document(cursor, document)
        self._edit.setTextCursor(cursor)
        self._edit.setFocus()

    def set_editor_enabled(self, enabled: bool) -> None:
        self._edit.setEnabled(enabled)

    # ------------------------------------------------- formatting commands
    def _merge_char_format(self, fmt: QTextCharFormat) -> None:
        cursor = self._edit.textCursor()
        cursor.mergeCharFormat(fmt)
        self._edit.mergeCurrentCharFormat(fmt)

    def toggle_bold(self) -> None:
        fmt = QTextCharFormat()
        currently_bold = self._edit.currentCharFormat().fontWeight() >= 600
        fmt.setFontWeight(
            QFont.Weight.Normal if currently_bold else QFont.Weight.Bold
        )
        self._merge_char_format(fmt)

    def toggle_italic(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self._edit.currentCharFormat().fontItalic())
        self._merge_char_format(fmt)

    def toggle_underline(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self._edit.currentCharFormat().fontUnderline())
        self._merge_char_format(fmt)

    def _on_font_size(self) -> None:
        size = self._size_box.currentData()
        if size:
            fmt = QTextCharFormat()
            fmt.setFontPointSize(float(size))
            self._merge_char_format(fmt)
        self._edit.setFocus()

    def set_alignment(self, alignment: Qt.AlignmentFlag) -> None:
        self._edit.setAlignment(alignment)
        self._edit.setFocus()

    def apply_heading(self, level: int) -> None:
        """Make the current block a heading (level 1/2) or body text (0)."""
        cursor = self._edit.textCursor()
        block_format = cursor.blockFormat()
        block_format.setHeadingLevel(level)
        char_format = QTextCharFormat()
        if level > 0:
            char_format.setFontPointSize(HEADING_POINT_SIZES.get(level, 13.0))
            char_format.setFontWeight(QFont.Weight.Bold)
        else:
            char_format.setFontPointSize(BODY_POINT_SIZE)
            char_format.setFontWeight(QFont.Weight.Normal)
        cursor.beginEditBlock()
        cursor.setBlockFormat(block_format)
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        cursor.mergeCharFormat(char_format)
        cursor.endEditBlock()
        self._edit.mergeCurrentCharFormat(char_format)
        self._edit.setFocus()

    def _toggle_list(self, style: QTextListFormat.Style) -> None:
        cursor = self._edit.textCursor()
        current_list = cursor.currentList()
        cursor.beginEditBlock()
        if current_list is not None and current_list.format().style() == style:
            # Remove from list: detach block and clear indentation.
            current_list.remove(cursor.block())
            block_format = cursor.blockFormat()
            block_format.setIndent(0)
            cursor.setBlockFormat(block_format)
        else:
            list_format = QTextListFormat()
            list_format.setStyle(style)
            list_format.setIndent(1)
            cursor.createList(list_format)
        cursor.endEditBlock()
        self._edit.setFocus()

    def toggle_bullet_list(self) -> None:
        self._toggle_list(QTextListFormat.Style.ListDisc)

    def toggle_numbered_list(self) -> None:
        self._toggle_list(QTextListFormat.Style.ListDecimal)

    def _on_line_spacing(self) -> None:
        percent = _LINE_SPACINGS.get(self._spacing_box.currentText(), 100)
        cursor = self._edit.textCursor()
        block_format = cursor.blockFormat()
        block_format.setLineHeight(
            float(percent), QTextBlockFormat.LineHeightTypes.ProportionalHeight.value
        )
        cursor.setBlockFormat(block_format)
        self._edit.setFocus()

    def insert_page_break(self) -> None:
        cursor = self._edit.textCursor()
        block_format = QTextBlockFormat()
        block_format.setPageBreakPolicy(
            QTextBlockFormat.PageBreakFlag.PageBreak_AlwaysBefore
        )
        cursor.insertBlock(block_format)
        self._edit.setTextCursor(cursor)
        self._edit.setFocus()

    def new_paragraph(self) -> None:
        cursor = self._edit.textCursor()
        cursor.insertBlock()
        # A fresh paragraph returns to body formatting.
        block_format = cursor.blockFormat()
        block_format.setHeadingLevel(0)
        cursor.setBlockFormat(block_format)
        char_format = QTextCharFormat()
        char_format.setFontPointSize(BODY_POINT_SIZE)
        char_format.setFontWeight(QFont.Weight.Normal)
        char_format.setFontItalic(False)
        char_format.setFontUnderline(False)
        self._edit.setTextCursor(cursor)
        self._edit.mergeCurrentCharFormat(char_format)

    def new_line(self) -> None:
        cursor = self._edit.textCursor()
        cursor.insertText("\u2028")  # U+2028: soft line break within the paragraph
        self._edit.setTextCursor(cursor)

    # ------------------------------------------------------------ dictation
    def insert_dictation(self, text: str) -> None:
        """Insert dictated words at the cursor with sensible spacing."""
        text = text.strip()
        if not text:
            return
        cursor = self._edit.textCursor()
        position = cursor.position()
        needs_space = False
        if position > 0:
            probe = QTextCursor(cursor)
            probe.movePosition(
                QTextCursor.MoveOperation.PreviousCharacter,
                QTextCursor.MoveMode.KeepAnchor,
            )
            previous_char = probe.selectedText()
            # No space after whitespace, soft line breaks (U+2028) or
            # paragraph separators (U+2029).
            needs_space = bool(previous_char) and previous_char not in (
                " ",
                "\u2028",
                "\u2029",
            )
        cursor.insertText((" " if needs_space else "") + text)
        self._edit.setTextCursor(cursor)

    def apply_command(self, command: ParsedCommand) -> None:
        """Execute one parsed voice command."""
        handlers = {
            CommandType.HEADING: lambda: self.apply_heading(1),
            CommandType.SUBHEADING: lambda: self.apply_heading(2),
            CommandType.BOLD: self.toggle_bold,
            CommandType.ITALIC: self.toggle_italic,
            CommandType.UNDERLINE: self.toggle_underline,
            CommandType.CENTER: lambda: self.set_alignment(
                Qt.AlignmentFlag.AlignCenter
            ),
            CommandType.ALIGN_LEFT: lambda: self.set_alignment(
                Qt.AlignmentFlag.AlignLeft
            ),
            CommandType.ALIGN_RIGHT: lambda: self.set_alignment(
                Qt.AlignmentFlag.AlignRight
            ),
            CommandType.BULLET_LIST: self.toggle_bullet_list,
            CommandType.NUMBERED_LIST: self.toggle_numbered_list,
            CommandType.NEW_PARAGRAPH: self.new_paragraph,
            CommandType.NEW_LINE: self.new_line,
            CommandType.PAGE_BREAK: self.insert_page_break,
        }
        handler = handlers.get(command.command)
        if handler is not None:
            handler()
            return
        if command.command is CommandType.NEXT_PAGE:
            self.navigation_requested.emit("next", 0)
        elif command.command is CommandType.PREVIOUS_PAGE:
            self.navigation_requested.emit("previous", 0)
        elif command.command is CommandType.GO_TO_PAGE:
            self.navigation_requested.emit("goto", int(command.argument or 0))
        else:  # pragma: no cover - future command types
            logger.warning("Unhandled voice command: %s", command.command)
