# WorthApply — Improvement Changelog

Short story of how the solution evolved. Same evaluation cases and rubric
for measured runs. Results are from actual files under `results/` — not invented.

---

## Improvement changelog (submission table)

| STAGE | WHAT YOU TRIED AND WHY | EVIDENCE | DECISION / LEARNING |
|-------|------------------------|----------|---------------------|
| **Baseline** | Started with a **single LLM + one structured prompt** (resume + JD → report). No agents, no web tools. Needed a fair starting point before adding complexity. | `results/baseline/`: primary **Opportunity Decision Accuracy = 88.2% exact / 94.1% weighted** on **17** scored cases; **8** cases failed (timeouts/errors). Avg ~30s/case, ~$0.0007/case (cloud). | Established the starting point. Strong on labels when it finished, but **cannot verify companies**, collapses fit vs opportunity quality, and coverage was incomplete. |
| **Iteration 1** | Added **Job Intelligence** + **Student Fit** agents to fix required-vs-preferred mix-ups and “skill match” claims with no resume evidence. | Structured `JobProfile` + evidence-backed MATCHED / PARTIAL / MISSING in the report UI. Same 25-case dataset wired for later comparison. | **Kept.** Extraction + grounded fit is the foundation for every later stage. |
| **Iteration 2** | Added **Company Verification** (search + page fetch) + **Opportunity Risk** after baseline could not check if a posting/company was real or stale. | Live runs: boards (e.g. Internshala) vs official careers could be distinguished; stuck on some real sites (e.g. direct Lanmea careers URL still showed weak verification) and early risk logic over-flagged normal job boards. | **Kept, then revised.** Softened “job board alone = HIGH risk”; stopped stamping one URL on website/careers/listing. Learning: verification tools help, but heuristics + weak search still fail on some official pages. |
| **Iteration 3** | Added **Evidence Verifier** + **Decision Synthesizer** so fit, confidence, risk, and evidence quality stay **separate** (needed for adversarial “great fit / shaky opportunity” cases). Parallel orchestration: Job Intel → (Company Verify ∥ Student Fit) → Risk → Evidence → Synthesis. | Report shows separate dimensions instead of one opaque score. Challenging category **J** cases exist in `data/evaluation_cases.json`. Traces under `traces/` show each agent step. | **Kept.** Dimension separation is the main agentic design win vs baseline collapse. |
| **Iteration 4 (stuck → fix)** | Product stuck points during demo builds: (1) LLM **rewrote/truncated Source URL**; (2) false skill gaps (e.g. Bedrock ≠ AWS); (3) JD years vs internship experience; (4) empty reports when local LLM was down. | Fix: always prefer user-provided `source_url` in Job Intelligence sanitize. Post-filters for false gaps + experience gate. Clearer provider/error behavior for local vs cloud. Batch mode with concurrency limit (semaphore = 2). | **Kept the fixes.** Learning: never trust the LLM for fields the user already gave; gate experience with rules, not vibes. |
| **Removal / revise** | Tried treating “always search + multi-fetch” as mandatory even when the user pastes a **direct company careers JD link**. | Extra search often did not improve UI links and sometimes hurt clarity vs the URL the student already provided. | **Revised (not fully removed).** Search stays important for **job boards**; direct official JD URLs should be trusted more. No whole agent removed yet — removal experiment still open for Evidence Verifier if cost ≫ value. |
| **Final** | Combined agents that earned their place + Streamlit product UI (single + batch), tracing, eval scripts, reproduction docs. | `results/final/`: **25/25** completed; primary accuracy **56% exact / 72% weighted**; fit accuracy **36%**, risk accuracy **48%**. Runtime long (~2h total for full set on the run recorded; cost $0 in that summary — local/dev-style run). | **Honest outcome:** final did **not** beat baseline on the primary label metric. Main contribution is **decision support** (separate fit vs confidence vs risk), verification tooling, trajectories, and a usable student UI — not a higher accuracy number. Next: re-eval final on the **same cloud model** as baseline and update this table. |

---

## Measured numbers (source of truth)

| Run | Cases scored | Exact accuracy | Weighted accuracy | Notes |
|-----|--------------|----------------|-------------------|-------|
| Baseline | 17 / 25 | 0.882 | 0.941 | Cloud provider; several timeouts |
| Final pipeline | 25 / 25 | 0.560 | 0.720 | Full coverage; primary metric lower |

Files: `results/baseline/evaluation.json`, `results/final/evaluation.json`.

---

## What we learned (short)

1. A strong single-prompt baseline can look good on priority labels and still fail the real student job (verify + separate risk from fit).
2. Agents should map to **observed** failures (extraction, evidence, verification), not agent-count.
3. Web verification is valuable but brittle without strong search / clean URL handling.
4. User-provided facts (Source URL) must never be overwritten by the model.
5. Do not claim “multi-agent won” on accuracy until final is re-measured on the same model/provider as baseline.

---

## Related docs

- Removal/revise write-up: [removal_experiment.md](removal_experiment.md)
- Comparison table: `results/comparison.md`
- Final report: `results/final/report.md`
- Why `results/iterations/` is empty: `results/iterations/README.md`
- Streamlit Cloud deploy: [deployment.md](deployment.md)

## Still open

- Optional: fill mid-stage JSON under `results/iterations/` (story already in this changelog).
- Optional: full A/B removal of Evidence Verifier on the same cloud model.
- Same-cloud-model re-eval of final vs baseline for a fair accuracy claim.
- ≤5 min solution video.
