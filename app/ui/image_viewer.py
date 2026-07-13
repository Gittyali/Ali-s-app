"""Image viewer.

A ``QGraphicsView``-based viewer with zoom (wheel + shortcuts), pan (drag),
fit-to-screen, rotation and non-destructive brightness/contrast/enhancement
adjustments.  Adjustments are recomputed from the original image on a
background thread and never modify the file on disk.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QSlider,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.utils.image_utils import apply_adjustments, load_image, pil_to_qpixmap, rotate_image
from app.utils.workers import run_in_background

logger = logging.getLogger(__name__)

_ZOOM_STEP = 1.2
_MIN_SCALE = 0.05
_MAX_SCALE = 12.0


class _GraphicsView(QGraphicsView):
    """Inner view handling wheel-zoom and drag-pan."""

    def __init__(self, scene: QGraphicsScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._scale = 1.0

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        factor = _ZOOM_STEP if event.angleDelta().y() > 0 else 1 / _ZOOM_STEP
        self.apply_zoom(factor)

    def apply_zoom(self, factor: float) -> None:
        target = self._scale * factor
        if not (_MIN_SCALE <= target <= _MAX_SCALE):
            return
        self._scale = target
        self.scale(factor, factor)

    def reset_zoom(self) -> None:
        self.resetTransform()
        self._scale = 1.0

    @property
    def current_scale(self) -> float:
        return self._scale


class ImageViewer(QWidget):
    """Viewer pane for the currently selected page.

    Signals:
        * ``adjustments_changed(int, float, float, bool)`` —
          rotation, brightness, contrast, enhanced; persisted per page.
    """

    adjustments_changed = Signal(int, float, float, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)
        self._view = _GraphicsView(self._scene, self)

        self._original: Image.Image | None = None
        self._image_path: Path | None = None
        self._rotation = 0
        self._brightness = 1.0
        self._contrast = 1.0
        self._enhanced = False
        self._render_token = 0  # discards stale async renders

        self._placeholder = QLabel(
            "Import pages to begin\n(File > Import Pages, or Ctrl+I)"
        )
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._build_controls())
        layout.addWidget(self._view, stretch=1)
        layout.addWidget(self._placeholder, stretch=1)
        self._view.hide()

    # ------------------------------------------------------------- controls
    def _build_controls(self) -> QWidget:
        # A QToolBar collapses overflowing controls into a "»" popup, so the
        # viewer keeps working at any window width (responsive layout).
        bar = QToolBar("Image tools", self)
        bar.setMovable(False)
        bar.setIconSize(QSize(16, 16))

        def tool(text: str, tooltip: str, slot) -> QToolButton:
            button = QToolButton(bar)
            button.setText(text)
            button.setToolTip(tooltip)
            button.clicked.connect(slot)
            bar.addWidget(button)
            return button

        tool("+", "Zoom in (Ctrl++)", self.zoom_in)
        tool("−", "Zoom out (Ctrl+-)", self.zoom_out)
        tool("Fit", "Fit to screen (Ctrl+0)", self.fit_to_screen)
        tool("100%", "Actual size", self.actual_size)
        bar.addSeparator()
        tool("⟳", "Rotate 90° clockwise", lambda: self.rotate(90))
        tool("⟲", "Rotate 90° counter-clockwise", lambda: self.rotate(-90))
        self._enhance_button = tool(
            "Enhance", "Toggle document enhancement (auto-contrast + sharpen)",
            self._toggle_enhance,
        )
        self._enhance_button.setCheckable(True)
        bar.addSeparator()

        brightness_label = QLabel(" ☀ ")
        brightness_label.setToolTip("Brightness")
        bar.addWidget(brightness_label)
        self._brightness_slider = self._make_slider(bar, self._on_brightness, "Brightness")
        contrast_label = QLabel(" ◑ ")
        contrast_label.setToolTip("Contrast")
        bar.addWidget(contrast_label)
        self._contrast_slider = self._make_slider(bar, self._on_contrast, "Contrast")
        return bar

    def _make_slider(self, bar: QToolBar, slot, tooltip: str) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(20, 200)  # 0.2x .. 2.0x
        slider.setValue(100)
        slider.setFixedWidth(80)
        slider.setToolTip(tooltip)
        slider.valueChanged.connect(slot)
        bar.addWidget(slider)
        return slider

    # ------------------------------------------------------------- loading
    def clear(self) -> None:
        """Show the placeholder (no page selected)."""
        self._original = None
        self._image_path = None
        self._pixmap_item.setPixmap(QPixmap())
        self._view.hide()
        self._placeholder.show()

    def show_page(
        self,
        image_path: Path,
        rotation: int,
        brightness: float,
        contrast: float,
        enhanced: bool,
    ) -> None:
        """Display a page image with its stored adjustments."""
        self._image_path = image_path
        self._rotation = rotation % 360
        self._brightness = brightness
        self._contrast = contrast
        self._enhanced = enhanced
        self._sync_controls()

        token = self._render_token = self._render_token + 1

        def load() -> Image.Image:
            return load_image(image_path)

        def loaded(image: Image.Image) -> None:
            if token != self._render_token:
                return  # user already switched pages
            self._original = image
            self._rerender(fit=True)

        run_in_background(load, on_result=loaded, on_error=self._on_load_error)

    def _on_load_error(self, message: str) -> None:
        logger.error("Could not load page image: %s", message)
        self._placeholder.setText(f"Could not load this page image:\n{message}")
        self._view.hide()
        self._placeholder.show()

    def _sync_controls(self) -> None:
        self._brightness_slider.blockSignals(True)
        self._brightness_slider.setValue(int(self._brightness * 100))
        self._brightness_slider.blockSignals(False)
        self._contrast_slider.blockSignals(True)
        self._contrast_slider.setValue(int(self._contrast * 100))
        self._contrast_slider.blockSignals(False)
        self._enhance_button.setChecked(self._enhanced)

    # ----------------------------------------------------------- rendering
    def _rerender(self, fit: bool = False) -> None:
        if self._original is None:
            return
        token = self._render_token = self._render_token + 1
        source = self._original
        rotation, brightness = self._rotation, self._brightness
        contrast, enhanced = self._contrast, self._enhanced

        def process() -> Image.Image:
            image = rotate_image(source, rotation)
            return apply_adjustments(image, brightness, contrast, enhanced)

        def done(image: Image.Image) -> None:
            if token != self._render_token:
                return
            self._pixmap_item.setPixmap(pil_to_qpixmap(image))
            self._scene.setSceneRect(self._pixmap_item.boundingRect())
            self._placeholder.hide()
            self._view.show()
            if fit:
                self.fit_to_screen()

        run_in_background(process, on_result=done, on_error=self._on_load_error)

    def processed_image(self) -> Image.Image | None:
        """The image exactly as displayed (for OCR/AI), or None."""
        if self._original is None:
            return None
        image = rotate_image(self._original, self._rotation)
        return apply_adjustments(image, self._brightness, self._contrast, self._enhanced)

    # ------------------------------------------------------------- actions
    def zoom_in(self) -> None:
        self._view.apply_zoom(_ZOOM_STEP)

    def zoom_out(self) -> None:
        self._view.apply_zoom(1 / _ZOOM_STEP)

    def actual_size(self) -> None:
        self._view.reset_zoom()

    def fit_to_screen(self) -> None:
        if self._pixmap_item.pixmap().isNull():
            return
        self._view.reset_zoom()
        self._view.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        # Track the effective scale so wheel-zoom limits stay accurate.
        self._view._scale = self._view.transform().m11()

    def rotate(self, degrees: int) -> None:
        if self._original is None:
            return
        self._rotation = (self._rotation + degrees) % 360
        self._rerender(fit=True)
        self._emit_adjustments()

    def _toggle_enhance(self) -> None:
        self._enhanced = self._enhance_button.isChecked()
        self._rerender()
        self._emit_adjustments()

    def _on_brightness(self, value: int) -> None:
        self._brightness = value / 100.0
        self._rerender()
        self._emit_adjustments()

    def _on_contrast(self, value: int) -> None:
        self._contrast = value / 100.0
        self._rerender()
        self._emit_adjustments()

    def _emit_adjustments(self) -> None:
        self.adjustments_changed.emit(
            self._rotation, self._brightness, self._contrast, self._enhanced
        )
