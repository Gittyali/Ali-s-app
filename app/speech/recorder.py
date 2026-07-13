"""Microphone capture via ``sounddevice``.

The recorder pushes raw PCM chunks into a thread-safe queue from the audio
callback (which runs on PortAudio's thread); the dictation session drains
the queue on its own worker thread.  No Qt types are used here.
"""

from __future__ import annotations

import logging
import queue
from typing import Any

from app.speech.base import CHANNELS, SAMPLE_RATE, SpeechEngineError

logger = logging.getLogger(__name__)

#: Capture block size: 0.1 s of audio, a good latency/overhead balance.
BLOCK_FRAMES = SAMPLE_RATE // 10


def list_input_devices() -> list[str]:
    """Names of microphone-capable devices, for the settings dialog."""
    try:
        import sounddevice
    except (ImportError, OSError):
        return []
    names: list[str] = []
    try:
        for device in sounddevice.query_devices():
            if int(device.get("max_input_channels", 0)) > 0:
                name = str(device.get("name", "")).strip()
                if name and name not in names:
                    names.append(name)
    except Exception as exc:  # pragma: no cover - hardware dependent
        logger.warning("Could not enumerate audio devices: %s", exc)
    return names


class AudioRecorder:
    """Continuously captures 16 kHz mono int16 PCM from a microphone."""

    def __init__(self, device_name: str = "") -> None:
        self._device_name = device_name.strip()
        self._queue: queue.Queue[bytes] = queue.Queue()
        self._stream: Any = None

    @classmethod
    def is_available(cls) -> bool:
        try:
            import sounddevice  # noqa: F401
        except (ImportError, OSError):
            return False
        return True

    def _resolve_device(self) -> int | None:
        """Translate the configured device name into a device index."""
        if not self._device_name:
            return None
        import sounddevice

        for index, device in enumerate(sounddevice.query_devices()):
            if (
                int(device.get("max_input_channels", 0)) > 0
                and str(device.get("name", "")).strip() == self._device_name
            ):
                return index
        logger.warning(
            "Configured microphone '%s' not found; using default", self._device_name
        )
        return None

    def start(self) -> None:
        """Open the input stream. Raises SpeechEngineError on failure."""
        if not self.is_available():
            raise SpeechEngineError(
                "The 'sounddevice' package is not installed (or PortAudio is "
                "missing). Run: pip install sounddevice"
            )
        import sounddevice

        def callback(indata: Any, frames: int, time_info: Any, status: Any) -> None:
            if status:
                logger.debug("Audio stream status: %s", status)
            self._queue.put(bytes(indata))

        try:
            self._stream = sounddevice.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=BLOCK_FRAMES,
                channels=CHANNELS,
                dtype="int16",
                device=self._resolve_device(),
                callback=callback,
            )
            self._stream.start()
        except Exception as exc:
            self._stream = None
            raise SpeechEngineError(
                f"Could not open the microphone: {exc}. Check Settings > Speech "
                "and that no other application holds the device exclusively."
            ) from exc
        logger.info("Microphone stream started (device=%s)", self._device_name or "default")

    def read(self, timeout: float = 0.2) -> bytes | None:
        """Next PCM chunk, or None if none arrived within *timeout* seconds."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self) -> None:
        """Close the stream and discard buffered audio."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:  # pragma: no cover - hardware dependent
                logger.warning("Error closing audio stream: %s", exc)
            self._stream = None
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        logger.info("Microphone stream stopped")
