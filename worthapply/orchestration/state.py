"""Pipeline state — tracks progress through the analysis workflow."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from worthapply.models.schemas import (
    CompanyVerification,
    JobProfile,
    OpportunityReport,
    RiskAssessment,
    StudentFitResult,
)
from worthapply.providers.base import LLMUsage


class StageStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class StageResult:
    status: StageStatus = StageStatus.PENDING
    started_at: float = 0.0
    finished_at: float = 0.0
    error: str | None = None
    usage: LLMUsage | None = None

    @property
    def elapsed_ms(self) -> float:
        if self.started_at and self.finished_at:
            return round((self.finished_at - self.started_at) * 1000, 1)
        return 0.0


@dataclass
class PipelineState:
    """Full state for one opportunity analysis run."""

    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    started_at: float = field(default_factory=time.perf_counter)

    # Inputs
    student_text: str = ""
    job_text: str = ""
    job_url: str = ""

    # Intermediate results
    job_profile: JobProfile | None = None
    student_fit: StudentFitResult | None = None
    company_verification: CompanyVerification | None = None
    risk_assessment: RiskAssessment | None = None
    evidence_quality: str = ""
    unsupported_claims: int = 0

    # Final output
    report: OpportunityReport | None = None

    # Stage tracking
    stages: dict[str, StageResult] = field(default_factory=lambda: {
        "job_intelligence": StageResult(),
        "student_fit": StageResult(),
        "company_verification": StageResult(),
        "opportunity_risk": StageResult(),
        "evidence_verification": StageResult(),
        "decision_synthesis": StageResult(),
    })

    # Usage tracking
    all_usage: list[LLMUsage] = field(default_factory=list)

    @property
    def total_elapsed_ms(self) -> float:
        return round((time.perf_counter() - self.started_at) * 1000, 1)

    @property
    def total_cost(self) -> float:
        return sum(u.estimated_cost_usd for u in self.all_usage)

    @property
    def total_tokens(self) -> int:
        return sum(u.total_tokens for u in self.all_usage)

    def begin_stage(self, name: str) -> None:
        if name in self.stages:
            self.stages[name].status = StageStatus.RUNNING
            self.stages[name].started_at = time.perf_counter()

    def complete_stage(self, name: str, usage: LLMUsage | None = None) -> None:
        if name in self.stages:
            self.stages[name].status = StageStatus.COMPLETED
            self.stages[name].finished_at = time.perf_counter()
            self.stages[name].usage = usage
            if usage:
                self.all_usage.append(usage)

    def fail_stage(self, name: str, error: str) -> None:
        if name in self.stages:
            self.stages[name].status = StageStatus.FAILED
            self.stages[name].finished_at = time.perf_counter()
            self.stages[name].error = error

    def get_progress(self) -> list[dict[str, Any]]:
        """Return stage progress for UI display."""
        return [
            {
                "stage": name,
                "status": result.status.value,
                "elapsed_ms": result.elapsed_ms,
            }
            for name, result in self.stages.items()
        ]

    def to_summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "total_elapsed_ms": self.total_elapsed_ms,
            "total_cost_usd": round(self.total_cost, 6),
            "total_tokens": self.total_tokens,
            "stages": {
                name: {
                    "status": r.status.value,
                    "elapsed_ms": r.elapsed_ms,
                    "error": r.error,
                }
                for name, r in self.stages.items()
            },
        }
