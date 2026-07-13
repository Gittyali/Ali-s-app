"""Filesystem locations used by the application.

All user data lives under a single per-user application directory so it can
be backed up or wiped easily:

* Windows:  ``%APPDATA%/AIDocumentAssistant``
* Linux:    ``~/.local/share/AIDocumentAssistant``
* macOS:    ``~/Library/Application Support/AIDocumentAssistant``
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_APP_DIR_NAME = "AIDocumentAssistant"


def app_data_dir() -> Path:
    """Return (and create) the root directory for all persistent app data."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / _APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    """Directory holding rotating log files."""
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def projects_dir() -> Path:
    """Default directory for saved projects."""
    path = app_data_dir() / "projects"
    path.mkdir(parents=True, exist_ok=True)
    return path


def autosave_dir() -> Path:
    """Directory for autosave snapshots used in crash recovery."""
    path = app_data_dir() / "autosave"
    path.mkdir(parents=True, exist_ok=True)
    return path


def models_dir() -> Path:
    """Directory where local speech/vision models may be stored."""
    path = app_data_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_export_dir() -> Path:
    """Default folder for exported documents (the user's Documents folder)."""
    docs = Path.home() / "Documents"
    return docs if docs.is_dir() else Path.home()
