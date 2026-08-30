"""Structured tracing for agent trajectories.

Captures: run_id, agent_name, input, context, tool_calls, output,
timestamps, model/provider, token usage, cost — without secrets.

Supports concurrent agents (parallel stages) via per-agent active traces.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from worthapply.providers.base import LLMUsage


@dataclass
class ToolCall:
    tool: str = ""
    input: dict = field(default_factory=dict)
    output: str = ""
    duration_ms: float = 0.0
    error: str | None = None


@dataclass
class AgentTrace:
    """Full trace for one agent invocation."""

    run_id: str = ""
    case_id: str = ""
    agent_name: str = ""
    started_at: str = ""
    finished_at: str = ""
    input_summary: str = ""
    context_summary: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    output_summary: str = ""
    retries: int = 0
    errors: list[str] = field(default_factory=list)
    usage: LLMUsage | None = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        if d.get("usage") and isinstance(d["usage"], dict):
            d["usage"].pop("run_id", None)
        return d


class Tracer:
    """Collects and persists agent traces for a pipeline run.

    Parallel-safe: each agent keeps its own active trace keyed by name.
    """

    def __init__(
        self, run_id: str | None = None, trace_dir: str | Path = "traces"
    ) -> None:
        self.run_id = run_id or str(uuid.uuid4())[:12]
        self.trace_dir = Path(trace_dir)
        self._traces: list[AgentTrace] = []
        self._active: dict[str, AgentTrace] = {}
        self._start_times: dict[str, float] = {}

    def begin(self, agent_name: str, case_id: str = "", **context: Any) -> None:
        self._start_times[agent_name] = time.perf_counter()
        self._active[agent_name] = AgentTrace(
            run_id=self.run_id,
            case_id=case_id,
            agent_name=agent_name,
            started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            input_summary=str(context.get("input_summary", "")),
            context_summary=str(context.get("context_summary", "")),
        )

    def log_tool_call(
        self,
        tool: str,
        inp: dict,
        output: str,
        duration_ms: float = 0,
        error: str | None = None,
        agent_name: str | None = None,
    ) -> None:
        current = self._resolve(agent_name)
        if current:
            current.tool_calls.append(
                ToolCall(
                    tool=tool,
                    input=inp,
                    output=output[:2000],
                    duration_ms=duration_ms,
                    error=error,
                )
            )

    def log_retry(self, error: str, agent_name: str | None = None) -> None:
        current = self._resolve(agent_name)
        if current:
            current.retries += 1
            current.errors.append(error)

    def end(
        self,
        output_summary: str,
        usage: LLMUsage | None = None,
        agent_name: str | None = None,
    ) -> AgentTrace:
        if agent_name is None:
            if len(self._active) == 1:
                agent_name = next(iter(self._active))
            elif not self._active:
                raise RuntimeError("No active trace — call begin() first")
            else:
                raise RuntimeError(
                    "Multiple active traces — pass agent_name to end()"
                )

        current = self._active.pop(agent_name, None)
        if current is None:
            raise RuntimeError(
                f"No active trace for '{agent_name}' — call begin() first"
            )

        start = self._start_times.pop(agent_name, time.perf_counter())
        elapsed = (time.perf_counter() - start) * 1000
        current.finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        current.duration_ms = round(elapsed, 1)
        current.output_summary = output_summary[:5000]
        current.usage = usage
        self._traces.append(current)
        return current

    def save(self, case_id: str = "") -> Path:
        out_dir = self.trace_dir / (case_id or self.run_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        for trace in self._traces:
            path = out_dir / f"{trace.agent_name}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(trace.to_dict(), f, indent=2, default=str)

        return out_dir

    def get_traces(self) -> list[AgentTrace]:
        return list(self._traces)

    def _resolve(self, agent_name: str | None) -> AgentTrace | None:
        if agent_name and agent_name in self._active:
            return self._active[agent_name]
        if agent_name is None and len(self._active) == 1:
            return next(iter(self._active.values()))
        return None
