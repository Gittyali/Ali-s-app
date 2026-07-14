"""UI behaviour tests: resizing, word wrap, smart buttons, button states.

These run offscreen; modal dialogs are stubbed out so nothing blocks.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.core.project import Project
from app.settings.settings_manager import SettingsManager


@pytest.fixture()
def window(qapp, tmp_path: Path, monkeypatch):
    """A MainWindow with stubbed dialogs and a 3-page project loaded."""
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

    from app.ui.main_window import MainWindow

    settings = SettingsManager()
    settings.last_project_path = ""
    window = MainWindow(settings)
    # Consume the deferred _startup_project timer NOW, while the dialog
    # stubs are active — otherwise it fires inside a later test's event
    # pump against a deleted window.
    for _ in range(3):
        qapp.processEvents()

    project = Project.create(tmp_path / "ui.adaproj", "UI")
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


class TestWindowResizing:
    def test_minimum_size_is_modest(self, window) -> None:
        # The window must shrink well below the default 1400x860.
        assert window.minimumWidth() <= 720
        assert window.minimumHeight() <= 460

    def test_resize_small_and_large(self, window) -> None:
        window.resize(760, 480)
        assert window.width() == 760
        assert window.height() == 480
        window.resize(1600, 900)
        assert window.width() == 1600

    def test_no_fixed_size_lock(self, window) -> None:
        # maximumSize stays at Qt's "unbounded" sentinel: resizable freely.
        assert window.maximumWidth() >= 16000
        assert window.maximumHeight() >= 16000


class TestWordWrap:
    def test_editor_wraps_at_widget_width(self, window) -> None:
        from PySide6.QtGui import QTextOption
        from PySide6.QtWidgets import QTextEdit

        edit = window._editor._edit
        assert edit.lineWrapMode() == QTextEdit.LineWrapMode.WidgetWidth
        assert edit.wordWrapMode() == QTextOption.WrapMode.WordWrap


class TestSmartButtons:
    def test_single_selection_label(self, window) -> None:
        window._on_sidebar_selection_changed(1)
        assert window._action_read_page.text() == "Read Current Page"

    def test_multi_selection_label(self, window) -> None:
        window._on_sidebar_selection_changed(10)
        assert window._action_read_page.text() == "Read Selected Pages (10)"

    def test_sidebar_selection_drives_label(self, window) -> None:
        listw = window._sidebar._list
        listw.item(0).setSelected(True)
        listw.item(1).setSelected(True)
        assert window._action_read_page.text() == "Read Selected Pages (2)"

    def test_selected_ids_in_sidebar_order(self, window) -> None:
        listw = window._sidebar._list
        # Select in reverse click order; result must be sidebar order.
        listw.item(2).setSelected(True)
        listw.item(0).setSelected(True)
        ids = window._sidebar.selected_page_ids()
        assert ids == [
            window._project.pages[0].page_id,
            window._project.pages[2].page_id,
        ]

    def test_read_all_button_is_permanent(self, window) -> None:
        from PySide6.QtWidgets import QToolBar

        assert window._action_read_all.text() == "Read All Pages"
        main_toolbar = next(
            bar for bar in window.findChildren(QToolBar) if bar.windowTitle() == "Main"
        )
        assert window._action_read_all in main_toolbar.actions()
        # Enabled whenever the project has pages (and no batch is running).
        assert window._action_read_all.isEnabled()


class TestReadButtonState:
    def test_disabled_during_batch(self, window) -> None:
        pid = window._project.pages[0].page_id
        window._sidebar.select_page(pid)
        window._activate_page(pid)
        assert window._action_read_page.isEnabled()

        window._controller._batch_active = True
        window._update_action_states()
        assert not window._action_read_page.isEnabled()
        assert not window._action_read_all.isEnabled()

        window._controller._batch_active = False
        window._update_action_states()
        assert window._action_read_page.isEnabled()
        assert window._action_read_all.isEnabled()

    def test_reenabled_after_failure(self, window) -> None:
        pid = window._project.pages[0].page_id
        window._sidebar.select_page(pid)
        window._activate_page(pid)
        window._on_read_started(pid)
        window._controller._busy_pages.add(pid)
        window._update_action_states()
        assert not window._action_read_page.isEnabled()

        window._controller._busy_pages.discard(pid)  # controller cleanup
        window._on_read_failed(pid, "synthetic error")
        assert window._action_read_page.isEnabled()


class TestOutputModes:
    def _outcome(self, page_id: str, text: str):
        from app.core.controller import ReadOutcome
        from app.document.model import (
            BlockType,
            InlineSpan,
            ParagraphBlock,
            StructuredDocument,
        )

        return ReadOutcome(
            page_id,
            StructuredDocument(
                blocks=[
                    ParagraphBlock(
                        block_type=BlockType.PARAGRAPH,
                        spans=[InlineSpan(text=text)],
                    )
                ]
            ),
        )

    def test_append_mode_builds_single_document(self, window, monkeypatch) -> None:
        monkeypatch.setattr(
            SettingsManager, "output_mode", property(lambda self: "append")
        )
        monkeypatch.setattr(
            SettingsManager, "insert_page_separators", property(lambda self: True)
        )
        pages = window._project.pages
        window._sidebar.select_page(pages[0].page_id)
        window._activate_page(pages[0].page_id)

        window._on_read_finished(self._outcome(pages[0].page_id, "alpha text"))
        window._on_read_finished(self._outcome(pages[1].page_id, "bravo text"))
        window._on_read_finished(self._outcome(pages[2].page_id, "charlie text"))

        plain = window._editor._edit.toPlainText()
        assert plain.index("alpha") < plain.index("bravo") < plain.index("charlie")
        assert "— Page 2 —" in plain
        # No duplicates: each page inserted exactly once.
        assert plain.count("bravo text") == 1
        # The combined document is stored on the host page.
        assert "bravo text" in pages[0].document_html

    def test_replace_mode_stores_per_page(self, window, monkeypatch) -> None:
        monkeypatch.setattr(
            SettingsManager, "output_mode", property(lambda self: "replace")
        )
        pages = window._project.pages
        window._sidebar.select_page(pages[0].page_id)
        window._activate_page(pages[0].page_id)

        window._on_read_finished(self._outcome(pages[0].page_id, "alpha text"))
        window._on_read_finished(self._outcome(pages[1].page_id, "bravo text"))

        assert "alpha text" in window._editor._edit.toPlainText()
        assert "bravo text" not in window._editor._edit.toPlainText()
        assert "bravo text" in pages[1].document_html
