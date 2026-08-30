# `results/iterations/` — why this folder is mostly empty

Hackathon layout expects:

```
results/
  baseline/
  iterations/   ← mid-stage scored runs
  final/
```

## What we did instead

Agents were added in sequence (Job Intelligence → Student Fit → Company Verify → Risk → Evidence → Synthesizer), but **separate scored batch runs were not saved** after every single agent add. Only:

- `results/baseline/` — single-prompt baseline (measured)
- `results/final/` — full multi-agent pipeline (measured)

## How to read “iterations” for judges

Use the narrative + evidence table in:

**`docs/improvement_changelog.md`**

That document is the iteration record (what / why / evidence / keep-or-revise). Product and live-demo evidence for mid stages (verification UI, dimension split, source-URL fix) comes from the deployed app and `traces/`, not from missing mid-folder JSON.

## Optional future fill (not required for current code)

If re-running evals later, drop files here such as:

- `iter1_job_fit/evaluation.json`
- `iter2_verify_risk/evaluation.json`
- `iter3_evidence_synth/evaluation.json`

Each should use the **same** 25 cases and `evaluation/rubric.md`. Application code does not need to change for that — only new eval runs + saving outputs here.
