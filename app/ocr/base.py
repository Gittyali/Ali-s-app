"""OCR engine interface and result types.

Engines return geometry-aware results (:class:`OCRWord` boxes grouped into
:class:`OCRLine` rows) so the layout analyser can reconstruct headings,
alignment and lists from positions and sizes — not just raw text.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

from PIL import Image


@dataclass
class OCRWord:
    """One recognised word with its bounding box in image pixels."""

    text: str
    left: int
    top: int
    width: int
    height: int
    confidence: float

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


@dataclass
class OCRLine:
    """A horizontal line of words, in reading order."""

    words: list[OCRWord] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(word.text for word in self.words)

    @property
    def left(self) -> int:
        return min((w.left for w in self.words), default=0)

    @property
    def right(self) -> int:
        return max((w.right for w in self.words), default=0)

    @property
    def top(self) -> int:
        return min((w.top for w in self.words), default=0)

    @property
    def bottom(self) -> int:
        return max((w.bottom for w in self.words), default=0)

    @property
    def height(self) -> int:
        heights = sorted(w.height for w in self.words)
        return heights[len(heights) // 2] if heights else 0

    @property
    def confidence(self) -> float:
        if not self.words:
            return 0.0
        return sum(w.confidence for w in self.words) / len(self.words)


@dataclass
class OCRResult:
    """Full result of recognising one page image."""

    lines: list[OCRLine] = field(default_factory=list)
    image_width: int = 0
    image_height: int = 0
    engine_id: str = ""

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def mean_confidence(self) -> float:
        if not self.lines:
            return 0.0
        return sum(line.confidence for line in self.lines) / len(self.lines)


class OCREngineNotAvailableError(RuntimeError):
    """Raised when an engine's backing library or binary is missing."""


class OCREngine(abc.ABC):
    """Contract every OCR backend must fulfil."""

    #: Stable identifier stored in settings (e.g. ``"tesseract"``).
    engine_id: str = ""
    #: Human-readable name shown in the settings dialog.
    display_name: str = ""

    @classmethod
    @abc.abstractmethod
    def is_available(cls) -> bool:
        """Return True when the backend can actually run on this machine."""

    @abc.abstractmethod
    def recognize(self, image: Image.Image, languages: str) -> OCRResult:
        """Recognise text in *image*.

        *languages* uses the engine's own syntax (documented per engine).
        Raises :class:`OCREngineNotAvailableError` if the backend is missing
        and ``RuntimeError`` with a readable message for recognition errors.
        """


def group_words_into_lines(
    words: list[OCRWord], vertical_tolerance_ratio: float = 0.6
) -> list[OCRLine]:
    """Cluster word boxes into text lines by vertical overlap.

    Used by engines whose APIs return flat word/fragment lists.  Words whose
    vertical centres fall within ``tolerance * median_height`` of a line's
    centre join that line; lines are then sorted top-to-bottom and words
    left-to-right.
    """
    if not words:
        return []
    heights = sorted(w.height for w in words if w.height > 0)
    median_height = heights[len(heights) // 2] if heights else 10
    tolerance = max(4.0, median_height * vertical_tolerance_ratio)

    lines: list[list[OCRWord]] = []
    for word in sorted(words, key=lambda w: (w.top, w.left)):
        centre = word.top + word.height / 2
        placed = False
        for line in lines:
            line_centre = sum(w.top + w.height / 2 for w in line) / len(line)
            if abs(centre - line_centre) <= tolerance:
                line.append(word)
                placed = True
                break
        if not placed:
            lines.append([word])

    result = [OCRLine(words=sorted(line, key=lambda w: w.left)) for line in lines]
    result.sort(key=lambda line: line.top)
    return result
