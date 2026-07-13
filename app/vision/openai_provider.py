"""OpenAI vision provider (Chat Completions API over HTTPS).

Also serves as the base for :class:`~app.vision.local_provider.LocalVisionProvider`
since local servers (Ollama, LM Studio) expose the same wire format.
"""

from __future__ import annotations

import base64
import logging

import requests
from PIL import Image

from app.utils.image_utils import image_to_png_bytes
from app.vision.base import VisionProvider, VisionProviderError
from app.vision.prompts import SYSTEM_PROMPT, build_user_prompt, strip_code_fences

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 180


class OpenAIVisionProvider(VisionProvider):
    """Reads pages with GPT vision models via the Chat Completions API."""

    provider_id = "openai"
    display_name = "OpenAI Vision"

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self._api_key = api_key.strip()
        self._model = model.strip() or "gpt-4o"
        self._base_url = base_url.rstrip("/")

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def read_page(
        self,
        image: Image.Image,
        ocr_hint: str = "",
        *,
        ignore_underlines: bool = True,
        ignore_watermarks: bool = True,
    ) -> str:
        if not self.is_configured():
            raise VisionProviderError(
                f"{self.display_name} is not configured. "
                "Add credentials in Settings > AI Provider."
            )
        data_url = "data:image/png;base64," + base64.b64encode(
            image_to_png_bytes(image)
        ).decode("ascii")
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {
                            "type": "text",
                            "text": build_user_prompt(
                                ocr_hint, ignore_underlines, ignore_watermarks
                            ),
                        },
                    ],
                },
            ],
        }
        url = f"{self._base_url}/chat/completions"
        try:
            response = requests.post(
                url, json=payload, headers=self._headers(), timeout=_TIMEOUT_SECONDS
            )
        except requests.RequestException as exc:
            raise VisionProviderError(
                f"Could not reach {self.display_name} at {url}: {exc}"
            ) from exc

        if response.status_code != 200:
            raise VisionProviderError(
                f"{self.display_name} error {response.status_code}: "
                f"{response.text[:300]}"
            )
        try:
            text = response.json()["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise VisionProviderError(
                f"Unexpected response from {self.display_name}: {exc}"
            ) from exc

        logger.info("%s returned %d characters", self.display_name, len(text))
        return strip_code_fences(text)
