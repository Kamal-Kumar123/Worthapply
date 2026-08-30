"""Tests for data model schemas."""

import pytest
from worthapply.models.schemas import (
    JobProfile,
    OpportunityReport,
    Priority,
    Recommendation,
    RiskAssessment,
    RiskLevel,
    RiskSignal,
    SkillMatch,
    SkillMatchLevel,
    StudentFitResult,
    StudentProfile,
    VerificationStatus,
)
from worthapply.models.evidence import Claim, ClaimType, EvidenceSource, EvidenceStore


class TestJobProfile:
    def test_default_construction(self):
        job = JobProfile()
        assert job.title == ""
        assert job.required_skills == []
        assert job.posting_date is None

    def test_full_construction(self):
        job = JobProfile(
            title="Software Engineer",
            company="TechCorp",
            required_skills=["Python", "SQL"],
            preferred_skills=["AWS"],
        )
        assert job.title == "Software Engineer"
        assert len(job.required_skills) == 2


class TestStudentProfile:
    def test_default_construction(self):
        sp = StudentProfile()
        assert sp.skills == []

    def test_with_data(self):
        sp = StudentProfile(
            name="Jane Doe",
            skills=["Python", "Java", "SQL"],
            education=["BS Computer Science"],
        )
        assert "Python" in sp.skills


class TestSkillMatch:
    def test_matched(self):
        sm = SkillMatch(skill="Python", match_level=SkillMatchLevel.MATCHED, evidence="Used in project X")
        assert sm.match_level == SkillMatchLevel.MATCHED

    def test_missing(self):
        sm = SkillMatch(skill="Rust", match_level=SkillMatchLevel.MISSING)
        assert sm.evidence == ""


class TestStudentFitResult:
    def test_score_bounds(self):
        fit = StudentFitResult(fit_score=85.0)
        assert 0 <= fit.fit_score <= 100

    def test_invalid_score_clamped(self):
        fit = StudentFitResult(fit_score=150.0)
        assert fit.fit_score == 100.0


class TestRiskAssessment:
    def test_default(self):
        ra = RiskAssessment()
        assert ra.risk_level == RiskLevel.LOW
        assert ra.signals == []

    def test_with_signals(self):
        ra = RiskAssessment(
            risk_level=RiskLevel.MEDIUM,
            signals=[
                RiskSignal(signal="Old posting", severity=RiskLevel.MEDIUM, confidence=0.8)
            ],
        )
        assert len(ra.signals) == 1


class TestOpportunityReport:
    def test_default(self):
        report = OpportunityReport()
        assert report.recommendation == Recommendation.LOW_PRIORITY
        assert report.priority == Priority.MEDIUM

    def test_custom(self):
        report = OpportunityReport(
            recommendation=Recommendation.APPLY,
            priority=Priority.HIGH,
            opportunity_confidence=90.0,
        )
        assert report.opportunity_confidence == 90.0


class TestEvidenceStore:
    def test_add_and_retrieve(self):
        store = EvidenceStore(run_id="test-001")
        store.add(Claim(
            claim_id="c1",
            claim="Python is required",
            claim_type=ClaimType.JOB_REQUIREMENT,
            confidence=0.95,
            verified=True,
        ))
        store.add(Claim(
            claim_id="c2",
            claim="Student has AWS",
            claim_type=ClaimType.STUDENT_SKILL,
            confidence=0.8,
            verified=False,
        ))
        assert len(store.claims) == 2
        assert len(store.get_verified()) == 1
        assert len(store.get_unverified()) == 1
        assert len(store.get_by_type(ClaimType.JOB_REQUIREMENT)) == 1

    def test_average_confidence(self):
        store = EvidenceStore()
        store.add(Claim(confidence=0.8))
        store.add(Claim(confidence=0.6))
        assert abs(store.average_confidence() - 0.7) < 0.01

    def test_empty_store(self):
        store = EvidenceStore()
        assert store.average_confidence() == 0.0
