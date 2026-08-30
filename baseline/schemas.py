"""Baseline output schema — single structured response from one LLM call."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BaselineSkillMatch(BaseModel):
    skill: str
    match_level: str = ""  # "MATCHED", "PARTIALLY_MATCHED", "MISSING"
    evidence: str = ""


class BaselineRiskSignal(BaseModel):
    signal: str
    severity: str = "LOW"  # "LOW", "MEDIUM", "HIGH"
    evidence: str = ""


class BaselineReport(BaseModel):
    """The complete output from the baseline single-prompt approach."""

    # Job info
    job_title: str = ""
    company: str = ""
    location: str = ""
    employment_type: str = ""

    # Fit
    fit_score: float = Field(ge=0, le=100, default=50.0)
    required_skills: list[BaselineSkillMatch] = Field(default_factory=list)
    preferred_skills: list[BaselineSkillMatch] = Field(default_factory=list)
    experience_match: str = ""
    education_match: str = ""
    project_evidence: list[str] = Field(default_factory=list)
    fit_concerns: list[str] = Field(default_factory=list)

    # Opportunity assessment
    opportunity_confidence: float = Field(ge=0, le=100, default=50.0)
    company_verification_status: str = ""
    job_verification_status: str = ""

    # Risk
    risk_level: str = "LOW"  # "LOW", "MEDIUM", "HIGH"
    risk_signals: list[BaselineRiskSignal] = Field(default_factory=list)

    # Decision
    recommendation: str = ""  # "APPLY", "APPLY_IF_TIME", "LOW_PRIORITY"
    priority: str = ""  # "HIGH", "MEDIUM", "LOW"
    evidence_quality: str = ""
    reasons: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    summary: str = ""
