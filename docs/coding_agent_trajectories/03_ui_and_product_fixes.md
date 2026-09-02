# Session 3 — Streamlit product UI and real-posting fixes

**Tool:** Cursor Agent mode.
**Instruction (human):** Build the product UI, then fix what breaks when I run real postings
(job boards and official career pages) through it.

## Trajectory

1. **Action:** Build the Streamlit app.
   **Result:** `worthapply/app/ui/streamlit_app.py` — resume upload (PDF/DOCX), job URL or pasted
   description, staged progress (parsing → fit → company → risk → evidence → recommendation),
   then a product-style report: recommendation on top, then Student Fit / Opportunity Confidence /
   Risk / Evidence Quality, then Job Summary, Fit Breakdown, Risk Indicators, Gaps, Next Steps.
   **Human decision:** Must look like a product, not raw model output.

2. **Observed problem (human, real run):** Risk showed HIGH mainly because the posting came from a
   job board and no careers page was found.
   **Action:** Soften the rule so board-sourced postings and a missing careers page are not, by
   themselves, escalations; genuine red flags still escalate.
   **Result:** Risk levels became defensible on real postings.

3. **Observed problem:** Company verification block was raw and confusing (`name_hits=` style
   evidence, the same URL repeated across all three checks).
   **Action:** Rewrite as a checklist — Found / Not found with links, humanized evidence, each
   distinct URL shown once, `getmereferred.com`-style hosts treated as job boards.

4. **Observed problem:** False gaps — "AWS missing" because the JD mentioned Amazon Bedrock, and
   "education in a different field" for an IT/CS student applying to software/AI roles.
   **Action:** Post-filters in the agents plus a display sanitizer.

5. **Observed problem:** Fit score stayed high for postings demanding multiple years of experience.
   **Action:** Experience gate in `agents/student_fit.py` — parse the JD's minimum years, compare
   against resume/internship evidence, hard-cap the fit score and add an explicit concern when the
   student is clearly below a 2+ year requirement.
   **Verification:** dedicated tests in `tests/test_experience_gate.py`.

6. **Observed problem:** Analyses were lost between runs; no way to keep a report.
   **Action:** History with run ID, tokens, and stage summary, plus `.md` / `.json` download of the
   full formatted report.

7. **Action:** Batch mode (only after single-job mode was stable).
   **Result:** Per-job text and/or URL, the same `AnalysisWorkflow.analyze()` path as single mode,
   a ranked table, and a full report view identical to single mode.
   **Concurrency:** `asyncio.Semaphore` with `BATCH_CONCURRENCY` default **2**.
   **Human decision:** Keep concurrency low so a live demo cannot trip provider rate limits.
   Behavior with 3 jobs and a limit of 2: two run, the third waits for a free slot; progress
   updates as each finishes.

8. **Action:** Deploy.
   **Result:** Live on Streamlit Community Cloud with cloud API keys in platform secrets; no local
   model dependency in production.

## Human corrections in this session

- Rejected the idea that a job-board source implies a suspicious opportunity.
- Rejected duplicate URL stamping in the verification checklist.
- Required batch mode to reuse the exact single-mode analysis path rather than a parallel code path.
