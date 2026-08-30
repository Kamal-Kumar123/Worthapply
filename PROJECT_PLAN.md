# WorthApply — Project Plan

**Tagline:** Investigate. Verify. Match. Prioritize.

---

## Problem

Students discover internship and job opportunities online but lack efficient
tools to evaluate whether each opportunity is worth their limited application
time. Before applying, a student must manually:

1. Verify that the posting is current and the company is real.
2. Check that job details are consistent across sources.
3. Determine how well their skills/experience match the requirements.
4. Identify missing qualifications.
5. Spot risk indicators (stale posting, missing official listing, conflicting info).
6. Decide whether to invest time in the application.

This manual process takes 15–45 minutes per opportunity and is error-prone,
leading students to either waste time on low-fit or questionable postings, or
skip legitimate opportunities out of fatigue.

## Target User

University students and recent graduates actively searching for internships
and entry-level positions — typically evaluating 10–30 opportunities per week.

## Current Bottleneck

**Investigation time per opportunity.** Each posting requires cross-referencing
the company, reading the full description, mapping requirements to the
student's resume, and making a subjective priority judgment. Students either
shortcut this process (applying blindly) or burn out and stop applying.

## Product Objective

Provide an **agentic decision-support system** that, given a student's resume
and a job URL, produces a structured **Opportunity Intelligence Report**
covering:

- Student–job fit (with evidence)
- Opportunity confidence (verification status)
- Risk indicators
- Evidence quality
- Actionable recommendation

The system does NOT submit applications, contact recruiters, or make
consequential decisions on behalf of the student.

## Architecture Hypothesis

A multi-agent pipeline where specialized agents handle distinct verification
dimensions will outperform a single-prompt baseline on opportunity
classification accuracy, evidence quality, and risk detection.

**Target architecture** (to be validated through experiments):

```
JOB URL + RESUME
       |
       v
  Job Intelligence Agent  -->  structured job profile
       |
  +----+----+----+
  |    |    |    |
  v    v    v    v
Company  Risk  Student Fit
Verify   Agent    Agent
  |    |    |
  +----+----+
       |
       v
  Evidence Verification Agent
       |
       v
  Decision Synthesizer
       |
       v
  Opportunity Intelligence Report
```

The actual final architecture will be determined by measured experiments.
Components that do not produce measurable improvement will be removed.

## Development Phases

| Phase | Description                              | Status           |
|-------|------------------------------------------|------------------|
| 0     | Problem definition + eval specification  | IN PROGRESS      |
| 1     | Simple baseline (single LLM + prompt)    | NOT STARTED      |
| 2     | Run baseline, analyze failures           | NOT STARTED      |
| 3     | Job Intelligence Agent                   | NOT STARTED      |
| 4     | Student Fit Agent                        | NOT STARTED      |
| 5     | Company Verification Agent               | NOT STARTED      |
| 6     | Opportunity Risk/Freshness Agent         | NOT STARTED      |
| 7     | Evidence Verification Agent              | NOT STARTED      |
| 8     | Decision Synthesizer                     | NOT STARTED      |
| 9     | Evaluate all versions                    | NOT STARTED      |
| 10    | Test/remove unnecessary components       | NOT STARTED      |
| 11    | Freeze final architecture                | NOT STARTED      |
| 12    | Build polished UI                        | NOT STARTED      |
| 13    | Build reproducibility package            | NOT STARTED      |
| 14    | Prepare hackathon documentation & demo   | NOT STARTED      |

## Evaluation Strategy

- **Primary metric:** Opportunity Decision Accuracy — system's ability to
  correctly classify opportunities as HIGH / MEDIUM / LOW priority.
- **Evaluation dataset:** 25 synthetic/public cases across 10 categories.
- **Method:** Same cases, same ground truth, same rubric for baseline and
  every iteration.
- **Secondary metrics:** Fit Accuracy, Evidence Support Rate, Risk Detection
  Rate, Latency, Cost, Human Time Saved.
- **Rubric defined before evaluation.**

## Metrics

| Metric                      | Type        | Target     |
|-----------------------------|-------------|------------|
| Opportunity Decision Acc.   | Primary     | ≥ 80%      |
| Student Fit Accuracy        | Secondary   | ≥ 75%      |
| Evidence Support Rate       | Secondary   | ≥ 70%      |
| Risk Signal Detection       | Secondary   | ≥ 70%      |
| Avg Latency (per case)      | Operational | < 60s      |
| Avg Cost (per case)         | Operational | < $0.10    |

All targets are hypotheses. Actual results will be measured.

## Risks

1. xAI API rate limits or downtime during evaluation runs.
2. Web scraping may fail for dynamically rendered career pages.
3. Local LLM quality may be insufficient for structured extraction.
4. Evaluation dataset may not cover edge cases discovered later.
5. Multi-agent overhead may not justify improvement over baseline.

## Assumptions

1. Students have a PDF/DOCX resume available.
2. Job postings have a publicly accessible URL or pasteable description.
3. xAI Grok models support structured output and tool/function calling.
4. Public web information is sufficient for basic company verification.
5. 25 evaluation cases provide enough signal for meaningful comparison.

## LLM Deployment Strategy

### Provider Abstraction

All agents use a `LLMProvider` interface. No agent directly calls a specific
API. Provider is selected at runtime via `LLM_PROVIDER` env var.

### Mode A — Cloud / Production (Primary)

- **Provider:** xAI API (OpenAI-compatible)
- **Endpoint:** `https://api.x.ai/v1`
- **Model:** Configurable via `XAI_MODEL` (default: `grok-3-mini-fast`)
- **Auth:** `XAI_API_KEY` from `.env`
- **Requirement:** Cloud deployment must work with ONLY the xAI API.

### Mode B — Local Development (Optional)

- **Provider:** Ollama or compatible local server
- **Model:** ~7B parameter quantized model (≤ 8 GB RAM)
- **Endpoint:** `http://localhost:11434/v1`
- **Requirement:** NOT required for deployment. Development convenience only.
- **Fallback:** If local unavailable, clear error directs user to configure xAI.

### Cost Tracking

Every LLM call records: model, tokens (in/out), estimated cost, latency,
provider, timestamp, run ID, agent name. No API keys in logs.
