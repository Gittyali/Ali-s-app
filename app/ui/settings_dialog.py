"""Settings dialog.

Tabbed configuration for General (theme, export folder, autosave), OCR,
AI Provider, Speech and Keyboard Shortcuts.  Values are written through
:class:`~app.settings.settings_manager.SettingsManager` only when the user
clicks OK.
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.ocr.factory import all_engines, available_engines
from app.settings.settings_manager import (
    DEFAULT_SHORTCUTS,
    SHORTCUT_LABELS,
    SettingsManager,
)
from app.speech.recorder import list_input_devices
from app.vision.factory import available_providers

logger = logging.getLogger(__name__)

_SPEECH_LANGUAGES = {
    "en": "English",
    "ur": "Urdu (اردو)",
    "ur-roman": "Roman Urdu",
}

_API_KEY_PROVIDERS = ("anthropic", "openai", "gemini")


class SettingsDialog(QDialog):
    """Modal settings editor; call :meth:`exec` and check the result."""

    def __init__(self, settings: SettingsManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)

        tabs = QTabWidget(self)
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_reading_tab(), "Reading")
        tabs.addTab(self._build_ocr_tab(), "OCR")
        tabs.addTab(self._build_ai_tab(), "AI Provider")
        tabs.addTab(self._build_speech_tab(), "Speech")
        tabs.addTab(self._build_shortcuts_tab(), "Shortcuts")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._apply_and_close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    # -------------------------------------------------------------- general
    def _build_general_tab(self) -> QWidget:
        widget = QWidget(self)
        form = QFormLayout(widget)

        self._theme_box = QComboBox()
        self._theme_box.addItem("Light", "light")
        self._theme_box.addItem("Dark", "dark")
        self._theme_box.setCurrentIndex(1 if self._settings.theme == "dark" else 0)
        form.addRow("Theme:", self._theme_box)

        self._export_folder = QLineEdit(self._settings.export_folder)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._pick_export_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self._export_folder)
        folder_row.addWidget(browse)
        form.addRow("Export folder:", folder_row)

        self._autosave_spin = QSpinBox()
        self._autosave_spin.setRange(1, 60)
        self._autosave_spin.setSuffix(" min")
        self._autosave_spin.setValue(self._settings.autosave_interval_minutes)
        form.addRow("Autosave every:", self._autosave_spin)
        return widget

    def _pick_export_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Choose export folder", self._export_folder.text()
        )
        if folder:
            self._export_folder.setText(folder)

    # -------------------------------------------------------------- reading
    def _build_reading_tab(self) -> QWidget:
        widget = QWidget(self)
        form = QFormLayout(widget)

        self._output_mode_box = QComboBox()
        self._output_mode_box.addItem(
            "Append — build one continuous document", "append"
        )
        self._output_mode_box.addItem(
            "Replace — store content on each page", "replace"
        )
        self._output_mode_box.setCurrentIndex(
            0 if self._settings.output_mode == "append" else 1
        )
        form.addRow("Output mode:", self._output_mode_box)

        self._auto_read_check = QCheckBox("Start reading automatically after import")
        self._auto_read_check.setChecked(self._settings.auto_read_after_import)
        form.addRow("Auto read:", self._auto_read_check)

        self._separators_check = QCheckBox(
            "Insert a small “— Page N —” marker between appended pages"
        )
        self._separators_check.setChecked(self._settings.insert_page_separators)
        form.addRow("Page separators:", self._separators_check)

        self._continue_check = QCheckBox(
            "Continue with the remaining pages when one page fails"
        )
        self._continue_check.setChecked(self._settings.continue_after_error)
        form.addRow("On errors:", self._continue_check)

        self._underlines_check = QCheckBox(
            "Ignore decorative underlines (ruled/notebook lines, form rules)"
        )
        self._underlines_check.setChecked(self._settings.ignore_decorative_underlines)
        form.addRow("Underlines:", self._underlines_check)

        self._watermarks_check = QCheckBox(
            "Ignore watermarks, stamps, logos and background noise"
        )
        self._watermarks_check.setChecked(self._settings.ignore_watermarks)
        form.addRow("Watermarks:", self._watermarks_check)

        self._ocr_fallback_check = QCheckBox(
            "Fall back to plain OCR when AI reading fails (may reduce quality)"
        )
        self._ocr_fallback_check.setChecked(self._settings.ocr_fallback_when_ai_fails)
        form.addRow("AI failure:", self._ocr_fallback_check)

        form.addRow(
            QLabel(
                "Append mode collects every page you read into one continuous "
                "document in the editor, in sidebar order."
            )
        )
        return widget

    # ------------------------------------------------------------------ ocr
    def _build_ocr_tab(self) -> QWidget:
        widget = QWidget(self)
        form = QFormLayout(widget)

        installed = available_engines()
        self._ocr_box = QComboBox()
        for engine_id, name in all_engines().items():
            suffix = "" if engine_id in installed else " (not installed)"
            self._ocr_box.addItem(name + suffix, engine_id)
            if engine_id == self._settings.ocr_engine:
                self._ocr_box.setCurrentIndex(self._ocr_box.count() - 1)
        form.addRow("OCR engine:", self._ocr_box)

        self._ocr_languages = QLineEdit(self._settings.ocr_languages)
        self._ocr_languages.setToolTip(
            "Tesseract: eng, urd, eng+urd — EasyOCR: en,ur — PaddleOCR: en"
        )
        form.addRow("Languages:", self._ocr_languages)

        self._tesseract_path = QLineEdit(self._settings.tesseract_path)
        self._tesseract_path.setPlaceholderText(
            r"Optional, e.g. C:\Program Files\Tesseract-OCR\tesseract.exe"
        )
        form.addRow("Tesseract path:", self._tesseract_path)

        form.addRow(
            QLabel(
                "Tip: install at least one engine — Tesseract is the lightest "
                "(pip install pytesseract + the Windows installer)."
            )
        )
        return widget

    # ------------------------------------------------------------------- ai
    def _build_ai_tab(self) -> QWidget:
        widget = QWidget(self)
        form = QFormLayout(widget)

        self._provider_box = QComboBox()
        for provider_id, name in available_providers().items():
            self._provider_box.addItem(name, provider_id)
            if provider_id == self._settings.vision_provider:
                self._provider_box.setCurrentIndex(self._provider_box.count() - 1)
        form.addRow("AI provider:", self._provider_box)

        self._api_keys: dict[str, QLineEdit] = {}
        for provider in _API_KEY_PROVIDERS:
            field = QLineEdit(self._settings.vision_api_key(provider))
            field.setEchoMode(QLineEdit.EchoMode.Password)
            self._api_keys[provider] = field
            form.addRow(f"{provider.capitalize()} API key:", field)

        self._model_fields: dict[str, QLineEdit] = {}
        for provider in (*_API_KEY_PROVIDERS, "local"):
            field = QLineEdit(self._settings.vision_model(provider))
            self._model_fields[provider] = field
            form.addRow(f"{provider.capitalize()} model:", field)

        self._local_endpoint = QLineEdit(self._settings.local_vision_endpoint)
        form.addRow("Local endpoint:", self._local_endpoint)

        form.addRow(
            QLabel(
                "With a provider configured, \"Read Current Page\" uses AI to "
                "reconstruct structure; otherwise OCR layout analysis is used."
            )
        )
        return widget

    # --------------------------------------------------------------- speech
    def _build_speech_tab(self) -> QWidget:
        widget = QWidget(self)
        form = QFormLayout(widget)

        self._microphone_box = QComboBox()
        self._microphone_box.addItem("System default", "")
        for name in list_input_devices():
            self._microphone_box.addItem(name, name)
            if name == self._settings.microphone_device:
                self._microphone_box.setCurrentIndex(self._microphone_box.count() - 1)
        form.addRow("Microphone:", self._microphone_box)

        self._speech_language_box = QComboBox()
        for code, label in _SPEECH_LANGUAGES.items():
            self._speech_language_box.addItem(label, code)
            if code == self._settings.speech_language:
                self._speech_language_box.setCurrentIndex(
                    self._speech_language_box.count() - 1
                )
        form.addRow("Dictation language:", self._speech_language_box)

        self._vosk_path = QLineEdit(self._settings.vosk_model_path)
        vosk_browse = QPushButton("Browse…")
        vosk_browse.clicked.connect(self._pick_vosk_model)
        vosk_row = QHBoxLayout()
        vosk_row.addWidget(self._vosk_path)
        vosk_row.addWidget(vosk_browse)
        form.addRow("Vosk model folder:", vosk_row)

        form.addRow(
            QLabel(
                "Download a model for your language from "
                "alphacephei.com/vosk/models (English: vosk-model-small-en-us; "
                "Roman Urdu works well with an English model)."
            )
        )
        return widget

    def _pick_vosk_model(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Choose Vosk model folder", self._vosk_path.text()
        )
        if folder:
            self._vosk_path.setText(folder)

    # ------------------------------------------------------------ shortcuts
    def _build_shortcuts_tab(self) -> QWidget:
        widget = QWidget(self)
        form = QFormLayout(widget)
        self._shortcut_edits: dict[str, QKeySequenceEdit] = {}
        for action_id in DEFAULT_SHORTCUTS:
            editor = QKeySequenceEdit(self._settings.shortcut(action_id))
            self._shortcut_edits[action_id] = editor
            form.addRow(f"{SHORTCUT_LABELS[action_id]}:", editor)
        return widget

    # ---------------------------------------------------------------- apply
    def _apply_and_close(self) -> None:
        settings = self._settings
        settings.theme = str(self._theme_box.currentData())
        settings.export_folder = self._export_folder.text().strip()
        settings.autosave_interval_minutes = self._autosave_spin.value()

        settings.output_mode = str(self._output_mode_box.currentData())
        settings.auto_read_after_import = self._auto_read_check.isChecked()
        settings.insert_page_separators = self._separators_check.isChecked()
        settings.continue_after_error = self._continue_check.isChecked()
        settings.ignore_decorative_underlines = self._underlines_check.isChecked()
        settings.ignore_watermarks = self._watermarks_check.isChecked()
        settings.ocr_fallback_when_ai_fails = self._ocr_fallback_check.isChecked()

        settings.ocr_engine = str(self._ocr_box.currentData())
        settings.ocr_languages = self._ocr_languages.text().strip() or "eng"
        settings.tesseract_path = self._tesseract_path.text().strip()

        settings.vision_provider = str(self._provider_box.currentData())
        for provider, field in self._api_keys.items():
            settings.set_vision_api_key(provider, field.text().strip())
        for provider, field in self._model_fields.items():
            settings.set_vision_model(provider, field.text().strip())
        settings.local_vision_endpoint = self._local_endpoint.text().strip()

        settings.microphone_device = str(self._microphone_box.currentData())
        settings.speech_language = str(self._speech_language_box.currentData())
        settings.vosk_model_path = self._vosk_path.text().strip()

        for action_id, editor in self._shortcut_edits.items():
            settings.set_shortcut(action_id, editor.keySequence().toString())

        logger.info("Settings updated")
        self.accept()
