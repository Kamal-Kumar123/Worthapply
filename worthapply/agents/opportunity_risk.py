"""Opportunity Risk / Freshness Agent — identifies risk indicators."""

from __future__ import annotations

from worthapply.agents.base import BaseAgent
from worthapply.agents.company_verification import is_job_board_url
from worthapply.models.schemas import (
    CompanyVerification,
    JobProfile,
    RiskAssessment,
    RiskLevel,
    RiskSignal,
)
from worthapply.providers.base import LLMProvider

_SYSTEM = """You are an opportunity risk analyst. Identify risk INDICATORS —
NOT accusations of fraud.

How to assess (in order):
1. First look at the job posting itself (pay-to-apply, telegram-only hiring,
   unrealistic salary, missing role details, pressure tactics).
2. If the source is a known job board (SimplyHired, Indeed, LinkedIn, Naukri,
   Glassdoor, etc.), that is NORMAL. Do NOT treat "listed on a job board" or
   "not found on company careers page" as HIGH risk by itself.
3. Then use company official-website verification. Risk rises when the COMPANY
   itself cannot be found anywhere, or official sources conflict badly.
4. Only escalate to HIGH when multiple serious signals converge (e.g. fake-looking
   company + money requested + no public footprint).

Rules:
- NEVER say "this is a scam." Use "Potential risk indicator detected".
- Severity: LOW / MEDIUM / HIGH.
- A real company with a job only on SimplyHired/Indeed ⇒ typically LOW risk
  (maybe LOW note: confirm on company site when possible).
- Missing official careers listing alone ⇒ at most LOW, never HIGH.
- risk_level: LOW if only minor notes; MEDIUM for real concerns; HIGH only for
  strong converging red flags."""

_PROMPT = """Analyze this opportunity for risk indicators.

## Job Details
Title: {title}
Company: {company}
Location: {location}
Type: {employment_type}
Posted: {posting_date}
Source: {source_url}
Source type: {source_type}
Application URL: {application_url}

## Job Description Summary
Required Skills: {required_skills}
Preferred Skills: {preferred_skills}
Experience: {experience_req}
Responsibilities count: {resp_count}

## Company Verification Summary
Verification Status: {verification_status}
Website Found: {website_found}
Careers Page Found: {careers_found}
Job Listing Found on company site: {listing_found}
Verification Confidence: {verification_confidence}
Unresolved Questions: {unresolved}

Remember: job-board listings are normal. Focus risk on posting content and
whether the company itself looks real, not on the aggregator URL."""


_BOARD_ONLY_PHRASES = (
    "unverified",
    "careers page",
    "job listing",
    "source of the job",
    "not provided",
    "website",
    "official listing",
    "company's website",
)


class OpportunityRiskAgent(BaseAgent):
    name = "opportunity_risk"

    def __init__(self, provider: LLMProvider) -> None:
        super().__init__(provider)

    async def run(
        self,
        job: JobProfile,
        company_verification: CompanyVerification | None = None,
    ) -> RiskAssessment:
        cv = company_verification or CompanyVerification()
        on_board = is_job_board_url(job.source_url or "")
        source_type = (
            "Known job board / aggregator (normal listing channel)"
            if on_board
            else ("Direct / other URL" if job.source_url else "No URL")
        )

        prompt = _PROMPT.format(
            title=job.title or "Not specified",
            company=job.company or "Not specified",
            location=job.location or "Not specified",
            employment_type=job.employment_type or "Not specified",
            posting_date=job.posting_date or "Not available",
            source_url=job.source_url or "Not provided",
            source_type=source_type,
            application_url=job.application_url or "Not provided",
            required_skills=", ".join(job.required_skills) or "None listed",
            preferred_skills=", ".join(job.preferred_skills) or "None listed",
            experience_req=job.experience_requirement or "Not specified",
            resp_count=len(job.responsibilities),
            verification_status=cv.verification_status.value,
            website_found=cv.website_found,
            careers_found=cv.careers_page_found,
            listing_found=cv.job_listing_found,
            verification_confidence=cv.confidence,
            unresolved="; ".join(cv.unresolved_questions) or "None",
        )

        resp = await self.generate_structured(
            prompt, RiskAssessment, system=_SYSTEM, max_tokens=2048
        )

        if resp.ok and resp.structured:
            return self._normalize(resp.structured, on_board=on_board, cv=cv)

        return RiskAssessment(summary="Unable to assess risk due to LLM error.")

    def _normalize(
        self,
        assessment: RiskAssessment,
        *,
        on_board: bool,
        cv: CompanyVerification,
    ) -> RiskAssessment:
        """Downgrade false alarms: job-board + only 'unverified site' notes ≠ HIGH."""
        if not on_board:
            return assessment

        softened: list[RiskSignal] = []
        for sig in assessment.signals:
            text = f"{sig.signal} {sig.evidence}".lower()
            board_only = any(p in text for p in _BOARD_ONLY_PHRASES) and not any(
                bad in text
                for bad in (
                    "pay to apply",
                    "telegram",
                    "whatsapp only",
                    "upfront fee",
                    "guaranteed job",
                    "money",
                )
            )
            if board_only and sig.severity in (RiskLevel.HIGH, RiskLevel.MEDIUM):
                softened.append(
                    RiskSignal(
                        signal=sig.signal,
                        severity=RiskLevel.LOW,
                        evidence=(
                            (sig.evidence or "")
                            + " (Job-board listing is normal; treat as a soft check "
                            "to confirm on the company site when possible.)"
                        ).strip(),
                        source=sig.source,
                        confidence=min(sig.confidence, 0.4),
                    )
                )
            else:
                softened.append(sig)

        assessment.signals = softened

        # Cap overall risk when company partially verified / website found
        if cv.website_found or cv.verification_status.value in (
            "VERIFIED",
            "PARTIALLY_VERIFIED",
        ):
            if assessment.risk_level == RiskLevel.HIGH:
                assessment.risk_level = RiskLevel.LOW
            elif assessment.risk_level == RiskLevel.MEDIUM and not any(
                s.severity == RiskLevel.MEDIUM for s in assessment.signals
            ):
                assessment.risk_level = RiskLevel.LOW
        elif assessment.risk_level == RiskLevel.HIGH and all(
            s.severity == RiskLevel.LOW for s in assessment.signals
        ):
            assessment.risk_level = RiskLevel.LOW

        if on_board and assessment.risk_level == RiskLevel.HIGH:
            # Last safety valve for aggregator-only "unverified" hallucinations
            if all(
                any(p in f"{s.signal} {s.evidence}".lower() for p in _BOARD_ONLY_PHRASES)
                for s in assessment.signals
            ) or not assessment.signals:
                assessment.risk_level = RiskLevel.LOW
                assessment.summary = (
                    (assessment.summary or "")
                    + " Source is a known job board; overall risk capped to LOW absent "
                    "stronger scam indicators."
                ).strip()

        return assessment
