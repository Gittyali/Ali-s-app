"""Structured document model.

The classes here form the neutral intermediate representation between the
recognition side (OCR layout analysis, AI vision output) and the editing side
(the Qt rich-text editor).  Neither side depends on the other; both depend
only on this model.
"""

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

__all__ = [
    "Block",
    "BlockType",
    "InlineSpan",
    "ListBlock",
    "ParagraphBlock",
    "StructuredDocument",
    "TableBlock",
    "TextAlignment",
]
