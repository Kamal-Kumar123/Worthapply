"""Base agent class — shared infrastructure for all WorthApply agents."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Type

from pydantic import BaseModel

from worthapply.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


def _rate_limit_wait_seconds(error: str) -> float | None:
    """Extract suggested wait from Groq/OpenAI 429 messages, if present."""
    if "429" not in error and "rate_limit" not in error.lower():
        return None
    match = re.search(r"try again in ([\d.]+)s", error, re.IGNORECASE)
    if match:
        return float(match.group(1)) + 1.0
    return 16.0


class BaseAgent:
    """Common base for every WorthApply agent.

    Provides: LLM access, structured generation, retry logic, logging.
    Subclasses implement `run()` with their specific logic.
    """

    name: str = "base_agent"
    max_retries: int = 3

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def _local_max_tokens(self, max_tokens: int) -> int:
        if getattr(self.provider, "provider_name", "") == "local":
            return min(max_tokens, 1024)
        return max_tokens

    async def generate(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            resp = await self.provider.generate(
                prompt,
                system=system,
                agent_name=self.name,
                temperature=temperature,
                max_tokens=self._local_max_tokens(max_tokens),
            )
            if resp.ok:
                return resp
            last_error = resp.error or "Unknown error"
            wait = _rate_limit_wait_seconds(last_error)
            if wait is not None:
                logger.warning(
                    "[%s] rate limited (attempt %d). Waiting %.1fs…",
                    self.name,
                    attempt,
                    wait,
                )
                print(
                    f"\n  [rate limit] {self.name} — waiting {wait:.0f}s then retrying..."
                )
                await asyncio.sleep(wait)
            else:
                logger.warning(
                    "[%s] attempt %d failed: %s", self.name, attempt, last_error
                )
                await asyncio.sleep(1.5 * attempt)

        return LLMResponse(
            error=f"All {self.max_retries} attempts failed. Last: {last_error}"
        )

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        *,
        system: str = "",
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            resp = await self.provider.generate_structured(
                prompt,
                response_model,
                system=system,
                agent_name=self.name,
                temperature=temperature,
                max_tokens=self._local_max_tokens(max_tokens),
            )
            if resp.ok:
                return resp
            last_error = resp.error or "Unknown error"
            wait = _rate_limit_wait_seconds(last_error)
            if wait is not None:
                logger.warning(
                    "[%s] rate limited (attempt %d). Waiting %.1fs…",
                    self.name,
                    attempt,
                    wait,
                )
                print(
                    f"\n  [rate limit] {self.name} — waiting {wait:.0f}s then retrying..."
                )
                await asyncio.sleep(wait)
            else:
                logger.warning(
                    "[%s] structured attempt %d failed: %s",
                    self.name,
                    attempt,
                    last_error,
                )
                await asyncio.sleep(1.5 * attempt)

        return LLMResponse(
            error=f"All {self.max_retries} attempts failed. Last: {last_error}"
        )
