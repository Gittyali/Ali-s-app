"""Regression tests for the second round of real-world feedback:

* numbered headings from AI markdown are consistently bold headings;
* empty page extractions count as failures — never a silent "all done";
* page separators are opt-in (off by default);
* in append mode, clicking any page keeps the combined document visible
  and can jump to that page's section via anchors.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from PIL import Image

from app.core.controller import AppController, BatchSummary, PageReadSpec, ReadOutcome
from app.document.model import (
    BlockType,
    InlineSpan,
    ListBlock,
    ParagraphBlock,
    StructuredDocument,
)
from app.formatting.markdown_parser import parse_markdown
from app.settings.settings_manager import SettingsManager


def _document(text: str) -> StructuredDocument:
    return StructuredDocument(
        blocks=[
            ParagraphBlock(
                block_type=BlockType.PARAGRAPH, spans=[InlineSpan(text=text)]
            )
        ]
    )


class TestConsistentHeadings:
    def test_plain_numbered_section_becomes_heading(self) -> None:
        document = parse_markdown("2. RELVANT PROVISION:\n\nSec 246 to 249.")
        first = document.blocks[0]
        assert isinstance(first, ParagraphBlock)
        assert first.block_type is BlockType.SUBHEADING
        assert first.plain_text().startswith("2.")

    def test_uppercase_without_colon_becomes_heading(self) -> None:
        document = parse_markdown("14. DUTIES OF AUDITOR\n\nBody text.")
        assert document.blocks[0].block_type is BlockType.SUBHEADING

    def test_ordinary_numbered_items_stay_lists(self) -> None:
        document = parse_markdown(
            "1. The auditor checks all records carefully.\n"
            "2. The auditor gives an independent opinion."
        )
        block = document.blocks[0]
        assert isinstance(block, ListBlock)
        assert len(block.items) == 2

    def test_unparseable_content_kept_as_raw_text(self) -> None:
        document = parse_markdown("|---|---|")
        assert not document.is_empty()


class TestEmptyPageIsFailure:
    def test_empty_outcome_reported_in_summary(
        self, qapp, tmp_path: Path, monkeypatch
    ) -> None:
        def recognize(self, page_id, image, snapshot, provider):
            if page_id == "page-2":  # the "conclusion" page yields nothing
                return ReadOutcome(page_id, StructuredDocument())
            return ReadOutcome(page_id, _document(page_id))

        monkeypatch.setattr(AppController, "_recognize", recognize)
        controller = AppController(SettingsManager())
        specs = []
        for index in range(3):
            path = tmp_path / f"p{index}.png"
            Image.new("RGB", (30, 30), "white").save(path)
            specs.append(
                PageReadSpec(
                    page_id=f"page-{index}", image_path=path, label=f"Page {index+1}"
                )
            )

        summaries: list[BatchSummary] = []
        controller.batch_finished.connect(summaries.append)
        controller.read_all_pages(specs)

        from PySide6.QtCore import QEventLoop

        deadline = time.time() + 10
        while time.time() < deadline and not summaries:
            qapp.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 25)

        summary = summaries[0]
        assert summary.succeeded == 2
        assert len(summary.failures) == 1
        assert summary.failures[0][0] == "Page 3"
        assert "No text was recognised" in summary.failures[0][1]


class TestAnchors:
    def test_append_tags_sections_with_anchors(self, qapp) -> None:
        from PySide6.QtGui import QTextDocument

        from app.formatting.rich_text import append_structured_document

        target = QTextDocument()
        append_structured_document(target, _document("alpha"), anchor="page-a")
        append_structured_document(target, _document("beta"), anchor="page-b")
        html = target.toHtml()
        assert "page-a" in html
        assert "page-b" in html

    def test_anchors_survive_html_round_trip(self, qapp) -> None:
        from PySide6.QtGui import QTextDocument

        from app.formatting.rich_text import append_structured_document

        target = QTextDocument()
        append_structured_document(target, _document("alpha"), anchor="page-a")
        reloaded = QTextDocument()
        reloaded.setHtml(target.toHtml())
        assert "page-a" in reloaded.toHtml()


@pytest.fixture()
def window(qapp, tmp_path: Path, monkeypatch):
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    monkeypatch.setattr(
        QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok),
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    monkeypatch.setattr(
        QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False))
    )

    from app.core.project import Project
    from app.ui.main_window import MainWindow

    settings = SettingsManager()
    settings.last_project_path = ""
    window = MainWindow(settings)
    # Consume the deferred _startup_project timer while stubs are active.
    for _ in range(3):
        qapp.processEvents()
    project = Project.create(tmp_path / "nav.adaproj", "Nav")
    images = []
    for index in range(3):
        path = tmp_path / f"img{index}.png"
        Image.new("RGB", (60, 80), "white").save(path)
        images.append(path)
    project.import_files(images)
    window._set_project(project)
    yield window
    window._autosave.watch(None, 1)
    window.deleteLater()
    for _ in range(3):
        qapp.processEvents()


class TestCombinedNavigation:
    def _outcome(self, page_id: str, text: str) -> ReadOutcome:
        return ReadOutcome(page_id, _document(text))

    def test_clicking_other_pages_keeps_combined_document(
        self, window, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            SettingsManager, "output_mode", property(lambda self: "append")
        )
        pages = window._project.pages
        window._sidebar.select_page(pages[0].page_id)
        window._activate_page(pages[0].page_id)
        for index, text in enumerate(["alpha text", "bravo text", "charlie text"]):
            window._on_read_finished(self._outcome(pages[index].page_id, text))

        # Click page 2: the editor must still show the whole document.
        window._activate_page(pages[1].page_id)
        plain = window._editor._edit.toPlainText()
        assert "alpha text" in plain
        assert "bravo text" in plain
        assert "charlie text" in plain
        assert window._editor_page_id == pages[0].page_id  # host document
        assert window._active_page_id == pages[1].page_id  # viewer follows

        # Click page 3: still the combined document, never blank.
        window._activate_page(pages[2].page_id)
        assert "charlie text" in window._editor._edit.toPlainText()

    def test_host_persisted_on_project(self, window, monkeypatch) -> None:
        monkeypatch.setattr(
            SettingsManager, "output_mode", property(lambda self: "append")
        )
        pages = window._project.pages
        window._sidebar.select_page(pages[0].page_id)
        window._activate_page(pages[0].page_id)
        window._on_read_finished(self._outcome(pages[0].page_id, "alpha"))
        assert window._project.host_page_id == pages[0].page_id

    def test_legacy_project_without_host_still_shows_content(
        self, window, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            SettingsManager, "output_mode", property(lambda self: "append")
        )
        pages = window._project.pages
        # Simulate a project saved before host tracking existed: content on
        # page 1 only, no host id recorded.
        window._project.set_page_document(
            pages[0].page_id, "<p>combined legacy content</p>", edited_by_user=False
        )
        window._project.host_page_id = ""

        window._activate_page(pages[1].page_id)
        assert "combined legacy content" in window._editor._edit.toPlainText()

    def test_replace_mode_unaffected(self, window, monkeypatch) -> None:
        monkeypatch.setattr(
            SettingsManager, "output_mode", property(lambda self: "replace")
        )
        pages = window._project.pages
        window._sidebar.select_page(pages[0].page_id)
        window._activate_page(pages[0].page_id)
        window._on_read_finished(self._outcome(pages[0].page_id, "alpha"))
        window._on_read_finished(self._outcome(pages[1].page_id, "bravo"))

        window._activate_page(pages[1].page_id)
        plain = window._editor._edit.toPlainText()
        assert "bravo" in plain
        assert "alpha" not in plain
