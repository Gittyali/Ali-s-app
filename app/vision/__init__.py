"""AI Vision subsystem.

A provider-independent interface (:class:`~app.vision.base.VisionProvider`)
with implementations for Anthropic Claude, OpenAI, Google Gemini and local
OpenAI-compatible servers (Ollama, LM Studio).  Providers receive a page
image and return the document reconstructed as constrained Markdown, which
:mod:`app.formatting.markdown_parser` converts into the neutral model.
"""

from app.vision.base import VisionProvider, VisionProviderError
from app.vision.factory import available_providers, create_provider

__all__ = [
    "VisionProvider",
    "VisionProviderError",
    "available_providers",
    "create_provider",
]
