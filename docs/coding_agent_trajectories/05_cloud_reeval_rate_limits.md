# Session 5 — Same-provider re-evaluation attempt and rate-limit handling

**Tool:** Cursor Agent mode.
**Instruction (human):** The baseline ran on the cloud API, so run the **final agent pipeline** on
the same cloud API and see whether accuracy improves — a fair comparison.

## Trajectory

1. **Action:** Verify provider configuration without exposing secrets.
   **Tools:** shell (`python -c` printing only provider, model, base URL, key presence and length).
   **Result:** `.env` was set to `LLM_PROVIDER=local`; cloud model and key were configured.
   **Decision:** Override the provider for this run only, via environment variables, instead of
   editing committed configuration.

2. **Action:** Back up the existing local-run results before overwriting.
   **Result:** `raw_results_local_backup.json`, `evaluation_local_backup.json`,
   `summary_local_backup.json` in `results/final/`.
   **Decision (human):** Never destroy a measured run to make room for a new one.

3. **Action:** Dry-run the pipeline on the cloud provider.
   **Result:** 25 cases loaded, provider reported as cloud, setup OK.

4. **Action:** Single-case smoke test (`--case case_001`).
   **Result:** Success in ~89 s, ~12.2k tokens, ~$0.0024 — with two **429 rate-limit** retries
   (student_fit, decision_synthesizer) that waited and then succeeded.
   **Observation:** The retry path works; the cost is latency, not correctness.

5. **Action:** Start the full 25-case cloud run with a longer inter-case pause.
   **Result:** cases 1–6 succeeded (~70 s each), then the run was stopped by the human before completion.
   **Consequence:** No complete same-model final evaluation exists yet; the honest baseline-vs-final
   caveat in the docs therefore stands.

6. **Observed problem:** The free API tier returns intermittent `rate_limit_exceeded` (429s visible in
   the provider dashboard) because each report makes roughly 8 LLM calls.
   **Analysis given to the human:** retries preserve accuracy — the same prompt is re-sent and scored
   only on the successful response — so 429s inflate latency and slightly inflate cost, but do not
   degrade decision accuracy unless every retry fails and the case errors out.
   **Mitigations:** larger `CASE_PAUSE_SECONDS` (15–30) for batch evaluation, concurrency of 1–2,
   local model for bulk iteration, cloud API for demos and the fair evaluation run.

## Status

- Same-provider final re-evaluation: **started, not finished** — documented as open work rather
  than reported as a result.
- Rate-limit behavior: understood, mitigated, and disclosed.
