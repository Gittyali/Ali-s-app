"""Voice formatting/navigation command parsing.

A final transcript such as::

    "heading introduction new paragraph this act shall be called"

is split into a stream of commands and dictation text.  Command phrases are
recognised in English, Urdu script and Roman Urdu.  Parsing is longest-match
first, so "sub heading" wins over "heading" and "go to page fifteen" is one
command, not dictation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CommandType(Enum):
    """All voice-controllable actions."""

    HEADING = "heading"
    SUBHEADING = "subheading"
    BOLD = "bold"
    ITALIC = "italic"
    UNDERLINE = "underline"
    CENTER = "center"
    ALIGN_LEFT = "align_left"
    ALIGN_RIGHT = "align_right"
    BULLET_LIST = "bullet_list"
    NUMBERED_LIST = "numbered_list"
    NEW_PARAGRAPH = "new_paragraph"
    NEW_LINE = "new_line"
    PAGE_BREAK = "page_break"
    NEXT_PAGE = "next_page"
    PREVIOUS_PAGE = "previous_page"
    GO_TO_PAGE = "go_to_page"


@dataclass
class ParsedCommand:
    """One recognised command; ``argument`` carries the page number, if any."""

    command: CommandType
    argument: int | None = None


@dataclass
class TranscriptPart:
    """A slice of the transcript: either dictation text or a command."""

    text: str = ""
    command: ParsedCommand | None = None


# ---------------------------------------------------------------------------
# Phrase tables.  Keys are normalised (lowercase, single spaces).  Urdu
# phrases include common recogniser spellings.
# ---------------------------------------------------------------------------
_COMMAND_PHRASES: dict[str, CommandType] = {
    # --- English ---
    "sub heading": CommandType.SUBHEADING,
    "subheading": CommandType.SUBHEADING,
    "heading": CommandType.HEADING,
    "bold": CommandType.BOLD,
    "italic": CommandType.ITALIC,
    "italics": CommandType.ITALIC,
    "underline": CommandType.UNDERLINE,
    "center": CommandType.CENTER,
    "centre": CommandType.CENTER,
    "center align": CommandType.CENTER,
    "left align": CommandType.ALIGN_LEFT,
    "align left": CommandType.ALIGN_LEFT,
    "right align": CommandType.ALIGN_RIGHT,
    "align right": CommandType.ALIGN_RIGHT,
    "bullet list": CommandType.BULLET_LIST,
    "bullet points": CommandType.BULLET_LIST,
    "numbered list": CommandType.NUMBERED_LIST,
    "number list": CommandType.NUMBERED_LIST,
    "new paragraph": CommandType.NEW_PARAGRAPH,
    "next paragraph": CommandType.NEW_PARAGRAPH,
    "new line": CommandType.NEW_LINE,
    "next line": CommandType.NEW_LINE,
    "insert page break": CommandType.PAGE_BREAK,
    "page break": CommandType.PAGE_BREAK,
    "next page": CommandType.NEXT_PAGE,
    "previous page": CommandType.PREVIOUS_PAGE,
    "last page": CommandType.PREVIOUS_PAGE,
    # --- Roman Urdu ---
    "sub sarkhi": CommandType.SUBHEADING,
    "choti sarkhi": CommandType.SUBHEADING,
    "sarkhi": CommandType.HEADING,
    "unwan": CommandType.HEADING,
    "mota": CommandType.BOLD,
    "mota karo": CommandType.BOLD,
    "terha": CommandType.ITALIC,
    "terha karo": CommandType.ITALIC,
    "khat kasheeda": CommandType.UNDERLINE,
    "underline karo": CommandType.UNDERLINE,
    "darmiyan": CommandType.CENTER,
    "center karo": CommandType.CENTER,
    "bayen taraf": CommandType.ALIGN_LEFT,
    "dayen taraf": CommandType.ALIGN_RIGHT,
    "nai fehrist": CommandType.BULLET_LIST,
    "number fehrist": CommandType.NUMBERED_LIST,
    "naya paragraph": CommandType.NEW_PARAGRAPH,
    "nai satar": CommandType.NEW_LINE,
    "agla safha": CommandType.NEXT_PAGE,
    "agla page": CommandType.NEXT_PAGE,
    "pichla safha": CommandType.PREVIOUS_PAGE,
    "pichla page": CommandType.PREVIOUS_PAGE,
    # --- Urdu script ---
    "سرخی": CommandType.HEADING,
    "عنوان": CommandType.HEADING,
    "ذیلی سرخی": CommandType.SUBHEADING,
    "موٹا": CommandType.BOLD,
    "ترچھا": CommandType.ITALIC,
    "خط کشیدہ": CommandType.UNDERLINE,
    "درمیان": CommandType.CENTER,
    "بائیں طرف": CommandType.ALIGN_LEFT,
    "دائیں طرف": CommandType.ALIGN_RIGHT,
    "نیا پیراگراف": CommandType.NEW_PARAGRAPH,
    "نئی سطر": CommandType.NEW_LINE,
    "اگلا صفحہ": CommandType.NEXT_PAGE,
    "پچھلا صفحہ": CommandType.PREVIOUS_PAGE,
}

# "go to page N" prefixes; the tail is parsed as a number.
_GO_TO_PAGE_PREFIXES: tuple[str, ...] = (
    "go to page",
    "goto page",
    "jump to page",
    "open page",
    "page number",
    "safha number",
    "page par jao",
    "safhe par jao",
    "صفحہ نمبر",
)

_NUMBER_WORDS: dict[str, int] = {
    # English units and teens
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
    # English tens
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": 100,
    # Roman Urdu
    "aik": 1, "ek": 1, "do": 2, "teen": 3, "chaar": 4, "char": 4,
    "paanch": 5, "panch": 5, "chay": 6, "che": 6, "saat": 7,
    "aath": 8, "nau": 9, "das": 10, "gyara": 11, "bara": 12,
    "tera": 13, "chauda": 14, "pandra": 15, "sola": 16, "satra": 17,
    "athara": 18, "unnees": 19, "bees": 20, "tees": 30, "chalees": 40,
    "pachas": 50, "saath": 60, "sattar": 70, "assi": 80, "nawway": 90,
    "sau": 100,
    # Urdu script
    "ایک": 1, "دو": 2, "تین": 3, "چار": 4, "پانچ": 5, "چھ": 6,
    "سات": 7, "آٹھ": 8, "نو": 9, "دس": 10, "بیس": 20, "تیس": 30,
    "چالیس": 40, "پچاس": 50, "ساٹھ": 60, "ستر": 70, "اسی": 80,
    "نوے": 90, "سو": 100,
}

_URDU_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def parse_number(tokens: list[str]) -> tuple[int | None, int]:
    """Parse a number at the start of *tokens*.

    Returns ``(value, tokens_consumed)``; ``(None, 0)`` when the tokens do
    not start with a number.  Handles digits ("15"), Urdu digits ("۱۵") and
    compound words ("one hundred twenty five", "bees").
    """
    if not tokens:
        return None, 0

    first = tokens[0].translate(_URDU_DIGITS)
    if re.fullmatch(r"\d{1,4}", first):
        return int(first), 1

    total = 0
    current = 0
    consumed = 0
    for token in tokens:
        word = token.lower()
        if word == "and":
            consumed += 1
            continue
        value = _NUMBER_WORDS.get(word)
        if value is None:
            break
        if value == 100:
            current = max(1, current) * 100
        else:
            current += value
        consumed += 1
    total += current
    if consumed == 0 or total == 0:
        return None, 0
    # Trailing "and" without a following number should not be consumed.
    while consumed > 0 and tokens[consumed - 1].lower() == "and":
        consumed -= 1
    return total, consumed


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


class VoiceCommandParser:
    """Splits final transcripts into dictation text and commands."""

    def __init__(self) -> None:
        # Longest phrases first so greedy matching prefers them.
        self._phrases: list[tuple[list[str], CommandType]] = sorted(
            ((phrase.split(), command) for phrase, command in _COMMAND_PHRASES.items()),
            key=lambda item: len(item[0]),
            reverse=True,
        )
        self._go_to_prefixes: list[list[str]] = sorted(
            (prefix.split() for prefix in _GO_TO_PAGE_PREFIXES),
            key=len,
            reverse=True,
        )

    def _match_go_to_page(
        self, tokens: list[str], index: int
    ) -> tuple[ParsedCommand, int] | None:
        for prefix in self._go_to_prefixes:
            end = index + len(prefix)
            if [token.lower() for token in tokens[index:end]] == prefix:
                number, consumed = parse_number(tokens[end:])
                if number is not None and number > 0:
                    return (
                        ParsedCommand(CommandType.GO_TO_PAGE, argument=number),
                        len(prefix) + consumed,
                    )
        return None

    def _match_phrase(
        self, tokens: list[str], index: int
    ) -> tuple[ParsedCommand, int] | None:
        for phrase, command in self._phrases:
            end = index + len(phrase)
            if [token.lower() for token in tokens[index:end]] == phrase:
                return ParsedCommand(command), len(phrase)
        return None

    def parse(self, transcript: str) -> list[TranscriptPart]:
        """Split *transcript* into an ordered list of text and command parts."""
        tokens = _normalise(transcript).split()
        parts: list[TranscriptPart] = []
        buffer: list[str] = []

        def flush_text() -> None:
            if buffer:
                parts.append(TranscriptPart(text=" ".join(buffer)))
                buffer.clear()

        index = 0
        while index < len(tokens):
            matched = self._match_go_to_page(tokens, index) or self._match_phrase(
                tokens, index
            )
            if matched:
                command, consumed = matched
                flush_text()
                parts.append(TranscriptPart(command=command))
                index += consumed
            else:
                buffer.append(tokens[index])
                index += 1
        flush_text()

        if any(part.command for part in parts):
            logger.debug(
                "Parsed transcript %r into %d parts (%d commands)",
                transcript,
                len(parts),
                sum(1 for part in parts if part.command),
            )
        return parts
