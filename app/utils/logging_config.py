"""Central logging configuration.

Call :func:`setup_logging` once at startup; afterwards every module obtains a
logger via ``logging.getLogger(__name__)``.  Logs go to a rotating file in the
user data directory and, at a higher threshold, to stderr.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys

from app.utils.paths import logs_dir

_LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
_MAX_BYTES = 2 * 1024 * 1024
_BACKUP_COUNT = 5

_configured = False


def setup_logging(level: int = logging.DEBUG) -> None:
    """Configure root logging handlers exactly once."""
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(level)

    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir() / "app.log",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root.addHandler(console_handler)

    # Third-party libraries tend to be noisy at DEBUG.
    for noisy in ("PIL", "urllib3", "requests", "fitz"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info("Logging initialised (dir=%s)", logs_dir())


def install_excepthook() -> None:
    """Log uncaught exceptions instead of letting the process die silently."""

    def _hook(exc_type: type, exc: BaseException, tb: object) -> None:
        logging.getLogger("uncaught").critical(
            "Uncaught exception", exc_info=(exc_type, exc, tb)
        )
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook
