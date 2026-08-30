# Evaluation Strategy

## Principles

1. Primary metric defined **before** evaluation.
2. Same cases, same ground truth, same rubric for baseline and all iterations.
3. No cherry-picking.
4. Results not fabricated — marked "NOT YET EVALUATED" until measured.
5. Failures included alongside successes.

## Primary Metric

**Opportunity Decision Accuracy**

The system classifies opportunities into HIGH / MEDIUM / LOW priority.
Ground truth is pre-defined in the evaluation dataset.

| Prediction vs Truth | Score |
|---------------------|-------|
| Exact match         | 1.0   |
| Adjacent            | 0.5   |
| Opposite            | 0.0   |

## Secondary Metrics

| Metric                 | Description                              |
|------------------------|------------------------------------------|
| Recommendation Accuracy| APPLY / APPLY_IF_TIME / LOW_PRIORITY     |
| Student Fit Accuracy   | Fit score within expected range           |
| Risk Detection         | Recall of expected risk signals           |
| Evidence Support Rate  | % of claims backed by evidence            |
| Latency                | Seconds per case                          |
| Cost                   | USD per case                              |

## Dataset

- 25 synthetic cases across 10 categories (A-J)
- Includes at least 1 challenging/adversarial case
- Ground truth is explainable and pre-defined
- No private student data

## Results

All results stored in `results/` directory. Current status:

- Baseline: NOT YET EVALUATED
- Iteration 1: NOT YET EVALUATED
- Final: NOT YET EVALUATED
