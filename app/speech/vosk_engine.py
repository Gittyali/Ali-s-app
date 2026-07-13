"""Vosk offline streaming speech recognition.

Vosk gives low-latency partial results while speaking and a final result at
each utterance boundary — ideal for live dictation.  The user downloads a
model for their language from https://alphacephei.com/vosk/models (e.g.
``vosk-model-small-en-us-0.15``) and points Settings > Speech at the
extracted folder.  Roman Urdu dictation works well with an English model,
since Roman Urdu uses Latin script.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.speech.base import SAMPLE_RATE, SpeechEngine, SpeechEngineError, TranscriptEvent

logger = logging.getLogger(__name__)


class VoskEngine(SpeechEngine):
    """Streaming recogniser backed by a local Vosk model."""

    engine_id = "vosk"

    def __init__(self, model_path: str) -> None:
        self._model_path = model_path.strip()
        self._recognizer = None
        self._last_partial = ""

    @classmethod
    def is_available(cls) -> bool:
        try:
            import vosk  # noqa: F401
        except ImportError:
            return False
        return True

    def start(self) -> None:
        if not self.is_available():
            raise SpeechEngineError(
                "The 'vosk' package is not installed. Run: pip install vosk"
            )
        if not self._model_path or not Path(self._model_path).is_dir():
            raise SpeechEngineError(
                "No Vosk model folder configured. Download a model for your "
                "language from https://alphacephei.com/vosk/models, extract "
                "it, and select the folder in Settings > Speech."
            )
        import vosk

        vosk.SetLogLevel(-1)
        try:
            model = vosk.Model(self._model_path)
        except Exception as exc:
            raise SpeechEngineError(
                f"Could not load the Vosk model at '{self._model_path}': {exc}"
            ) from exc
        self._recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)
        self._recognizer.SetWords(False)
        self._last_partial = ""
        logger.info("Vosk model loaded from %s", self._model_path)

    def accept_audio(self, pcm_chunk: bytes) -> list[TranscriptEvent]:
        if self._recognizer is None:
            raise SpeechEngineError("Vosk engine used before start().")
        events: list[TranscriptEvent] = []
        if self._recognizer.AcceptWaveform(pcm_chunk):
            text = json.loads(self._recognizer.Result()).get("text", "").strip()
            self._last_partial = ""
            if text:
                events.append(TranscriptEvent(text=text, is_final=True))
        else:
            partial = json.loads(self._recognizer.PartialResult()).get(
                "partial", ""
            ).strip()
            if partial and partial != self._last_partial:
                self._last_partial = partial
                events.append(TranscriptEvent(text=partial, is_final=False))
        return events

    def finish(self) -> list[TranscriptEvent]:
        if self._recognizer is None:
            return []
        text = json.loads(self._recognizer.FinalResult()).get("text", "").strip()
        self._recognizer = None
        self._last_partial = ""
        return [TranscriptEvent(text=text, is_final=True)] if text else []
