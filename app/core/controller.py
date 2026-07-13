"""Application controller: orchestrates recognition jobs.

The controller owns the "Read Current Page" pipeline and the sequential
"Read All Pages" batch pipeline.  It decides between plain OCR
reconstruction and AI vision (based on settings), runs the work on the
thread pool, and reports back through Qt signals.  It knows nothing about
widgets, which keeps it unit-testable.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, Signal

from app.document.model import StructuredDocument
from app.formatting.markdown_parser import parse_markdown
from app.ocr.base import OCREngineNotAvailableError, OCRResult
from app.ocr.factory import create_engine
from app.ocr.layout import reconstruct_document
from app.settings.settings_manager import SettingsManager
from app.utils.image_utils import apply_adjustments, load_image, rotate_image
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


@dataclass
class PageReadSpec:
    """Everything the batch pipeline needs to read one page from disk.

    Carrying the stored view adjustments means a batch read sees exactly
    what the user would see opening the page (rotation fixed, enhanced...).
    """

    page_id: str
    image_path: Path
    rotation: int = 0
    brightness: float = 1.0
    contrast: float = 1.0
    enhanced: bool = False
    label: str = ""  # human-readable name for progress/error reports


@dataclass
class BatchSummary:
    """Final report of a "Read All Pages" run."""

    total: int
    succeeded: int
    failures: list[tuple[str, str]]  # (page label, error message)
    cancelled: bool


class AppController(QObject):
    """Runs recognition pipelines in the background.

    Single-page signals:
        * ``read_started(str)`` — page_id.
        * ``read_finished(object)`` — a :class:`ReadOutcome`.
        * ``read_failed(str, str)`` — page_id, user-readable error.
        * ``read_progress(str, str)`` — page_id, stage description.

    Batch signals (Read All Pages):
        * ``batch_started(int)`` — total page count.
        * ``batch_progress(int, int, str)`` — 1-based current page number,
          total, page_id now being read.
        * ``batch_page_failed(str, str)`` — page_id, error (batch continues).
        * ``batch_finished(object)`` — a :class:`BatchSummary`.

    Successful batch pages are delivered through the same
    ``read_finished`` signal as single reads, so storage/UI handling is
    identical for both paths.
    """

    read_started = Signal(str)
    read_finished = Signal(object)
    read_failed = Signal(str, str)
    read_progress = Signal(str, str)

    batch_started = Signal(int)
    batch_progress = Signal(int, int, str)
    batch_page_failed = Signal(str, str)
    batch_finished = Signal(object)

    def __init__(self, settings: SettingsManager, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._busy_pages: set[str] = set()
        self._batch_active = False
        self._batch_cancel = threading.Event()

    def is_page_busy(self, page_id: str) -> bool:
        return page_id in self._busy_pages or self._batch_active

    @property
    def is_batch_active(self) -> bool:
        return self._batch_active

    def _settings_snapshot(self) -> dict[str, str]:
        """Copy the OCR settings so a running job is immune to edits."""
        return {
            "ocr_engine": self._settings.ocr_engine,
            "ocr_languages": self._settings.ocr_languages,
            "tesseract_path": self._settings.tesseract_path,
        }

    # ------------------------------------------------------- single page
    def read_page(self, page_id: str, image: Image.Image) -> None:
        """Start recognising *image* for *page_id* (returns immediately)."""
        if self.is_page_busy(page_id):
            logger.warning("Page %s is already being read; ignoring", page_id)
            return
        self._busy_pages.add(page_id)
        self.read_started.emit(page_id)

        snapshot = self._settings_snapshot()
        provider = create_provider(self._settings)

        run_in_background(
            self._recognize,
            page_id,
            image,
            snapshot,
            provider,
            on_result=self._on_pipeline_result,
            on_error=lambda message, pid=page_id: self._on_pipeline_error(pid, message),
        )

    def _recognize(
        self,
        page_id: str,
        image: Image.Image,
        settings_snapshot: dict[str, str],
        provider: object,
    ) -> ReadOutcome:
        """Shared recognition core; runs on a worker thread (no widgets).

        Raises ``RuntimeError`` with a user-readable message when neither
        the AI provider nor OCR can produce content.
        """

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

    def _on_pipeline_result(self, outcome: ReadOutcome) -> None:
        self._busy_pages.discard(outcome.page_id)
        self.read_finished.emit(outcome)

    def _on_pipeline_error(self, page_id: str, message: str) -> None:
        self._busy_pages.discard(page_id)
        self.read_failed.emit(page_id, message)

    # --------------------------------------------------------- batch mode
    def read_all_pages(self, specs: list[PageReadSpec]) -> None:
        """Read *specs* sequentially in the background (Read All Pages).

        Page order is preserved: page N's result is always delivered before
        page N+1 starts.  A failing page is reported and skipped; the batch
        continues with the next page.  :meth:`cancel_batch` stops the run
        after the page currently being processed.
        """
        if self._batch_active:
            logger.warning("A batch read is already running; ignoring")
            return
        if not specs:
            self.batch_finished.emit(BatchSummary(0, 0, [], cancelled=False))
            return

        self._batch_active = True
        self._batch_cancel.clear()
        self.batch_started.emit(len(specs))

        snapshot = self._settings_snapshot()
        provider = create_provider(self._settings)

        run_in_background(
            self._batch_pipeline,
            list(specs),
            snapshot,
            provider,
            on_result=self._on_batch_done,
            on_error=self._on_batch_crashed,
        )

    def cancel_batch(self) -> None:
        """Request the running batch to stop after the current page."""
        if self._batch_active:
            logger.info("Batch read cancellation requested")
            self._batch_cancel.set()

    def _batch_pipeline(
        self,
        specs: list[PageReadSpec],
        settings_snapshot: dict[str, str],
        provider: object,
    ) -> BatchSummary:
        """Sequential batch loop; runs entirely on one worker thread."""
        total = len(specs)
        succeeded = 0
        failures: list[tuple[str, str]] = []
        cancelled = False

        for index, spec in enumerate(specs, start=1):
            if self._batch_cancel.is_set():
                cancelled = True
                break
            self.batch_progress.emit(index, total, spec.page_id)
            try:
                image = load_image(spec.image_path)
                image = rotate_image(image, spec.rotation)
                image = apply_adjustments(
                    image, spec.brightness, spec.contrast, spec.enhanced
                )
                outcome = self._recognize(
                    spec.page_id, image, settings_snapshot, provider
                )
            except Exception as exc:
                # One bad page must never stop the batch.
                logger.warning("Batch: page %d/%d failed: %s", index, total, exc)
                failures.append((spec.label or f"Item {index}", str(exc)))
                self.batch_page_failed.emit(spec.page_id, str(exc))
                continue
            succeeded += 1
            self.read_finished.emit(outcome)

        return BatchSummary(
            total=total, succeeded=succeeded, failures=failures, cancelled=cancelled
        )

    def _on_batch_done(self, summary: BatchSummary) -> None:
        self._batch_active = False
        logger.info(
            "Batch read finished: %d/%d succeeded, %d failed, cancelled=%s",
            summary.succeeded,
            summary.total,
            len(summary.failures),
            summary.cancelled,
        )
        self.batch_finished.emit(summary)

    def _on_batch_crashed(self, message: str) -> None:
        # Defensive: _batch_pipeline catches per-page errors, so this only
        # fires on unexpected infrastructure failures.
        self._batch_active = False
        logger.error("Batch read aborted unexpectedly: %s", message)
        self.batch_finished.emit(
            BatchSummary(
                total=0, succeeded=0, failures=[("Batch", message)], cancelled=False
            )
        )
