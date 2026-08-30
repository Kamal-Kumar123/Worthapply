"""Decision Synthesizer — combines all agent outputs into a final report."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from worthapply.agents.base import BaseAgent
from worthapply.agents.student_fit import sanitize_gap_list
from worthapply.models.schemas import (
    CompanyVerification,
    JobProfile,
    OpportunityReport,
    Priority,
    Recommendation,
    RiskAssessment,
    StudentFitResult,
)
from worthapply.providers.base import LLMProvider

_SYSTEM = """You are a decision synthesizer for an opportunity intelligence system.
Combine inputs from multiple analysis agents into a final recommendation.

Critical rules:
1. Keep these dimensions SEPARATE — never collapse them into one score:
   - Student Fit (how well the student matches)
   - Opportunity Confidence (how verifiable/trustworthy the posting is)
   - Risk Level (risk indicators found)
   - Evidence Quality (how well-supported are the claims)
2. A student can be a 95% fit for a HIGH-risk opportunity. Report BOTH.
3. Only use evidence from the input agents — do NOT invent new information.
4. Be explicit about uncertainty — what could NOT be determined.
5. Recommendation:
   - APPLY: strong fit AND confident opportunity AND low risk
   - APPLY_IF_TIME: decent fit but some concerns, OR great fit with verification needed
   - LOW_PRIORITY: poor fit OR significant concerns
6. Priority: HIGH (definitely apply), MEDIUM (worth considering), LOW (skip or deprioritize)
7. Weight skills, projects, and experience far above education. Do NOT make education
   mismatch the main reason to deprioritize if practical evidence is strong.
8. Do NOT invent gaps:
   - Never add "Missing AWS" unless Missing Skills / Concerns already include a real AWS gap.
   - Never add "education in a different field" for IT/CS students on software/AI roles.
9. Do not repeat the same bullet in both uncertainty and missing_requirements."""


class SynthesisInput(BaseModel):
    fit_score: float = 0.0
    fit_summary: str = ""
    matched_required: int = 0
    total_required: int = 0
    missing_skills: list[str] = Field(default_factory=list)
    opportunity_confidence: float = 50.0
    verification_status: str = ""
    risk_level: str = "LOW"
    risk_signals: list[str] = Field(default_factory=list)
    evidence_quality: str = ""
    unsupported_claims: int = 0
    company: str = ""
    job_title: str = ""
    concerns: list[str] = Field(default_factory=list)


class SynthesisOutput(BaseModel):
    recommendation: str = "LOW_PRIORITY"
    priority: str = "MEDIUM"
    opportunity_confidence: float = Field(ge=0, le=100, default=50.0)
    evidence_quality: str = ""
    reasons: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    summary: str = ""

    @field_validator("opportunity_confidence", mode="before")
    @classmethod
    def _score(cls, v):
        try:
            s = float(v)
        except (TypeError, ValueError):
            return 50.0
        if 0 < s <= 1:
            s *= 100
        return max(0.0, min(100.0, s))

    @field_validator(
        "reasons", "missing_requirements", "uncertainty", "next_steps", mode="before"
    )
    @classmethod
    def _lists(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            out = []
            for item in v:
                if isinstance(item, dict):
                    out.append(str(item.get("text") or item.get("reason") or item))
                else:
                    out.append(str(item))
            return out
        return [str(v)]


_PROMPT = """Synthesize the following analysis into a final opportunity recommendation.

## Opportunity
Company: {company}
Position: {job_title}

## Student Fit
Fit Score: {fit_score}/100
Summary: {fit_summary}
Required Skills Matched: {matched_required}/{total_required}
Missing Skills: {missing_skills}

## Opportunity Verification
Verification Status: {verification_status}
Confidence: {opportunity_confidence}/100

## Risk Assessment
Risk Level: {risk_level}
Signals: {risk_signals}

## Evidence Quality
Quality: {evidence_quality}
Unsupported Claims: {unsupported_claims}

## Concerns
{concerns}

Produce a final recommendation. Remember to keep fit, confidence, risk, and
evidence quality as SEPARATE dimensions."""


class DecisionSynthesizerAgent(BaseAgent):
    name = "decision_synthesizer"

    def __init__(self, provider: LLMProvider) -> None:
        super().__init__(provider)

    async def run(
        self,
        job: JobProfile,
        fit: StudentFitResult,
        verification: CompanyVerification,
        risk: RiskAssessment,
        evidence_quality: str = "",
        unsupported_claims: int = 0,
        student_text: str = "",
        job_text: str = "",
    ) -> OpportunityReport:
        matched = sum(
            1 for s in fit.required_skills if s.match_level.value == "MATCHED"
        )
        missing = [
            s.skill
            for s in fit.required_skills
            if s.match_level.value == "MISSING"
        ]
        risk_signal_texts = [s.signal for s in risk.signals]

        prompt = _PROMPT.format(
            company=job.company,
            job_title=job.title,
            fit_score=fit.fit_score,
            fit_summary=fit.summary,
            matched_required=matched,
            total_required=len(fit.required_skills),
            missing_skills=", ".join(missing) or "None",
            verification_status=verification.verification_status.value,
            opportunity_confidence=verification.confidence * 100,
            risk_level=risk.risk_level.value,
            risk_signals="; ".join(risk_signal_texts) or "None detected",
            evidence_quality=evidence_quality or "Not assessed",
            unsupported_claims=unsupported_claims,
            concerns="\n".join(f"- {c}" for c in fit.concerns) if fit.concerns else "None noted",
        )

        resp = await self.generate_structured(
            prompt, SynthesisOutput, system=_SYSTEM, max_tokens=2048
        )

        report = OpportunityReport(
            job=job,
            student_fit=fit,
            company_verification=verification,
            risk_assessment=risk,
        )

        if resp.ok and resp.structured:
            synth: SynthesisOutput = resp.structured
            report.recommendation = _parse_recommendation(synth.recommendation)
            report.priority = _parse_priority(synth.priority)
            report.opportunity_confidence = synth.opportunity_confidence
            report.evidence_quality = synth.evidence_quality or evidence_quality
            report.reasons = sanitize_gap_list(
                synth.reasons, student_text=student_text, job=job, job_text=job_text
            )
            report.missing_requirements = sanitize_gap_list(
                synth.missing_requirements,
                student_text=student_text,
                job=job,
                job_text=job_text,
            )
            report.uncertainty = sanitize_gap_list(
                synth.uncertainty,
                student_text=student_text,
                job=job,
                job_text=job_text,
            )
            # Dedupe uncertainty against concerns / missing
            concern_keys = {
                c.strip().lower() for c in (fit.concerns or []) if c.strip()
            }
            missing_keys = {
                m.strip().lower() for m in report.missing_requirements if m.strip()
            }
            report.uncertainty = [
                u
                for u in report.uncertainty
                if u.strip().lower() not in concern_keys
                and u.strip().lower() not in missing_keys
            ]
            report.next_steps = sanitize_gap_list(
                synth.next_steps,
                student_text=student_text,
                job=job,
                job_text=job_text,
            )
            report.summary = synth.summary
            # Clean invented phrases from summary lightly
            if report.summary:
                low = report.summary.lower()
                if "missing aws" in low or "aws experience" in low:
                    # Keep summary but strip false AWS sentences if not hard-required
                    from worthapply.agents.student_fit import aws_hard_required

                    if not aws_hard_required(job, job_text):
                        import re as _re

                        report.summary = _re.sub(
                            r"[^.]*\bAWS\b[^.]*\.",
                            "",
                            report.summary,
                            flags=_re.I,
                        ).strip()
                        report.summary = _re.sub(r"\s{2,}", " ", report.summary)
        else:
            report.summary = "Decision synthesis failed. Review individual agent outputs."
            report.uncertainty = ["Synthesis agent encountered an error."]

        # Always re-sanitize fit concerns on the report object
        fit.concerns = sanitize_gap_list(
            fit.concerns, student_text=student_text, job=job, job_text=job_text
        )
        report.student_fit = fit
        return report


def _parse_recommendation(val: str) -> Recommendation:
    val = val.upper().strip()
    for r in Recommendation:
        if r.value == val:
            return r
    if "APPLY_IF" in val or "IF_TIME" in val:
        return Recommendation.APPLY_IF_TIME
    if "APPLY" in val:
        return Recommendation.APPLY
    return Recommendation.LOW_PRIORITY


def _parse_priority(val: str) -> Priority:
    val = val.upper().strip()
    for p in Priority:
        if p.value == val:
            return p
    return Priority.MEDIUM
