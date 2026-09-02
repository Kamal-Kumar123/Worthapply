# Session 4 — Measured results, changelog, submission docs

**Tool:** Cursor Agent mode.
**Instruction (human):** Audit the project against the hackathon requirements, then sync the
documentation to the **real** measured numbers. Do not change application code.

## Trajectory

1. **Action:** Requirement audit.
   **Tools:** file reads, greps, `pytest`, inspection of `results/` and `traces/`.
   **Result (findings):** code, agents, baseline, dataset (25 cases, A–J incl. adversarial),
   rubric, traces (41 runs), UI, and ~60 passing tests were all present; **documentation was stale** —
   README and several docs still said "NOT YET EVALUATED" although `results/` contained measured runs,
   `results/final/report.md` was missing, `results/iterations/` was empty, and `PROJECT_PLAN.md`
   still listed every phase as NOT STARTED.

2. **Observed problem (from the data):** baseline exact accuracy **88.2%** on 17 scored cases
   (8 timeouts) versus final pipeline **56%** on 25/25 — the agentic system looked *worse*.
   **Investigation:** `results/baseline/summary.json` shows a cloud provider and non-zero cost;
   `results/final/summary.json` shows **$0** cost, i.e. a local/dev-style run.
   **Human decision:** Do **not** spin this as an improvement. Publish both numbers and state plainly
   that it is not a same-model A/B, with model mismatch and baseline timeouts named as likely causes.

3. **Action:** Write the improvement changelog as a submission-shaped table.
   **Result:** `docs/improvement_changelog.md` — baseline → iterations → final with what was tried,
   the evidence, and keep / revise decisions, plus measured numbers and what was learned.

4. **Action:** Fill the reporting gaps (docs only).
   **Result:**
   - `results/final/report.md` — primary/secondary metrics, per-category breakdown, runtime, cost, fairness note
   - `results/comparison.md` — baseline vs agent side by side, including human time and cost per task
   - `results/iterations/README.md` — why mid-stage JSON is absent and where the iteration story lives
   - `docs/removal_experiment.md` — the "always web-search even for direct company career links"
     experiment and why it was revised
   - `docs/deployment.md` — Streamlit Community Cloud (not Render/Vercel), secrets, dev vs deploy
   - `docs/evaluation.md`, `docs/reproduction.md`, `docs/baseline.md`,
     `docs/baseline_failure_analysis.md`, `README.md`, `PROJECT_PLAN.md` — synced to measured values

5. **Action:** Record product metrics that the batch JSON does not capture.
   **Result:** human time 15–45 min manual versus ~50 s typical on deploy; dev cost $0 on the local
   model; ~$0.0031 per report and ~8 LLM calls on the deployed cloud API.

6. **Constraint respected:** No application code was modified in this session — documentation,
   reports, and plan status only.

## Human corrections in this session

- Blocked any claim that the multi-agent system beat the baseline on accuracy.
- Kept the pre-declared secondary metric *targets* unchanged; measured values were added
  separately rather than quietly lowered to match results.
