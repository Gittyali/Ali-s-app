"""Core application layer.

* :mod:`app.core.page` — the page data model.
* :mod:`app.core.project` — a project (ordered pages + per-page documents)
  with disk persistence and import logic.
* :mod:`app.core.autosave` — periodic snapshots and crash recovery.
* :mod:`app.core.controller` — orchestrates OCR/AI jobs and dictation on
  top of the project, exposing Qt signals for the UI.
"""

from app.core.page import Page, PageStatus
from app.core.project import Project

__all__ = ["Page", "PageStatus", "Project"]
