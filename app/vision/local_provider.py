"""Local vision provider for OpenAI-compatible servers.

Works with Ollama (``http://localhost:11434/v1``), LM Studio and any other
server speaking the Chat Completions wire format with vision models such as
``llava`` or ``qwen2.5-vl``.  No API key is required by default.
"""

from __future__ import annotations

import logging

from app.vision.openai_provider import OpenAIVisionProvider

logger = logging.getLogger(__name__)


class LocalVisionProvider(OpenAIVisionProvider):
    """Reads pages with a locally hosted vision model."""

    provider_id = "local"
    display_name = "Local Vision Model"

    def __init__(
        self,
        endpoint: str = "http://localhost:11434/v1",
        model: str = "llava",
        api_key: str = "",
    ) -> None:
        super().__init__(
            api_key=api_key or "local",
            model=model or "llava",
            base_url=endpoint or "http://localhost:11434/v1",
        )

    def is_configured(self) -> bool:
        # A local endpoint needs no key; the base URL is always set.
        return True
