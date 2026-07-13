"""Project model and persistence.

A project is a directory::

    MyProject.adaproj/
        project.json     <- metadata + per-page document HTML
        pages/           <- imported page images (copies; originals untouched)

Copying imports into the project folder makes projects self-contained and
movable, and means deleting/renaming source files never breaks a project.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from app.core.page import Page, PageStatus
from app.utils.image_utils import is_pdf, is_supported_image, render_pdf_pages

logger = logging.getLogger(__name__)

PROJECT_SUFFIX = ".adaproj"
_PROJECT_FILE = "project.json"
_PAGES_DIR = "pages"
_FORMAT_VERSION = 1


class ProjectError(RuntimeError):
    """Raised with user-readable messages for project I/O problems."""


class Project:
    """An ordered collection of pages plus persistence."""

    def __init__(self, directory: Path, name: str = "") -> None:
        self.directory = directory
        self.name = name or directory.stem
        self.pages: list[Page] = []
        self.modified = False
        self._last_saved: float = 0.0

    # ------------------------------------------------------------- factory
    @classmethod
    def create(cls, directory: Path, name: str = "") -> Project:
        """Create a new project directory (must not already contain one)."""
        if directory.suffix != PROJECT_SUFFIX:
            directory = directory.with_suffix(PROJECT_SUFFIX)
        if (directory / _PROJECT_FILE).exists():
            raise ProjectError(
                f"A project already exists at '{directory}'. Open it instead."
            )
        try:
            (directory / _PAGES_DIR).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ProjectError(f"Could not create project folder: {exc}") from exc
        project = cls(directory, name)
        project.save()
        logger.info("Created project at %s", directory)
        return project

    @classmethod
    def load(cls, directory: Path) -> Project:
        """Load a project from its directory."""
        project_file = directory / _PROJECT_FILE
        if not project_file.is_file():
            raise ProjectError(f"'{directory}' does not contain a project file.")
        try:
            data: dict[str, Any] = json.loads(project_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProjectError(f"Could not read project file: {exc}") from exc

        project = cls(directory, str(data.get("name", directory.stem)))
        for page_data in data.get("pages", []):
            page = Page.from_dict(page_data)
            # Stored paths are relative to the project directory.
            if not page.image_path.is_absolute():
                page.image_path = directory / page.image_path
            if page.image_path.is_file():
                project.pages.append(page)
            else:
                logger.warning("Skipping missing page image %s", page.image_path)
        project._last_saved = time.time()
        logger.info("Loaded project '%s' (%d pages)", project.name, len(project.pages))
        return project

    # --------------------------------------------------------------- state
    @property
    def pages_dir(self) -> Path:
        return self.directory / _PAGES_DIR

    def mark_modified(self) -> None:
        self.modified = True

    def page_index(self, page_id: str) -> int:
        """Index of a page by id, or -1."""
        for index, page in enumerate(self.pages):
            if page.page_id == page_id:
                return index
        return -1

    # --------------------------------------------------------------- save
    def to_dict(self) -> dict[str, Any]:
        pages: list[dict[str, Any]] = []
        for page in self.pages:
            data = page.to_dict()
            try:
                data["image_path"] = str(page.image_path.relative_to(self.directory))
            except ValueError:
                data["image_path"] = str(page.image_path)
            pages.append(data)
        return {"version": _FORMAT_VERSION, "name": self.name, "pages": pages}

    def save(self, target_file: Path | None = None) -> None:
        """Write project.json atomically (temp file + rename)."""
        target = target_file or (self.directory / _PROJECT_FILE)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            temp.write_text(
                json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp.replace(target)
        except OSError as exc:
            temp.unlink(missing_ok=True)
            raise ProjectError(f"Could not save project: {exc}") from exc
        if target_file is None:
            self.modified = False
            self._last_saved = time.time()
        logger.info("Saved project to %s", target)

    # ------------------------------------------------------------- import
    def import_files(
        self,
        paths: list[Path],
        progress_callback: Any = None,
    ) -> list[Page]:
        """Copy images / render PDFs into the project; return the new pages.

        Unsupported or unreadable files are collected and reported in one
        ``ProjectError`` at the end, after all readable files were imported.
        """
        new_pages: list[Page] = []
        failures: list[str] = []
        total = len(paths)

        for index, source in enumerate(paths):
            if progress_callback is not None:
                percent = int((index / max(1, total)) * 100)
                progress_callback(percent, f"Importing {source.name}")
            try:
                if is_pdf(source):
                    rendered = render_pdf_pages(source, self.pages_dir)
                    for page_path in rendered:
                        new_pages.append(
                            Page(image_path=page_path, source_name=source.name)
                        )
                elif is_supported_image(source):
                    target = self.pages_dir / (
                        f"{source.stem}_{uuid.uuid4().hex[:8]}{source.suffix.lower()}"
                    )
                    shutil.copy2(source, target)
                    new_pages.append(Page(image_path=target, source_name=source.name))
                else:
                    failures.append(f"{source.name}: unsupported file type")
            except (OSError, RuntimeError) as exc:
                failures.append(f"{source.name}: {exc}")

        self.pages.extend(new_pages)
        if new_pages:
            self.mark_modified()
        if progress_callback is not None:
            progress_callback(100, f"Imported {len(new_pages)} pages")
        logger.info("Imported %d pages (%d failures)", len(new_pages), len(failures))
        if failures:
            raise ProjectError(
                "Some files could not be imported:\n" + "\n".join(failures)
            )
        return new_pages

    def remove_page(self, page_id: str) -> bool:
        """Delete a page and its image copy. Returns True when found."""
        index = self.page_index(page_id)
        if index < 0:
            return False
        page = self.pages.pop(index)
        try:
            if page.image_path.is_file() and self.pages_dir in page.image_path.parents:
                page.image_path.unlink()
        except OSError as exc:
            logger.warning("Could not delete page image %s: %s", page.image_path, exc)
        self.mark_modified()
        return True

    def set_page_document(self, page_id: str, html: str, edited_by_user: bool) -> None:
        """Store new document HTML for a page and update its status."""
        index = self.page_index(page_id)
        if index < 0:
            return
        page = self.pages[index]
        if page.document_html == html:
            return
        page.document_html = html
        if edited_by_user:
            page.status = PageStatus.EDITED
        elif page.status is not PageStatus.EDITED:
            page.status = PageStatus.READ
        self.mark_modified()
