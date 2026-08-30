"""Provider factory — selects the right LLMProvider at runtime."""

from __future__ import annotations

import os
from typing import Any

from worthapply.providers.base import LLMProvider


def get_provider(**kwargs: Any) -> LLMProvider:
    """Return an LLMProvider based on the LLM_PROVIDER env var.

    Raises clear errors for misconfiguration rather than silently falling back.
    """
    provider_name = os.getenv("LLM_PROVIDER", "xai").lower().strip()

    if provider_name == "xai":
        from worthapply.providers.xai_provider import XAIProvider

        return XAIProvider(**kwargs)

    if provider_name == "local":
        from worthapply.providers.local_provider import LocalProvider

        return LocalProvider(**kwargs)

    raise ValueError(
        f"Unknown LLM_PROVIDER='{provider_name}'. "
        "Supported values: 'xai' (cloud, default), 'local' (development)."
    )
