"""Integration tests for WorthApply using mocked LLM responses."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Type
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from worthapply.agents.job_intelligence import JobIntelligenceAgent
from worthapply.agents.student_fit import StudentFitAgent
from worthapply.agents.decision_synthesizer import DecisionSynthesizerAgent
from worthapply.agents.opportunity_risk import OpportunityRiskAgent
from worthapply.agents.evidence_verifier import EvidenceVerifierAgent
from worthapply.models.schemas import (
    CompanyVerification,
    JobProfile,
    OpportunityReport,
    Priority,
    Recommendation,
    RiskAssessment,
    RiskLevel,
    SkillMatch,
    SkillMatchLevel,
    StudentFitResult,
    VerificationStatus,
)
from worthapply.orchestration.state import PipelineState, StageStatus
from worthapply.providers.base import LLMProvider, LLMResponse, LLMUsage


class MockProvider(LLMProvider):
    """Mock LLM provider that returns pre-configured responses."""

    provider_name = "mock"

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        super().__init__("mock-model")
        self._responses = responses or {}
        self._call_count = 0

    async def _generate(self, prompt, *, system, temperature, max_tokens, **kw) -> LLMResponse:
        self._call_count += 1
        return LLMResponse(content="Mock response", usage=LLMUsage(input_tokens=10, output_tokens=20, total_tokens=30))

    async def _generate_structured(self, prompt, response_model, *, system, temperature, max_tokens, **kw) -> LLMResponse:
        self._call_count += 1
        model_name = response_model.__name__

        if model_name in self._responses:
            data = self._responses[model_name]
            if isinstance(data, dict):
                parsed = response_model.model_validate(data)
            else:
                parsed = data
            return LLMResponse(
                content=json.dumps(data) if isinstance(data, dict) else str(data),
                structured=parsed,
                usage=LLMUsage(input_tokens=100, output_tokens=200, total_tokens=300),
            )

        try:
            default = response_model()
            return LLMResponse(
                content="{}",
                structured=default,
                usage=LLMUsage(input_tokens=50, output_tokens=100, total_tokens=150),
            )
        except Exception:
            return LLMResponse(error=f"No mock for {model_name}")


MOCK_JOB_PROFILE = {
    "title": "Software Engineer",
    "company": "TechCorp",
    "location": "San Francisco, CA",
    "employment_type": "Full-time",
    "required_skills": ["Python", "SQL", "Git"],
    "preferred_skills": ["AWS", "Docker"],
    "experience_requirement": "1-3 years",
    "education_requirements": ["BS Computer Science"],
    "responsibilities": ["Build APIs", "Write tests", "Code review"],
}

MOCK_FIT_RESULT = {
    "fit_score": 78.0,
    "required_skills": [
        {"skill": "Python", "match_level": "MATCHED", "evidence": "Used in capstone project"},
        {"skill": "SQL", "match_level": "MATCHED", "evidence": "Database course + project"},
        {"skill": "Git", "match_level": "MATCHED", "evidence": "Used in all projects"},
    ],
    "preferred_skills": [
        {"skill": "AWS", "match_level": "PARTIALLY_MATCHED", "evidence": "Basic EC2 usage in project"},
        {"skill": "Docker", "match_level": "MISSING", "evidence": ""},
    ],
    "experience_match": "Limited — 1 internship, looking for entry-level",
    "education_match": "BS CS matches requirement",
    "project_evidence": ["REST API project with Flask", "Database design project"],
    "concerns": ["Limited professional experience"],
    "summary": "Strong skill match with limited experience. Good fit for entry-level.",
}

MOCK_RISK = {
    "risk_level": "LOW",
    "signals": [],
    "summary": "No significant risk indicators found.",
}

MOCK_SYNTHESIS = {
    "recommendation": "APPLY",
    "priority": "HIGH",
    "opportunity_confidence": 85.0,
    "evidence_quality": "MODERATE",
    "reasons": ["Strong skill match", "Legitimate company"],
    "missing_requirements": ["Docker experience"],
    "uncertainty": ["Could not verify current job availability"],
    "next_steps": ["Apply through official careers page"],
    "summary": "Strong match with a legitimate opportunity.",
}


class TestJobIntelligenceAgent:
    def test_run(self):
        provider = MockProvider(responses={"JobProfile": MOCK_JOB_PROFILE})
        agent = JobIntelligenceAgent(provider)
        result = asyncio.run(agent.run("Software Engineer at TechCorp..."))
        assert result is not None
        assert result.title == "Software Engineer"
        assert "Python" in result.required_skills


class TestStudentFitAgent:
    def test_run(self):
        provider = MockProvider(responses={"StudentFitResult": MOCK_FIT_RESULT})
        agent = StudentFitAgent(provider)
        job = JobProfile(**MOCK_JOB_PROFILE)
        result = asyncio.run(agent.run("Student resume text...", job))
        assert result is not None
        # Grounding blends LLM score (78) with required-skill coverage (3/3 MATCHED).
        assert result.fit_score == 92.3
        assert len(result.required_skills) == 3


class TestOpportunityRiskAgent:
    def test_run(self):
        provider = MockProvider(responses={"RiskAssessment": MOCK_RISK})
        agent = OpportunityRiskAgent(provider)
        job = JobProfile(**MOCK_JOB_PROFILE)
        result = asyncio.run(agent.run(job))
        assert result.risk_level == RiskLevel.LOW


class TestEvidenceVerifierAgent:
    def test_empty_claims(self):
        provider = MockProvider()
        agent = EvidenceVerifierAgent(provider)
        result = asyncio.run(agent.run(claims=[]))
        assert result.summary == "No claims to verify."

    def test_extract_claims(self):
        provider = MockProvider()
        agent = EvidenceVerifierAgent(provider)
        claims = agent.extract_claims(
            fit_summary="Student has strong Python skills matching the requirement.",
            risk_summary="",
            verification_summary="Company website was found and confirmed.",
        )
        assert len(claims) > 0


class TestDecisionSynthesizerAgent:
    def test_run(self):
        from worthapply.agents.decision_synthesizer import SynthesisOutput

        provider = MockProvider(responses={"SynthesisOutput": MOCK_SYNTHESIS})
        agent = DecisionSynthesizerAgent(provider)

        job = JobProfile(**MOCK_JOB_PROFILE)
        fit = StudentFitResult(**MOCK_FIT_RESULT)
        verification = CompanyVerification(
            company_name="TechCorp",
            verification_status=VerificationStatus.VERIFIED,
            confidence=0.9,
        )
        risk = RiskAssessment(**MOCK_RISK)

        report = asyncio.run(agent.run(job, fit, verification, risk))
        assert isinstance(report, OpportunityReport)
        assert report.recommendation == Recommendation.APPLY
        assert report.priority == Priority.HIGH


class TestPipelineState:
    def test_stage_tracking(self):
        state = PipelineState()
        state.begin_stage("job_intelligence")
        import time
        time.sleep(0.01)
        state.complete_stage("job_intelligence", LLMUsage(total_tokens=100, estimated_cost_usd=0.001))

        assert state.stages["job_intelligence"].status == StageStatus.COMPLETED
        assert state.stages["job_intelligence"].elapsed_ms > 0
        assert state.total_tokens == 100
        assert state.total_cost == 0.001

    def test_progress(self):
        state = PipelineState()
        progress = state.get_progress()
        assert len(progress) == 6
        assert all(p["status"] == "PENDING" for p in progress)

    def test_failure(self):
        state = PipelineState()
        state.fail_stage("student_fit", "LLM error")
        assert state.stages["student_fit"].status == StageStatus.FAILED
        assert state.stages["student_fit"].error == "LLM error"


class TestEndToEndMocked:
    """Full pipeline with mocked provider — no API calls."""

    def test_full_pipeline(self):
        from worthapply.agents.evidence_verifier import VerificationResult

        responses = {
            "JobProfile": MOCK_JOB_PROFILE,
            "StudentFitResult": MOCK_FIT_RESULT,
            "CompanyVerification": {
                "company_name": "TechCorp",
                "verification_status": "VERIFIED",
                "website_found": True,
                "careers_page_found": True,
                "job_listing_found": True,
                "confidence": 0.9,
                "summary": "Company verified.",
            },
            "RiskAssessment": MOCK_RISK,
            "VerificationResult": {
                "verified_claims": [],
                "overall_evidence_quality": "MODERATE",
                "unsupported_count": 0,
                "summary": "All claims supported.",
            },
            "SynthesisOutput": MOCK_SYNTHESIS,
        }

        provider = MockProvider(responses=responses)

        from worthapply.orchestration.workflow import AnalysisWorkflow

        with patch("worthapply.agents.company_verification.web_search", new_callable=AsyncMock) as mock_search, \
             patch("worthapply.agents.company_verification.fetch_webpage", new_callable=AsyncMock) as mock_fetch:

            from worthapply.tools.web_search import SearchResponse
            from worthapply.tools.webpage_fetcher import FetchResult

            mock_search.return_value = SearchResponse(query="test", error="No API key")
            mock_fetch.return_value = FetchResult(
                url="https://example.com/jobs/123",
                status_code=200,
                content="TechCorp is hiring a Software Engineer.",
                title="TechCorp Jobs",
            )

            workflow = AnalysisWorkflow(provider)
            report, state = asyncio.run(
                workflow.analyze(
                    student_text="Student with Python, SQL, Git...",
                    job_text="Software Engineer at TechCorp...",
                    job_url="https://example.com/jobs/123",
                )
            )

            assert isinstance(report, OpportunityReport)
            assert report.job.title == "Software Engineer"
            assert report.student_fit.fit_score == 92.3
            assert report.recommendation == Recommendation.APPLY

            summary = state.to_summary()
            assert summary["total_tokens"] > 0
