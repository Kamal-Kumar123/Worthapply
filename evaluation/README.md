# Evaluation Framework

## Overview

The evaluation framework scores WorthApply outputs against pre-defined
ground truth using a rubric established **before** any evaluation run.

## Dataset

- **Location:** `data/evaluation_cases.json`
- **Size:** 25 cases across 10 categories
- **Type:** Synthetic/public (no private student data)

## Primary Metric

**Opportunity Decision Accuracy** — correct classification of
opportunities as HIGH / MEDIUM / LOW priority.

- Exact match: 1.0
- Adjacent (HIGH↔MEDIUM, MEDIUM↔LOW): 0.5
- Opposite (HIGH↔LOW): 0.0

## Running Evaluation

```bash
# Evaluate baseline
python -m baseline.evaluator

# Compare all versions
python -m evaluation.evaluate --all
```

## Results

Results are stored in `results/<version>/`:

- `raw_results.json` — complete outputs
- `evaluation.json` — scored results
- `summary.json` — runtime/cost
- `report.md` — human-readable report
