# AI / Coding-Agent Disclosure

This project was built with a coding agent. This document discloses which tools were
used, what they did, what the human author decided and verified, and where the
build trajectories are.

## Tools used

| Tool | Role in this project |
|------|----------------------|
| **Cursor IDE — Agent mode (coding agent)** | Primary build tool. Scaffolding, writing agents/tools/UI, evaluation harness, tests, documentation, and refactors. Ran shell commands (git, pytest, pipeline runs) under human approval. |
| Frontier LLMs inside Cursor Agent | Used as the coding agent's backing models. The exact model varied across build sessions; no single model is claimed as sole author. |
| **Ollama (local runtime)** | Not a coding agent — this is the *product's* optional dev LLM (`worthapply-dev`, based on `qwen2.5:1.5b-instruct-q4_K_M`) used to test WorthApply repeatedly without hitting API limits. |
| **Cloud LLM API (xAI-compatible endpoint)** | The *product's* production provider for the deployed app and for the measured baseline evaluation. |

The public GitHub repository shows `cursoragent` as a contributor alongside the
human author, consistent with this disclosure.

## What the coding agent did

- Created the initial project skeleton and `PROJECT_PLAN.md`.
- Implemented the `LLMProvider` abstraction (cloud + optional local) and the six agents:
  Job Intelligence, Student Fit, Company Verification, Opportunity Risk, Evidence Verifier,
  Decision Synthesizer.
- Implemented tools (resume parser, web search, webpage fetcher), orchestration/state, and tracing.
- Implemented the single-prompt baseline (`baseline/`), the 25-case dataset, the rubric,
  and the scoring/evaluation scripts.
- Built the Streamlit UI (single + batch modes), report rendering, history, and downloads.
- Wrote the test suite (~60 mocked tests) and the documentation set under `docs/`.
- Ran evaluations and wrote measured results into `results/`.

## What the human author decided and owns

These were human calls, not agent suggestions accepted blindly:

- **Problem, user, and bottleneck** — student job triage (15–45 min per posting).
- **Scope boundaries** — no auto-apply, no recruiter contact, no "this is a scam" verdicts,
  no accounts/DB in the hackathon build.
- **Dimension separation** — student fit must stay separate from opportunity confidence and risk.
- **Provider strategy** — local `worthapply-dev` for unlimited dev iteration, cloud API for
  deploy/demo; deployment must never depend on a local model.
- **Deployment target** — Streamlit Community Cloud (not Render/Vercel).
- **Concurrency limit** — batch analysis capped (`BATCH_CONCURRENCY`, default 2) to avoid
  provider rate-limit failures during demos.
- **Honesty rules** — no fabricated metrics; unmeasured items are stated as open, and the
  recorded baseline-vs-final comparison is explicitly labelled as *not* a same-model A/B
  instead of being spun as an improvement.
- **Behavior corrections** — rejecting over-aggressive risk flags on normal job boards,
  refusing to let the model overwrite a user-provided Source URL, and revising the
  "always web-search" behavior for direct company career links.

## Human verification process

- Read the diff for every substantive change; failure paths reviewed, not just happy paths.
- `pytest tests/ -v` (~60 tests, mocked LLM, no paid API calls) before relying on a change.
- Manual runs of the deployed app against real postings (job boards and official career pages)
  to catch behavior the tests could not, e.g. wrong Source URL, false skill gaps,
  weak company verification.
- Measured results checked against the files in `results/` rather than agent claims.

## Two different kinds of trajectories in this repo

| Path | What it contains |
|------|------------------|
| `traces/` | **Product** agent trajectories — per-run, per-agent JSON (input, tool calls, output, retries, tokens, cost, timings) for WorthApply's own six agents. |
| `docs/coding_agent_trajectories/` | **Build** trajectories — curated, session-by-session record of how the coding agent was used. |
| `docs/coding_agent_trajectories/raw/` | **Raw** coding-agent session logs (JSON Lines, 6 files, ~1.5 MB, 2 main sessions + 4 subagent runs) with credentials redacted. |

Raw traces were exported with [`scripts/export_agent_traces.py`](../scripts/export_agent_traces.py),
which redacts credential values and key-shaped strings before writing; the export was
verified to contain zero credential-shaped strings. See
[`raw/README.md`](coding_agent_trajectories/raw/README.md).

## Secrets

No API keys were committed. Keys live in `.env` locally (gitignored) and in
Streamlit Cloud secrets in production, and are never printed, logged, or stored in traces.
