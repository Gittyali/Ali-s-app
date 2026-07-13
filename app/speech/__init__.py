"""Speech subsystem.

* :mod:`app.speech.base` — engine interface and transcript events.
* :mod:`app.speech.recorder` — microphone capture (sounddevice).
* :mod:`app.speech.vosk_engine` — offline streaming recognition (Vosk).
* :mod:`app.speech.session` — Qt-facing dictation session (signals).
* :mod:`app.speech.commands` — voice formatting/navigation command parser
  for English, Urdu and Roman Urdu.
"""

from app.speech.commands import CommandType, ParsedCommand, VoiceCommandParser
from app.speech.session import DictationSession

__all__ = [
    "CommandType",
    "DictationSession",
    "ParsedCommand",
    "VoiceCommandParser",
]
