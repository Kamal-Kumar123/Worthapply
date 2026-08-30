"""Main analysis workflow — orchestrates all agents with tracing."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable

from worthapply.agents.company_verification import CompanyVerificationAgent
from worthapply.agents.decision_synthesizer import DecisionSynthesizerAgent
from worthapply.agents.evidence_verifier import EvidenceVerifierAgent
from worthapply.agents.job_intelligence import JobIntelligenceAgent
from worthapply.agents.opportunity_risk import OpportunityRiskAgent
from worthapply.agents.student_fit import StudentFitAgent
from worthapply.models.schemas import (
    CompanyVerification,
    JobProfile,
    OpportunityReport,
    RiskAssessment,
    StudentFitResult,
    VerificationStatus,
)
from worthapply.orchestration.state import PipelineState
from worthapply.providers.base import LLMProvider
from worthapply.tracing import Tracer

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str], Any]


class AnalysisWorkflow:
    """Orchestrates the full opportunity analysis pipeline.

    Stages:
    1. Job Intelligence (extract structured profile)
    2. In parallel: Company Verification, Student Fit
    3. Risk Assessment (depends on verification)
    4. Evidence Verification
    5. Decision Synthesis

    Every agent invocation is traced and saved to disk.
    """

    def __init__(
        self,
        provider: LLMProvider,
        progress_callback: ProgressCallback | None = None,
        trace_dir: str = "traces",
    ) -> None:
        self.provider = provider
        self._progress = progress_callback or (lambda stage, status: None)
        self._trace_dir = trace_dir

    async def analyze(
        self,
        student_text: str,
        job_text: str,
        job_url: str = "",
        case_id: str = "",
    ) -> tuple[OpportunityReport, PipelineState]:
        """Run the full analysis pipeline. Returns (report, state)."""
        # Fetch URL content when caller only provided a link
        if job_url and not (job_text or "").strip():
            try:
                from worthapply.tools.webpage_fetcher import fetch_webpage

                fetched = await fetch_webpage(job_url)
                if fetched.ok and fetched.content.strip():
                    job_text = fetched.content
                    if fetched.title:
                        job_text = f"Page title: {fetched.title}\n\n{job_text}"
                else:
                    logger.warning(
                        "URL fetch failed for %s: %s", job_url, fetched.error
                    )
            except Exception as exc:
                logger.warning("URL fetch error: %s", exc)

        state = PipelineState(student_text=student_text, job_text=job_text, job_url=job_url)
        tracer = Tracer(run_id=state.run_id, trace_dir=self._trace_dir)

        # ── Stage 1: Job Intelligence ─────────────────────────────────
        self._progress("job_intelligence", "RUNNING")
        state.begin_stage("job_intelligence")
        tracer.begin(
            "job_intelligence",
            case_id=case_id,
            input_summary=f"Job text ({len(job_text)} chars), URL: {job_url or 'none'}",
        )
        try:
            agent = JobIntelligenceAgent(self.provider)
            job_profile = await agent.run(job_text, source_url=job_url)
            if job_profile:
                state.job_profile = job_profile
                usage = self.provider.get_cumulative_usage()
                last_usage = usage[-1] if usage else None
                state.complete_stage("job_intelligence", last_usage)
                tracer.end(
                    f"Extracted: {job_profile.title} at {job_profile.company}, "
                    f"{len(job_profile.required_skills)} required skills",
                    usage=last_usage,
                    agent_name="job_intelligence",
                )
                self._progress("job_intelligence", "COMPLETED")
            else:
                state.job_profile = JobProfile(source_url=job_url)
                state.fail_stage("job_intelligence", "Failed to extract job profile")
                tracer.end("FAILED: No profile extracted", agent_name="job_intelligence")
                self._progress("job_intelligence", "FAILED")
        except Exception as exc:
            logger.error("Job intelligence failed: %s", exc)
            state.job_profile = JobProfile(source_url=job_url)
            state.fail_stage("job_intelligence", str(exc))
            tracer.end(f"EXCEPTION: {exc}", agent_name="job_intelligence")
            self._progress("job_intelligence", "FAILED")

        job = state.job_profile

        # ── Stage 2: Parallel — Company Verification + Student Fit ────
        async def _company_verification():
            self._progress("company_verification", "RUNNING")
            state.begin_stage("company_verification")
            tracer.begin(
                "company_verification",
                case_id=case_id,
                input_summary=f"Company: {job.company}, Title: {job.title}",
            )
            try:
                agent = CompanyVerificationAgent(self.provider)
                result = await agent.run(
                    company=job.company,
                    job_title=job.title,
                    source_url=job.source_url or job_url,
                    job_text=job_text or state.job_text,
                )
                state.company_verification = result
                usage = self.provider.get_cumulative_usage()
                last_usage = usage[-1] if usage else None
                state.complete_stage("company_verification", last_usage)
                tracer.end(
                    f"Status: {result.verification_status.value}, "
                    f"confidence: {result.confidence:.2f}",
                    usage=last_usage,
                    agent_name="company_verification",
                )
                self._progress("company_verification", "COMPLETED")
            except Exception as exc:
                logger.error("Company verification failed: %s", exc)
                state.company_verification = CompanyVerification(
                    company_name=job.company,
                    verification_status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                    summary=f"Verification failed: {exc}",
                )
                state.fail_stage("company_verification", str(exc))
                tracer.end(f"EXCEPTION: {exc}", agent_name="company_verification")
                self._progress("company_verification", "FAILED")

        async def _student_fit():
            self._progress("student_fit", "RUNNING")
            state.begin_stage("student_fit")
            tracer.begin(
                "student_fit",
                case_id=case_id,
                input_summary=f"Student text ({len(student_text)} chars), "
                f"Job: {job.title}, {len(job.required_skills)} required skills",
            )
            try:
                agent = StudentFitAgent(self.provider)
                result = await agent.run(student_text, job, job_text=job_text or state.job_text)
                if result:
                    state.student_fit = result
                    usage = self.provider.get_cumulative_usage()
                    last_usage = usage[-1] if usage else None
                    state.complete_stage("student_fit", last_usage)
                    tracer.end(
                        f"Fit score: {result.fit_score}, "
                        f"{len(result.required_skills)} skills assessed",
                        usage=last_usage,
                        agent_name="student_fit",
                    )
                    self._progress("student_fit", "COMPLETED")
                else:
                    state.student_fit = StudentFitResult(
                        summary="Fit assessment failed."
                    )
                    state.fail_stage("student_fit", "No result returned")
                    tracer.end("FAILED: No result returned", agent_name="student_fit")
                    self._progress("student_fit", "FAILED")
            except Exception as exc:
                logger.error("Student fit failed: %s", exc)
                state.student_fit = StudentFitResult(
                    summary=f"Fit assessment failed: {exc}"
                )
                state.fail_stage("student_fit", str(exc))
                tracer.end(f"EXCEPTION: {exc}", agent_name="student_fit")
                self._progress("student_fit", "FAILED")

        # Sequential (not gather) — free-tier TPM (~8k/min) can't handle
        # two large structured calls at once without frequent 429s.
        await _company_verification()
        await _student_fit()

        # ── Stage 3: Risk Assessment (depends on verification) ────────
        self._progress("opportunity_risk", "RUNNING")
        state.begin_stage("opportunity_risk")
        tracer.begin(
            "opportunity_risk",
            case_id=case_id,
            input_summary=f"Job: {job.title}, Verification: "
            f"{state.company_verification.verification_status.value if state.company_verification else 'N/A'}",
        )
        try:
            agent = OpportunityRiskAgent(self.provider)
            result = await agent.run(job, state.company_verification)
            state.risk_assessment = result
            usage = self.provider.get_cumulative_usage()
            last_usage = usage[-1] if usage else None
            state.complete_stage("opportunity_risk", last_usage)
            tracer.end(
                f"Risk: {result.risk_level.value}, "
                f"{len(result.signals)} signals",
                usage=last_usage,
                agent_name="opportunity_risk",
            )
            self._progress("opportunity_risk", "COMPLETED")
        except Exception as exc:
            logger.error("Risk assessment failed: %s", exc)
            state.risk_assessment = RiskAssessment(
                summary=f"Risk assessment failed: {exc}"
            )
            state.fail_stage("opportunity_risk", str(exc))
            tracer.end(f"EXCEPTION: {exc}", agent_name="opportunity_risk")
            self._progress("opportunity_risk", "FAILED")

        # ── Stage 4: Evidence Verification ────────────────────────────
        self._progress("evidence_verification", "RUNNING")
        state.begin_stage("evidence_verification")
        tracer.begin(
            "evidence_verification",
            case_id=case_id,
            input_summary="Verifying claims from fit, risk, and company agents",
        )
        try:
            ev_agent = EvidenceVerifierAgent(self.provider)
            claims = ev_agent.extract_claims(
                fit_summary=state.student_fit.summary if state.student_fit else "",
                risk_summary=state.risk_assessment.summary if state.risk_assessment else "",
                verification_summary=(
                    state.company_verification.summary
                    if state.company_verification else ""
                ),
            )
            if claims:
                ev_result = await ev_agent.run(
                    claims=claims,
                    student_text=student_text[:3000],
                    job_text=job_text[:3000],
                )
                state.evidence_quality = ev_result.overall_evidence_quality
                state.unsupported_claims = ev_result.unsupported_count
            else:
                state.evidence_quality = "NO_CLAIMS_TO_VERIFY"
                state.unsupported_claims = 0

            usage = self.provider.get_cumulative_usage()
            last_usage = usage[-1] if usage else None
            state.complete_stage("evidence_verification", last_usage)
            tracer.end(
                f"Quality: {state.evidence_quality}, "
                f"unsupported: {state.unsupported_claims}, "
                f"claims checked: {len(claims)}",
                usage=last_usage,
                agent_name="evidence_verification",
            )
            self._progress("evidence_verification", "COMPLETED")
        except Exception as exc:
            logger.error("Evidence verification failed: %s", exc)
            state.evidence_quality = "VERIFICATION_FAILED"
            state.fail_stage("evidence_verification", str(exc))
            tracer.end(f"EXCEPTION: {exc}", agent_name="evidence_verification")
            self._progress("evidence_verification", "FAILED")

        # ── Stage 5: Decision Synthesis ───────────────────────────────
        self._progress("decision_synthesis", "RUNNING")
        state.begin_stage("decision_synthesis")
        tracer.begin(
            "decision_synthesis",
            case_id=case_id,
            input_summary=f"Fit: {state.student_fit.fit_score if state.student_fit else '?'}, "
            f"Risk: {state.risk_assessment.risk_level.value if state.risk_assessment else '?'}, "
            f"Evidence: {state.evidence_quality}",
        )
        try:
            synth_agent = DecisionSynthesizerAgent(self.provider)
            report = await synth_agent.run(
                job=job,
                fit=state.student_fit or StudentFitResult(),
                verification=state.company_verification or CompanyVerification(),
                risk=state.risk_assessment or RiskAssessment(),
                evidence_quality=state.evidence_quality,
                unsupported_claims=state.unsupported_claims,
                student_text=student_text,
                job_text=job_text or state.job_text,
            )
            state.report = report
            usage = self.provider.get_cumulative_usage()
            last_usage = usage[-1] if usage else None
            state.complete_stage("decision_synthesis", last_usage)
            tracer.end(
                f"Recommendation: {report.recommendation.value}, "
                f"Priority: {report.priority.value}, "
                f"Confidence: {report.opportunity_confidence}",
                usage=last_usage,
                agent_name="decision_synthesis",
            )
            self._progress("decision_synthesis", "COMPLETED")
        except Exception as exc:
            logger.error("Decision synthesis failed: %s", exc)
            state.report = OpportunityReport(
                job=job,
                student_fit=state.student_fit or StudentFitResult(),
                company_verification=state.company_verification or CompanyVerification(),
                risk_assessment=state.risk_assessment or RiskAssessment(),
                summary=f"Synthesis failed: {exc}",
            )
            state.fail_stage("decision_synthesis", str(exc))
            tracer.end(f"EXCEPTION: {exc}", agent_name="decision_synthesis")
            self._progress("decision_synthesis", "FAILED")

        # ── Save traces ───────────────────────────────────────────────
        try:
            trace_path = tracer.save(case_id=case_id or state.run_id)
            logger.info("Traces saved to %s", trace_path)
        except Exception as exc:
            logger.warning("Failed to save traces: %s", exc)

        return state.report, state
