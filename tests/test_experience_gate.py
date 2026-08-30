"""Unit tests for experience year parsing / fit gate."""

from worthapply.agents.student_fit import (
    apply_experience_gate,
    estimate_student_years,
    parse_required_min_years,
)
from worthapply.models.schemas import JobProfile, StudentFitResult


def test_parse_min_years_ranges():
    assert parse_required_min_years("3-5 years experience") == 3.0
    assert parse_required_min_years("Experience: 7+ years") == 7.0
    assert parse_required_min_years("at least 2 years of experience") == 2.0
    assert parse_required_min_years("Fresher / entry-level role") == 0.0
    assert parse_required_min_years("Great culture, competitive pay") is None


def test_estimate_student_internships_default():
    resume = """
    Experience
    Software Engineering Intern — Acme
    ML Intern — Beta Labs
    """
    years = estimate_student_years(resume)
    assert 0.5 <= years <= 1.5


def test_experience_gate_hard_penalty():
    fit = StudentFitResult(fit_score=92.0, summary="Strong skills")
    job = JobProfile(
        title="AI Engineer",
        experience_requirement="7+ years",
    )
    resume = "Internships at A and B. Total internship experience about 1 year."
    out = apply_experience_gate(fit, resume, job)
    assert out.fit_score <= 30
    assert "Experience gap" in (out.experience_match or "")
    assert any("experience" in c.lower() for c in out.concerns)


def test_experience_gate_ok_for_early_career_jd():
    fit = StudentFitResult(fit_score=88.0)
    job = JobProfile(title="Junior Developer", experience_requirement="0-1 years")
    resume = "Two internships totaling about 1 year."
    out = apply_experience_gate(fit, resume, job)
    assert out.fit_score == 88.0
    assert "OK to apply" in (out.experience_match or "")
