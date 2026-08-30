"""Optional local LLM provider (Ollama or compatible OpenAI-API server).

Use for development/testing to avoid cloud API quota. For deployment set
LLM_PROVIDER=xai (or groq-compatible cloud).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Type

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from worthapply.providers.base import LLMProvider, LLMResponse, LLMUsage


def _compact_schema(model: Type[BaseModel]) -> str:
    """Short field list — full JSON Schema blows the local context window."""
    props = model.model_json_schema().get("properties", {})
    lines = []
    for name, meta in props.items():
        t = meta.get("type") or meta.get("anyOf", [{"type": "any"}])[0].get("type", "any")
        if "$ref" in meta:
            t = "object"
        if meta.get("items"):
            t = "array"
        lines.append(f'  "{name}": <{t}>')
    return "{\n" + ",\n".join(lines) + "\n}"


class LocalProvider(LLMProvider):
    """Provider backed by a local OpenAI-compatible server (e.g. Ollama)."""

    provider_name = "local"
    _input_cost_per_m = 0.0
    _output_cost_per_m = 0.0

    def __init__(self, model: str | None = None, **kwargs: Any) -> None:
        model = model or os.getenv("LOCAL_MODEL", "worthapply-dev")
        super().__init__(model, **kwargs)

        base_url = os.getenv("LOCAL_BASE_URL", "http://localhost:11434/v1")
        self._num_ctx = int(os.getenv("LOCAL_NUM_CTX", "4096"))
        self._client = AsyncOpenAI(
            api_key="ollama",
            base_url=base_url,
            timeout=300.0,
        )
        self._ollama_options = {"num_ctx": self._num_ctx}

    def _cap_tokens(self, max_tokens: int) -> int:
        # Leave headroom for prompt inside the context window
        return max(256, min(max_tokens, self._num_ctx // 2))

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
        max_tokens = self._cap_tokens(max_tokens)

        try:
            completion = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body={"options": self._ollama_options},
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
            return LLMResponse(
                error=(
                    f"Local LLM error: {exc}. "
                    "Ensure Ollama is running (`ollama serve`) and LOCAL_MODEL is pulled."
                )
            )

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
        max_tokens = self._cap_tokens(max_tokens)
        schema_hint = _compact_schema(response_model)
        schema_instruction = (
            "Respond ONLY with a single valid JSON object matching this shape:\n"
            f"{schema_hint}\n"
            "Use arrays of strings where listed as array. No markdown. No extra text."
        )
        full_system = f"{system}\n\n{schema_instruction}" if system else schema_instruction
        # Truncate long prompts for tiny local models
        user_prompt = prompt if len(prompt) < 3500 else prompt[:3500] + "\n...(truncated)"

        messages: list[dict[str, str]] = [
            {"role": "system", "content": full_system[:2500]},
            {"role": "user", "content": user_prompt},
        ]

        raw_content = ""
        try:
            completion = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                extra_body={"options": self._ollama_options},
            )
            choice = completion.choices[0]
            usage = completion.usage
            raw_content = choice.message.content or ""
            parsed = self._parse_structured(raw_content, response_model)
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
        except ValidationError as exc:
            return LLMResponse(
                content=raw_content,
                error=f"Local LLM validation error: {exc}",
            )
        except json.JSONDecodeError as exc:
            return LLMResponse(
                content=raw_content,
                error=f"JSON parse error from local model: {exc}",
            )
        except Exception as exc:
            if "response_format" in str(exc).lower() or "json_object" in str(exc).lower():
                return await self._generate_structured_plain(
                    messages, response_model, temperature, max_tokens
                )
            return LLMResponse(
                error=(
                    f"Local LLM error: {exc}. "
                    "Ensure Ollama is running (`ollama serve`) and LOCAL_MODEL is pulled."
                )
            )

    async def _generate_structured_plain(
        self,
        messages: list[dict[str, str]],
        response_model: Type[BaseModel],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        raw_content = ""
        try:
            completion = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body={"options": self._ollama_options},
            )
            choice = completion.choices[0]
            usage = completion.usage
            raw_content = choice.message.content or ""
            parsed = self._parse_structured(raw_content, response_model)
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
        except Exception as exc:
            return LLMResponse(
                content=raw_content,
                error=f"Local LLM error: {exc}",
            )

    def _parse_structured(
        self, raw: str, response_model: Type[BaseModel]
    ) -> BaseModel:
        cleaned = self._clean_json(raw)
        data = json.loads(cleaned)
        return response_model.model_validate(data)

    @staticmethod
    def _clean_json(raw: str) -> str:
        cleaned = raw.strip()
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]
        # Fix trailing commas common in small-model JSON
        cleaned = re.sub(r",\s*}", "}", cleaned)
        cleaned = re.sub(r",\s*]", "]", cleaned)
        return cleaned
