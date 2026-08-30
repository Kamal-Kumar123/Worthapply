# Baseline Failure Analysis

## Status: ANALYSIS BASED ON EXPECTED BASELINE BEHAVIOR

This analysis documents expected failure modes of the single-prompt baseline
approach, which motivated the multi-agent architecture. Actual quantitative
results require running the baseline with `python -m baseline.runner` and
evaluating with `python -m baseline.evaluator`.

## Expected Failure Categories

### 1. Required vs. Preferred Skill Confusion

**Problem:** The baseline prompt asks the LLM to distinguish required from
preferred skills, but in a single pass over the full job description, the model
frequently conflates them — especially when the job posting itself is ambiguous.

**Expected impact:** Fit scores inflated (counting preferred-matches as
required-matches) or deflated (treating preferred-misses as required-misses).

**Motivates:** Job Intelligence Agent (structured skill extraction with explicit
required/preferred separation).

### 2. Unsupported Fit Claims

**Problem:** The baseline may claim "Student has X skill" without pointing to
specific evidence in the resume (project, course, or experience).

**Expected impact:** Fit assessments look reasonable but lack traceability.
Reviewers cannot verify the claim.

**Motivates:** Student Fit Agent (evidence-backed matching) + Evidence
Verification Agent.

### 3. Inability to Verify Company/Posting

**Problem:** The baseline operates on the provided text only — it has no access
to web search or company career pages. It cannot check whether the company
exists, whether the job is currently listed, or whether information is
consistent across sources.

**Expected impact:** Opportunity confidence is guessed from text signals alone.
Categories D, E, F, H, I, and J all suffer because baseline cannot distinguish
a legitimate posting from a stale/fake one.

**Motivates:** Company Verification Agent + Opportunity Risk Agent.

### 4. Overconfident Recommendations

**Problem:** Without independent verification, the baseline tends to recommend
"APPLY" for any reasonable-looking job description, even if the posting is old
or unverifiable.

**Expected impact:** High false-positive rate for opportunity confidence.
The challenging J-category cases (95% fit + questionable opportunity) will
likely get "APPLY" instead of "APPLY IF TIME" or "VERIFY FIRST."

**Motivates:** Risk Agent + Dimension Separation (fit ≠ opportunity confidence).

### 5. Dimension Collapse

**Problem:** The baseline collapses student fit and opportunity quality into a
single recommendation without maintaining them as separate scores. A 95% fit
student + questionable opportunity may get "APPLY" because the fit dominates.

**Expected impact:** Adversarial cases (category J) are misclassified.

**Motivates:** Decision Synthesizer with explicit dimension separation.

### 6. Missing Risk Signal Detection

**Problem:** The baseline has no access to external data, so it cannot detect:
- Old posting dates (unless explicitly stated in text)
- Missing official listings
- Cross-source inconsistencies
- Employee count discrepancies

**Expected impact:** Categories D, E, I, J will have low risk detection recall.

**Motivates:** Opportunity Risk Agent with web tool access.

### 7. Hallucinated Company Information

**Problem:** When asked about company verification, the baseline may generate
plausible-sounding but fabricated information about the company's website,
founding date, or employee count.

**Expected impact:** False confidence in company legitimacy.

**Motivates:** Company Verification Agent with actual web search + Evidence
Verification Agent to catch unsupported claims.

## Expected Category-Level Performance

| Category | Expected Baseline Performance | Why |
|----------|-------------------------------|-----|
| A (Legit + Strong Fit) | Good — straightforward match | Text-based matching works |
| B (Legit + Weak Fit) | Moderate — may overstate fit | No evidence grounding |
| C (Legit + Medium Fit) | Moderate | Partial matches hard to score |
| D (Old Posting) | Poor — cannot detect age | No web access |
| E (Cross-Source) | Poor — cannot cross-reference | No web access |
| F (Fit + Concerns) | Poor — overrates opportunity | Dimension collapse |
| G (Weak Fit + Legit) | Moderate — may underrate opportunity | |
| H (Missing Info) | Poor — cannot check external | No web access |
| I (Conflicting) | Poor — cannot detect conflicts | No web access |
| J (Adversarial) | Poor — dimension collapse trap | Designed to fool single-pass |

## Conclusion

The baseline's primary weakness is **lack of independent verification** and
**dimension collapse**. It can perform text-based skill matching reasonably
well but cannot assess opportunity quality or detect risk indicators.

This justifies building:
1. **Job Intelligence Agent** — structured extraction
2. **Student Fit Agent** — evidence-backed matching
3. **Company Verification Agent** — web-based verification
4. **Opportunity Risk Agent** — risk signal detection
5. **Evidence Verification Agent** — claim validation
6. **Decision Synthesizer** — dimension-separated recommendation
