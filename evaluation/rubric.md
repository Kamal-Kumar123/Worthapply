# WorthApply Evaluation Rubric

> This rubric is defined **before** any evaluation runs.
> The same rubric applies to the baseline and every subsequent iteration.
> No cherry-picking of results is permitted.
> Any metric that has not yet been measured must be marked **NOT YET EVALUATED**.

---

## Primary Metric: Opportunity Decision Accuracy

The system classifies each opportunity as **HIGH**, **MEDIUM**, or **LOW** priority.
Ground truth labels are pre-defined in the evaluation dataset.

### Scoring

| Predicted vs Expected | Score |
|----------------------|-------|
| Exact match          | 1.0   |
| Adjacent (HIGH↔MEDIUM or MEDIUM↔LOW) | 0.5 |
| Opposite (HIGH↔LOW)  | 0.0   |

### Reported Statistics

- **Accuracy** — fraction of exact matches across all cases.
- **Weighted Accuracy** — mean of per-case scores (accounts for partial credit).
- **Per-Category Breakdown** — accuracy and weighted accuracy for each ground-truth
  category (HIGH, MEDIUM, LOW) separately, so that class imbalance is visible.

---

## Secondary Metrics

### 1. Student Fit Accuracy

The system produces a numeric fit score (0–100).
Each evaluation case specifies an **expected range** `[low, high]`.

| Condition | Score |
|-----------|-------|
| Predicted score falls within expected range | 1.0 |
| Predicted score is within 15 points of the nearest range bound | 0.5 |
| Otherwise | 0.0 |

### 2. Evidence Support Rate

Every claim the system makes should cite evidence from the resume or job description.

$$\text{Evidence Support Rate} = \frac{\text{claims with non-empty evidence}}{\text{total claims}}$$

A claim is a dictionary with at least a `statement` field and an `evidence` field.
If `evidence` is non-empty (non-null, non-blank string or non-empty list), the claim
counts as supported.

### 3. Risk Signal Detection

Each evaluation case lists **expected risk signals** (e.g., "missing required skill",
"visa sponsorship unlikely"). The system should surface these in its analysis.

$$\text{Risk Recall} = \frac{|\text{detected signals} \cap \text{expected signals}|}{|\text{expected signals}|}$$

Matching is case-insensitive substring matching: a detected signal matches an expected
signal if the expected signal appears as a substring of the detected signal (or vice
versa), after lowercasing both.

### 4. Recommendation Accuracy

The system emits one of three recommendations:

- `APPLY`
- `APPLY_IF_TIME`
- `LOW_PRIORITY`

| Predicted vs Expected | Score |
|----------------------|-------|
| Exact match          | 1.0   |
| Adjacent (APPLY↔APPLY_IF_TIME or APPLY_IF_TIME↔LOW_PRIORITY) | 0.5 |
| Opposite (APPLY↔LOW_PRIORITY) | 0.0 |

### 5. Latency

Wall-clock seconds from request submission to response completion, measured per case.
Report **mean**, **median**, **p95**, and **max**.

### 6. Cost

Estimated USD per case, derived from token counts and model pricing.
Report **mean** and **total** across the evaluation batch.

---

## Qualitative Rubric (Human Review)

Each dimension is scored on a 1–5 scale by a human reviewer.

### Evidence Quality (1–5)

| Score | Criteria |
|-------|----------|
| 5 | Every claim is traced to a specific line or section in the resume or job description. |
| 4 | Most claims are traced; a few minor claims lack sources. |
| 3 | About half of claims have traceable evidence. |
| 2 | Few claims are traced; many are asserted without sources. |
| 1 | No evidence tracing at all. |

### Uncertainty Handling (1–5)

| Score | Criteria |
|-------|----------|
| 5 | System explicitly flags what it cannot verify and distinguishes confident from uncertain conclusions. |
| 4 | Most uncertainties are acknowledged; occasional overconfident statements. |
| 3 | Some uncertainties noted, but important gaps are treated as certainties. |
| 2 | Rarely acknowledges uncertainty; mostly presents conclusions as fact. |
| 1 | No acknowledgment of uncertainty whatsoever. |

### Separation of Dimensions (1–5)

| Score | Criteria |
|-------|----------|
| 5 | Fit, confidence, and risk are clearly presented as separate dimensions with independent scores/assessments. |
| 4 | Dimensions are mostly separate; minor conflation in one area. |
| 3 | Partial separation; two dimensions are sometimes merged. |
| 2 | Dimensions are frequently conflated. |
| 1 | All dimensions are collapsed into a single undifferentiated assessment. |

### Actionability (1–5)

| Score | Criteria |
|-------|----------|
| 5 | Report gives the student a clear action plan: what to emphasize, what gaps to address, and whether to apply. |
| 4 | Mostly actionable; a few recommendations are vague. |
| 3 | Some actionable advice mixed with generic statements. |
| 2 | Mostly generic; little specific guidance. |
| 1 | No actionable information; purely descriptive. |

---

## Scoring Rules

1. **Rubric defined BEFORE evaluation.** This document was written before any system
   output was scored.
2. **Same rubric for all iterations.** The baseline and every improved version are
   evaluated using this exact rubric, with no modifications between runs.
3. **No cherry-picking.** All cases in the evaluation dataset are scored. Results are
   reported in aggregate; individual cases are available for inspection but do not
   replace aggregate metrics.
4. **Unmarked = NOT YET EVALUATED.** If a metric has not been computed for a given
   iteration, it is reported as **NOT YET EVALUATED** rather than omitted.
