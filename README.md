# WorthApply

**Investigate. Verify. Match. Prioritize.**

An agentic opportunity-intelligence system that helps students decide
whether a job or internship is worth their limited application time.

---

## Problem

Students evaluating internships and jobs online must manually:

1. Verify the posting is current and the company is real
2. Check job details for consistency
3. Map their skills to requirements
4. Identify missing qualifications
5. Spot risk indicators
6. Decide whether to invest 30-60 minutes in an application

This takes **15-45 minutes per opportunity** and students typically
evaluate 10-30 postings per week.

## Who Has This Problem?

University students and recent graduates actively job-hunting —
especially those applying to 10+ positions per week.

## Current Bottleneck

**Investigation time per opportunity.** Each posting requires
cross-referencing the company, reading requirements, matching skills,
and making a judgment call.

## Why It Matters

A student's time is their most constrained resource during job search.
Efficient opportunity triage means they can focus effort where it
matters most.

## Solution

Given a student's resume (PDF/DOCX) and a job URL or description,
WorthApply produces an **Opportunity Intelligence Report** with:

- **Student Fit** — skill matching with evidence from the resume
- **Opportunity Confidence** — verification status of company/posting
- **Risk Indicators** — signals (not accusations) about the opportunity
- **Evidence Quality** — how well-supported the analysis is
- **Recommendation** — APPLY / APPLY IF TIME / LOW PRIORITY

These dimensions are kept **separate** — a student can be a 95% fit
for a questionable opportunity, and the system communicates both facts.

## Architecture

### LLM Provider Abstraction

All agents use an abstract `LLMProvider` interface. No agent code
changes when switching providers.

| Mode | Provider | Use Case |
|------|----------|----------|
| Cloud (default) | xAI-compatible API (`https://api.x.ai/v1`) | Production (Streamlit Cloud) |
| Local (optional) | Ollama `worthapply-dev` (~1.5B Q4, ≤8GB RAM) | Development / unlimited local testing |

### Agent Pipeline

```
Resume + Job Description
       │
       ▼
  Job Intelligence Agent  →  Structured JobProfile
       │
  ┌────┴────┬──────────┐
  │         │          │
  ▼         ▼          ▼
Company   Student    (wait)
Verify    Fit Agent
  │         │
  └────┬────┘
       │
       ▼
  Opportunity Risk Agent
       │
       ▼
  Evidence Verification Agent
       │
       ▼
  Decision Synthesizer
       │
       ▼
  Opportunity Intelligence Report
```

### Agent Responsibilities

| Agent | Responsibility |
|-------|---------------|
| Job Intelligence | Extract structured job profile (required/preferred skills, requirements) |
| Student Fit | Evidence-backed skill matching against student resume |
| Company Verification | Web search + page fetch to verify company existence |
| Opportunity Risk | Identify risk signals (stale posting, inconsistencies, missing info) |
| Evidence Verifier | Audit claims from other agents against source material |
| Decision Synthesizer | Combine all dimensions into final recommendation |

## Baseline

Single-prompt approach: one LLM call receives the resume + job description
and produces a structured report.

**Measured result** (`results/baseline/`):

| Metric | Value |
|--------|-------|
| Exact decision accuracy | **88.2%** (17/25 scored; 8 timeouts) |
| Weighted accuracy | **94.1%** |
| Avg latency | ~30 s/case |
| Avg cost | ~$0.0007/case (cloud) |

See [Baseline Failure Analysis](docs/baseline_failure_analysis.md) and
[Baseline report](results/baseline/report.md).

## Improvement Changelog

See [Improvement Changelog](docs/improvement_changelog.md).
Removal/revise write-up: [Removal experiment](docs/removal_experiment.md).

## Evaluation

- **Primary Metric:** Opportunity Decision Accuracy (HIGH/MEDIUM/LOW)
- **Dataset:** 25 synthetic cases across 10 categories (incl. adversarial J)
- **Rubric:** Defined before evaluation in [Rubric](evaluation/rubric.md)
- **Same cases** for baseline and final

### Evaluation Categories

| Cat | Name | Cases |
|-----|------|-------|
| A | Legitimate + Strong Fit | 3 |
| B | Legitimate + Weak Fit | 3 |
| C | Legitimate + Medium Fit | 3 |
| D | Old/Questionable Posting | 2 |
| E | Cross-Source Inconsistency | 2 |
| F | Strong Fit + Opportunity Concerns | 3 |
| G | Weak Fit + Legitimate Opportunity | 2 |
| H | Missing Official Information | 2 |
| I | Conflicting Information | 2 |
| J | Challenging/Adversarial | 3 |

### Results (measured)

> **Important — the accuracy drop is not “agents failed.”**
>
> Baseline **88.2%** used a **cloud API**. That API was dropped for the full agent eval because of **cost and rate limits** (8 baseline cases timed out). The recorded agent run used a **local LLM** so eval cost stayed **$0**, which is why exact accuracy is **56%** (all 25 cases). Same-model re-eval on the cloud API has not been done. Live app still uses a cloud API.

| METRIC | Baseline | Agent (final) |
|--------|----------|---------------|
| Decision accuracy (exact) | 88.2% (17 scored) | 56% (25/25) |
| Weighted accuracy | 94.1% | 72% |
| Human time / task | 15–45 min manual | ~50 s typical on deploy |
| Cost / task | ~$0.0007 (baseline cloud) | Dev local **$0**; deploy ~**$0.0031**/report |

Side-by-side: [results/comparison.md](results/comparison.md) · Final report: [results/final/report.md](results/final/report.md).

**Fairness:** cloud baseline vs local-LLM agents — do not claim agents win or lose on label accuracy until same-model re-eval. Product win = verification + separate dimensions + Streamlit UI.

## Live demo

**Streamlit Cloud:** https://worthapply-hack.streamlit.app/  
Deploy notes: [docs/deployment.md](docs/deployment.md) (not Render/Vercel).

## Reproduction

See [Reproduction Guide](docs/reproduction.md).

### Quick Start

```bash
# Setup
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS/Linux
pip install -r requirements.txt
cp .env.example .env           # add XAI_API_KEY

# Run baseline
python -m baseline.runner
python -m baseline.evaluator

# Run full pipeline
python -m worthapply.pipeline
python -m worthapply.pipeline_evaluator

# Run UI
streamlit run worthapply/app/ui/streamlit_app.py

# Run tests
pytest tests/ -v
```

## Configuration

```env
LLM_PROVIDER=xai          # "xai" (default) or "local"
XAI_API_KEY=your-key       # required for cloud / Streamlit secrets
XAI_MODEL=grok-3-mini-fast # configurable
SERPER_API_KEY=your-key    # optional, for company verification
LOCAL_MODEL=worthapply-dev # optional local Ollama model for dev
```

## Runtime

| Mode | Typical |
|------|---------|
| Unit tests | ~20 s (60 passed, mocked LLM) |
| Baseline batch (25) | ~12 min wall (~30 s/case avg; some timeouts) |
| Final batch (25) | ~2.1 h on recorded local/dev-style run |
| Single report (Streamlit Cloud) | ~50 s typical; ~136 s heavy careers sample |

## Cost

| Mode | Cost |
|------|------|
| Local dev (`worthapply-dev`) | **$0** / task |
| Baseline cloud eval | ~$0.016 total / ~$0.0007 per case |
| Deployed API report | ~**$0.0031** / report (~8 LLM calls, ~17k tokens sample) |

## Limitations

See [Limitations](docs/limitations.md).

Key points:
- Risk indicators are **signals, not proof** of fraud
- Verification relies on public web information only
- Recommendations are **decision support**, not decisions
- The system never submits applications or contacts anyone

## Responsible Use

WorthApply provides decision support. Students should independently
verify important opportunities. Risk indicators are not accusations.

## Hot Take

See [Hot Take](docs/hot_take.md) — on the uncomfortable truth about
whether multi-agent systems actually earn their complexity.

## License

MIT
