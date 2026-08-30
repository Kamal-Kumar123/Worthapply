"""Evidence Verification Agent — validates claims from other agents."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from worthapply.agents.base import BaseAgent
from worthapply.providers.base import LLMProvider

_SYSTEM = """You are an evidence auditor. Review claims made by other agents
and determine whether each claim is well-supported by evidence.

Rules:
- A claim is SUPPORTED if specific evidence from the source text backs it up.
- A claim is UNSUPPORTED if no evidence exists or the evidence is vague.
- A claim is CONFLICTING if evidence contradicts it.
- Be strict — "Student knows Python" needs specific resume evidence.
- Assign confidence 0.0-1.0 based on evidence strength.
- Mark unsupported claims clearly so they can be downgraded."""


class VerifiedClaim(BaseModel):
    claim: str = ""
    supported: bool = False
    confidence: float = Field(ge=0, le=1, default=0.5)
    evidence: str = ""
    reason: str = ""

    @field_validator("claim", "evidence", "reason", mode="before")
    @classmethod
    def _none_str(cls, v):
        return "" if v is None else str(v)

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v):
        try:
            c = float(v)
        except (TypeError, ValueError):
            return 0.5
        if c > 1.0:
            c = min(1.0, c / 100.0)
        return max(0.0, min(1.0, c))


class VerificationResult(BaseModel):
    verified_claims: list[VerifiedClaim] = Field(default_factory=list)
    overall_evidence_quality: str = ""
    unsupported_count: int = 0
    summary: str = ""

    @field_validator("verified_claims", mode="before")
    @classmethod
    def _claims(cls, v):
        if v is None:
            return []
        if isinstance(v, dict):
            return [v]
        if isinstance(v, str):
            return [{"claim": v, "supported": False}]
        if isinstance(v, list):
            out = []
            for item in v:
                if isinstance(item, str):
                    out.append({"claim": item, "supported": False})
                elif isinstance(item, dict):
                    out.append(item)
                else:
                    out.append({"claim": str(item), "supported": False})
            return out
        return []

    @field_validator("unsupported_count", mode="before")
    @classmethod
    def _count(cls, v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0


_PROMPT = """Review these claims for evidence support.

## Source Material

### Student Profile
{student_text}

### Job Description
{job_text}

## Claims to Verify
{claims_text}

For each claim, determine:
1. Is it supported by evidence from the source material?
2. What specific evidence supports or contradicts it?
3. Confidence level (0.0 to 1.0)?

Also provide an overall evidence quality assessment (STRONG/MODERATE/WEAK/POOR)
and count unsupported claims."""


class EvidenceVerifierAgent(BaseAgent):
    name = "evidence_verifier"

    def __init__(self, provider: LLMProvider) -> None:
        super().__init__(provider)

    async def run(
        self,
        claims: list[str],
        student_text: str = "",
        job_text: str = "",
    ) -> VerificationResult:
        if not claims:
            return VerificationResult(
                overall_evidence_quality="N/A",
                summary="No claims to verify.",
            )

        claims_text = "\n".join(f"{i+1}. {c}" for i, c in enumerate(claims))

        prompt = _PROMPT.format(
            student_text=student_text[:3000] if student_text else "Not available",
            job_text=job_text[:3000] if job_text else "Not available",
            claims_text=claims_text,
        )

        resp = await self.generate_structured(
            prompt, VerificationResult, system=_SYSTEM, max_tokens=3072
        )

        if resp.ok and resp.structured:
            return resp.structured

        return VerificationResult(
            overall_evidence_quality="UNABLE_TO_VERIFY",
            summary="Evidence verification failed due to LLM error.",
        )

    def extract_claims(
        self,
        fit_summary: str,
        risk_summary: str,
        verification_summary: str,
    ) -> list[str]:
        """Extract key claims from agent outputs for verification."""
        claims = []
        for text in [fit_summary, risk_summary, verification_summary]:
            if text:
                sentences = text.replace(". ", ".\n").split("\n")
                for s in sentences:
                    s = s.strip()
                    if len(s) > 20 and any(kw in s.lower() for kw in [
                        "match", "miss", "require", "skill", "experience",
                        "risk", "verif", "found", "confirm", "evidence",
                        "student has", "student lacks", "company",
                    ]):
                        claims.append(s)
        return claims[:15]
