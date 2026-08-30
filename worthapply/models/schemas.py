"""Core data models for WorthApply.

These Pydantic models define the structured inputs/outputs exchanged between
agents and used in the final Opportunity Intelligence Report.

Validators coerce common small-local-model JSON quirks so development on
Ollama does not fail on shape mismatches.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Enums ──────────────────────────────────────────────────────────────

class SkillMatchLevel(str, Enum):
    MATCHED = "MATCHED"
    PARTIALLY_MATCHED = "PARTIALLY_MATCHED"
    MISSING = "MISSING"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    CONFLICTING = "CONFLICTING"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Recommendation(str, Enum):
    APPLY = "APPLY"
    APPLY_IF_TIME = "APPLY_IF_TIME"
    LOW_PRIORITY = "LOW_PRIORITY"


class Priority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


def _as_str_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v.strip() else []
    if not isinstance(v, list):
        return [str(v)]
    out: list[str] = []
    for item in v:
        if isinstance(item, dict):
            if "skill" in item and "evidence" in item:
                out.append(f"{item.get('skill')}: {item.get('evidence')}")
            elif "text" in item:
                out.append(str(item["text"]))
            elif "evidence" in item:
                out.append(str(item["evidence"]))
            else:
                out.append(json.dumps(item, ensure_ascii=False))
        else:
            out.append(str(item))
    return out


def _as_float(v: Any, default: float = 0.0) -> float:
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _normalize_enum(v: Any, mapping: dict[str, str], default: str) -> str:
    if v is None:
        return default
    if isinstance(v, Enum):
        return str(v.value)
    s = str(v).strip().upper().replace(" ", "_").replace("-", "_")
    # Handle "SkillMatchLevel.MATCHED" style strings
    if "." in s:
        s = s.rsplit(".", 1)[-1]
    aliases = {
        "PARTIAL": "PARTIALLY_MATCHED",
        "PARTIAL_MATCH": "PARTIALLY_MATCHED",
        "PARTIALLY": "PARTIALLY_MATCHED",
        "YES": "MATCHED",
        "NO": "MISSING",
        "NONE": "MISSING",
        "OK": "LOW",
        "MODERATE": "MEDIUM",
        "MED": "MEDIUM",
        "APPLY_IF_POSSIBLE": "APPLY_IF_TIME",
        "MAYBE": "APPLY_IF_TIME",
        "SKIP": "LOW_PRIORITY",
        "REJECT": "LOW_PRIORITY",
    }
    s = aliases.get(s, s)
    return mapping.get(s, default)


# ── Job Profile ────────────────────────────────────────────────────────

class SkillRequirement(BaseModel):
    skill: str
    required: bool = True
    category: str = ""


class JobProfile(BaseModel):
    title: str = ""
    company: str = ""
    location: str = ""
    employment_type: str = ""
    experience_requirement: str = ""
    education_requirements: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    posting_date: Optional[str] = None
    application_url: str = ""
    source_url: str = ""

    @field_validator(
        "title",
        "company",
        "location",
        "employment_type",
        "experience_requirement",
        "application_url",
        "source_url",
        mode="before",
    )
    @classmethod
    def _none_to_str(cls, v: Any) -> str:
        return "" if v is None else str(v)

    @field_validator(
        "education_requirements",
        "required_skills",
        "preferred_skills",
        "responsibilities",
        mode="before",
    )
    @classmethod
    def _coerce_lists(cls, v: Any) -> list[str]:
        return _as_str_list(v)


# ── Student Profile ───────────────────────────────────────────────────

class StudentProfile(BaseModel):
    name: str = ""
    email: str = ""
    education: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    experience: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    summary: str = ""
    raw_text: str = ""

    @field_validator(
        "education", "skills", "experience", "projects", "certifications", mode="before"
    )
    @classmethod
    def _coerce_lists(cls, v: Any) -> list[str]:
        return _as_str_list(v)


# ── Skill Match ────────────────────────────────────────────────────────

class SkillMatch(BaseModel):
    skill: str = ""
    match_level: SkillMatchLevel = SkillMatchLevel.MISSING
    evidence: str = ""

    @field_validator("match_level", mode="before")
    @classmethod
    def _coerce_level(cls, v: Any) -> str:
        if isinstance(v, Enum):
            return str(v.value)
        if v is not None:
            raw = str(v).strip().upper().replace(" ", "_").replace("-", "_")
            skill_aliases = {
                "HIGH": "MATCHED",
                "HIGH_MATCH": "MATCHED",
                "MEDIUM": "PARTIALLY_MATCHED",
                "MED": "PARTIALLY_MATCHED",
                "LOW": "MISSING",
                "LOW_MATCH": "MISSING",
            }
            if raw in skill_aliases:
                return skill_aliases[raw]
        return _normalize_enum(
            v,
            {e.value: e.value for e in SkillMatchLevel},
            SkillMatchLevel.MISSING.value,
        )

    @model_validator(mode="before")
    @classmethod
    def _from_loose(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"skill": data, "match_level": "MISSING", "evidence": ""}
        if isinstance(data, dict):
            data = dict(data)
            if "name" in data and "skill" not in data:
                data["skill"] = data["name"]
            for alt in ("level", "status", "match", "matched", "result"):
                if alt in data and "match_level" not in data:
                    data["match_level"] = data[alt]
            # Boolean helpers from small models
            if "match_level" not in data:
                if data.get("matched") is True or data.get("present") is True:
                    data["match_level"] = "MATCHED"
                elif data.get("matched") is False:
                    data["match_level"] = "MISSING"
            # If evidence exists but level missing → at least partial
            if not data.get("match_level") and str(data.get("evidence") or "").strip():
                data["match_level"] = "PARTIALLY_MATCHED"
        return data


# ── Student Fit ────────────────────────────────────────────────────────

class StudentFitResult(BaseModel):
    fit_score: float = Field(ge=0, le=100, default=0.0)
    required_skills: list[SkillMatch] = Field(default_factory=list)
    preferred_skills: list[SkillMatch] = Field(default_factory=list)
    experience_match: str = ""
    education_match: str = ""
    project_evidence: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    summary: str = ""

    @field_validator("fit_score", mode="before")
    @classmethod
    def _coerce_score(cls, v: Any) -> float:
        score = _as_float(v, 0.0)
        if score <= 1.0 and score > 0:
            # model sometimes returns 0-1 instead of 0-100
            score *= 100
        return max(0.0, min(100.0, score))

    @field_validator("project_evidence", "concerns", mode="before")
    @classmethod
    def _coerce_str_lists(cls, v: Any) -> list[str]:
        return _as_str_list(v)

    @field_validator("required_skills", "preferred_skills", mode="before")
    @classmethod
    def _coerce_skill_lists(cls, v: Any) -> Any:
        if v is None:
            return []
        if isinstance(v, dict):
            return [v]
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [{"skill": v, "match_level": "MISSING"}]
        return []


# ── Risk Signal ────────────────────────────────────────────────────────

class RiskSignal(BaseModel):
    signal: str = ""
    severity: RiskLevel = RiskLevel.LOW
    evidence: str = ""
    source: str = ""
    confidence: float = Field(ge=0, le=1, default=0.5)

    @field_validator("severity", mode="before")
    @classmethod
    def _coerce_severity(cls, v: Any) -> str:
        return _normalize_enum(
            v, {e.value: e.value for e in RiskLevel}, RiskLevel.LOW.value
        )

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_conf(cls, v: Any) -> float:
        c = _as_float(v, 0.5)
        if c > 1.0:
            c = min(1.0, c / 100.0)
        return max(0.0, min(1.0, c))


class RiskAssessment(BaseModel):
    risk_level: RiskLevel = RiskLevel.LOW
    signals: list[RiskSignal] = Field(default_factory=list)
    summary: str = ""

    @field_validator("risk_level", mode="before")
    @classmethod
    def _coerce_level(cls, v: Any) -> str:
        return _normalize_enum(
            v, {e.value: e.value for e in RiskLevel}, RiskLevel.LOW.value
        )

    @field_validator("signals", mode="before")
    @classmethod
    def _coerce_signals(cls, v: Any) -> Any:
        if v is None:
            return []
        if isinstance(v, dict):
            return [v]
        if isinstance(v, str):
            return [{"signal": v, "severity": "LOW"}]
        if isinstance(v, list):
            out = []
            for item in v:
                if isinstance(item, str):
                    out.append({"signal": item, "severity": "LOW"})
                elif isinstance(item, dict):
                    out.append(item)
                else:
                    out.append({"signal": str(item), "severity": "LOW"})
            return out
        return v


# ── Company Verification ──────────────────────────────────────────────

class CompanyVerification(BaseModel):
    company_name: str = ""
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    website_found: bool = False
    careers_page_found: bool = False
    job_listing_found: bool = False
    website_url: str = ""
    careers_page_url: str = ""
    job_listing_url: str = ""
    evidence: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, default=0.0)
    unresolved_questions: list[str] = Field(default_factory=list)
    summary: str = ""

    @field_validator("verification_status", mode="before")
    @classmethod
    def _coerce_status(cls, v: Any) -> str:
        return _normalize_enum(
            v,
            {e.value: e.value for e in VerificationStatus},
            VerificationStatus.UNVERIFIED.value,
        )

    @field_validator("evidence", "source_urls", "unresolved_questions", mode="before")
    @classmethod
    def _coerce_lists(cls, v: Any) -> list[str]:
        return _as_str_list(v)

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_conf(cls, v: Any) -> float:
        c = _as_float(v, 0.0)
        if c > 1.0:
            c = min(1.0, c / 100.0)
        return max(0.0, min(1.0, c))


# ── Opportunity Intelligence Report (final output) ────────────────────

class OpportunityReport(BaseModel):
    """The complete output of the WorthApply pipeline."""

    job: JobProfile = Field(default_factory=JobProfile)
    student_fit: StudentFitResult = Field(default_factory=StudentFitResult)
    company_verification: CompanyVerification = Field(
        default_factory=CompanyVerification
    )
    risk_assessment: RiskAssessment = Field(default_factory=RiskAssessment)

    recommendation: Recommendation = Recommendation.LOW_PRIORITY
    priority: Priority = Priority.MEDIUM
    opportunity_confidence: float = Field(ge=0, le=100, default=50.0)
    evidence_quality: str = ""

    reasons: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    summary: str = ""

    @field_validator("recommendation", mode="before")
    @classmethod
    def _coerce_rec(cls, v: Any) -> str:
        return _normalize_enum(
            v,
            {e.value: e.value for e in Recommendation},
            Recommendation.LOW_PRIORITY.value,
        )

    @field_validator("priority", mode="before")
    @classmethod
    def _coerce_pri(cls, v: Any) -> str:
        return _normalize_enum(
            v, {e.value: e.value for e in Priority}, Priority.MEDIUM.value
        )

    @field_validator("opportunity_confidence", mode="before")
    @classmethod
    def _coerce_conf(cls, v: Any) -> float:
        score = _as_float(v, 50.0)
        if score <= 1.0 and score > 0:
            score *= 100
        return max(0.0, min(100.0, score))

    @field_validator(
        "reasons", "missing_requirements", "uncertainty", "next_steps", mode="before"
    )
    @classmethod
    def _coerce_lists(cls, v: Any) -> list[str]:
        return _as_str_list(v)
