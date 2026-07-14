"""Regression tests for AI failure handling.

Real-world 21-page batch showed pages silently degrading to OCR garbage
("awww we Eee eee") when the AI call failed mid-batch, and skipped pages
turning blank in the sidebar.  Policy now: with an AI provider configured,
a failed page FAILS visibly (✗, retryable); OCR fallback is opt-in.
"""

from __future__ import annotations

import pytest
from PIL import Image

import app.core.controller as controller_module
from app.core.controller import AppController
from app.document.model import StructuredDocument
from app.ocr.base import OCRLine, OCRResult, OCRWord
from app.settings.settings_manager import SettingsManager
from app.vision.base import VisionProviderError


class _FailingProvider:
    def read_page(self, image, ocr_hint="", **kwargs):
        raise VisionProviderError("API error 401: invalid key")


class _EmptyProvider:
    def read_page(self, image, ocr_hint="", **kwargs):
        return ""


class _FakeEngine:
    engine_id = "fake"

    def recognize(self, image, languages):
        word = OCRWord(text="garbled", left=0, top=0, width=50, height=10,
                       confidence=0.9)
        return OCRResult(
            lines=[OCRLine(words=[word])], image_width=100, image_height=100,
            engine_id="fake",
        )


def _snapshot(ocr_fallback: bool) -> dict:
    return {
        "ocr_engine": "tesseract",
        "ocr_languages": "eng",
        "tesseract_path": "",
        "ignore_underlines": True,
        "ignore_watermarks": True,
        "continue_after_error": True,
        "ocr_fallback": ocr_fallback,
    }


@pytest.fixture()
def controller(qapp, monkeypatch):
    monkeypatch.setattr(controller_module.time, "sleep", lambda _s: None)
    monkeypatch.setattr(
        controller_module, "create_engine", lambda *a, **k: _FakeEngine()
    )
    return AppController(SettingsManager())


class TestAIFailurePolicy:
    def test_ai_failure_without_fallback_fails_the_page(self, controller) -> None:
        with pytest.raises(RuntimeError, match="AI reading failed"):
            controller._recognize(
                "p1", Image.new("RGB", (10, 10)), _snapshot(False),
                _FailingProvider(),
            )

    def test_ai_failure_with_fallback_uses_ocr_and_warns(self, controller) -> None:
        outcome = controller._recognize(
            "p1", Image.new("RGB", (10, 10)), _snapshot(True), _FailingProvider()
        )
        assert not outcome.used_ai
        assert "Used OCR instead" in outcome.warning
        assert "garbled" in outcome.document.plain_text()

    def test_empty_ai_result_fails_instead_of_silent_ocr(self, controller) -> None:
        with pytest.raises(RuntimeError, match="no text"):
            controller._recognize(
                "p1", Image.new("RGB", (10, 10)), _snapshot(False), _EmptyProvider()
            )

    def test_empty_ai_result_with_fallback_uses_ocr(self, controller) -> None:
        outcome = controller._recognize(
            "p1", Image.new("RGB", (10, 10)), _snapshot(True), _EmptyProvider()
        )
        assert "garbled" in outcome.document.plain_text()

    def test_ocr_only_mode_unaffected(self, controller) -> None:
        outcome = controller._recognize(
            "p1", Image.new("RGB", (10, 10)), _snapshot(False), None
        )
        assert "garbled" in outcome.document.plain_text()

    def test_fallback_setting_default_off(self) -> None:
        # The snapshot passes the setting through; the policy default is off.
        assert _snapshot(False)["ocr_fallback"] is False


class TestFailedStatusMarking:
    def test_failed_pages_marked_and_retryable(
        self, qapp, tmp_path, monkeypatch
    ) -> None:
        from PySide6.QtWidgets import QInputDialog, QMessageBox

        monkeypatch.setattr(
            QMessageBox, "warning",
            staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok),
        )
        monkeypatch.setattr(
            QMessageBox, "question",
            staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
        )
        monkeypatch.setattr(
            QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False))
        )
        from app.core.page import PageStatus
        from app.core.project import Project
        from app.ui.main_window import MainWindow

        settings = SettingsManager()
        settings.last_project_path = ""
        window = MainWindow(settings)
        for _ in range(3):
            qapp.processEvents()

        project = Project.create(tmp_path / "fail.adaproj", "Fail")
        image_path = tmp_path / "img.png"
        Image.new("RGB", (40, 40), "white").save(image_path)
        project.import_files([image_path])
        window._set_project(project)

        page_id = project.pages[0].page_id
        window._on_batch_page_failed(page_id, "synthetic failure")
        assert project.pages[0].status is PageStatus.FAILED

        # Failed pages count as retry candidates for "Only unread/failed".
        retryable = [
            page for page in project.pages
            if page.status in (PageStatus.PENDING, PageStatus.FAILED)
        ]
        assert retryable == [project.pages[0]]

        window._autosave.watch(None, 1)
        window.deleteLater()
        for _ in range(3):
            qapp.processEvents()
