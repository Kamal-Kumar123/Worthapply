# WorthApply — Reproduction Guide

## Prerequisites

- Python 3.11+
- pip
- An xAI API key (get one at https://console.x.ai)
- (Optional) Serper API key for company verification web search

## Quick Start

### 1. Clone / Copy the Project

```bash
git clone <repo-url>
cd Frontier_Hacks
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and set:

```
XAI_API_KEY=your-key-here
LLM_PROVIDER=xai
XAI_MODEL=grok-3-mini-fast
```

Optional (for company verification with web search):
```
SERPER_API_KEY=your-serper-key
```

### 5. Run Tests

```bash
pytest tests/ -v
```

All 56 tests should pass without any API key (uses mocked LLM responses).

### 6. Run Baseline

```bash
python -m baseline.runner
```

Runs all 25 evaluation cases through the single-prompt baseline.

### 7. Evaluate Baseline

```bash
python -m baseline.evaluator
```

Results saved to `results/baseline/`.

### 8. Run Full Pipeline

```bash
python -m worthapply.pipeline
```

Runs all 25 cases through the multi-agent pipeline.

### 9. Evaluate Full Pipeline

```bash
python -m worthapply.pipeline_evaluator
```

Results saved to `results/final/`.

### 10. Compare Versions

```bash
python -m evaluation.evaluate --all
```

### 11. Run the UI

```bash
streamlit run worthapply/app/ui/streamlit_app.py
```

## Cloud Deployment

Cloud deployment requires ONLY the xAI API. No local model needed.

Environment variables:

```
LLM_PROVIDER=xai
XAI_API_KEY=<your-key>
XAI_MODEL=grok-3-mini-fast
```

Deploy to any platform (Render, Railway, etc.) that supports Python + Streamlit.

## Optional: Local Development with Ollama

For offline testing (not required):

1. Install Ollama: https://ollama.ai
2. Pull a small model: `ollama pull qwen2.5:7b`
3. Set in `.env`:

```
LLM_PROVIDER=local
LOCAL_MODEL=qwen2.5:7b
LOCAL_BASE_URL=http://localhost:11434/v1
```

## Project Structure

```
Frontier_Hacks/
├── worthapply/               # Main application
│   ├── agents/               # 6 specialized agents
│   ├── providers/            # LLM provider abstraction
│   ├── orchestration/        # Workflow + state management
│   ├── tools/                # Web search, page fetch, resume parser
│   ├── models/               # Pydantic schemas + evidence model
│   ├── app/ui/               # Streamlit UI
│   ├── pipeline.py           # Full pipeline runner
│   ├── pipeline_evaluator.py # Full pipeline evaluator
│   └── tracing.py            # Agent trajectory capture
├── baseline/                 # Single-prompt baseline
├── evaluation/               # Rubric, scoring, dataset
├── data/                     # 25 evaluation cases
├── results/                  # Baseline + final results
├── tests/                    # 56 tests (unit + integration)
├── docs/                     # Documentation
└── traces/                   # Agent trajectories
```

## Expected Runtime

- Tests: ~20 seconds
- Baseline (25 cases): ~3-5 minutes (estimated)
- Full pipeline (25 cases): ~10-15 minutes (estimated)
- Single opportunity analysis: ~30-60 seconds (estimated)

## Expected Cost

- Baseline (25 cases): ~$0.02-0.05 (estimated with grok-3-mini-fast)
- Full pipeline (25 cases): ~$0.10-0.30 (estimated, 6 LLM calls per case)
- Single opportunity: ~$0.005-0.015

All estimates — actual costs depend on model and token usage.

## Output Files

```
results/
  baseline/
    raw_results.json      # Complete baseline outputs
    evaluation.json       # Scored results
    summary.json          # Runtime/cost summary
    report.md             # Human-readable report
  final/
    raw_results.json      # Full pipeline outputs
    evaluation.json       # Scored results
    summary.json          # Runtime/cost summary
  comparison.md           # Side-by-side comparison
```
