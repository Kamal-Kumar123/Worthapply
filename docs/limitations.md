# WorthApply — Limitations and Responsible Use

## What WorthApply Is

WorthApply is a **decision-support tool** that helps students evaluate job
and internship opportunities more efficiently. It provides structured
analysis of student-job fit, opportunity indicators, and risk signals.

## What WorthApply Is NOT

- NOT a fraud detection system
- NOT a definitive authority on job legitimacy
- NOT an automated application submitter
- NOT a replacement for human judgment

## Known Limitations

### Verification Limitations

- Company verification relies on publicly available web information, which
  may be incomplete or outdated.
- Job posting freshness cannot always be determined from a description alone.
- The system cannot access private databases, government registries, or
  internal company systems.
- A posting that cannot be verified is NOT necessarily fraudulent — it may
  simply have limited public presence.

### Fit Assessment Limitations

- Skill matching is based on text analysis of the resume and job description.
- The system may miss implicit skills or overvalue keyword matches.
- Project relevance assessment is approximate.
- Years of experience are estimated from text, not verified.

### Risk Indicator Limitations

- Risk indicators are **signals, not proof** of problems.
- Missing information may indicate a small company, not a fraudulent one.
- Inconsistencies may result from normal editing/updating of postings.
- The system errs on the side of flagging — false positives are expected.

### Technical Limitations

- Web scraping may fail for JavaScript-rendered career pages.
- Rate limiting may affect response times during batch processing.
- LLM outputs are probabilistic — the same input may produce slightly
  different results.
- Cost tracking is approximate (based on token counts and published pricing).

## Responsible Use

1. **Treat recommendations as input, not decisions.** Always apply your own
   judgment before deciding whether to apply.
2. **Verify important information independently.** If the system flags
   concerns, investigate them yourself.
3. **Do not rely solely on fit scores.** They are estimates based on
   text matching, not deep assessment of your capabilities.
4. **Risk indicators are not accusations.** A "MEDIUM risk" posting may
   be perfectly legitimate.
5. **The system does not submit applications or contact anyone on your
   behalf.** You remain in full control.

## Data Privacy

- Student resumes are processed in memory and not stored permanently.
- No student data is sent to third parties beyond the LLM API.
- API keys are never logged or stored in traces.
- Evaluation uses synthetic data, not real student information.
