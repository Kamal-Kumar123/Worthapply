# Final Pipeline Evaluation Report

Measured from `results/final/evaluation.json` and `results/final/summary.json`.
Same 25 cases and rubric as the baseline. **Do not invent numbers.**

## Primary Metric: Opportunity Decision Accuracy

- **Exact Accuracy:** 0.56 (56%)
- **Weighted Accuracy:** 0.72 (72%)
- **Cases evaluated:** 25 / 25
- **Execution errors:** 0

## Secondary Metrics

| Metric | Score |
|--------|-------|
| Recommendation Accuracy | 0.78 |
| Fit Accuracy | 0.36 |
| Risk Accuracy | 0.48 |

## Runtime / Cost (batch eval summary)

| Field | Value |
|-------|-------|
| Total elapsed | ~7472 s (~2.1 h for 25 cases) |
| Total tokens | 121,970 |
| Estimated cost (this run) | $0.00 (local/dev-style provider in summary) |
| Avg cost per case (this run) | $0.00 |

## Deployed product (Streamlit Cloud) — per-task sample

Not the batch eval above. Live app: https://worthapply-hack.streamlit.app/

| Field | Sample (Microsoft careers run) |
|-------|--------------------------------|
| Elapsed | ~136 s (135,827 ms) |
| Tokens | ~16,715 |
| Estimated cost | ~$0.0031 |
| LLM calls | ~8 per report |
| Typical deploy latency (stated) | ~50 s |

Development used local Ollama model `worthapply-dev` (`qwen2.5:1.5b-instruct-q4_K_M`) at **$0/task** to avoid API limits while iterating.

## Per-Category Breakdown

| Category | Count | Avg Priority Score |
|----------|-------|--------------------|
| A | 3 | 0.0 |
| B | 3 | 1.0 |
| C | 3 | 0.8333 |
| D | 2 | 0.75 |
| E | 2 | 1.0 |
| F | 3 | 0.8333 |
| G | 2 | 1.0 |
| H | 2 | 0.75 |
| I | 2 | 0.75 |
| J | 3 | 0.5 |

## Interpretation (fairness note)

The recorded **final** primary accuracy is **lower** than the recorded **baseline** (56% vs 88.2% on scored cases). Likely contributors:

1. **Model / provider mismatch** — baseline cloud run vs final often exercised with a weaker local/dev model.
2. Baseline scored only **17/25** cases (timeouts); final scored **all 25**.
3. Multi-agent pipeline is stricter on verification/risk dimensions; label-only accuracy is not the only product goal.

**Fair next step (not yet done):** re-run final pipeline on the **same cloud model** as baseline and refresh this report.

## Product value beyond the primary label

- Separate Student Fit / Opportunity Confidence / Risk / Evidence Quality
- Company verification tools (search + fetch)
- Agent trajectories under `traces/`
- Usable Streamlit UI (single + batch)

Source files: `evaluation.json`, `summary.json`, `raw_results.json`.
