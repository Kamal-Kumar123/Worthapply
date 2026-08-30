"""Abstract LLM provider interface.

All agents depend on this abstraction — never on a specific API.
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Type

from pydantic import BaseModel


@dataclass
class LLMUsage:
    """Token / cost accounting for a single LLM call."""

    model: str = ""
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    latency_ms: float = 0.0
    timestamp: str = ""
    run_id: str = ""
    agent_name: str = ""


@dataclass
class LLMResponse:
    """Unified response from any LLM provider."""

    content: str = ""
    structured: Any = None
    usage: LLMUsage = field(default_factory=LLMUsage)
    raw: dict = field(default_factory=dict)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class LLMProvider(ABC):
    """Abstract interface that every provider must implement."""

    provider_name: str = "base"

    # Approximate costs per 1M tokens — override in subclasses
    _input_cost_per_m: float = 0.0
    _output_cost_per_m: float = 0.0

    def __init__(self, model: str, **kwargs: Any) -> None:
        self.model = model
        self._run_id = kwargs.get("run_id", str(uuid.uuid4())[:8])
        self._cumulative_usage: list[LLMUsage] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        *,
        system: str = "",
        agent_name: str = "unknown",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a free-form text completion."""
        start = time.perf_counter()
        resp = await self._generate(
            prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        elapsed = (time.perf_counter() - start) * 1000
        self._fill_usage(resp, agent_name, elapsed)
        self._cumulative_usage.append(resp.usage)
        return resp

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        *,
        system: str = "",
        agent_name: str = "unknown",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate output conforming to a Pydantic model."""
        start = time.perf_counter()
        resp = await self._generate_structured(
            prompt,
            response_model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        elapsed = (time.perf_counter() - start) * 1000
        self._fill_usage(resp, agent_name, elapsed)
        self._cumulative_usage.append(resp.usage)
        return resp

    # ------------------------------------------------------------------
    # Cost / usage helpers
    # ------------------------------------------------------------------

    def get_cumulative_usage(self) -> list[LLMUsage]:
        return list(self._cumulative_usage)

    def get_total_cost(self) -> float:
        return sum(u.estimated_cost_usd for u in self._cumulative_usage)

    def get_total_tokens(self) -> int:
        return sum(u.total_tokens for u in self._cumulative_usage)

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens * self._input_cost_per_m / 1_000_000
            + output_tokens * self._output_cost_per_m / 1_000_000
        )

    def _fill_usage(
        self, resp: LLMResponse, agent_name: str, elapsed_ms: float
    ) -> None:
        u = resp.usage
        u.model = self.model
        u.provider = self.provider_name
        u.run_id = self._run_id
        u.agent_name = agent_name
        u.latency_ms = round(elapsed_ms, 1)
        u.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if u.estimated_cost_usd == 0.0:
            u.estimated_cost_usd = self._estimate_cost(
                u.input_tokens, u.output_tokens
            )

    # ------------------------------------------------------------------
    # Subclass hooks
    # ------------------------------------------------------------------

    @abstractmethod
    async def _generate(
        self,
        prompt: str,
        *,
        system: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> LLMResponse:
        ...

    @abstractmethod
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
        ...
