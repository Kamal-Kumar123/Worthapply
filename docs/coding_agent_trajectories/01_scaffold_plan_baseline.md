# Session 1 — Plan, provider abstraction, rubric, dataset, baseline

**Tool:** Cursor Agent mode.
**Instruction (human):** Build a hackathon-ready agentic project "WorthApply" from scratch,
but do **not** build the multi-agent system first. Inspect the repo, write a plan, create the
LLM provider abstraction, define the rubric and dataset, implement a single-prompt baseline,
then **stop** for failure analysis.

## Trajectory

1. **Action:** Inspect repository state.
   **Tools:** shell (`Get-ChildItem`, `git status`, `python --version`).
   **Result:** Empty directory, Python 3.11 available.
   **Decision:** Build from scratch; initialize git.

2. **Action:** Create foundational files.
   **Tools:** file writes.
   **Result:** `.gitignore` (secrets, venv, caches), `.env.example`, `requirements.txt`,
   directory skeleton (`worthapply/`, `baseline/`, `evaluation/`, `results/`, `traces/`, `docs/`, `tests/`, `data/`).
   **Decision (human):** Secrets never committed; `.env` gitignored from commit one.

3. **Action:** Write `PROJECT_PLAN.md`.
   **Result:** Problem, target user, bottleneck, objective, architecture *hypothesis*,
   phased plan, evaluation strategy, metric targets, risks, assumptions, LLM deployment strategy.
   **Decision (human):** Architecture is a hypothesis to be validated by measurement, not a fixed design.

4. **Action:** Implement provider abstraction.
   **Result:** `providers/base.py` (`LLMProvider` with generate / generate_structured, usage
   and cost tracking), `xai_provider.py`, `local_provider.py`, `factory.py` selecting via `LLM_PROVIDER`.
   **Decision (human):** No agent may call a vendor SDK directly; cloud must work without any local model.

5. **Action:** Define evaluation before building the system.
   **Result:** `evaluation/rubric.md` (primary = Opportunity Decision Accuracy with partial
   credit; secondaries incl. fit, evidence support, risk recall, latency, cost),
   `data/evaluation_cases.json` with 25 cases across categories A–J including adversarial (J).
   **Decision (human):** Ground truth is human-authored; the model does not create labels.

6. **Action:** Implement the baseline.
   **Result:** `baseline/prompt.txt`, `schemas.py`, `runner.py`, `evaluator.py` — one LLM call,
   one structured prompt, no tools, no agents.
   **Decision (human):** Baseline is mandatory; agents must beat or justify themselves against it.

7. **Action:** Write `docs/baseline_failure_analysis.md`.
   **Result:** Failure categories: required-vs-preferred confusion, unsupported fit claims,
   no company verification, overconfident recommendations, dimension collapse, missed risk signals,
   hallucinated company info.
   **Decision (human):** Only build agents that map to these observed/expected failures.

8. **Stop point:** Session ended at baseline + failure analysis, per instruction, before
   implementing specialized agents.

## Human corrections in this session

- Insisted on "NOT YET EVALUATED" wording anywhere a number had not actually been measured.
- Required the local model to remain strictly optional so cloud deployment is self-sufficient.
