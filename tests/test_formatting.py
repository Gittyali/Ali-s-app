"""Tests for markdown parsing and rich-text rendering."""

from __future__ import annotations

from app.document.model import (
    BlockType,
    ListBlock,
    ParagraphBlock,
    TableBlock,
    TextAlignment,
)
from app.formatting.markdown_parser import parse_inline, parse_markdown


class TestParseInline:
    def test_plain(self) -> None:
        spans = parse_inline("hello world")
        assert len(spans) == 1
        assert spans[0].text == "hello world"
        assert not spans[0].bold

    def test_bold_and_italic(self) -> None:
        spans = parse_inline("a **b** c *d*")
        texts = [(s.text, s.bold, s.italic) for s in spans]
        assert ("b", True, False) in texts
        assert ("d", False, True) in texts

    def test_underline(self) -> None:
        spans = parse_inline("<u>under</u>")
        assert spans[0].text == "under"
        assert spans[0].underline


class TestParseMarkdown:
    def test_heading_levels(self) -> None:
        doc = parse_markdown("# Title\n\n## Section")
        assert doc.blocks[0].block_type is BlockType.HEADING
        assert doc.blocks[1].block_type is BlockType.SUBHEADING

    def test_paragraph_merging(self) -> None:
        doc = parse_markdown("line one\nline two\n\nsecond para")
        paragraphs = [b for b in doc.blocks if isinstance(b, ParagraphBlock)]
        assert len(paragraphs) == 2
        assert paragraphs[0].plain_text() == "line one line two"

    def test_lists(self) -> None:
        doc = parse_markdown("- a\n- b\n\n1. x\n2. y")
        bullets = doc.blocks[0]
        numbered = doc.blocks[1]
        assert isinstance(bullets, ListBlock)
        assert bullets.block_type is BlockType.BULLET_LIST
        assert len(bullets.items) == 2
        assert isinstance(numbered, ListBlock)
        assert numbered.block_type is BlockType.NUMBERED_LIST

    def test_table(self) -> None:
        doc = parse_markdown("| A | B |\n|---|---|\n| 1 | 2 |")
        table = doc.blocks[0]
        assert isinstance(table, TableBlock)
        assert table.rows == [["A", "B"], ["1", "2"]]

    def test_footnote(self) -> None:
        doc = parse_markdown("[^1]: a footnote")
        assert doc.blocks[0].block_type is BlockType.FOOTNOTE

    def test_centered(self) -> None:
        doc = parse_markdown("<center>IN THE HIGH COURT</center>")
        block = doc.blocks[0]
        assert isinstance(block, ParagraphBlock)
        assert block.alignment is TextAlignment.CENTER

    def test_empty_input(self) -> None:
        assert parse_markdown("").is_empty()


class TestRichTextRoundTrip:
    def test_insert_into_qtextdocument(self, qapp) -> None:
        from PySide6.QtGui import QTextCursor, QTextDocument

        from app.formatting.rich_text import insert_structured_document

        doc = parse_markdown(
            "# Title\n\nBody **bold** text.\n\n- one\n- two\n\n| A |\n|---|\n| 1 |"
        )
        qdoc = QTextDocument()
        insert_structured_document(QTextCursor(qdoc), doc)
        plain = qdoc.toPlainText()
        assert "Title" in plain
        assert "bold" in plain
        assert "one" in plain
        assert "1" in plain
