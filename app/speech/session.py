"""Qt-facing dictation session.

Owns the microphone recorder and the speech engine, runs them on a dedicated
``QThread`` and republishes results as signals.  Qt delivers the signals on
the UI thread, so slots may touch widgets directly.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QThread, Signal

from app.speech.base import SpeechEngine, SpeechEngineError
from app.speech.recorder import AudioRecorder
from app.speech.vosk_engine import VoskEngine

logger = logging.getLogger(__name__)


class _DictationWorker(QObject):
    """Runs the capture/recognise loop; lives on the session's QThread."""

    partial = Signal(str)
    final = Signal(str)
    failed = Signal(str)
    stopped = Signal()

    def __init__(self, recorder: AudioRecorder, engine: SpeechEngine) -> None:
        super().__init__()
        self._recorder = recorder
        self._engine = engine
        self._running = False

    def stop(self) -> None:
        """Request the loop to end (thread-safe: sets a flag only)."""
        self._running = False

    def run(self) -> None:
        """Blocking loop: start devices, pump audio, emit transcripts."""
        try:
            self._engine.start()
            self._recorder.start()
        except SpeechEngineError as exc:
            self.failed.emit(str(exc))
            self.stopped.emit()
            return

        self._running = True
        try:
            while self._running:
                chunk = self._recorder.read(timeout=0.2)
                if chunk is None:
                    continue
                for event in self._engine.accept_audio(chunk):
                    if event.is_final:
                        self.final.emit(event.text)
                    else:
                        self.partial.emit(event.text)
            for event in self._engine.finish():
                if event.text:
                    self.final.emit(event.text)
        except Exception as exc:  # Never let the audio loop kill the app.
            logger.exception("Dictation loop failed")
            self.failed.emit(f"Dictation stopped unexpectedly: {exc}")
        finally:
            self._recorder.stop()
            self.stopped.emit()


class DictationSession(QObject):
    """Start/stop wrapper around one live dictation run.

    Signals:
        * ``partial_text(str)`` — live hypothesis for the current utterance.
        * ``final_text(str)`` — completed utterance (feed to command parser).
        * ``error(str)`` — user-readable failure description.
        * ``state_changed(bool)`` — True when listening, False when idle.
    """

    partial_text = Signal(str)
    final_text = Signal(str)
    error = Signal(str)
    state_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _DictationWorker | None = None

    @property
    def is_active(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start(self, model_path: str, device_name: str = "") -> None:
        """Begin listening. Emits ``error`` instead of raising."""
        if self.is_active:
            logger.warning("Dictation already active; ignoring start request")
            return
        if not VoskEngine.is_available():
            self.error.emit(
                "Speech recognition is not installed. Run: pip install vosk "
                "sounddevice"
            )
            return

        recorder = AudioRecorder(device_name=device_name)
        engine = VoskEngine(model_path=model_path)
        worker = _DictationWorker(recorder, engine)
        thread = QThread(self)
        worker.moveToThread(thread)

        worker.partial.connect(self.partial_text)
        worker.final.connect(self.final_text)
        worker.failed.connect(self.error)
        worker.stopped.connect(thread.quit)
        thread.started.connect(worker.run)
        thread.finished.connect(self._on_thread_finished)

        self._worker = worker
        self._thread = thread
        thread.start()
        self.state_changed.emit(True)
        logger.info("Dictation session started")

    def stop(self) -> None:
        """Stop listening; the final utterance is still flushed."""
        if self._worker is not None:
            self._worker.stop()

    def _on_thread_finished(self) -> None:
        if self._thread is not None:
            self._thread.deleteLater()
        if self._worker is not None:
            self._worker.deleteLater()
        self._thread = None
        self._worker = None
        self.state_changed.emit(False)
        logger.info("Dictation session ended")
