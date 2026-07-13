"""Image helpers shared by the viewer, OCR and vision modules.

Everything internal uses Pillow images; conversion to Qt types happens only
at the UI boundary so that worker threads never touch Qt GUI classes.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps
from PySide6.QtGui import QImage, QPixmap

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS: tuple[str, ...] = (
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".tif",
    ".tiff",
)
PDF_EXTENSION = ".pdf"

# Rendering DPI when converting PDF pages to raster images.
PDF_RENDER_DPI = 200


def is_supported_image(path: Path) -> bool:
    """True when *path* points to a raster format the app can display."""
    return path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS


def is_pdf(path: Path) -> bool:
    """True when *path* is a PDF document."""
    return path.suffix.lower() == PDF_EXTENSION


def load_image(path: Path) -> Image.Image:
    """Load an image from disk, normalising orientation and colour mode."""
    image = Image.open(path)
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    return image


def pil_to_qimage(image: Image.Image) -> QImage:
    """Convert a Pillow image into a QImage (deep copy, thread-safe data)."""
    if image.mode == "L":
        data = image.tobytes()
        qimage = QImage(
            data, image.width, image.height, image.width, QImage.Format.Format_Grayscale8
        )
    else:
        rgb = image if image.mode == "RGB" else image.convert("RGB")
        data = rgb.tobytes()
        qimage = QImage(
            data, rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888
        )
    return qimage.copy()


def pil_to_qpixmap(image: Image.Image) -> QPixmap:
    """Convert a Pillow image into a QPixmap for display."""
    return QPixmap.fromImage(pil_to_qimage(image))


def apply_adjustments(
    image: Image.Image,
    brightness: float = 1.0,
    contrast: float = 1.0,
    enhance: bool = False,
) -> Image.Image:
    """Return a copy of *image* with viewer adjustments applied.

    ``brightness``/``contrast`` are multipliers where 1.0 means unchanged.
    ``enhance`` runs a document-oriented cleanup (auto-contrast + sharpen)
    that usually improves both readability and OCR accuracy.
    """
    result = image
    if enhance:
        base = result.convert("L") if result.mode != "L" else result
        result = ImageOps.autocontrast(base, cutoff=1).convert("RGB")
        result = ImageEnhance.Sharpness(result).enhance(1.6)
    if abs(brightness - 1.0) > 1e-3:
        result = ImageEnhance.Brightness(result).enhance(brightness)
    if abs(contrast - 1.0) > 1e-3:
        result = ImageEnhance.Contrast(result).enhance(contrast)
    return result


def rotate_image(image: Image.Image, degrees: int) -> Image.Image:
    """Rotate by a multiple of 90 degrees (clockwise-positive)."""
    steps = (degrees // 90) % 4
    if steps == 0:
        return image
    transposes = {
        1: Image.Transpose.ROTATE_270,  # 90 degrees clockwise
        2: Image.Transpose.ROTATE_180,
        3: Image.Transpose.ROTATE_90,  # 270 degrees clockwise
    }
    return image.transpose(transposes[steps])


def make_thumbnail(image: Image.Image, max_size: int = 160) -> Image.Image:
    """Return a sidebar-sized thumbnail preserving aspect ratio."""
    thumb = image.copy()
    thumb.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    return thumb


def image_to_png_bytes(image: Image.Image, max_dimension: int = 2000) -> bytes:
    """Encode *image* as PNG bytes, downscaling huge pages for API transport."""
    working = image
    largest = max(working.width, working.height)
    if largest > max_dimension:
        scale = max_dimension / largest
        working = working.resize(
            (max(1, int(working.width * scale)), max(1, int(working.height * scale))),
            Image.Resampling.LANCZOS,
        )
    buffer = io.BytesIO()
    working.save(buffer, format="PNG")
    return buffer.getvalue()


def render_pdf_pages(pdf_path: Path, output_dir: Path) -> list[Path]:
    """Render every page of *pdf_path* to PNG files inside *output_dir*.

    Returns the list of created image paths in page order.  Raises
    ``RuntimeError`` with a user-readable message when the PDF cannot be read.
    """
    import fitz  # PyMuPDF; imported lazily to keep startup fast

    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        document = fitz.open(pdf_path)
    except Exception as exc:  # pragma: no cover - fitz raises various types
        raise RuntimeError(f"Could not open PDF '{pdf_path.name}': {exc}") from exc

    try:
        zoom = PDF_RENDER_DPI / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        for index, page in enumerate(document):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            target = output_dir / f"{pdf_path.stem}_page{index + 1:04d}.png"
            pixmap.save(target)
            created.append(target)
    finally:
        document.close()

    logger.info("Rendered %d pages from %s", len(created), pdf_path.name)
    return created
