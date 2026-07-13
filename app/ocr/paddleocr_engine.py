"""PaddleOCR backend.

Languages use PaddleOCR codes (single value), e.g. ``en`` or ``ar`` — Urdu
script is covered by PaddleOCR's Arabic-script models.  The OCR pipeline is
cached per language because model loading is expensive.
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

_LANGUAGE_ALIASES = {"eng": "en", "urd": "ar", "ur": "ar"}


class PaddleOCREngine(OCREngine):
    """OCR engine backed by PaddleOCR."""

    engine_id = "paddleocr"
    display_name = "PaddleOCR"

    def __init__(self) -> None:
        self._pipeline: Any = None
        self._pipeline_language: str = ""

    @classmethod
    def is_available(cls) -> bool:
        try:
            import paddleocr  # noqa: F401
        except ImportError:
            return False
        return True

    @staticmethod
    def _normalise_language(languages: str) -> str:
        first = languages.replace("+", ",").split(",")[0].strip() or "en"
        return _LANGUAGE_ALIASES.get(first, first)

    def _get_pipeline(self, language: str) -> Any:
        from paddleocr import PaddleOCR

        if self._pipeline is None or self._pipeline_language != language:
            logger.info("Creating PaddleOCR pipeline for language %s", language)
            self._pipeline = PaddleOCR(lang=language, show_log=False)
            self._pipeline_language = language
        return self._pipeline

    def recognize(self, image: Image.Image, languages: str) -> OCRResult:
        """Run PaddleOCR and group detected fragments into lines."""
        if not self.is_available():
            raise OCREngineNotAvailableError(
                "PaddleOCR is not installed. Run: pip install paddleocr paddlepaddle"
            )
        pipeline = self._get_pipeline(self._normalise_language(languages))
        array = np.array(image.convert("RGB"))
        try:
            raw = pipeline.ocr(array)
        except Exception as exc:
            raise RuntimeError(f"PaddleOCR recognition failed: {exc}") from exc

        words: list[OCRWord] = []
        pages = raw if isinstance(raw, list) else []
        for page in pages:
            if not page:
                continue
            for detection in page:
                try:
                    bbox, (text, confidence) = detection
                except (TypeError, ValueError):
                    continue
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
        logger.info("PaddleOCR recognised %d lines", len(lines))
        return OCRResult(
            lines=lines,
            image_width=image.width,
            image_height=image.height,
            engine_id=self.engine_id,
        )
