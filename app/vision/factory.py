"""Vision provider registry and factory."""

from __future__ import annotations

import logging

from app.settings.settings_manager import SettingsManager
from app.vision.anthropic_provider import AnthropicVisionProvider
from app.vision.base import VisionProvider
from app.vision.gemini_provider import GeminiVisionProvider
from app.vision.local_provider import LocalVisionProvider
from app.vision.openai_provider import OpenAIVisionProvider

logger = logging.getLogger(__name__)

PROVIDER_NONE = "none"

_PROVIDER_NAMES: dict[str, str] = {
    PROVIDER_NONE: "None (OCR only)",
    AnthropicVisionProvider.provider_id: AnthropicVisionProvider.display_name,
    OpenAIVisionProvider.provider_id: OpenAIVisionProvider.display_name,
    GeminiVisionProvider.provider_id: GeminiVisionProvider.display_name,
    LocalVisionProvider.provider_id: LocalVisionProvider.display_name,
}


def available_providers() -> dict[str, str]:
    """Map of ``provider_id -> display_name`` for the settings dialog."""
    return dict(_PROVIDER_NAMES)


def create_provider(settings: SettingsManager) -> VisionProvider | None:
    """Build the provider selected in settings, or ``None`` for OCR-only mode."""
    provider_id = settings.vision_provider
    if provider_id in ("", PROVIDER_NONE):
        return None
    if provider_id == AnthropicVisionProvider.provider_id:
        return AnthropicVisionProvider(
            api_key=settings.vision_api_key(provider_id),
            model=settings.vision_model(provider_id),
        )
    if provider_id == OpenAIVisionProvider.provider_id:
        return OpenAIVisionProvider(
            api_key=settings.vision_api_key(provider_id),
            model=settings.vision_model(provider_id),
        )
    if provider_id == GeminiVisionProvider.provider_id:
        return GeminiVisionProvider(
            api_key=settings.vision_api_key(provider_id),
            model=settings.vision_model(provider_id),
        )
    if provider_id == LocalVisionProvider.provider_id:
        return LocalVisionProvider(
            endpoint=settings.local_vision_endpoint,
            model=settings.vision_model(provider_id),
            api_key=settings.vision_api_key(provider_id),
        )
    logger.warning("Unknown vision provider '%s'; using OCR only", provider_id)
    return None
