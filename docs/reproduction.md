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

## Cloud Deployment (Streamlit Community Cloud)

**Live:** https://worthapply-hack.streamlit.app/

Full notes: [deployment.md](deployment.md). Hosting is **Streamlit Cloud** (not Render/Vercel).

Cloud requires ONLY the cloud LLM API. No local model / Ollama on the server.

Environment / Streamlit **Secrets**:

```
LLM_PROVIDER=xai
XAI_API_KEY=<your-key>
XAI_MODEL=<your-cloud-model>
```

Repo deploy helpers already present: `runtime.txt`, `requirements.txt`, `.streamlit/config.toml`.

## Optional: Local Development with Ollama

For offline testing and avoiding API rate limits while iterating (not required for deploy):

1. Install Ollama: https://ollama.ai
2. Create the project model: `ollama create worthapply-dev -f Modelfile.worthapply`
3. Set in `.env`:

```
LLM_PROVIDER=local
LOCAL_MODEL=worthapply-dev
LOCAL_BASE_URL=http://localhost:11434/v1
```

Local cost: **$0**/task. Quality is weaker than the cloud API — expect lower extraction/fit/verify accuracy vs deploy.

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
├── results/                  # Baseline + final results (+ iterations README)
├── tests/                    # ~60 tests (unit + integration)
├── docs/                     # Documentation
└── traces/                   # Agent trajectories
```

## Measured Runtime

- Tests: ~20 seconds (60 passed, mocked LLM)
- Baseline (25 cases): ~12 min wall (~30 s/case avg; some timeouts) — see `results/baseline/summary.json`
- Full pipeline (25 cases): ~2.1 h on the recorded local/dev-style run — see `results/final/summary.json`
- Single opportunity (Streamlit Cloud): ~50 s typical; ~136 s heavy sample

## Measured / observed Cost

- Baseline cloud batch: ~$0.016 total (~$0.0007/case)
- Full pipeline recorded summary: $0 (local/dev-style)
- Local iteration: $0 (`worthapply-dev`)
- Deployed API report: ~$0.0031/report (~8 LLM calls)

## Output Files

```
results/
  baseline/
    raw_results.json
    evaluation.json
    summary.json
    report.md
  iterations/
    README.md             # Explains why mid-stage JSON is absent
  final/
    raw_results.json
    evaluation.json
    summary.json
    report.md
  comparison.md
```
