"""Tests for sidebar ordering, append/replace output, prompt flags,
retry behaviour and the stop-on-error batch option."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from PIL import Image

import app.core.controller as controller_module
from app.core.controller import (
    AppController,
    BatchSummary,
    PageReadSpec,
    ReadOutcome,
    _is_transient_provider_error,
)
from app.core.project import Project
from app.document.model import BlockType, InlineSpan, ParagraphBlock, StructuredDocument
from app.settings.settings_manager import SettingsManager
from app.vision.base import VisionProviderError
from app.vision.prompts import build_user_prompt


def _document(text: str) -> StructuredDocument:
    return StructuredDocument(
        blocks=[
            ParagraphBlock(
                block_type=BlockType.PARAGRAPH, spans=[InlineSpan(text=text)]
            )
        ]
    )


def _pump_until(qapp, condition, timeout: float = 10.0) -> None:
    from PySide6.QtCore import QEventLoop

    deadline = time.time() + timeout
    while time.time() < deadline:
        qapp.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 25)
        if condition():
            return
    raise AssertionError("Timed out waiting for signals")


class TestSidebarOrdering:
    def test_reorder_valid_permutation(self, tmp_path: Path) -> None:
        project = Project.create(tmp_path / "p.adaproj")
        images = []
        for index in range(3):
            path = tmp_path / f"img{index}.png"
            Image.new("RGB", (40, 40), "white").save(path)
            images.append(path)
        project.import_files(images)
        ids = [page.page_id for page in project.pages]

        assert project.reorder([ids[2], ids[0], ids[1]])
        assert [page.page_id for page in project.pages] == [ids[2], ids[0], ids[1]]
        assert project.modified

    def test_reorder_rejects_bad_id_list(self, tmp_path: Path) -> None:
        project = Project.create(tmp_path / "p.adaproj")
        path = tmp_path / "img.png"
        Image.new("RGB", (40, 40), "white").save(path)
        project.import_files([path])
        original = [page.page_id for page in project.pages]

        assert not project.reorder(["bogus-id"])
        assert not project.reorder([])
        assert [page.page_id for page in project.pages] == original

    def test_processing_follows_project_order(self, tmp_path: Path) -> None:
        """Specs built from project.pages inherit the sidebar order."""
        project = Project.create(tmp_path / "p.adaproj")
        images = []
        for index in range(3):
            path = tmp_path / f"img{index}.png"
            Image.new("RGB", (40, 40), "white").save(path)
            images.append(path)
        project.import_files(images)
        ids = [page.page_id for page in project.pages]
        project.reorder([ids[1], ids[2], ids[0]])

        specs = [PageReadSpec(page.page_id, page.image_path) for page in project.pages]
        assert [spec.page_id for spec in specs] == [ids[1], ids[2], ids[0]]


class TestAppendMode:
    def test_append_preserves_order_with_blank_line(self, qapp) -> None:
        from PySide6.QtGui import QTextDocument

        from app.formatting.rich_text import append_structured_document

        target = QTextDocument()
        append_structured_document(target, _document("page one text"))
        append_structured_document(target, _document("page two text"))
        append_structured_document(target, _document("page three text"))

        plain = target.toPlainText()
        assert plain.index("page one") < plain.index("page two") < plain.index(
            "page three"
        )
        # A blank line separates consecutive pages.
        assert "\n\n" in plain.replace(" ", "\n")

    def test_append_separator_marker(self, qapp) -> None:
        from PySide6.QtGui import QTextDocument

        from app.formatting.rich_text import append_structured_document

        target = QTextDocument()
        append_structured_document(target, _document("alpha"), "— Page 1 —")
        append_structured_document(target, _document("beta"), "— Page 2 —")
        plain = target.toPlainText()
        assert "— Page 1 —" in plain
        assert "— Page 2 —" in plain
        assert plain.index("— Page 2 —") > plain.index("alpha")

    def test_first_append_has_no_leading_blank(self, qapp) -> None:
        from PySide6.QtGui import QTextDocument

        from app.formatting.rich_text import append_structured_document

        target = QTextDocument()
        append_structured_document(target, _document("only page"))
        assert not target.toPlainText().startswith("\n\n")

    def test_replace_mode_keeps_single_page_content(self, qapp) -> None:
        """insert_document(replace=True) fully replaces prior content."""
        from app.ui.editor import DocumentEditor

        editor = DocumentEditor()
        editor.insert_document(_document("old content"), replace=True)
        editor.insert_document(_document("new content"), replace=True)
        plain = editor._edit.toPlainText()
        assert "new content" in plain
        assert "old content" not in plain


class TestPromptFlags:
    def test_underline_clause_toggles(self) -> None:
        with_clause = build_user_prompt(ignore_underlines=True, ignore_watermarks=False)
        without = build_user_prompt(ignore_underlines=False, ignore_watermarks=False)
        assert "underline" in with_clause.lower()
        assert "decorative underline" not in without.lower()

    def test_watermark_clause_toggles(self) -> None:
        with_clause = build_user_prompt(ignore_underlines=False, ignore_watermarks=True)
        without = build_user_prompt(ignore_underlines=False, ignore_watermarks=False)
        assert "watermark" in with_clause.lower()
        assert "watermark" not in without.lower()

    def test_unclear_marker_always_present(self) -> None:
        assert "[unclear]" in build_user_prompt()

    def test_no_hallucination_rules_always_present(self) -> None:
        lowered = build_user_prompt().lower()
        assert "do not summarize" in lowered
        assert "hallucinate" in lowered


class TestProviderRetry:
    def test_transient_detection(self) -> None:
        assert _is_transient_provider_error("Anthropic API error 429: slow down")
        assert _is_transient_provider_error("Could not reach the Gemini API")
        assert _is_transient_provider_error("error 503: overloaded")
        assert not _is_transient_provider_error("API error 401: bad key")

    def test_retry_then_success(self, qapp, monkeypatch) -> None:
        monkeypatch.setattr(controller_module.time, "sleep", lambda _s: None)
        controller = AppController(SettingsManager())
        snapshot = {"ignore_underlines": True, "ignore_watermarks": True}
        calls = []

        class FlakyProvider:
            def read_page(self, image, ocr_hint="", **kwargs):
                calls.append(1)
                if len(calls) < 3:
                    raise VisionProviderError("error 503: overloaded")
                return "# Recovered"

        result = controller._call_provider_with_retry(
            FlakyProvider(), Image.new("RGB", (10, 10)), "", snapshot, "p1"
        )
        assert result == "# Recovered"
        assert len(calls) == 3

    def test_no_retry_for_permanent_errors(self, qapp, monkeypatch) -> None:
        monkeypatch.setattr(controller_module.time, "sleep", lambda _s: None)
        controller = AppController(SettingsManager())
        snapshot = {"ignore_underlines": True, "ignore_watermarks": True}
        calls = []

        class AuthFailProvider:
            def read_page(self, image, ocr_hint="", **kwargs):
                calls.append(1)
                raise VisionProviderError("API error 401: invalid key")

        with pytest.raises(VisionProviderError):
            controller._call_provider_with_retry(
                AuthFailProvider(), Image.new("RGB", (10, 10)), "", snapshot, "p1"
            )
        assert len(calls) == 1


class TestStopOnError:
    def test_batch_stops_when_continue_disabled(
        self, qapp, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            SettingsManager, "continue_after_error", property(lambda self: False)
        )

        def recognize(self, page_id, image, snapshot, provider):
            if page_id == "page-1":
                raise RuntimeError("boom")
            return ReadOutcome(page_id, _document(page_id))

        monkeypatch.setattr(AppController, "_recognize", recognize)
        controller = AppController(SettingsManager())

        specs = []
        for index in range(4):
            path = tmp_path / f"p{index}.png"
            Image.new("RGB", (30, 30), "white").save(path)
            specs.append(
                PageReadSpec(
                    page_id=f"page-{index}", image_path=path, label=f"Page {index+1}"
                )
            )

        received: list[str] = []
        summaries: list[BatchSummary] = []
        controller.read_finished.connect(lambda o: received.append(o.page_id))
        controller.batch_finished.connect(summaries.append)
        controller.read_all_pages(specs)
        _pump_until(qapp, lambda: summaries)

        assert received == ["page-0"]  # stopped right after the failure
        assert summaries[0].succeeded == 1
        assert len(summaries[0].failures) == 1
