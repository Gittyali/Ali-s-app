"""AI vision provider interface."""

from __future__ import annotations

import abc

from PIL import Image


class VisionProviderError(RuntimeError):
    """Raised for any provider failure, with a user-readable message."""


class VisionProvider(abc.ABC):
    """Contract every AI vision backend must fulfil.

    Implementations convert a page image into constrained Markdown that
    preserves the document's structure (see :mod:`app.vision.prompts`).
    """

    #: Stable identifier stored in settings (e.g. ``"anthropic"``).
    provider_id: str = ""
    #: Human-readable name shown in the settings dialog.
    display_name: str = ""

    @abc.abstractmethod
    def read_page(
        self,
        image: Image.Image,
        ocr_hint: str = "",
        *,
        ignore_underlines: bool = True,
        ignore_watermarks: bool = True,
    ) -> str:
        """Return the page content as constrained Markdown.

        *ocr_hint* optionally carries raw OCR text for the same page; cloud
        models use it to cross-check hard-to-read regions.  The two flags
        toggle the decorative-underline and watermark/noise prompt clauses
        (Settings > Reading).  Implementations raise
        :class:`VisionProviderError` on any failure (network, auth,
        malformed response) with a message suitable for direct display.
        """

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """True when the provider has the credentials/endpoint it needs."""
