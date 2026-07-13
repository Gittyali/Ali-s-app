"""Application controller: orchestrates recognition jobs.

The controller owns the "Read Current Page" pipeline.  It decides between
plain OCR reconstruction and AI vision (based on settings), runs the work on
the thread pool, and reports back through Qt signals.  It knows nothing
about widgets, which keeps it unit-testable.
"""

from __future__ import annotations

import logging

from PIL import Image
from PySide6.QtCore import QObject, Signal

from app.document.model import StructuredDocument
from app.formatting.markdown_parser import parse_markdown
from app.ocr.base import OCREngineNotAvailableError, OCRResult
from app.ocr.factory import create_engine
from app.ocr.layout import reconstruct_document
from app.settings.settings_manager import SettingsManager
from app.utils.workers import run_in_background
from app.vision.base import VisionProviderError
from app.vision.factory import create_provider

logger = logging.getLogger(__name__)


class ReadOutcome:
    """Result bundle of one page-reading job."""

    def __init__(
        self,
        page_id: str,
        document: StructuredDocument,
        warning: str = "",
        used_ai: bool = False,
    ) -> None:
        self.page_id = page_id
        self.document = document
        self.warning = warning
        self.used_ai = used_ai


class AppController(QObject):
    """Runs recognition pipelines in the background.

    Signals:
        * ``read_started(str)`` — page_id.
        * ``read_finished(object)`` — a :class:`ReadOutcome`.
        * ``read_failed(str, str)`` — page_id, user-readable error.
        * ``read_progress(str, str)`` — page_id, stage description.
    """

    read_started = Signal(str)
    read_finished = Signal(object)
    read_failed = Signal(str, str)
    read_progress = Signal(str, str)

    def __init__(self, settings: SettingsManager, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._busy_pages: set[str] = set()

    def is_page_busy(self, page_id: str) -> bool:
        return page_id in self._busy_pages

    # ------------------------------------------------------------ pipeline
    def read_page(self, page_id: str, image: Image.Image) -> None:
        """Start recognising *image* for *page_id* (returns immediately)."""
        if page_id in self._busy_pages:
            logger.warning("Page %s is already being read; ignoring", page_id)
            return
        self._busy_pages.add(page_id)
        self.read_started.emit(page_id)

        settings_snapshot = {
            "ocr_engine": self._settings.ocr_engine,
            "ocr_languages": self._settings.ocr_languages,
            "tesseract_path": self._settings.tesseract_path,
        }
        provider = create_provider(self._settings)

        run_in_background(
            self._read_pipeline,
            page_id,
            image,
            settings_snapshot,
            provider,
            on_result=self._on_pipeline_result,
            on_error=lambda message, pid=page_id: self._on_pipeline_error(pid, message),
        )

    def _read_pipeline(
        self,
        page_id: str,
        image: Image.Image,
        settings_snapshot: dict[str, str],
        provider: object,
        progress_callback: object = None,
    ) -> ReadOutcome:
        """Runs on a worker thread. Must not touch Qt widgets."""

        def report(stage: str) -> None:
            self.read_progress.emit(page_id, stage)

        ocr_result: OCRResult | None = None
        ocr_error = ""
        report("Running OCR…")
        try:
            engine = create_engine(
                settings_snapshot["ocr_engine"],
                tesseract_path=settings_snapshot["tesseract_path"],
            )
            ocr_result = engine.recognize(image, settings_snapshot["ocr_languages"])
        except (OCREngineNotAvailableError, RuntimeError) as exc:
            ocr_error = str(exc)
            logger.warning("OCR unavailable/failed for page %s: %s", page_id, exc)

        # Preferred path: AI reconstruction with the OCR text as a hint.
        if provider is not None:
            report("Asking the AI to reconstruct the page…")
            try:
                hint = ocr_result.text if ocr_result is not None else ""
                markdown = provider.read_page(image, ocr_hint=hint)  # type: ignore[attr-defined]
                document = parse_markdown(markdown)
                if not document.is_empty():
                    return ReadOutcome(page_id, document, used_ai=True)
                logger.warning("AI returned an empty document for page %s", page_id)
            except VisionProviderError as exc:
                logger.warning("Vision provider failed for page %s: %s", page_id, exc)
                if ocr_result is not None:
                    return ReadOutcome(
                        page_id,
                        reconstruct_document(ocr_result),
                        warning=f"AI reading failed ({exc}); used OCR instead.",
                    )
                raise RuntimeError(
                    f"AI reading failed: {exc}"
                    + (f" OCR also failed: {ocr_error}" if ocr_error else "")
                ) from exc

        # OCR-only path.
        if ocr_result is None:
            raise RuntimeError(
                ocr_error
                or "No OCR engine or AI provider is available. Configure one in Settings."
            )
        report("Reconstructing layout…")
        document = reconstruct_document(ocr_result)
        warning = ""
        if ocr_result.mean_confidence and ocr_result.mean_confidence < 0.55:
            warning = (
                "OCR confidence was low on this page. Consider enabling image "
                "enhancement or configuring an AI provider for better results."
            )
        return ReadOutcome(page_id, document, warning=warning)

    # ------------------------------------------------------------- results
    def _on_pipeline_result(self, outcome: ReadOutcome) -> None:
        self._busy_pages.discard(outcome.page_id)
        self.read_finished.emit(outcome)

    def _on_pipeline_error(self, page_id: str, message: str) -> None:
        self._busy_pages.discard(page_id)
        self.read_failed.emit(page_id, message)
