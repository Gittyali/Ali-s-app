"""AI Document Assistant — application entry point.

Run with::

    python main.py
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app import __app_name__, __organization__, __version__
from app.settings.settings_manager import SettingsManager
from app.ui.main_window import MainWindow
from app.utils.logging_config import install_excepthook, setup_logging


def main() -> int:
    """Create the application, show the main window, run the event loop."""
    setup_logging()
    install_excepthook()

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(__organization__)

    settings = SettingsManager()
    window = MainWindow(settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
