"""Page sidebar.

A vertical list of every imported page with thumbnail, label and workflow
status.  Pages are permanent: they never disappear or reorder on their own,
and the selection changes only on explicit user action (click, keyboard or
voice command routed through the main window) — never automatically.

Thumbnails load lazily on a background thread so importing hundreds of
pages stays instant.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.page import Page, PageStatus
from app.utils.image_utils import load_image, make_thumbnail, pil_to_qimage
from app.utils.workers import run_in_background

logger = logging.getLogger(__name__)

_THUMB_SIZE = 120

_STATUS_MARKS = {
    PageStatus.PENDING: "",
    PageStatus.PROCESSING: " ⏳",
    PageStatus.READ: " ✓",
    PageStatus.EDITED: " ✎",
}


class PageSidebar(QWidget):
    """List of imported pages with explicit-only selection.

    Signals:
        * ``page_selected(str)`` — page_id, on user click/keyboard only.
        * ``page_delete_requested(str)`` — page_id (Delete key).
    """

    page_selected = Signal(str)
    page_delete_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._header = QLabel("Pages")
        self._header.setStyleSheet("font-weight: bold; padding: 4px;")
        self._list = QListWidget(self)
        self._list.setIconSize(QSize(_THUMB_SIZE, _THUMB_SIZE))
        self._list.setUniformItemSizes(True)
        self._list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self._list.itemActivated.connect(self._emit_selection)
        self._list.itemClicked.connect(self._emit_selection)
        self._list.currentItemChanged.connect(self._on_current_changed)
        # Guard flag: programmatic updates must not emit page_selected.
        self._programmatic_change = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._header)
        layout.addWidget(self._list)
        self.setMinimumWidth(170)

    # -------------------------------------------------------------- content
    def set_pages(self, pages: list[Page]) -> None:
        """Rebuild the list (import, project open, page removal)."""
        selected = self.current_page_id()
        self._programmatic_change = True
        try:
            self._list.clear()
            for index, page in enumerate(pages):
                item = QListWidgetItem(self._label_for(index, page))
                item.setData(Qt.ItemDataRole.UserRole, page.page_id)
                item.setToolTip(page.source_name or page.image_path.name)
                self._list.addItem(item)
                self._request_thumbnail(item, page.image_path)
            if selected:
                self.select_page(selected)
        finally:
            self._programmatic_change = False
        self._header.setText(f"Pages ({len(pages)})")

    @staticmethod
    def _label_for(index: int, page: Page) -> str:
        return f"Page {index + 1}{_STATUS_MARKS.get(page.status, '')}"

    def update_page_status(self, index: int, page: Page) -> None:
        """Refresh one row's label after a status change."""
        item = self._list.item(index)
        if item is not None:
            item.setText(self._label_for(index, page))

    def _request_thumbnail(self, item: QListWidgetItem, image_path: Path) -> None:
        def build() -> object:
            return pil_to_qimage(make_thumbnail(load_image(image_path), _THUMB_SIZE))

        def apply(qimage: object) -> None:
            # The item may have been removed while the thumbnail rendered.
            for row in range(self._list.count()):
                if self._list.item(row) is item:
                    item.setIcon(QIcon(QPixmap.fromImage(qimage)))
                    return

        run_in_background(
            build,
            on_result=apply,
            on_error=lambda msg: logger.warning(
                "Thumbnail failed for %s: %s", image_path.name, msg
            ),
        )

    # ------------------------------------------------------------ selection
    def current_page_id(self) -> str:
        item = self._list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item else ""

    def current_index(self) -> int:
        return self._list.currentRow()

    def page_count(self) -> int:
        return self._list.count()

    def select_page(self, page_id: str) -> None:
        """Programmatic selection (does NOT emit page_selected)."""
        self._programmatic_change = True
        try:
            for row in range(self._list.count()):
                item = self._list.item(row)
                if str(item.data(Qt.ItemDataRole.UserRole)) == page_id:
                    self._list.setCurrentItem(item)
                    return
        finally:
            self._programmatic_change = False

    def select_row(self, row: int) -> str:
        """Programmatic selection by index; returns the page_id or ''."""
        if 0 <= row < self._list.count():
            self._programmatic_change = True
            try:
                self._list.setCurrentRow(row)
            finally:
                self._programmatic_change = False
            return self.current_page_id()
        return ""

    def _emit_selection(self, item: QListWidgetItem) -> None:
        if item is not None and not self._programmatic_change:
            self.page_selected.emit(str(item.data(Qt.ItemDataRole.UserRole)))

    def _on_current_changed(
        self, current: QListWidgetItem, previous: QListWidgetItem
    ) -> None:
        # Covers keyboard navigation (arrow keys) inside the list.
        if current is not None and not self._programmatic_change:
            self.page_selected.emit(str(current.data(Qt.ItemDataRole.UserRole)))

    # ------------------------------------------------------------ keyboard
    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.key() == Qt.Key.Key_Delete and self.current_page_id():
            self.page_delete_requested.emit(self.current_page_id())
            return
        super().keyPressEvent(event)
