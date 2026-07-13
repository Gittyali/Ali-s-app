"""Typed wrapper around ``QSettings``.

Centralising every key here (instead of scattering string literals through
the codebase) gives one place to see, validate and migrate all settings.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, QSettings, Signal

from app import __app_name__, __organization__
from app.utils.paths import default_export_dir

logger = logging.getLogger(__name__)

DEFAULT_SHORTCUTS: dict[str, str] = {
    "import_pages": "Ctrl+I",
    "read_current_page": "Ctrl+R",
    "toggle_dictation": "Ctrl+D",
    "next_page": "Ctrl+Right",
    "previous_page": "Ctrl+Left",
    "save_project": "Ctrl+S",
    "export_docx": "Ctrl+E",
    "export_pdf": "Ctrl+Shift+E",
    "bold": "Ctrl+B",
    "italic": "Ctrl+Shift+I",
    "underline": "Ctrl+U",
    "zoom_in": "Ctrl++",
    "zoom_out": "Ctrl+-",
    "fit_screen": "Ctrl+0",
}

SHORTCUT_LABELS: dict[str, str] = {
    "import_pages": "Import Pages",
    "read_current_page": "Read Current Page",
    "toggle_dictation": "Start/Stop Dictation",
    "next_page": "Next Page",
    "previous_page": "Previous Page",
    "save_project": "Save Project",
    "export_docx": "Export DOCX",
    "export_pdf": "Export PDF",
    "bold": "Bold",
    "italic": "Italic",
    "underline": "Underline",
    "zoom_in": "Zoom In",
    "zoom_out": "Zoom Out",
    "fit_screen": "Fit to Screen",
}


class SettingsManager(QObject):
    """Application-wide settings store.

    Emits :attr:`changed` with the key name whenever a value is written, so
    live components (theme, autosave timer, shortcuts) can react immediately.
    """

    changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._settings = QSettings(__organization__, __app_name__)

    # ------------------------------------------------------------------ raw
    def _get(self, key: str, default: Any) -> Any:
        return self._settings.value(key, default)

    def _set(self, key: str, value: Any) -> None:
        self._settings.setValue(key, value)
        self._settings.sync()
        self.changed.emit(key)

    # -------------------------------------------------------------- general
    @property
    def theme(self) -> str:
        """UI theme: ``light`` or ``dark``."""
        return str(self._get("general/theme", "light"))

    @theme.setter
    def theme(self, value: str) -> None:
        self._set("general/theme", value if value in ("light", "dark") else "light")

    @property
    def export_folder(self) -> str:
        return str(self._get("general/export_folder", str(default_export_dir())))

    @export_folder.setter
    def export_folder(self, value: str) -> None:
        self._set("general/export_folder", value)

    @property
    def autosave_interval_minutes(self) -> int:
        try:
            return max(1, int(self._get("general/autosave_interval", 3)))
        except (TypeError, ValueError):
            return 3

    @autosave_interval_minutes.setter
    def autosave_interval_minutes(self, value: int) -> None:
        self._set("general/autosave_interval", max(1, int(value)))

    @property
    def last_project_path(self) -> str:
        return str(self._get("general/last_project_path", ""))

    @last_project_path.setter
    def last_project_path(self, value: str) -> None:
        self._set("general/last_project_path", value)

    # ------------------------------------------------------------------ ocr
    @property
    def ocr_engine(self) -> str:
        """Preferred OCR engine id: ``tesseract``, ``easyocr`` or ``paddleocr``."""
        return str(self._get("ocr/engine", "tesseract"))

    @ocr_engine.setter
    def ocr_engine(self, value: str) -> None:
        self._set("ocr/engine", value)

    @property
    def ocr_languages(self) -> str:
        """Language hint passed to the OCR engine (engine-specific syntax)."""
        return str(self._get("ocr/languages", "eng"))

    @ocr_languages.setter
    def ocr_languages(self, value: str) -> None:
        self._set("ocr/languages", value)

    @property
    def tesseract_path(self) -> str:
        """Explicit path to tesseract.exe; empty means use PATH."""
        return str(self._get("ocr/tesseract_path", ""))

    @tesseract_path.setter
    def tesseract_path(self, value: str) -> None:
        self._set("ocr/tesseract_path", value)

    # --------------------------------------------------------------- vision
    @property
    def vision_provider(self) -> str:
        """AI provider id: ``anthropic``, ``openai``, ``gemini``, ``local`` or ``none``."""
        return str(self._get("vision/provider", "none"))

    @vision_provider.setter
    def vision_provider(self, value: str) -> None:
        self._set("vision/provider", value)

    def vision_api_key(self, provider: str) -> str:
        return str(self._get(f"vision/{provider}/api_key", ""))

    def set_vision_api_key(self, provider: str, value: str) -> None:
        self._set(f"vision/{provider}/api_key", value)

    def vision_model(self, provider: str) -> str:
        defaults = {
            "anthropic": "claude-sonnet-5",
            "openai": "gpt-4o",
            "gemini": "gemini-2.0-flash",
            "local": "llava",
        }
        return str(self._get(f"vision/{provider}/model", defaults.get(provider, "")))

    def set_vision_model(self, provider: str, value: str) -> None:
        self._set(f"vision/{provider}/model", value)

    @property
    def local_vision_endpoint(self) -> str:
        """Base URL of an OpenAI-compatible local server (Ollama, LM Studio)."""
        return str(self._get("vision/local/endpoint", "http://localhost:11434/v1"))

    @local_vision_endpoint.setter
    def local_vision_endpoint(self, value: str) -> None:
        self._set("vision/local/endpoint", value)

    # --------------------------------------------------------------- speech
    @property
    def microphone_device(self) -> str:
        """Input device name; empty string means the system default."""
        return str(self._get("speech/microphone", ""))

    @microphone_device.setter
    def microphone_device(self, value: str) -> None:
        self._set("speech/microphone", value)

    @property
    def speech_language(self) -> str:
        """Dictation language: ``en`` (English), ``ur`` (Urdu), ``ur-roman``."""
        return str(self._get("speech/language", "en"))

    @speech_language.setter
    def speech_language(self, value: str) -> None:
        self._set("speech/language", value)

    @property
    def vosk_model_path(self) -> str:
        """Folder containing a downloaded Vosk model for the active language."""
        return str(self._get("speech/vosk_model_path", ""))

    @vosk_model_path.setter
    def vosk_model_path(self, value: str) -> None:
        self._set("speech/vosk_model_path", value)

    # ------------------------------------------------------------ shortcuts
    def shortcut(self, action_id: str) -> str:
        default = DEFAULT_SHORTCUTS.get(action_id, "")
        return str(self._get(f"shortcuts/{action_id}", default))

    def set_shortcut(self, action_id: str, sequence: str) -> None:
        self._set(f"shortcuts/{action_id}", sequence)

    def all_shortcuts(self) -> dict[str, str]:
        return {action: self.shortcut(action) for action in DEFAULT_SHORTCUTS}
