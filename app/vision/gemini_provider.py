"""Google Gemini vision provider (generateContent API over HTTPS)."""

from __future__ import annotations

import base64
import logging

import requests
from PIL import Image

from app.utils.image_utils import image_to_png_bytes
from app.vision.base import VisionProvider, VisionProviderError
from app.vision.prompts import SYSTEM_PROMPT, build_user_prompt, strip_code_fences

logger = logging.getLogger(__name__)

_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_TIMEOUT_SECONDS = 120


class GeminiVisionProvider(VisionProvider):
    """Reads pages with Gemini models via the Generative Language API."""

    provider_id = "gemini"
    display_name = "Gemini Vision (Google)"

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self._api_key = api_key.strip()
        self._model = model.strip() or "gemini-2.0-flash"

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def read_page(self, image: Image.Image, ocr_hint: str = "") -> str:
        if not self.is_configured():
            raise VisionProviderError(
                "No Gemini API key configured. Add one in Settings > AI Provider."
            )
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": base64.b64encode(
                                    image_to_png_bytes(image)
                                ).decode("ascii"),
                            }
                        },
                        {"text": build_user_prompt(ocr_hint)},
                    ],
                }
            ],
        }
        url = f"{_API_BASE}/{self._model}:generateContent"
        try:
            response = requests.post(
                url,
                json=payload,
                headers={"x-goog-api-key": self._api_key},
                timeout=_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise VisionProviderError(f"Could not reach the Gemini API: {exc}") from exc

        if response.status_code != 200:
            raise VisionProviderError(
                f"Gemini API error {response.status_code}: {response.text[:300]}"
            )
        try:
            candidates = response.json().get("candidates", [])
            if not candidates:
                raise VisionProviderError(
                    "The Gemini API returned no candidates (the request may "
                    "have been blocked by safety filters)."
                )
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts)
        except (ValueError, TypeError, AttributeError) as exc:
            raise VisionProviderError(
                f"Unexpected response from the Gemini API: {exc}"
            ) from exc

        logger.info("Gemini returned %d characters", len(text))
        return strip_code_fences(text)
