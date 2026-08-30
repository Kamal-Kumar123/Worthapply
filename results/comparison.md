# Baseline vs Agent Solution — Comparison

Same dataset (`data/evaluation_cases.json`, 25 cases) and same rubric (`evaluation/rubric.md`).

## Primary & secondary (batch evaluation)

| METRIC | SIMPLE BASELINE | AGENT SOLUTION (final) | CHANGE |
|--------|-----------------|------------------------|--------|
| Opportunity Decision Accuracy (exact) | **88.2%** (17/25 scored; 8 timeouts) | **56.0%** (25/25 scored) | Labels: baseline higher on recorded runs. See fairness note below. |
| Weighted decision accuracy | **94.1%** | **72.0%** | Same caveat |
| Recommendation accuracy | 85.3% | 78.0% | Slightly lower on final run |
| Fit accuracy | 97.1% | 36.0% | Large drop on recorded final run (model mismatch likely) |
| Risk accuracy | 85.3% | 48.0% | Lower on recorded final run |

Sources: `results/baseline/evaluation.json`, `results/final/evaluation.json`.

## Human time & cost (product framing)

| METRIC | SIMPLE BASELINE / MANUAL | AGENT SOLUTION | CHANGE |
|--------|--------------------------|----------------|--------|
| Human time per task | **15–45 min** manual student triage | **~50 s** typical on Streamlit Cloud deploy (~136 s heavy sample) | **~20–50× faster** triage |
| Cost per task | Baseline cloud eval ~**$0.0007**/case | Dev local `worthapply-dev`: **$0**. Deploy API: **~$0.0031**/report (~8 LLM calls) | Dev free; production cents/report |

## Fairness note (same-model re-eval)

These batch numbers are **not** a clean same-model A/B:

- Baseline: cloud provider (`results/baseline/summary.json`)
- Final summary shows **$0** cost → local/dev-style run for the full 25-case agent pipeline

Until final is re-measured on the **same cloud API/model** as baseline, do **not** claim “multi-agent beats baseline on accuracy.” Claim instead: agents add **verification**, **dimension separation**, **traces**, and **usable deploy** (Streamlit Cloud).

## Where iteration mid-scores live

Per-agent scored checkpoints were **not** written as separate eval JSON under `results/iterations/`. See `results/iterations/README.md`. Story of each stage is in `docs/improvement_changelog.md`.
