"""EasyOCR backend.

Languages are comma-separated EasyOCR codes, e.g. ``en`` or ``en,ur``.
The reader (which loads neural network weights) is created once per language
set and cached, because construction is expensive.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from PIL import Image

from app.ocr.base import (
    OCREngine,
    OCREngineNotAvailableError,
    OCRResult,
    OCRWord,
    group_words_into_lines,
)

logger = logging.getLogger(__name__)

# Map common Tesseract-style codes to EasyOCR codes so one settings value
# works across engines.
_LANGUAGE_ALIASES = {"eng": "en", "urd": "ur"}


class EasyOCREngine(OCREngine):
    """OCR engine backed by the EasyOCR neural network models."""

    engine_id = "easyocr"
    display_name = "EasyOCR"

    def __init__(self) -> None:
        self._reader: Any = None
        self._reader_languages: tuple[str, ...] = ()

    @classmethod
    def is_available(cls) -> bool:
        try:
            import easyocr  # noqa: F401
        except ImportError:
            return False
        return True

    @staticmethod
    def _normalise_languages(languages: str) -> tuple[str, ...]:
        parts = [
            part.strip() for part in languages.replace("+", ",").split(",") if part.strip()
        ]
        normalised = tuple(_LANGUAGE_ALIASES.get(part, part) for part in parts)
        return normalised or ("en",)

    def _get_reader(self, languages: tuple[str, ...]) -> Any:
        import easyocr

        if self._reader is None or self._reader_languages != languages:
            logger.info("Creating EasyOCR reader for languages %s", languages)
            self._reader = easyocr.Reader(list(languages), gpu=False, verbose=False)
            self._reader_languages = languages
        return self._reader

    def recognize(self, image: Image.Image, languages: str) -> OCRResult:
        """Run EasyOCR and group its fragments into lines geometrically."""
        if not self.is_available():
            raise OCREngineNotAvailableError(
                "EasyOCR is not installed. Run: pip install easyocr"
            )
        reader = self._get_reader(self._normalise_languages(languages))
        array = np.array(image.convert("RGB"))
        try:
            detections = reader.readtext(array)
        except Exception as exc:
            raise RuntimeError(f"EasyOCR recognition failed: {exc}") from exc

        words: list[OCRWord] = []
        for bbox, text, confidence in detections:
            text = str(text).strip()
            if not text:
                continue
            xs = [point[0] for point in bbox]
            ys = [point[1] for point in bbox]
            left, top = int(min(xs)), int(min(ys))
            words.append(
                OCRWord(
                    text=text,
                    left=left,
                    top=top,
                    width=int(max(xs)) - left,
                    height=int(max(ys)) - top,
                    confidence=float(confidence),
                )
            )

        lines = group_words_into_lines(words)
        logger.info("EasyOCR recognised %d lines", len(lines))
        return OCRResult(
            lines=lines,
            image_width=image.width,
            image_height=image.height,
            engine_id=self.engine_id,
        )
