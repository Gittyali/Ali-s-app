"""Neutral, provider-independent document structure.

A :class:`StructuredDocument` is an ordered list of blocks.  Block types map
one-to-one onto concepts the rich-text editor and the exporters understand:
headings, paragraphs, lists, tables and footnotes.  Inline formatting lives
in :class:`InlineSpan` runs inside each block.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BlockType(Enum):
    """Semantic category of a document block."""

    HEADING = "heading"
    SUBHEADING = "subheading"
    PARAGRAPH = "paragraph"
    BULLET_LIST = "bullet_list"
    NUMBERED_LIST = "numbered_list"
    TABLE = "table"
    FOOTNOTE = "footnote"


class TextAlignment(Enum):
    """Horizontal alignment for a block."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"


@dataclass
class InlineSpan:
    """A run of text sharing one set of inline attributes."""

    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False


@dataclass
class Block:
    """Common base for every document block."""

    block_type: BlockType
    alignment: TextAlignment = TextAlignment.LEFT


@dataclass
class ParagraphBlock(Block):
    """Heading, subheading, paragraph or footnote text.

    ``level`` is meaningful for headings only (1 = title, 2 = section, ...).
    """

    spans: list[InlineSpan] = field(default_factory=list)
    level: int = 0

    def plain_text(self) -> str:
        """Concatenated text of all spans."""
        return "".join(span.text for span in self.spans)


@dataclass
class ListBlock(Block):
    """Bulleted or numbered list; each item is a list of inline spans."""

    items: list[list[InlineSpan]] = field(default_factory=list)

    def item_text(self, index: int) -> str:
        """Plain text of one list item."""
        return "".join(span.text for span in self.items[index])


@dataclass
class TableBlock(Block):
    """Simple rectangular table; ``rows[r][c]`` is a cell's plain text."""

    rows: list[list[str]] = field(default_factory=list)
    header_row: bool = True

    @property
    def column_count(self) -> int:
        return max((len(row) for row in self.rows), default=0)


@dataclass
class StructuredDocument:
    """Ordered sequence of blocks describing one page's content."""

    blocks: list[Block] = field(default_factory=list)

    def is_empty(self) -> bool:
        """True when the document has no blocks with visible content."""
        for block in self.blocks:
            if isinstance(block, ParagraphBlock) and block.plain_text().strip():
                return False
            if isinstance(block, ListBlock) and block.items:
                return False
            if isinstance(block, TableBlock) and block.rows:
                return False
        return True

    def plain_text(self) -> str:
        """Text-only rendering, used for logging and previews."""
        parts: list[str] = []
        for block in self.blocks:
            if isinstance(block, ParagraphBlock):
                parts.append(block.plain_text())
            elif isinstance(block, ListBlock):
                parts.extend(block.item_text(i) for i in range(len(block.items)))
            elif isinstance(block, TableBlock):
                parts.extend(" | ".join(row) for row in block.rows)
        return "\n".join(parts)
