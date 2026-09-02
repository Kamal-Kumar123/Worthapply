# Coding-Agent Build Trajectories

How this project was built with a coding agent (Cursor Agent mode). Tool disclosure:
[../ai_disclosure.md](../ai_disclosure.md).

These are **build** trajectories (agent used to write the project). For the
**product's** runtime agent trajectories, see `traces/`.

Each file follows the same shape:

```
instruction → agent action → tools used → result → human decision → next step
```

| Session | File | Focus |
|---------|------|-------|
| 1 | [01_scaffold_plan_baseline.md](01_scaffold_plan_baseline.md) | Repo inspection, plan, provider abstraction, rubric, dataset, baseline |
| 2 | [02_agents_orchestration_tests.md](02_agents_orchestration_tests.md) | Six agents, tools, orchestration, tracing, tests |
| 3 | [03_ui_and_product_fixes.md](03_ui_and_product_fixes.md) | Streamlit product UI, verification display, false-gap and experience fixes, batch mode |
| 4 | [04_evaluation_and_docs.md](04_evaluation_and_docs.md) | Measured results, changelog, comparison, submission docs |
| 5 | [05_cloud_reeval_rate_limits.md](05_cloud_reeval_rate_limits.md) | Same-provider re-evaluation attempt, 429 handling |

Raw session logs (JSON Lines, credentials redacted) are in
[`raw/`](raw/README.md) — 2 main sessions and 4 subagent runs, exported via
`scripts/export_agent_traces.py`.

## Reading notes

- Every session was human-initiated with an explicit instruction; the agent did not run unattended.
- Shell commands (git, pytest, pipeline runs) executed with human approval.
- Where the agent's output was wrong or overreaching, the correction is recorded in the
  "human decision" line — those corrections are the most useful part of these logs.
