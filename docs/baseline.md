# Baseline

## What Is the Baseline?

The baseline is a **single-prompt approach**: one LLM call receives the
student's resume and the job description, and produces a structured
Opportunity Intelligence Report in a single response.

No multi-agent orchestration. No web search. No verification tools.
No memory. No evidence verification.

## Why Start With a Baseline?

The hackathon requires demonstrating that the agentic approach adds
measurable value. Without a baseline comparison, claims about improvement
are unsupported.

The baseline also reveals specific failure modes that guide which
agents to build — rather than building agents speculatively.

## Architecture

```
Student Resume + Job Description
             │
             ▼
    ┌─────────────────┐
    │  Single LLM     │
    │  Structured     │
    │  Prompt         │
    └────────┬────────┘
             │
             ▼
    Opportunity Report
    (JSON structured output)
```

## Implementation

| File | Purpose |
|------|---------|
| `baseline/prompt.txt` | The structured prompt template |
| `baseline/schemas.py` | `BaselineReport` Pydantic model |
| `baseline/runner.py` | Runs all 25 evaluation cases |
| `baseline/evaluator.py` | Scores results against ground truth |

## Running the Baseline

```bash
# Run all 25 cases
python -m baseline.runner

# Run a single case
python -m baseline.runner --case case_001

# Dry run (show prompts, no LLM calls)
python -m baseline.runner --dry-run

# Evaluate results
python -m baseline.evaluator
```

## Output

Results are saved to `results/baseline/`:

- `raw_results.json` — complete structured outputs for all cases
- `evaluation.json` — scored results with per-case and per-category breakdown
- `summary.json` — runtime, cost, and token usage
- `report.md` — human-readable evaluation report

## What the Baseline Can Do

- Extract basic job information from the description
- Perform text-based skill matching
- Generate a structured recommendation
- Produce fit scores

## What the Baseline Cannot Do

- Independently verify the company exists
- Check if the job is currently listed on the company's career page
- Detect stale or outdated postings
- Cross-reference information across sources
- Distinguish between high-quality evidence and text patterns
- Keep student fit and opportunity quality as truly separate dimensions

## Measured Results

See [Baseline Failure Analysis](baseline_failure_analysis.md) for failure
modes that motivated the agents. Measured scores:

| Metric | Value |
|--------|-------|
| Exact decision accuracy | **88.2%** |
| Weighted accuracy | **94.1%** |
| Cases scored | 17 / 25 (8 timeouts/errors) |
| Avg latency | ~30 s/case |
| Avg cost | ~$0.0007/case (cloud) |

Artifacts: `results/baseline/report.md`, `evaluation.json`, `summary.json`.

**Status:** EVALUATED (with incomplete coverage due to timeouts)
