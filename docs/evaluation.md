# Evaluation Strategy

## Principles

1. Primary metric defined **before** evaluation.
2. Same cases, same ground truth, same rubric for baseline and all iterations.
3. No cherry-picking.
4. Results not fabricated — only measured values (or explicit gaps).
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
| Human time per task    | Manual triage vs agent wall-clock         |

## Dataset

- 25 synthetic cases across 10 categories (A-J)
- Includes adversarial cases (category J)
- Ground truth is explainable and pre-defined
- No private student data

## Results (measured)

| Run | Exact accuracy | Weighted | Coverage | Notes |
|-----|----------------|----------|----------|-------|
| Baseline | **88.2%** | **94.1%** | 17/25 scored | Cloud; 8 timeouts |
| Final agent pipeline | **56.0%** | **72.0%** | 25/25 | Recorded run cost $0 → local/dev-style |

Artifacts:

- `results/baseline/evaluation.json`, `report.md`, `summary.json`
- `results/final/evaluation.json`, `report.md`, `summary.json`
- `results/comparison.md`
- `results/iterations/README.md` (explains empty mid-folder)

### Product / deploy metrics (outside batch JSON)

| Metric | Value |
|--------|-------|
| Manual human time | 15–45 min / opportunity |
| Deployed agent time | ~50 s typical (Streamlit Cloud) |
| Dev cost (local LLM) | $0 |
| Deploy cost sample | ~$0.0031 / report (~8 calls) |

Live app: https://worthapply-hack.streamlit.app/

### Fairness

Baseline and final batch numbers are **not** yet a same-model A/B. Re-run final on the same cloud model as baseline before claiming an accuracy win. Until then, emphasize verification + dimension separation + time saved.
