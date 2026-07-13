"""Light and dark application themes.

Plain Qt stylesheets — deliberately simple and animation-free, tuned for
long editing sessions and readable contrast.
"""

from __future__ import annotations

_COMMON = """
QToolBar { spacing: 4px; padding: 3px; border: none; }
QToolButton { padding: 4px 8px; border-radius: 4px; }
QStatusBar QLabel { padding: 0 8px; }
QListWidget::item { padding: 4px; }
QSplitter::handle { width: 3px; }
"""

LIGHT_THEME = _COMMON + """
QMainWindow, QDialog, QWidget { background: #f5f5f5; color: #202020; }
QTextEdit, QLineEdit, QSpinBox, QComboBox, QListWidget {
    background: #ffffff; color: #202020;
    border: 1px solid #c8c8c8; border-radius: 4px;
}
QToolButton:hover { background: #e0e0e0; }
QToolButton:checked { background: #cfe3f7; }
QToolBar { background: #ececec; }
QStatusBar { background: #ececec; color: #404040; }
QListWidget::item:selected { background: #cfe3f7; color: #202020; }
QGraphicsView { background: #d9d9d9; border: 1px solid #c8c8c8; }
QPushButton {
    background: #ffffff; border: 1px solid #b8b8b8;
    border-radius: 4px; padding: 5px 14px;
}
QPushButton:hover { background: #eaeaea; }
QTabWidget::pane { border: 1px solid #c8c8c8; }
"""

DARK_THEME = _COMMON + """
QMainWindow, QDialog, QWidget { background: #262626; color: #e0e0e0; }
QTextEdit, QLineEdit, QSpinBox, QComboBox, QListWidget {
    background: #1e1e1e; color: #e0e0e0;
    border: 1px solid #454545; border-radius: 4px;
}
QToolButton:hover { background: #3a3a3a; }
QToolButton:checked { background: #2d4a66; }
QToolBar { background: #2e2e2e; }
QStatusBar { background: #2e2e2e; color: #b0b0b0; }
QListWidget::item:selected { background: #2d4a66; color: #e0e0e0; }
QGraphicsView { background: #1a1a1a; border: 1px solid #454545; }
QPushButton {
    background: #333333; border: 1px solid #505050;
    border-radius: 4px; padding: 5px 14px; color: #e0e0e0;
}
QPushButton:hover { background: #3d3d3d; }
QTabWidget::pane { border: 1px solid #454545; }
QMenu { background: #2e2e2e; color: #e0e0e0; }
QMenu::item:selected { background: #2d4a66; }
"""


def stylesheet_for(theme: str) -> str:
    """Return the stylesheet for a theme name (``light``/``dark``)."""
    return DARK_THEME if theme == "dark" else LIGHT_THEME
