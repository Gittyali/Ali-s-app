"""Shared prompt text for all AI vision providers.

Every provider sends the same instructions so results are interchangeable.
The output contract is the constrained Markdown dialect understood by
:mod:`app.formatting.markdown_parser`.  The decorative-underline and
watermark clauses are toggled by user settings (Settings > Reading).
"""

from __future__ import annotations

SYSTEM_PROMPT = (
    "You are an expert OCR transcription assistant. You convert images of "
    "scanned pages and screenshots into faithful, well-structured documents. "
    "You never summarise, never explain, never describe images, never "
    "hallucinate and never invent missing words."
)

READ_PAGE_INSTRUCTIONS = """\
Extract ONLY the meaningful visible text of this page and reconstruct the
document exactly as it appears, as Markdown:

- Preserve headings (`#` for the title, `##`/`###` for subheadings),
  paragraphs, lists (`- ` bullets, `1. ` numbering), tables (Markdown pipe
  tables with a `|---|` separator row) and the natural reading order.
- Preserve **bold** and *italic* where genuinely present in the typography.
- Wrap visually centered lines in <center>...</center>.
- Transcribe footnotes at the end as `[^1]: text`.
- Preserve all numbers, dates, amounts and legal citations exactly as written.
- Keep the original language(s) of the text; do not translate.
- If a word or passage is unreadable, write [unclear] in its place.
- Do NOT summarize. Do NOT explain. Do NOT describe images. Do NOT
  hallucinate or invent missing words.
- Return ONLY the reconstructed document text as Markdown: no commentary,
  no code fences.
"""

IGNORE_UNDERLINES_CLAUSE = """\
- Decorative underlines: many pages have every line underlined by ruled/
  notebook lines or form rules. Do NOT mark text as underlined because a
  line, rule or highlight passes under it. Use <u>...</u> only when an
  underline is genuinely meaningful in the original typography (e.g. a
  single defined term); when in doubt, omit the underline.
"""

IGNORE_WATERMARKS_CLAUSE = """\
- Ignore decorative elements entirely: watermarks, background stamps,
  logos, page borders, background graphics, shadows, highlighter marks and
  scanner noise must NOT appear in the output. Transcribe highlighted text
  itself with no special formatting for the highlight.
"""

OCR_HINT_PREFIX = (
    "\nFor reference, a raw OCR pass produced the text below. It may contain "
    "errors; trust the image over the OCR text when they disagree:\n\n"
)


def build_user_prompt(
    ocr_hint: str = "",
    ignore_underlines: bool = True,
    ignore_watermarks: bool = True,
) -> str:
    """Compose the user-message text with the configured extraction rules."""
    prompt = READ_PAGE_INSTRUCTIONS
    if ignore_underlines:
        prompt += IGNORE_UNDERLINES_CLAUSE
    if ignore_watermarks:
        prompt += IGNORE_WATERMARKS_CLAUSE
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
