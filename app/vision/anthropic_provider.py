"""Anthropic Claude vision provider (Messages API over HTTPS)."""

from __future__ import annotations

import base64
import logging

import requests
from PIL import Image

from app.utils.image_utils import image_to_png_bytes
from app.vision.base import VisionProvider, VisionProviderError
from app.vision.prompts import SYSTEM_PROMPT, build_user_prompt, strip_code_fences

logger = logging.getLogger(__name__)

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
_TIMEOUT_SECONDS = 120
_MAX_TOKENS = 8192


class AnthropicVisionProvider(VisionProvider):
    """Reads pages with Claude models via the Anthropic Messages API."""

    provider_id = "anthropic"
    display_name = "Claude Vision (Anthropic)"

    def __init__(self, api_key: str, model: str = "claude-sonnet-5") -> None:
        self._api_key = api_key.strip()
        self._model = model.strip() or "claude-sonnet-5"

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def read_page(self, image: Image.Image, ocr_hint: str = "") -> str:
        if not self.is_configured():
            raise VisionProviderError(
                "No Anthropic API key configured. Add one in Settings > AI Provider."
            )
        payload = {
            "model": self._model,
            "max_tokens": _MAX_TOKENS,
            "system": SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": base64.b64encode(
                                    image_to_png_bytes(image)
                                ).decode("ascii"),
                            },
                        },
                        {"type": "text", "text": build_user_prompt(ocr_hint)},
                    ],
                }
            ],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _API_VERSION,
            "content-type": "application/json",
        }
        try:
            response = requests.post(
                _API_URL, json=payload, headers=headers, timeout=_TIMEOUT_SECONDS
            )
        except requests.RequestException as exc:
            raise VisionProviderError(f"Could not reach the Anthropic API: {exc}") from exc

        if response.status_code != 200:
            raise VisionProviderError(
                f"Anthropic API error {response.status_code}: {response.text[:300]}"
            )
        try:
            blocks = response.json()["content"]
            text = "".join(
                block.get("text", "") for block in blocks if block.get("type") == "text"
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise VisionProviderError(
                f"Unexpected response from the Anthropic API: {exc}"
            ) from exc

        logger.info("Anthropic returned %d characters", len(text))
        return strip_code_fences(text)
