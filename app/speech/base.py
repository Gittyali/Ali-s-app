"""Speech engine interface and transcript event types.

Engines are fed raw PCM chunks and return transcript events synchronously,
which keeps them trivially testable and independent of Qt and of the audio
capture mechanism.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass

#: All engines receive 16 kHz mono little-endian int16 PCM.
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH_BYTES = 2


@dataclass
class TranscriptEvent:
    """A piece of recognised speech.

    ``is_final`` distinguishes a stable, completed utterance from a partial
    hypothesis that will be revised as more audio arrives.
    """

    text: str
    is_final: bool


class SpeechEngineError(RuntimeError):
    """Raised with a user-readable message when an engine cannot run."""


class SpeechEngine(abc.ABC):
    """Contract every streaming speech backend must fulfil."""

    #: Stable identifier (e.g. ``"vosk"``).
    engine_id: str = ""

    @abc.abstractmethod
    def start(self) -> None:
        """Prepare the engine (load models). May raise SpeechEngineError."""

    @abc.abstractmethod
    def accept_audio(self, pcm_chunk: bytes) -> list[TranscriptEvent]:
        """Feed one PCM chunk; return any transcript events it produced."""

    @abc.abstractmethod
    def finish(self) -> list[TranscriptEvent]:
        """Flush buffered audio at the end of a session."""
