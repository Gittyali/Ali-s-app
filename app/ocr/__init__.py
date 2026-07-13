"""OCR subsystem.

An abstract :class:`~app.ocr.base.OCREngine` interface with three concrete
implementations (Tesseract, EasyOCR, PaddleOCR).  The rest of the application
talks only to the interface and the :mod:`~app.ocr.factory`, so engines can
be added or swapped without touching any other module.
"""

from app.ocr.base import OCREngine, OCRLine, OCRResult, OCRWord
from app.ocr.factory import available_engines, create_engine

__all__ = [
    "OCREngine",
    "OCRLine",
    "OCRResult",
    "OCRWord",
    "available_engines",
    "create_engine",
]
