"""xAI / Grok cloud LLM provider (OpenAI-compatible API)."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Type

from openai import AsyncOpenAI
from pydantic import BaseModel

from worthapply.providers.base import LLMProvider, LLMResponse, LLMUsage

# Approximate pricing (USD per 1M tokens) — covers both xAI and Groq models
_PRICING: dict[str, tuple[float, float]] = {
    "grok-3-mini-fast": (0.10, 0.40),
    "grok-3-mini": (0.30, 0.50),
    "grok-3-fast": (5.00, 25.00),
    "grok-3": (3.00, 15.00),
    "qwen/qwen3.8-27b": (0.18, 0.22),
    "openai/gpt-oss-120b": (1.20, 1.20),
    "openai/gpt-oss-20b": (0.20, 0.20),
    "meta-llama/llama-prompt-guard-2-86m": (0.05, 0.05),
}


class XAIProvider(LLMProvider):
    """Provider backed by the xAI API (https://api.x.ai/v1)."""

    provider_name = "xai"

    def __init__(self, model: str | None = None, **kwargs: Any) -> None:
        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "XAI_API_KEY is not set. "
                "Add it to your .env file or export it as an environment variable."
            )

        model = model or os.getenv("XAI_MODEL", "grok-3-mini-fast")
        super().__init__(model, **kwargs)

        base_url = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=120.0)

        pricing = _PRICING.get(model, (0.30, 0.50))
        self._input_cost_per_m = pricing[0]
        self._output_cost_per_m = pricing[1]

    async def _generate(
        self,
        prompt: str,
        *,
        system: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> LLMResponse:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            completion = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            choice = completion.choices[0]
            usage = completion.usage
            return LLMResponse(
                content=choice.message.content or "",
                usage=LLMUsage(
                    input_tokens=usage.prompt_tokens if usage else 0,
                    output_tokens=usage.completion_tokens if usage else 0,
                    total_tokens=usage.total_tokens if usage else 0,
                ),
                raw=completion.model_dump() if hasattr(completion, "model_dump") else {},
            )
        except Exception as exc:
            return LLMResponse(error=str(exc))

    async def _generate_structured(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        *,
        system: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> LLMResponse:
        schema = response_model.model_json_schema()
        schema_instruction = (
            "You MUST respond with valid JSON that conforms to this schema:\n"
            f"```json\n{json.dumps(schema, indent=2)}\n```\n"
            "Respond ONLY with the JSON object. No markdown fences, no explanation."
        )
        full_system = f"{system}\n\n{schema_instruction}" if system else schema_instruction

        messages: list[dict[str, str]] = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": prompt},
        ]

        try:
            completion = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            choice = completion.choices[0]
            usage = completion.usage
            raw_content = choice.message.content or ""

            cleaned = raw_content.strip()
            cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = lines[1:]  # drop opening fence
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned = "\n".join(lines)

            parsed = response_model.model_validate_json(cleaned)
            return LLMResponse(
                content=raw_content,
                structured=parsed,
                usage=LLMUsage(
                    input_tokens=usage.prompt_tokens if usage else 0,
                    output_tokens=usage.completion_tokens if usage else 0,
                    total_tokens=usage.total_tokens if usage else 0,
                ),
                raw=completion.model_dump() if hasattr(completion, "model_dump") else {},
            )
        except json.JSONDecodeError as exc:
            return LLMResponse(
                content=raw_content if "raw_content" in dir() else "",
                error=f"JSON parse error: {exc}",
            )
        except Exception as exc:
            return LLMResponse(error=str(exc))
