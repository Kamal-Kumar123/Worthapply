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

> **Important — 88% vs 56% is not a like-for-like drop.**
>
> Baseline was scored on a **cloud API** (stronger model). That API was **not** used for the full agent eval because of **cost and rate limits** (8 of 25 baseline cases already timed out). To finish the 25-case agent batch at **$0**, the recorded final run used a **weaker local/dev LLM** — so headline accuracy fell even though the pipeline is stricter (web verification, separate fit vs risk) and scored **all 25 cases**.
>
> Do not read this table as “agents are worse than the single prompt.” It is **cloud baseline vs local-LLM agents**. Live Streamlit Cloud still uses a cloud API. A fair accuracy A/B requires re-running the agent pipeline on the **same cloud model** as baseline (not yet done).

| Run | Exact accuracy | Weighted | Coverage | Notes |
|-----|----------------|----------|----------|-------|
| Baseline | **88.2%** | **94.1%** | 17/25 scored | Cloud API; 8 timeouts — eval stopped using this API for the full agent batch (cost / limits) |
| Final agent pipeline | **56.0%** | **72.0%** | 25/25 | Local/dev LLM so recorded cost stayed **$0**; weaker model than baseline |

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

See the Important note above. Baseline and final batch numbers are **not** a same-model A/B. Re-run final on the same cloud model as baseline before claiming an accuracy win. Until then, emphasize verification + dimension separation + time saved.
