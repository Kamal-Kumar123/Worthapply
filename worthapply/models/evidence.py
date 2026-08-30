"""Evidence-first data model.

Every claim made by any agent is backed by a Claim object with source,
evidence, and confidence. The final report is generated from this layer.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    JOB_REQUIREMENT = "job_requirement"
    JOB_DETAIL = "job_detail"
    STUDENT_SKILL = "student_skill"
    STUDENT_EXPERIENCE = "student_experience"
    STUDENT_EDUCATION = "student_education"
    COMPANY_INFO = "company_info"
    RISK_SIGNAL = "risk_signal"
    FIT_ASSESSMENT = "fit_assessment"
    VERIFICATION = "verification"


class EvidenceSource(BaseModel):
    type: str = ""          # "job_description", "resume", "web_search", "careers_page"
    url: str = ""
    location: str = ""      # section/paragraph reference within the source


class Claim(BaseModel):
    claim_id: str = ""
    claim: str = ""
    claim_type: ClaimType = ClaimType.JOB_DETAIL
    source: EvidenceSource = Field(default_factory=EvidenceSource)
    evidence: str = ""
    confidence: float = Field(ge=0, le=1, default=0.5)
    verified: bool = False
    verification_reason: str = ""


class EvidenceStore(BaseModel):
    """Accumulates claims from all agents for a single analysis run."""

    claims: list[Claim] = Field(default_factory=list)
    run_id: str = ""

    def add(self, claim: Claim) -> None:
        self.claims.append(claim)

    def get_by_type(self, claim_type: ClaimType) -> list[Claim]:
        return [c for c in self.claims if c.claim_type == claim_type]

    def get_verified(self) -> list[Claim]:
        return [c for c in self.claims if c.verified]

    def get_unverified(self) -> list[Claim]:
        return [c for c in self.claims if not c.verified]

    def average_confidence(self) -> float:
        if not self.claims:
            return 0.0
        return sum(c.confidence for c in self.claims) / len(self.claims)
