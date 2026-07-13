"""Shared prompt text for all AI vision providers.

Every provider sends the same instructions so results are interchangeable.
The output contract is the constrained Markdown dialect understood by
:mod:`app.formatting.markdown_parser`.
"""

from __future__ import annotations

SYSTEM_PROMPT = (
    "You are a professional document transcription engine. You convert "
    "images of scanned pages and screenshots into faithful, well-structured "
    "documents. You never invent content and never summarise."
)

READ_PAGE_INSTRUCTIONS = """\
Transcribe this page into Markdown, reconstructing the document's structure \
exactly as it appears:

- Use `#` for the main heading/title and `##`/`###` for subheadings.
- Keep paragraphs intact; separate them with blank lines.
- Use `- ` for bulleted lists and `1. ` for numbered lists.
- Reproduce tables as Markdown pipe tables (header row, then `|---|` separator).
- Preserve **bold**, *italic* and <u>underlined</u> text where visible.
- Wrap visually centered lines in <center>...</center>.
- Transcribe footnotes at the end as `[^1]: text`.
- Preserve all numbers, dates, amounts and legal citations exactly as written.
- Keep the original language(s) of the text; do not translate.
- Output ONLY the Markdown transcription: no commentary, no code fences.
"""

OCR_HINT_PREFIX = (
    "\nFor reference, a raw OCR pass produced the text below. It may contain "
    "errors; trust the image over the OCR text when they disagree:\n\n"
)


def build_user_prompt(ocr_hint: str = "") -> str:
    """Compose the user-message text, optionally embedding an OCR hint."""
    prompt = READ_PAGE_INSTRUCTIONS
    hint = ocr_hint.strip()
    if hint:
        # Cap the hint so huge OCR dumps do not blow the context window.
        prompt += OCR_HINT_PREFIX + hint[:8000]
    return prompt


def strip_code_fences(text: str) -> str:
    """Remove a wrapping ``` fence if the model added one despite instructions."""
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1 :]
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]
    return stripped.strip()
