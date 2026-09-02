# Session 2 — Six agents, tools, orchestration, tracing, tests

**Tool:** Cursor Agent mode.
**Instruction (human):** Now add the agents that the baseline failure analysis justifies,
one capability at a time, with schemas, tools, tracing, and tests.

## Trajectory

1. **Action:** Job Intelligence agent.
   **Result:** `agents/job_intelligence.py` → structured `JobProfile` with **required vs preferred**
   skills separated, plus sanitization that drops invented companies, titles, and posting dates.
   **Human decision:** Keep. Foundation for every downstream agent.

2. **Action:** Student Fit agent.
   **Result:** `agents/student_fit.py` → per-skill MATCHED / PARTIALLY_MATCHED / MISSING with
   evidence quoted from the resume rather than keyword hits alone.
   **Human decision:** Keep. "Student has AWS" is unacceptable without a resume citation.

3. **Action:** Company Verification agent + web tools.
   **Tools built:** `tools/web_search.py`, `tools/webpage_fetcher.py` (timeouts, safe failure).
   **Result:** `agents/company_verification.py` → verification status, evidence, source URLs,
   confidence, unresolved questions; job-board hosts recognized separately from official sites.
   **Human decision:** Keep, but must return "could not independently verify" instead of guessing.

4. **Action:** Opportunity Risk agent.
   **Result:** `agents/opportunity_risk.py` → risk level plus individual signals with severity,
   evidence, and source.
   **Human correction:** Early behavior flagged *any* job-board posting as high risk. Softened to a
   rule where a board listing alone is a normal recruiting channel, not a red flag.

5. **Action:** Evidence Verifier agent.
   **Result:** `agents/evidence_verifier.py` → audits claims from other agents, marks unsupported
   ones, assigns confidence; `models/evidence.py` holds the claim/evidence model.
   **Human decision:** Keep. Final synthesis should lean on verified claims.

6. **Action:** Decision Synthesizer.
   **Result:** `agents/decision_synthesizer.py` → recommendation plus **separate** student fit,
   opportunity confidence, risk level, and evidence quality, with reasons and uncertainty.
   **Human decision:** Keep. This is the single most important design choice in the project —
   a 95% fit must never silently become "definitely apply" for an unverifiable posting.

7. **Action:** Orchestration and state.
   **Result:** `orchestration/workflow.py` + `state.py` — Job Intelligence first, then
   Company Verification and Student Fit, then Risk, then Evidence, then Synthesis, with
   structured state, error handling, and retry behavior.
   **Human decision:** Independent stages run concurrently; risk waits for verification.

8. **Action:** Tracing.
   **Result:** `worthapply/tracing.py` writes per-run, per-agent JSON to `traces/`
   (input, tool calls, output, retries, timings, tokens, cost) with no secrets.
   **Human decision:** Required for the hackathon's trajectory deliverable and for debugging regressions.

9. **Action:** Tests.
   **Tools:** shell (`pytest`).
   **Result:** ~60 unit/integration tests with mocked LLM responses — no paid API calls needed.
   **Verification:** `pytest tests/ -v` → all passing.

## Human corrections in this session

- Rejected stamping one URL simultaneously onto website / careers / listing checks.
- Required explicit states (UNVERIFIED, INSUFFICIENT_EVIDENCE) instead of confident filler.
- Refused adding any agent that did not map to a documented baseline failure.
