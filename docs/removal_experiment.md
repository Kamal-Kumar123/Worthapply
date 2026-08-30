# Removal / revise experiment

Judges often ask: what did you try and then remove?

## Experiment: “Always web-search, even on direct company JD URLs”

### What we tried

Company Verification always ran multiple search queries and followed up with page fetches, **even when** the student already pasted a direct official careers URL (e.g. `company.com/careers/...`).

### Why

Hypothesis: more public sources → higher verification confidence and better website/careers links in the report.

### What we observed

- On **job boards** (Internshala, etc.), search still helps find an official company surface.
- On **direct official JD links**, extra search often did **not** improve the UI links and sometimes confused Source / careers display versus the URL the user already gave.
- Product stuck point: Job Summary **Source** could show a truncated/LLM-rewritten URL instead of the user’s link (fixed by always preferring user `source_url` — see changelog Iteration 4).

### Decision

**Revised, not fully deleted as an agent.**

| Situation | Behavior intent |
|-----------|-----------------|
| Job-board URL | Keep search + fetch to corroborate company/careers |
| Direct non-board company JD URL | Trust / emphasize the provided URL; do not treat “must search” as equal priority |

No entire agent (e.g. Evidence Verifier) was removed from the frozen pipeline. A full A/B (pipeline with vs without Evidence Verifier on the same cloud model) was **not** run; open if judges want harder removal proof.

### Learning

More tools ≠ always better. Match tool use to the **source type**. Never overwrite user-provided URLs with model guesses.
