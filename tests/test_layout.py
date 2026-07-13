"""Tests for OCR geometric layout reconstruction."""

from __future__ import annotations

from app.document.model import BlockType, ListBlock, ParagraphBlock
from app.ocr.base import OCRLine, OCRResult, OCRWord, group_words_into_lines
from app.ocr.layout import reconstruct_document


def _line(text: str, top: int, height: int = 20, left: int = 50) -> OCRLine:
    words = []
    x = left
    for token in text.split():
        width = 12 * len(token)
        words.append(
            OCRWord(
                text=token, left=x, top=top, width=width, height=height, confidence=0.9
            )
        )
        x += width + 8
    return OCRLine(words=words)


class TestGroupWords:
    def test_two_rows(self) -> None:
        words = [
            OCRWord("b", 60, 10, 20, 18, 0.9),
            OCRWord("a", 10, 12, 20, 18, 0.9),
            OCRWord("c", 10, 60, 20, 18, 0.9),
        ]
        lines = group_words_into_lines(words)
        assert len(lines) == 2
        assert lines[0].text == "a b"
        assert lines[1].text == "c"

    def test_empty(self) -> None:
        assert group_words_into_lines([]) == []


class TestReconstruct:
    def test_heading_by_size(self) -> None:
        result = OCRResult(
            lines=[
                _line("BIG TITLE", top=40, height=40),
                _line("normal paragraph text goes here", top=150),
                _line("continuing the same paragraph", top=175),
            ],
            image_width=1000,
            image_height=1400,
        )
        doc = reconstruct_document(result)
        assert doc.blocks[0].block_type is BlockType.HEADING
        para = doc.blocks[1]
        assert isinstance(para, ParagraphBlock)
        assert "continuing" in para.plain_text()

    def test_numbered_list(self) -> None:
        result = OCRResult(
            lines=[
                _line("1. first item", top=100),
                _line("2. second item", top=130),
            ],
            image_width=1000,
            image_height=1400,
        )
        doc = reconstruct_document(result)
        block = doc.blocks[0]
        assert isinstance(block, ListBlock)
        assert block.block_type is BlockType.NUMBERED_LIST
        assert block.item_text(0) == "first item"

    def test_paragraph_split_on_gap(self) -> None:
        result = OCRResult(
            lines=[
                _line("first paragraph sentence", top=100),
                _line("second paragraph after a big gap", top=300),
            ],
            image_width=1000,
            image_height=1400,
        )
        doc = reconstruct_document(result)
        paragraphs = [b for b in doc.blocks if isinstance(b, ParagraphBlock)]
        assert len(paragraphs) == 2

    def test_empty_result(self) -> None:
        doc = reconstruct_document(OCRResult(lines=[], image_width=100, image_height=100))
        assert doc.is_empty()
