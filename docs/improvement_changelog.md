# WorthApply — Improvement Changelog

Every meaningful iteration is documented with observed problem,
hypothesis, change, result, decision, and learning.

---

## Baseline

**What:** Single LLM prompt (xAI Grok) that receives student resume + job
description and produces a structured opportunity report in one call.

**Why:** Establish a measurable starting point.

**Implementation:** `baseline/runner.py` + `baseline/prompt.txt` +
`baseline/schemas.py`. One structured prompt, one LLM call, one structured
JSON output.

**Result:** NOT YET EVALUATED (requires XAI_API_KEY)

**Expected weaknesses:** Cannot verify companies, cannot detect stale postings,
conflates student fit with opportunity quality, unsupported claims.

**Decision:** Proceed to multi-agent architecture based on expected failure
analysis. Validate quantitatively once API key is configured.

---

## Iteration 1 — Job Intelligence Agent

**Observed problem:** Baseline conflates required vs. preferred skills and
produces unstructured job analysis mixed into the recommendation.

**Hypothesis:** A dedicated extraction agent with a focused prompt and
structured output schema will produce cleaner required/preferred separation.

**Change:** Added `agents/job_intelligence.py` — takes raw job text, produces
a `JobProfile` with explicitly separated `required_skills` and
`preferred_skills` lists.

**Result:** NOT YET EVALUATED

**Decision:** Included in pipeline — foundational for all downstream agents.

---

## Iteration 2 — Student Fit Agent

**Observed problem:** Baseline claims skill matches without citing specific
resume evidence.

**Hypothesis:** A dedicated fit agent that receives the structured `JobProfile`
and student profile will produce evidence-backed skill matching.

**Change:** Added `agents/student_fit.py` — for each skill, outputs
MATCHED/PARTIALLY_MATCHED/MISSING with specific evidence from the resume.

**Result:** NOT YET EVALUATED

**Decision:** Included in pipeline.

---

## Iteration 3 — Company Verification Agent

**Observed problem:** Baseline cannot independently verify company existence
or job listing authenticity. May hallucinate company information.

**Hypothesis:** An agent with web search and page fetch tools can gather
public evidence about the company and cross-reference the job listing.

**Change:** Added `agents/company_verification.py` with web search + page
fetch tools. Outputs `CompanyVerification` with explicit verification status
and evidence.

**Result:** NOT YET EVALUATED

**Decision:** Included in pipeline. Requires SERPER_API_KEY for full
functionality; gracefully degrades without it.

---

## Iteration 4 — Opportunity Risk Agent

**Observed problem:** Baseline cannot detect stale postings, inconsistencies,
or missing information that would indicate opportunity-level risk.

**Hypothesis:** A dedicated risk agent that combines job details and
verification results can identify concrete risk signals.

**Change:** Added `agents/opportunity_risk.py` — produces `RiskAssessment`
with individual risk signals, severity levels, and evidence.

**Result:** NOT YET EVALUATED

**Decision:** Included in pipeline.

---

## Iteration 5 — Evidence Verification Agent

**Observed problem:** Claims from individual agents may be unsupported.
The final report should only rely on verified evidence.

**Hypothesis:** A verification pass that audits key claims against source
material will improve evidence quality and reduce hallucination.

**Change:** Added `agents/evidence_verifier.py` — extracts key claims from
agent outputs, checks each against source text, assigns confidence.

**Result:** NOT YET EVALUATED

**Decision:** Included in pipeline.

---

## Iteration 6 — Decision Synthesizer

**Observed problem:** Baseline collapses student fit, opportunity confidence,
risk, and evidence quality into a single undifferentiated recommendation.

**Hypothesis:** A synthesizer that explicitly maintains separate dimensions
(fit, confidence, risk, evidence) will produce better-calibrated
recommendations, especially on adversarial cases.

**Change:** Added `agents/decision_synthesizer.py` — combines all agent
outputs while keeping dimensions separate. Produces `OpportunityReport`.

**Result:** NOT YET EVALUATED

**Decision:** Included in pipeline.

---

## Orchestration

**What:** `orchestration/workflow.py` — runs Job Intelligence first, then
Company Verification + Student Fit in parallel, then Risk Assessment (depends
on verification), then Evidence Verification, then Decision Synthesis.

**Why:** Independent agents can run concurrently for latency reduction.
Risk assessment benefits from verification results.

**Result:** NOT YET EVALUATED

---

## Removal Experiments

No removal experiments conducted yet. After evaluation, components that do not
produce meaningful improvement will be candidates for removal.

Expected candidates:
- Evidence Verification Agent (if it adds cost without improving evidence quality)
- Company Verification Agent (if web search is not available/reliable)

---

## Failed Experiments

None yet. This section will document any components that were built, evaluated,
and removed because they did not meaningfully improve results.
