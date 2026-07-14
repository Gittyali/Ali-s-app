"""Main application window.

Layout: page sidebar (left) | image viewer (centre) | document editor
(right), a main toolbar and a status bar.  This class owns the project
lifecycle, page navigation, the read/dictate/export flows and autosave.

Page selection policy: pages change ONLY on explicit user action — sidebar
click, keyboard shortcut or voice command.  Nothing in this file (or any
other) switches pages automatically.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QStatusBar,
    QToolBar,
    QToolButton,
    QWidget,
)

from app import __app_name__, __version__
from app.core.autosave import (
    AutosaveManager,
    apply_snapshot,
    clear_snapshot_file,
    find_recoverable_snapshot,
)
from app.core.controller import (
    AppController,
    BatchSummary,
    PageReadSpec,
    ReadOutcome,
)
from app.core.page import PageStatus
from app.core.project import Project, ProjectError
from app.export import export_docx, export_pdf
from app.settings.settings_manager import SettingsManager
from app.speech.commands import VoiceCommandParser
from app.speech.session import DictationSession
from app.ui.editor import DocumentEditor
from app.ui.image_viewer import ImageViewer
from app.ui.settings_dialog import SettingsDialog
from app.ui.sidebar import PageSidebar
from app.ui.theme import stylesheet_for
from app.utils.image_utils import SUPPORTED_IMAGE_EXTENSIONS
from app.utils.paths import projects_dir
from app.utils.workers import run_in_background

logger = logging.getLogger(__name__)

_IMPORT_FILTER = (
    "Pages (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.pdf);;"
    "Images (*" + " *".join(SUPPORTED_IMAGE_EXTENSIONS) + ");;"
    "PDF documents (*.pdf);;All files (*)"
)


class MainWindow(QMainWindow):
    """Top-level window and application flow coordinator."""

    def __init__(self, settings: SettingsManager) -> None:
        super().__init__()
        self._settings = settings
        self._project: Project | None = None
        self._active_page_id: str = ""
        self._controller = AppController(settings, self)
        self._autosave = AutosaveManager(self)
        self._dictation = DictationSession(self)
        self._command_parser = VoiceCommandParser()
        # Append mode: page that hosts the combined document for the current
        # batch. Pinned at batch start so mid-batch navigation cannot split
        # the output across pages.
        self._append_host_page_id: str = ""
        # The page whose document the editor currently holds. In replace
        # mode this equals the active page; in append mode it is the host
        # page — the combined document stays visible on every page and
        # clicking a page scrolls to its section.
        self._editor_page_id: str = ""

        self.setWindowTitle(f"{__app_name__} {__version__}")
        self.resize(1400, 860)
        # Fully resizable from every edge/corner: only a small floor so the
        # window never collapses into an unusable sliver. All panes live in
        # a splitter and toolbars overflow into "»" popups, so any size works.
        self.setMinimumSize(720, 460)

        self._sidebar = PageSidebar(self)
        self._viewer = ImageViewer(self)
        self._editor = DocumentEditor(self)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._viewer)
        splitter.addWidget(self._editor)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([200, 620, 580])
        splitter.setChildrenCollapsible(True)
        self.setCentralWidget(splitter)

        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_status_bar()
        self._connect_signals()
        self._apply_theme()
        self._apply_shortcuts()
        self._update_action_states()

        # Deferred so the window is visible before any recovery dialog.
        QTimer.singleShot(0, self._startup_project)

    # ------------------------------------------------------------- actions
    def _build_actions(self) -> None:
        self._action_new_project = QAction("New Project", self)
        self._action_open_project = QAction("Open Project…", self)
        self._action_save_project = QAction("Save", self)
        self._action_import = QAction("Import Pages…", self)
        self._action_read_page = QAction("Read Current Page", self)
        self._action_read_all = QAction("Read All Pages", self)
        self._action_dictate = QAction("Start Dictation", self)
        self._action_dictate.setCheckable(True)
        self._action_prev_page = QAction("Previous Page", self)
        self._action_next_page = QAction("Next Page", self)
        self._action_export_docx = QAction("Export DOCX…", self)
        self._action_export_pdf = QAction("Export PDF…", self)
        self._action_settings = QAction("Settings…", self)
        self._action_exit = QAction("Exit", self)
        self._action_about = QAction("About", self)

        self._action_new_project.triggered.connect(self._new_project)
        self._action_open_project.triggered.connect(self._open_project)
        self._action_save_project.triggered.connect(self._save_project)
        self._action_import.triggered.connect(self._import_pages)
        self._action_read_page.triggered.connect(self._read_current_page)
        self._action_read_all.triggered.connect(self._read_all_pages)
        self._action_dictate.triggered.connect(self._toggle_dictation)
        self._action_prev_page.triggered.connect(lambda: self._navigate_relative(-1))
        self._action_next_page.triggered.connect(lambda: self._navigate_relative(1))
        self._action_export_docx.triggered.connect(lambda: self._export("docx"))
        self._action_export_pdf.triggered.connect(lambda: self._export("pdf"))
        self._action_settings.triggered.connect(self._open_settings)
        self._action_exit.triggered.connect(self.close)
        self._action_about.triggered.connect(self._show_about)

    def _build_menus(self) -> None:
        """Menu bar: every action is always reachable here, regardless of
        window width or toolbar overflow."""
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self._action_new_project)
        file_menu.addAction(self._action_open_project)
        file_menu.addAction(self._action_save_project)
        file_menu.addSeparator()
        file_menu.addAction(self._action_import)
        file_menu.addSeparator()
        file_menu.addAction(self._action_export_docx)
        file_menu.addAction(self._action_export_pdf)
        file_menu.addSeparator()
        file_menu.addAction(self._action_exit)

        read_menu = menubar.addMenu("&Reading")
        read_menu.addAction(self._action_read_page)
        read_menu.addAction(self._action_read_all)
        read_menu.addSeparator()
        read_menu.addAction(self._action_dictate)

        navigate_menu = menubar.addMenu("&Navigate")
        navigate_menu.addAction(self._action_prev_page)
        navigate_menu.addAction(self._action_next_page)

        tools_menu = menubar.addMenu("&Tools")
        tools_menu.addAction(self._action_settings)

        help_menu = menubar.addMenu("&Help")
        help_menu.addAction(self._action_about)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {__app_name__}",
            f"<b>{__app_name__}</b> {__version__}<br><br>"
            "Open-source AI document assistant: converts scanned pages and "
            "screenshots into editable, Word-like documents using OCR, AI "
            "vision and voice dictation.<br><br>"
            "Configure OCR engines and AI providers under "
            "<i>Tools &gt; Settings</i>.",
        )

    def _build_toolbar(self) -> None:
        # Standard-theme icons keep the look native and professional without
        # bundling an icon set; text stays beside the icon for clarity.
        style = self.style()
        icons = {
            self._action_new_project: style.standardIcon(
                style.StandardPixmap.SP_FileIcon
            ),
            self._action_open_project: style.standardIcon(
                style.StandardPixmap.SP_DirOpenIcon
            ),
            self._action_save_project: style.standardIcon(
                style.StandardPixmap.SP_DialogSaveButton
            ),
            self._action_import: style.standardIcon(
                style.StandardPixmap.SP_FileDialogNewFolder
            ),
            self._action_read_page: style.standardIcon(
                style.StandardPixmap.SP_MediaPlay
            ),
            self._action_read_all: style.standardIcon(
                style.StandardPixmap.SP_MediaSeekForward
            ),
            self._action_dictate: style.standardIcon(
                style.StandardPixmap.SP_MediaVolume
            ),
            self._action_prev_page: style.standardIcon(
                style.StandardPixmap.SP_ArrowLeft
            ),
            self._action_next_page: style.standardIcon(
                style.StandardPixmap.SP_ArrowRight
            ),
            self._action_settings: style.standardIcon(
                style.StandardPixmap.SP_FileDialogDetailedView
            ),
        }
        for action, icon in icons.items():
            action.setIcon(icon)

        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        for action in (
            self._action_new_project,
            self._action_open_project,
            self._action_save_project,
        ):
            toolbar.addAction(action)
        toolbar.addSeparator()
        toolbar.addAction(self._action_import)
        toolbar.addSeparator()
        toolbar.addAction(self._action_read_page)
        toolbar.addAction(self._action_read_all)
        toolbar.addAction(self._action_dictate)
        toolbar.addSeparator()
        toolbar.addAction(self._action_prev_page)
        toolbar.addAction(self._action_next_page)
        toolbar.addSeparator()

        # One compact Export dropdown instead of two wide buttons; the full
        # actions also live in File menu, so nothing can ever disappear.
        export_button = QToolButton(toolbar)
        export_button.setText("Export")
        export_button.setIcon(
            style.standardIcon(style.StandardPixmap.SP_DialogSaveButton)
        )
        export_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        export_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        export_menu = QMenu(export_button)
        export_menu.addAction(self._action_export_docx)
        export_menu.addAction(self._action_export_pdf)
        export_button.setMenu(export_menu)
        toolbar.addWidget(export_button)

        toolbar.addSeparator()
        toolbar.addAction(self._action_settings)
        self.addToolBar(toolbar)

    def _build_status_bar(self) -> None:
        bar = QStatusBar(self)
        self._status_page = QLabel("No project")
        self._status_job = QLabel("")
        self._status_dictation = QLabel("")

        # Batch progress: "Reading page X of N" + bar + cancel; hidden when idle.
        self._batch_progress_bar = QProgressBar(self)
        self._batch_progress_bar.setFixedWidth(220)
        self._batch_progress_bar.setTextVisible(True)
        self._batch_progress_bar.hide()
        self._batch_cancel_button = QToolButton(self)
        self._batch_cancel_button.setText("Cancel")
        self._batch_cancel_button.setToolTip(
            "Stop Read All Pages after the current page finishes"
        )
        self._batch_cancel_button.clicked.connect(self._cancel_batch)
        self._batch_cancel_button.hide()

        bar.addWidget(self._status_page)
        bar.addWidget(self._status_job, stretch=1)
        bar.addPermanentWidget(self._batch_progress_bar)
        bar.addPermanentWidget(self._batch_cancel_button)
        bar.addPermanentWidget(self._status_dictation)
        self.setStatusBar(bar)

    def _connect_signals(self) -> None:
        self._sidebar.page_selected.connect(self._on_page_selected)
        self._sidebar.selection_changed.connect(self._on_sidebar_selection_changed)
        self._sidebar.pages_reordered.connect(self._on_pages_reordered)
        self._sidebar.page_delete_requested.connect(self._on_page_delete)
        self._viewer.adjustments_changed.connect(self._on_adjustments_changed)
        self._editor.content_edited.connect(self._on_content_edited)
        self._editor.navigation_requested.connect(self._on_voice_navigation)

        self._controller.read_started.connect(self._on_read_started)
        self._controller.read_finished.connect(self._on_read_finished)
        self._controller.read_failed.connect(self._on_read_failed)
        self._controller.read_progress.connect(
            lambda _pid, stage: self._status_job.setText(stage)
        )
        self._controller.batch_started.connect(self._on_batch_started)
        self._controller.batch_progress.connect(self._on_batch_progress)
        self._controller.batch_page_failed.connect(self._on_batch_page_failed)
        self._controller.batch_finished.connect(self._on_batch_finished)

        self._dictation.partial_text.connect(self._on_dictation_partial)
        self._dictation.final_text.connect(self._on_dictation_final)
        self._dictation.error.connect(self._on_dictation_error)
        self._dictation.state_changed.connect(self._on_dictation_state)

        self._autosave.saved.connect(self._status_job.setText)
        self._settings.changed.connect(self._on_setting_changed)

    # ---------------------------------------------------------- appearance
    def _apply_theme(self) -> None:
        self.setStyleSheet(stylesheet_for(self._settings.theme))

    def _apply_shortcuts(self) -> None:
        mapping = {
            "import_pages": self._action_import,
            "read_current_page": self._action_read_page,
            "read_all_pages": self._action_read_all,
            "toggle_dictation": self._action_dictate,
            "next_page": self._action_next_page,
            "previous_page": self._action_prev_page,
            "save_project": self._action_save_project,
            "export_docx": self._action_export_docx,
            "export_pdf": self._action_export_pdf,
        }
        for action_id, action in mapping.items():
            action.setShortcut(QKeySequence(self._settings.shortcut(action_id)))

    def _on_setting_changed(self, key: str) -> None:
        if key == "general/theme":
            self._apply_theme()
        elif key.startswith("shortcuts/"):
            self._apply_shortcuts()
        elif key == "general/autosave_interval":
            self._autosave.set_interval(self._settings.autosave_interval_minutes)

    def _update_action_states(self) -> None:
        has_project = self._project is not None
        has_page = bool(self._active_page_id)
        has_pages = has_project and bool(self._project.pages)
        batch_running = self._controller.is_batch_active
        self._action_new_project.setEnabled(not batch_running)
        self._action_open_project.setEnabled(not batch_running)
        self._action_save_project.setEnabled(has_project)
        self._action_import.setEnabled(has_project and not batch_running)
        self._action_read_page.setEnabled(
            has_page and not self._controller.is_page_busy(self._active_page_id)
        )
        self._action_read_all.setEnabled(has_pages and not batch_running)
        self._action_dictate.setEnabled(has_page)
        self._action_prev_page.setEnabled(has_pages)
        self._action_next_page.setEnabled(has_pages)
        self._action_export_docx.setEnabled(has_pages and not batch_running)
        self._action_export_pdf.setEnabled(has_pages and not batch_running)
        self._editor.set_editor_enabled(has_page)

    # ----------------------------------------------------- project lifecycle
    def _startup_project(self) -> None:
        """Reopen the last project and offer crash recovery."""
        last = self._settings.last_project_path
        if last and Path(last).is_dir():
            try:
                self._set_project(Project.load(Path(last)))
            except ProjectError as exc:
                logger.warning("Could not reopen last project: %s", exc)
        if self._project is None:
            self._new_project(initial=True)
            if self._project is None:
                return

        snapshot = find_recoverable_snapshot()
        if snapshot is not None:
            snapshot_file, name = snapshot
            answer = QMessageBox.question(
                self,
                "Recover unsaved work?",
                f"An autosave snapshot for project '{name}' was found — the "
                "application may have closed unexpectedly.\n\nRecover the "
                "unsaved changes?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes and self._project is not None:
                restored = apply_snapshot(snapshot_file, self._project)
                self._refresh_sidebar()
                self._reload_active_page()
                self._status_job.setText(f"Recovered {restored} page(s) from autosave")
            clear_snapshot_file(snapshot_file)

    def _new_project(self, initial: bool = False) -> None:
        if not self._confirm_discard_changes():
            return
        name, accepted = QInputDialog.getText(
            self,
            "New Project",
            "Project name:",
            text="My Document" if initial else "",
        )
        if not accepted or not name.strip():
            return
        safe_name = "".join(c for c in name.strip() if c not in '\\/:*?"<>|')
        directory = projects_dir() / f"{safe_name}.adaproj"
        try:
            project = Project.create(directory, safe_name)
        except ProjectError as exc:
            self._show_error("Could not create project", str(exc))
            return
        self._set_project(project)

    def _open_project(self) -> None:
        if not self._confirm_discard_changes():
            return
        directory = QFileDialog.getExistingDirectory(
            self, "Open project folder (.adaproj)", str(projects_dir())
        )
        if not directory:
            return
        try:
            self._set_project(Project.load(Path(directory)))
        except ProjectError as exc:
            self._show_error("Could not open project", str(exc))

    def _set_project(self, project: Project) -> None:
        self._project = project
        self._active_page_id = ""
        self._editor_page_id = ""
        self._append_host_page_id = ""
        self._settings.last_project_path = str(project.directory)
        self._autosave.watch(project, self._settings.autosave_interval_minutes)
        self._refresh_sidebar()
        self._viewer.clear()
        self._editor.set_html("")
        self.setWindowTitle(f"{project.name} — {__app_name__}")
        self._status_page.setText(f"{project.name}: {len(project.pages)} pages")
        self._update_action_states()

    def _save_project(self) -> None:
        if self._project is None:
            return
        self._persist_active_document()
        try:
            self._project.save()
        except ProjectError as exc:
            self._show_error("Save failed", str(exc))
            return
        self._autosave.clear()
        self._status_job.setText("Project saved")

    def _confirm_discard_changes(self) -> bool:
        if self._project is None or not self._project.modified:
            return True
        answer = QMessageBox.question(
            self,
            "Unsaved changes",
            f"Project '{self._project.name}' has unsaved changes. Save before "
            "continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Save:
            self._save_project()
            return not self._project.modified
        return answer == QMessageBox.StandardButton.Discard

    # --------------------------------------------------------------- import
    def _import_pages(self) -> None:
        if self._project is None:
            return
        files, _selected_filter = QFileDialog.getOpenFileNames(
            self, "Import pages", "", _IMPORT_FILTER
        )
        if not files:
            return
        paths = [Path(f) for f in files]
        self._status_job.setText("Importing…")
        self._action_import.setEnabled(False)
        pages_before_import = len(self._project.pages)

        def do_import(progress_callback=None) -> int:
            new_pages = self._project.import_files(paths, progress_callback)
            return len(new_pages)

        def maybe_auto_read() -> None:
            if not self._settings.auto_read_after_import or self._project is None:
                return
            new_pages = self._project.pages[pages_before_import:]
            if new_pages:
                self._status_job.setText(
                    f"Auto-reading {len(new_pages)} imported page(s)…"
                )
                self._start_batch(new_pages)

        def done(count: int) -> None:
            self._finish_import()
            self._status_job.setText(f"Imported {count} page(s)")
            maybe_auto_read()

        def failed(message: str) -> None:
            # Partial imports still added pages; refresh before reporting.
            self._finish_import()
            self._show_error("Import problems", message)
            maybe_auto_read()

        run_in_background(
            do_import,
            on_result=done,
            on_error=failed,
            on_progress=lambda _pct, text: self._status_job.setText(text),
        )

    def _finish_import(self) -> None:
        self._refresh_sidebar()
        self._update_action_states()
        if self._project is not None:
            self._status_page.setText(
                f"{self._project.name}: {len(self._project.pages)} pages"
            )

    def _refresh_sidebar(self) -> None:
        if self._project is not None:
            self._sidebar.set_pages(self._project.pages)
            if self._active_page_id:
                self._sidebar.select_page(self._active_page_id)

    # ------------------------------------------------------ page navigation
    def _on_page_selected(self, page_id: str) -> None:
        """User clicked/keyed a page in the sidebar."""
        if page_id == self._active_page_id:
            return
        self._activate_page(page_id)

    def _on_sidebar_selection_changed(self, count: int) -> None:
        """Smart button: reflect how many pages a read would cover."""
        if count > 1:
            self._action_read_page.setText(f"Read Selected Pages ({count})")
        else:
            self._action_read_page.setText("Read Current Page")

    def _on_pages_reordered(self, ordered_ids: list) -> None:
        """Drag-and-drop reorder: the sidebar order is authoritative."""
        if self._project is None:
            return
        if self._project.reorder([str(page_id) for page_id in ordered_ids]):
            self._sidebar.refresh_labels(self._project.pages)
            index = self._project.page_index(self._active_page_id)
            if index >= 0:
                self._status_page.setText(
                    f"Page {index + 1} of {len(self._project.pages)}"
                )
            self._status_job.setText("Pages reordered")
        else:
            # Defensive: an inconsistent drop result rebuilds the list from
            # the project, which is the source of truth.
            self._refresh_sidebar()

    def _navigate_relative(self, delta: int) -> None:
        """Keyboard/voice navigation to an adjacent page."""
        if self._project is None or not self._project.pages:
            return
        current = self._project.page_index(self._active_page_id)
        target = 0 if current < 0 else current + delta
        if not 0 <= target < len(self._project.pages):
            self._status_job.setText(
                "Already at the first page" if delta < 0 else "Already at the last page"
            )
            return
        page_id = self._project.pages[target].page_id
        self._sidebar.select_page(page_id)
        self._activate_page(page_id)

    def _navigate_to_number(self, number: int) -> None:
        """Voice navigation: 'go to page N' (1-based)."""
        if self._project is None:
            return
        index = number - 1
        if not 0 <= index < len(self._project.pages):
            self._status_job.setText(
                f"Page {number} does not exist (project has "
                f"{len(self._project.pages)} pages)"
            )
            return
        page_id = self._project.pages[index].page_id
        self._sidebar.select_page(page_id)
        self._activate_page(page_id)

    def _on_voice_navigation(self, kind: str, number: int) -> None:
        if kind == "next":
            self._navigate_relative(1)
        elif kind == "previous":
            self._navigate_relative(-1)
        elif kind == "goto":
            self._navigate_to_number(number)

    def _document_host_for(self, page_id: str) -> str:
        """Which page's document the editor should show for *page_id*.

        Replace mode: the page itself.  Append mode: the page hosting the
        combined document, so every sidebar click keeps the full result
        visible.  Legacy projects saved before the host id existed derive
        it when exactly one page carries content.
        """
        if self._project is None or self._settings.output_mode != "append":
            return page_id
        host = self._project.host_page_id
        if host:
            index = self._project.page_index(host)
            if index >= 0 and self._project.pages[index].document_html.strip():
                return host
        pages_with_content = [
            page for page in self._project.pages if page.document_html.strip()
        ]
        if len(pages_with_content) == 1:
            self._project.host_page_id = pages_with_content[0].page_id
            return self._project.host_page_id
        return page_id

    def _activate_page(self, page_id: str) -> None:
        """Make *page_id* the active page (explicit user intent only)."""
        if self._project is None:
            return
        self._persist_active_document()
        index = self._project.page_index(page_id)
        if index < 0:
            return
        page = self._project.pages[index]
        self._active_page_id = page_id
        self._viewer.show_page(
            page.image_path,
            page.rotation,
            page.brightness,
            page.contrast,
            page.enhanced,
        )
        host_id = self._document_host_for(page_id)
        if host_id != self._editor_page_id:
            host_index = self._project.page_index(host_id)
            if host_index >= 0:
                self._editor.set_html(self._project.pages[host_index].document_html)
                self._editor_page_id = host_id
        if host_id != page_id:
            # Combined document: jump to this page's section.
            self._editor.scroll_to_anchor(f"page-{page_id}")
        self._status_page.setText(
            f"Page {index + 1} of {len(self._project.pages)}"
            + (f" — {page.source_name}" if page.source_name else "")
        )
        self._update_action_states()

    def _reload_active_page(self) -> None:
        if self._project is None or not self._editor_page_id:
            return
        index = self._project.page_index(self._editor_page_id)
        if index >= 0:
            self._editor.set_html(self._project.pages[index].document_html)

    def _persist_active_document(self) -> None:
        """Write the editor's content back to the page it belongs to."""
        if self._project is None or not self._editor_page_id:
            return
        index = self._project.page_index(self._editor_page_id)
        if index < 0:
            return
        page = self._project.pages[index]
        html = "" if self._editor.is_empty() else self._editor.to_html()
        if html != page.document_html:
            self._project.set_page_document(
                self._editor_page_id, html, edited_by_user=True
            )
            self._sidebar.update_page_status(index, page)

    def _on_content_edited(self) -> None:
        # Content is persisted lazily (on page switch / save / export); here
        # we only mark the project dirty so autosave picks it up.
        if self._project is not None and self._editor_page_id:
            self._project.mark_modified()

    def _on_adjustments_changed(
        self, rotation: int, brightness: float, contrast: float, enhanced: bool
    ) -> None:
        if self._project is None or not self._active_page_id:
            return
        index = self._project.page_index(self._active_page_id)
        if index < 0:
            return
        page = self._project.pages[index]
        page.rotation = rotation
        page.brightness = brightness
        page.contrast = contrast
        page.enhanced = enhanced
        self._project.mark_modified()

    def _on_page_delete(self, page_id: str) -> None:
        if self._project is None:
            return
        index = self._project.page_index(page_id)
        if index < 0:
            return
        answer = QMessageBox.question(
            self,
            "Remove page",
            f"Remove page {index + 1} from the project? The original file on "
            "disk is not affected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._project.remove_page(page_id)
        if page_id == self._active_page_id:
            self._active_page_id = ""
            self._viewer.clear()
        if page_id == self._editor_page_id:
            self._editor_page_id = ""
            self._editor.set_html("")
        self._finish_import()

    # ------------------------------------------------------------ AI reading
    def _read_current_page(self) -> None:
        """Read the active page — or, with a multi-selection, the selected
        pages sequentially in sidebar order (smart button)."""
        if self._project is None:
            return
        selected = self._sidebar.selected_page_ids()
        if len(selected) > 1:
            pages = []
            for page_id in selected:  # already in sidebar order
                index = self._project.page_index(page_id)
                if index >= 0:
                    pages.append(self._project.pages[index])
            self._start_batch(pages)
            return

        if not self._active_page_id:
            return
        # In replace mode a re-read overwrites the page's document; confirm.
        # Append mode adds to the combined document, nothing is lost.
        if self._settings.output_mode == "replace" and not self._editor.is_empty():
            answer = QMessageBox.question(
                self,
                "Replace page content?",
                "This page already has content in the editor. Reading the "
                "page again will replace it. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        image = self._viewer.processed_image()
        if image is None:
            self._show_error(
                "Page not ready",
                "The page image is still loading. Try again in a moment.",
            )
            return
        self._controller.read_page(self._active_page_id, image)

    def _set_page_status(self, page_id: str, status: PageStatus) -> None:
        if self._project is None:
            return
        index = self._project.page_index(page_id)
        if index >= 0:
            page = self._project.pages[index]
            page.status = status
            self._sidebar.update_page_status(index, page)

    def _on_read_started(self, page_id: str) -> None:
        self._set_page_status(page_id, PageStatus.PROCESSING)
        self._status_job.setText("Reading page…")
        if not self._controller.is_batch_active:
            # Indeterminate "busy" bar for a single-page read.
            self._batch_progress_bar.setRange(0, 0)
            self._batch_progress_bar.setFormat("Reading…")
            self._batch_progress_bar.show()
        self._update_action_states()

    def _hide_single_read_progress(self) -> None:
        if not self._controller.is_batch_active:
            self._batch_progress_bar.hide()

    def _on_read_finished(self, outcome: ReadOutcome) -> None:
        if self._project is None:
            return
        page_index = self._project.page_index(outcome.page_id)
        if page_index < 0:
            return  # page was removed while its read was in flight

        if self._settings.output_mode == "append":
            self._append_outcome(outcome, page_index)
        else:
            self._store_outcome_per_page(outcome)
        self._set_page_status(outcome.page_id, PageStatus.READ)

        # Requirement: extracted text survives a crash mid-batch — snapshot
        # after every completed page.
        if self._controller.is_batch_active:
            self._autosave.flush()

        self._hide_single_read_progress()
        source = "AI" if outcome.used_ai else "OCR"
        self._status_job.setText(f"Page read complete ({source})")
        if outcome.warning:
            self._status_job.setText(outcome.warning)
        self._update_action_states()

    def _append_outcome(self, outcome: ReadOutcome, page_index: int) -> None:
        """Append mode: every page joins ONE continuous document."""
        # Host = the batch's pinned page, else the current combined host,
        # else (single read before anything was active) the page just read.
        host_id = self._append_host_page_id
        if not host_id and self._active_page_id:
            host_id = self._document_host_for(self._active_page_id)
        if not host_id:
            self._sidebar.select_page(outcome.page_id)
            self._activate_page(outcome.page_id)
            host_id = outcome.page_id
        separator = ""
        if self._settings.insert_page_separators:
            separator = f"— Page {page_index + 1} —"
        # Anchor lets sidebar clicks jump to this page's section later.
        anchor = f"page-{outcome.page_id}"

        self._project.host_page_id = host_id
        if host_id == self._editor_page_id:
            self._editor.append_document(outcome.document, separator, anchor)
            self._persist_active_document()
            return
        # The editor is showing something else: append to the host page's
        # stored document without touching what the user is looking at.
        from PySide6.QtGui import QTextDocument as _QTextDocument

        host_index = self._project.page_index(host_id)
        if host_index < 0:  # host page deleted mid-batch; fall back
            self._store_outcome_per_page(outcome)
            return
        holder = _QTextDocument()
        holder.setHtml(self._project.pages[host_index].document_html)
        from app.formatting.rich_text import append_structured_document

        append_structured_document(holder, outcome.document, separator, anchor)
        self._project.set_page_document(host_id, holder.toHtml(), edited_by_user=False)

    def _store_outcome_per_page(self, outcome: ReadOutcome) -> None:
        """Replace mode: content replaces the owning page's document."""
        if outcome.page_id == self._editor_page_id:
            # The user may have switched pages while reading; content goes to
            # the page it belongs to, and the editor only updates if that
            # page is still active.
            self._editor.insert_document(outcome.document, replace=True)
            self._persist_active_document()
        else:
            from PySide6.QtGui import QTextCursor as _QTextCursor
            from PySide6.QtGui import QTextDocument as _QTextDocument

            from app.formatting.rich_text import insert_structured_document

            holder = _QTextDocument()
            insert_structured_document(_QTextCursor(holder), outcome.document)
            self._project.set_page_document(
                outcome.page_id, holder.toHtml(), edited_by_user=False
            )

    def _on_read_failed(self, page_id: str, message: str) -> None:
        self._set_page_status(page_id, PageStatus.FAILED)
        self._hide_single_read_progress()
        self._status_job.setText("Reading failed")
        self._show_error("Could not read page", message)
        self._update_action_states()

    # ------------------------------------------------------ Read All Pages
    def _read_all_pages(self) -> None:
        """Read every imported page sequentially, in page order."""
        if self._project is None or not self._project.pages:
            return
        if self._controller.is_batch_active:
            return
        self._persist_active_document()

        # "Unread" is tracked by workflow status (pending or failed), not
        # stored content — in append mode only the host page carries the
        # combined document.
        unread = [
            page
            for page in self._project.pages
            if page.status in (PageStatus.PENDING, PageStatus.FAILED)
        ]
        box = QMessageBox(self)
        box.setWindowTitle("Read All Pages")
        box.setText(
            f"This project has {len(self._project.pages)} pages "
            f"({len(unread)} unread or failed).\n\n"
            "Each page is read in order with the configured AI provider "
            "(or OCR). Failed pages are marked ✗ in the sidebar and can be "
            "retried with 'Only unread/failed pages'."
        )
        all_button = box.addButton("Read all pages", QMessageBox.ButtonRole.AcceptRole)
        unread_button = box.addButton(
            "Only unread/failed pages", QMessageBox.ButtonRole.AcceptRole
        )
        unread_button.setEnabled(bool(unread))
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()

        clicked = box.clickedButton()
        if clicked is all_button:
            targets = list(self._project.pages)
        elif clicked is unread_button:
            targets = unread
        else:
            return
        self._start_batch(targets)

    def _start_batch(self, pages: list) -> None:
        """Begin a sequential batch read of *pages* (already in sidebar order)."""
        if self._project is None or not pages or self._controller.is_batch_active:
            return
        if self._settings.output_mode == "append":
            # The combined document needs a host page. Use the existing
            # combined host if there is one, else the active page, else the
            # first batch page (the user just started this read).
            if not self._active_page_id:
                self._sidebar.select_page(pages[0].page_id)
                self._activate_page(pages[0].page_id)
            self._append_host_page_id = self._document_host_for(self._active_page_id)
        self._persist_active_document()
        specs = [
            PageReadSpec(
                page_id=page.page_id,
                image_path=page.image_path,
                rotation=page.rotation,
                brightness=page.brightness,
                contrast=page.contrast,
                enhanced=page.enhanced,
                label=f"Page {self._project.page_index(page.page_id) + 1}",
            )
            for page in pages
        ]
        self._controller.read_all_pages(specs)

    def _cancel_batch(self) -> None:
        self._controller.cancel_batch()
        self._batch_cancel_button.setEnabled(False)
        self._status_job.setText("Cancelling after the current page…")

    def _on_batch_started(self, total: int) -> None:
        self._batch_progress_bar.setRange(0, total)
        self._batch_progress_bar.setValue(0)
        self._batch_progress_bar.setFormat(f"Page 1 of {total}")
        self._batch_progress_bar.show()
        self._batch_cancel_button.setEnabled(True)
        self._batch_cancel_button.show()
        self._status_job.setText(f"Reading {total} pages…")
        self._update_action_states()

    def _on_batch_progress(self, current: int, total: int, page_id: str) -> None:
        self._batch_progress_bar.setValue(current - 1)
        self._batch_progress_bar.setFormat(f"Page {current} of {total}")
        label = ""
        if self._project is not None:
            index = self._project.page_index(page_id)
            if index >= 0:
                label = f" (Page {index + 1})"
        self._status_job.setText(f"Reading page {current} of {total}{label}…")
        self._set_page_status(page_id, PageStatus.PROCESSING)

    def _on_batch_page_failed(self, page_id: str, message: str) -> None:
        # Failures are collected in the summary; the sidebar marks the page
        # with ✗ so it is visibly a retry candidate, not silently blank.
        self._set_page_status(page_id, PageStatus.FAILED)
        logger.warning("Batch page failed (%s): %s", page_id, message)

    def _on_batch_finished(self, summary: BatchSummary) -> None:
        self._append_host_page_id = ""
        self._batch_progress_bar.hide()
        self._batch_cancel_button.hide()
        self._update_action_states()
        self._autosave.flush()  # a lot of new content; snapshot it now

        if summary.total == 0 and summary.failures:
            self._status_job.setText("Read All Pages failed")
            self._show_error("Read All Pages failed", summary.failures[0][1])
            return

        state = "cancelled" if summary.cancelled else "complete"
        self._status_job.setText(
            f"Reading {state}: {summary.succeeded} completed, "
            f"{len(summary.failures)} failed"
        )
        if summary.failures:
            detail = "\n".join(
                f"• {label}: {message}" for label, message in summary.failures[:10]
            )
            if len(summary.failures) > 10:
                detail += f"\n… and {len(summary.failures) - 10} more"
            QMessageBox.warning(
                self,
                "Reading finished with problems",
                f"{summary.succeeded} completed\n"
                f"{len(summary.failures)} failed\n\nFailed pages (skipped):\n"
                f"{detail}\n\n"
                "Failed pages are marked ✗ in the sidebar. Fix the cause "
                "(network, rate limit, API key — see Settings), then run "
                "Read All Pages > 'Only unread/failed pages' to retry them.",
            )
        elif not summary.cancelled:
            QMessageBox.information(
                self,
                "Reading complete",
                f"{summary.succeeded} completed\n0 failed\n\n"
                "Review the document in the editor, then use Export DOCX/PDF "
                "to produce the final file.",
            )

    # ------------------------------------------------------------ dictation
    def _toggle_dictation(self) -> None:
        if self._dictation.is_active:
            self._dictation.stop()
            return
        self._dictation.start(
            model_path=self._settings.vosk_model_path,
            device_name=self._settings.microphone_device,
        )

    def _on_dictation_state(self, listening: bool) -> None:
        self._action_dictate.setChecked(listening)
        self._action_dictate.setText(
            "Stop Dictation" if listening else "Start Dictation"
        )
        self._status_dictation.setText("● Listening…" if listening else "")

    def _on_dictation_partial(self, text: str) -> None:
        self._status_job.setText(f"Hearing: {text}")

    def _on_dictation_final(self, text: str) -> None:
        self._status_job.setText("")
        for part in self._command_parser.parse(text):
            if part.command is not None:
                self._editor.apply_command(part.command)
            elif part.text:
                self._editor.insert_dictation(part.text)

    def _on_dictation_error(self, message: str) -> None:
        self._action_dictate.setChecked(False)
        self._show_error("Dictation problem", message)

    # --------------------------------------------------------------- export
    def _export(self, fmt: str) -> None:
        if self._project is None or not self._project.pages:
            return
        self._persist_active_document()
        page_htmls = [page.document_html for page in self._project.pages]
        if not any(html.strip() for html in page_htmls):
            self._show_error(
                "Nothing to export",
                "No page has any document content yet. Read pages or dictate "
                "text first.",
            )
            return

        default_dir = Path(self._settings.export_folder)
        default_dir.mkdir(parents=True, exist_ok=True)
        suffix = ".docx" if fmt == "docx" else ".pdf"
        target, _selected_filter = QFileDialog.getSaveFileName(
            self,
            f"Export {fmt.upper()}",
            str(default_dir / (self._project.name + suffix)),
            f"{fmt.upper()} files (*{suffix})",
        )
        if not target:
            return
        output = Path(target)
        if output.suffix.lower() != suffix:
            output = output.with_suffix(suffix)

        self._status_job.setText(f"Exporting {fmt.upper()}…")
        exporter = export_docx if fmt == "docx" else export_pdf

        run_in_background(
            exporter,
            page_htmls,
            output,
            on_result=lambda path: self._status_job.setText(f"Exported to {path}"),
            on_error=lambda message: self._show_error("Export failed", message),
        )

    # -------------------------------------------------------------- settings
    def _open_settings(self) -> None:
        dialog = SettingsDialog(self._settings, self)
        dialog.exec()

    # ---------------------------------------------------------------- misc
    def _show_error(self, title: str, message: str) -> None:
        logger.error("%s: %s", title, message)
        QMessageBox.warning(self, title, message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._dictation.is_active:
            self._dictation.stop()
        if self._controller.is_batch_active:
            self._controller.cancel_batch()
        self._persist_active_document()
        if self._project is not None and self._project.modified:
            answer = QMessageBox.question(
                self,
                "Save before closing?",
                f"Project '{self._project.name}' has unsaved changes.",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if answer == QMessageBox.StandardButton.Save:
                self._save_project()
        if self._project is not None and not self._project.modified:
            self._autosave.clear()
        event.accept()
