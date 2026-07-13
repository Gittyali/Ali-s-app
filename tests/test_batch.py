"""Tests for the sequential "Read All Pages" batch pipeline."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from PIL import Image

from app.core.controller import AppController, BatchSummary, PageReadSpec, ReadOutcome
from app.document.model import BlockType, InlineSpan, ParagraphBlock, StructuredDocument
from app.settings.settings_manager import SettingsManager


def _pump_until(qapp, condition, timeout: float = 10.0) -> None:
    from PySide6.QtCore import QEventLoop

    deadline = time.time() + timeout
    while time.time() < deadline:
        qapp.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 25)
        if condition():
            return
    raise AssertionError("Timed out waiting for batch signals")


def _document(text: str) -> StructuredDocument:
    return StructuredDocument(
        blocks=[
            ParagraphBlock(
                block_type=BlockType.PARAGRAPH, spans=[InlineSpan(text=text)]
            )
        ]
    )


@pytest.fixture()
def specs(tmp_path: Path) -> list[PageReadSpec]:
    result = []
    for index in range(4):
        image_path = tmp_path / f"page{index}.png"
        Image.new("RGB", (60, 80), "white").save(image_path)
        result.append(
            PageReadSpec(
                page_id=f"page-{index}",
                image_path=image_path,
                label=f"Page {index + 1}",
            )
        )
    return result


@pytest.fixture()
def controller(qapp) -> AppController:
    return AppController(SettingsManager())


class TestBatchRead:
    def test_order_preserved(self, qapp, controller, specs, monkeypatch) -> None:
        monkeypatch.setattr(
            AppController,
            "_recognize",
            lambda self, page_id, image, snapshot, provider: ReadOutcome(
                page_id, _document(f"content {page_id}")
            ),
        )
        received: list[str] = []
        summaries: list[BatchSummary] = []
        controller.read_finished.connect(lambda o: received.append(o.page_id))
        controller.batch_finished.connect(summaries.append)

        controller.read_all_pages(specs)
        _pump_until(qapp, lambda: summaries)

        assert received == [spec.page_id for spec in specs]
        assert summaries[0].succeeded == 4
        assert summaries[0].failures == []
        assert not summaries[0].cancelled
        assert not controller.is_batch_active

    def test_failure_does_not_stop_batch(
        self, qapp, controller, specs, monkeypatch
    ) -> None:
        def recognize(self, page_id, image, snapshot, provider):
            if page_id == "page-1":
                raise RuntimeError("provider exploded")
            return ReadOutcome(page_id, _document(page_id))

        monkeypatch.setattr(AppController, "_recognize", recognize)
        received: list[str] = []
        failed: list[str] = []
        summaries: list[BatchSummary] = []
        controller.read_finished.connect(lambda o: received.append(o.page_id))
        controller.batch_page_failed.connect(lambda pid, _msg: failed.append(pid))
        controller.batch_finished.connect(summaries.append)

        controller.read_all_pages(specs)
        _pump_until(qapp, lambda: summaries)

        assert received == ["page-0", "page-2", "page-3"]
        assert failed == ["page-1"]
        summary = summaries[0]
        assert summary.succeeded == 3
        assert summary.failures == [("Page 2", "provider exploded")]

    def test_missing_image_is_a_page_failure(
        self, qapp, controller, specs, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            AppController,
            "_recognize",
            lambda self, page_id, image, snapshot, provider: ReadOutcome(
                page_id, _document(page_id)
            ),
        )
        specs[2].image_path.unlink()  # simulate a page whose file vanished
        summaries: list[BatchSummary] = []
        controller.batch_finished.connect(summaries.append)

        controller.read_all_pages(specs)
        _pump_until(qapp, lambda: summaries)

        assert summaries[0].succeeded == 3
        assert len(summaries[0].failures) == 1
        assert summaries[0].failures[0][0] == "Page 3"

    def test_cancellation(self, qapp, controller, specs, monkeypatch) -> None:
        def recognize(self, page_id, image, snapshot, provider):
            if page_id == "page-0":
                controller.cancel_batch()  # user cancels during page 1
            return ReadOutcome(page_id, _document(page_id))

        monkeypatch.setattr(AppController, "_recognize", recognize)
        received: list[str] = []
        summaries: list[BatchSummary] = []
        controller.read_finished.connect(lambda o: received.append(o.page_id))
        controller.batch_finished.connect(summaries.append)

        controller.read_all_pages(specs)
        _pump_until(qapp, lambda: summaries)

        assert received == ["page-0"]  # the in-flight page still completes
        assert summaries[0].cancelled
        assert summaries[0].succeeded == 1

    def test_empty_batch_finishes_immediately(self, qapp, controller) -> None:
        summaries: list[BatchSummary] = []
        controller.batch_finished.connect(summaries.append)
        controller.read_all_pages([])
        assert summaries and summaries[0].total == 0

    def test_second_batch_rejected_while_running(
        self, qapp, controller, specs, monkeypatch
    ) -> None:
        def slow_recognize(self, page_id, image, snapshot, provider):
            time.sleep(0.05)
            return ReadOutcome(page_id, _document(page_id))

        monkeypatch.setattr(AppController, "_recognize", slow_recognize)
        summaries: list[BatchSummary] = []
        controller.batch_finished.connect(summaries.append)

        controller.read_all_pages(specs)
        controller.read_all_pages(specs)  # must be ignored
        _pump_until(qapp, lambda: summaries)

        assert len(summaries) == 1
        assert summaries[0].total == 4


class TestNoiseFiltering:
    def test_low_confidence_lines_dropped(self) -> None:
        from app.ocr.base import OCRLine, OCRResult, OCRWord
        from app.ocr.layout import reconstruct_document

        def line(text: str, top: int, confidence: float) -> OCRLine:
            return OCRLine(
                words=[
                    OCRWord(
                        text=text,
                        left=50,
                        top=top,
                        width=200,
                        height=20,
                        confidence=confidence,
                    )
                ]
            )

        result = OCRResult(
            lines=[
                line("Real paragraph text", top=100, confidence=0.92),
                line("CONFIDENTIAL~~watermark##", top=140, confidence=0.15),
            ],
            image_width=1000,
            image_height=1400,
        )
        document = reconstruct_document(result)
        text = document.plain_text()
        assert "Real paragraph" in text
        assert "watermark" not in text

    def test_prompt_ignores_decoration(self) -> None:
        from app.vision.prompts import build_user_prompt

        lowered = build_user_prompt(
            ignore_underlines=True, ignore_watermarks=True
        ).lower()
        assert "watermark" in lowered
        assert "highlight" in lowered
        assert "decorative" in lowered
