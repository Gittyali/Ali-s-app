"""Autosave and crash recovery.

Every N minutes (Settings > General) the open project is snapshotted to
``<app-data>/autosave/<project-dir-hash>.json``.  A clean save or close
removes the snapshot; if the application crashes, the snapshot survives and
is offered for recovery on the next launch.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from app.core.page import Page
from app.core.project import Project
from app.utils.paths import autosave_dir

logger = logging.getLogger(__name__)


def _snapshot_path(project_directory: Path) -> Path:
    digest = hashlib.sha256(str(project_directory).encode("utf-8")).hexdigest()[:16]
    return autosave_dir() / f"{digest}.json"


def find_recoverable_snapshot() -> tuple[Path, str] | None:
    """Return ``(snapshot_file, project_name)`` for the newest snapshot, if any."""
    newest: tuple[float, Path, str] | None = None
    for candidate in autosave_dir().glob("*.json"):
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            name = str(data.get("name", "Untitled"))
            stamp = candidate.stat().st_mtime
        except (OSError, json.JSONDecodeError):
            continue
        if newest is None or stamp > newest[0]:
            newest = (stamp, candidate, name)
    if newest is None:
        return None
    return newest[1], newest[2]


def apply_snapshot(snapshot_file: Path, project: Project) -> int:
    """Merge a snapshot's page documents into *project*.

    Only page content is restored (documents, statuses); the page list on
    disk is authoritative for images.  Returns the number of pages updated.
    """
    try:
        data: dict[str, Any] = json.loads(snapshot_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read autosave snapshot: %s", exc)
        return 0
    restored = 0
    snapshot_pages = {
        str(page.get("page_id", "")): page for page in data.get("pages", [])
    }
    for page in project.pages:
        saved = snapshot_pages.get(page.page_id)
        if saved is None:
            continue
        recovered = Page.from_dict(saved)
        if recovered.document_html and recovered.document_html != page.document_html:
            page.document_html = recovered.document_html
            page.status = recovered.status
            restored += 1
    if restored:
        project.mark_modified()
    logger.info("Recovered %d pages from autosave snapshot", restored)
    return restored


class AutosaveManager(QObject):
    """Periodic snapshot writer bound to the currently open project."""

    saved = Signal(str)  # human-readable timestamp message for the status bar

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._project: Project | None = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._autosave_now)

    def watch(self, project: Project | None, interval_minutes: int) -> None:
        """Start (or retarget) autosaving for *project*."""
        self._project = project
        self._timer.stop()
        if project is not None:
            self._timer.start(max(1, interval_minutes) * 60 * 1000)
            logger.info(
                "Autosave watching '%s' every %d min", project.name, interval_minutes
            )

    def set_interval(self, interval_minutes: int) -> None:
        if self._timer.isActive():
            self._timer.start(max(1, interval_minutes) * 60 * 1000)

    def _autosave_now(self) -> None:
        project = self._project
        if project is None or not project.modified:
            return
        snapshot = _snapshot_path(project.directory)
        try:
            project.save(target_file=snapshot)
        except Exception as exc:  # Autosave must never interrupt the user.
            logger.error("Autosave failed: %s", exc)
            return
        self.saved.emit(time.strftime("Autosaved at %H:%M:%S"))

    def flush(self) -> None:
        """Write a snapshot immediately (e.g. before a risky operation)."""
        self._autosave_now()

    def clear(self) -> None:
        """Remove the snapshot after a successful explicit save/close."""
        if self._project is None:
            return
        snapshot = _snapshot_path(self._project.directory)
        try:
            snapshot.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not remove autosave snapshot: %s", exc)


def clear_snapshot_file(snapshot_file: Path) -> None:
    """Delete a specific snapshot file (after recovery or user decline)."""
    try:
        snapshot_file.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Could not remove snapshot %s: %s", snapshot_file, exc)
