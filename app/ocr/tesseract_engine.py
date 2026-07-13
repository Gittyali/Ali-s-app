"""Tesseract OCR backend (via ``pytesseract``).

Languages use Tesseract syntax, e.g. ``eng``, ``urd`` or ``eng+urd``.
On Windows the binary path can be set in Settings if tesseract.exe is not on
PATH (typically ``C:\\Program Files\\Tesseract-OCR\\tesseract.exe``).
"""

from __future__ import annotations

import logging
import shutil

from PIL import Image

from app.ocr.base import (
    OCREngine,
    OCREngineNotAvailableError,
    OCRLine,
    OCRResult,
    OCRWord,
)

logger = logging.getLogger(__name__)


class TesseractEngine(OCREngine):
    """OCR engine backed by the Tesseract binary."""

    engine_id = "tesseract"
    display_name = "Tesseract"

    def __init__(self, binary_path: str = "") -> None:
        self._binary_path = binary_path.strip()

    @classmethod
    def is_available(cls) -> bool:
        try:
            import pytesseract  # noqa: F401
        except ImportError:
            return False
        return True

    def _configure(self) -> None:
        import pytesseract

        if self._binary_path:
            pytesseract.pytesseract.tesseract_cmd = self._binary_path
        elif shutil.which("tesseract") is None:
            raise OCREngineNotAvailableError(
                "The Tesseract binary was not found on PATH. Install it from "
                "https://github.com/UB-Mannheim/tesseract/wiki or set its "
                "location in Settings > OCR."
            )

    def recognize(self, image: Image.Image, languages: str) -> OCRResult:
        """Run Tesseract and convert its TSV output into geometric lines."""
        if not self.is_available():
            raise OCREngineNotAvailableError(
                "pytesseract is not installed. Run: pip install pytesseract"
            )
        import pytesseract

        self._configure()
        lang = languages.strip() or "eng"
        try:
            data = pytesseract.image_to_data(
                image, lang=lang, output_type=pytesseract.Output.DICT
            )
        except pytesseract.TesseractError as exc:
            raise RuntimeError(
                f"Tesseract failed (language '{lang}'): {exc}. "
                "Check that the language data files are installed."
            ) from exc

        lines: list[OCRLine] = []
        current_key: tuple[int, int, int] | None = None
        current_words: list[OCRWord] = []
        for index in range(len(data["text"])):
            text = str(data["text"][index]).strip()
            if not text:
                continue
            try:
                confidence = float(data["conf"][index])
            except (TypeError, ValueError):
                confidence = 0.0
            if confidence < 0:
                continue
            key = (
                int(data["block_num"][index]),
                int(data["par_num"][index]),
                int(data["line_num"][index]),
            )
            word = OCRWord(
                text=text,
                left=int(data["left"][index]),
                top=int(data["top"][index]),
                width=int(data["width"][index]),
                height=int(data["height"][index]),
                confidence=confidence / 100.0,
            )
            if key != current_key:
                if current_words:
                    lines.append(OCRLine(words=current_words))
                current_key = key
                current_words = [word]
            else:
                current_words.append(word)
        if current_words:
            lines.append(OCRLine(words=current_words))

        logger.info("Tesseract recognised %d lines (lang=%s)", len(lines), lang)
        return OCRResult(
            lines=lines,
            image_width=image.width,
            image_height=image.height,
            engine_id=self.engine_id,
        )
