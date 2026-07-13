"""OCR engine registry and factory.

New engines are added by appending one entry to ``_ENGINE_CLASSES``; nothing
else in the application changes.
"""

from __future__ import annotations

import logging

from app.ocr.base import OCREngine, OCREngineNotAvailableError
from app.ocr.easyocr_engine import EasyOCREngine
from app.ocr.paddleocr_engine import PaddleOCREngine
from app.ocr.tesseract_engine import TesseractEngine

logger = logging.getLogger(__name__)

_ENGINE_CLASSES: dict[str, type[OCREngine]] = {
    TesseractEngine.engine_id: TesseractEngine,
    EasyOCREngine.engine_id: EasyOCREngine,
    PaddleOCREngine.engine_id: PaddleOCREngine,
}


def available_engines() -> dict[str, str]:
    """Map of ``engine_id -> display_name`` for engines usable right now."""
    return {
        engine_id: cls.display_name
        for engine_id, cls in _ENGINE_CLASSES.items()
        if cls.is_available()
    }


def all_engines() -> dict[str, str]:
    """Map of every known ``engine_id -> display_name`` (installed or not)."""
    return {engine_id: cls.display_name for engine_id, cls in _ENGINE_CLASSES.items()}


def create_engine(engine_id: str, tesseract_path: str = "") -> OCREngine:
    """Instantiate the requested engine, falling back to any available one.

    Raises :class:`OCREngineNotAvailableError` when no engine is installed.
    """
    cls = _ENGINE_CLASSES.get(engine_id)
    if cls is not None and cls.is_available():
        if cls is TesseractEngine:
            return TesseractEngine(binary_path=tesseract_path)
        return cls()

    for fallback_id, fallback_cls in _ENGINE_CLASSES.items():
        if fallback_cls.is_available():
            logger.warning(
                "OCR engine '%s' unavailable; falling back to '%s'",
                engine_id,
                fallback_id,
            )
            if fallback_cls is TesseractEngine:
                return TesseractEngine(binary_path=tesseract_path)
            return fallback_cls()

    raise OCREngineNotAvailableError(
        "No OCR engine is installed. Install one of: pytesseract (plus the "
        "Tesseract binary), easyocr, or paddleocr — see requirements.txt."
    )
