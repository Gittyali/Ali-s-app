"""Formatting layer.

Converts between representations:

* :mod:`app.formatting.markdown_parser` — Markdown produced by AI vision
  providers into a :class:`~app.document.model.StructuredDocument`.
* :mod:`app.formatting.rich_text` — a ``StructuredDocument`` into rich text
  inside a ``QTextDocument`` (the editor's native format).
"""

from app.formatting.markdown_parser import parse_markdown
from app.formatting.rich_text import (
    append_structured_document,
    insert_structured_document,
)

__all__ = [
    "append_structured_document",
    "insert_structured_document",
    "parse_markdown",
]
