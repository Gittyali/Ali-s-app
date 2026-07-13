"""Background task infrastructure.

Long-running work (OCR, AI vision calls, PDF rendering, exports) runs on the
global ``QThreadPool`` through :class:`Worker` so the UI thread never blocks.
Results and errors come back as Qt signals, which Qt delivers safely across
threads to the receiving object's thread.
"""

from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    """Signals emitted by a :class:`Worker`.

    ``finished`` always fires exactly once, after either ``result`` or
    ``error``.
    """

    result = Signal(object)
    error = Signal(str)
    progress = Signal(int, str)
    finished = Signal()


class Worker(QRunnable):
    """Run *fn* on the thread pool and report through :class:`WorkerSignals`.

    If *fn* accepts a ``progress_callback`` keyword argument it receives a
    ``Callable[[int, str], None]`` it may call to publish progress updates.
    """

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:  # noqa: D102 - QRunnable entry point
        try:
            if "progress_callback" in self._fn.__code__.co_varnames:
                self._kwargs.setdefault("progress_callback", self.signals.progress.emit)
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:
            logger.error(
                "Background task %s failed: %s\n%s",
                getattr(self._fn, "__name__", self._fn),
                exc,
                traceback.format_exc(),
            )
            self.signals.error.emit(str(exc))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


def run_in_background(
    fn: Callable[..., Any],
    *args: Any,
    on_result: Callable[[Any], None] | None = None,
    on_error: Callable[[str], None] | None = None,
    on_progress: Callable[[int, str], None] | None = None,
    on_finished: Callable[[], None] | None = None,
    **kwargs: Any,
) -> Worker:
    """Convenience wrapper: build a worker, wire callbacks, start it."""
    worker = Worker(fn, *args, **kwargs)
    if on_result is not None:
        worker.signals.result.connect(on_result)
    if on_error is not None:
        worker.signals.error.connect(on_error)
    if on_progress is not None:
        worker.signals.progress.connect(on_progress)
    if on_finished is not None:
        worker.signals.finished.connect(on_finished)
    QThreadPool.globalInstance().start(worker)
    return worker
