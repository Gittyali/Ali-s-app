"""Page data model.

A page couples one imported image with the rich text the user has produced
for it.  Images stay on disk (only thumbnails and the currently displayed
page are held in memory) so 500-page projects remain lightweight.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class PageStatus(Enum):
    """Workflow state of a page, shown in the sidebar."""

    PENDING = "pending"  # imported, not yet read
    PROCESSING = "processing"  # OCR / AI reading in progress
    READ = "read"  # has recognised content
    EDITED = "edited"  # user modified the content
    FAILED = "failed"  # last read attempt failed; retry candidate


@dataclass
class Page:
    """One imported page and its editable document."""

    image_path: Path
    page_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    source_name: str = ""
    rotation: int = 0  # multiples of 90, clockwise
    brightness: float = 1.0
    contrast: float = 1.0
    enhanced: bool = False
    document_html: str = ""  # rich text produced for this page
    status: PageStatus = PageStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable representation (paths relative to project dir)."""
        return {
            "page_id": self.page_id,
            "image_path": str(self.image_path),
            "source_name": self.source_name,
            "rotation": self.rotation,
            "brightness": self.brightness,
            "contrast": self.contrast,
            "enhanced": self.enhanced,
            "document_html": self.document_html,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Page:
        """Reconstruct a page from :meth:`to_dict` output, tolerating gaps."""
        try:
            status = PageStatus(str(data.get("status", "pending")))
        except ValueError:
            status = PageStatus.PENDING
        return cls(
            image_path=Path(str(data.get("image_path", ""))),
            page_id=str(data.get("page_id", "")) or uuid.uuid4().hex,
            source_name=str(data.get("source_name", "")),
            rotation=int(data.get("rotation", 0) or 0),
            brightness=float(data.get("brightness", 1.0) or 1.0),
            contrast=float(data.get("contrast", 1.0) or 1.0),
            enhanced=bool(data.get("enhanced", False)),
            document_html=str(data.get("document_html", "")),
            status=status,
        )
