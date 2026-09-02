# Raw coding-agent traces

Raw session logs from the coding agent (Cursor Agent mode) used to build WorthApply,
exported with credentials redacted.

## Files

| File | Type | Events |
|------|------|--------|
| `session_0d1afdc8_0d1afdc8.jsonl` | Main session | 290 |
| `subagent_0d1afdc8_10c7375c.jsonl` | Subagent of that session | 17 |
| `session_e693226f_e693226f.jsonl` | Main session | 702 |
| `subagent_e693226f_2ed4abb7.jsonl` | Subagent | 11 |
| `subagent_e693226f_cef2686f.jsonl` | Subagent | 18 |
| `subagent_e693226f_ffcd61db.jsonl` | Subagent | 8 |

Format: JSON Lines, one event per line, with `role` (`user` / `assistant`) and message
content. Assistant events include tool invocations (file writes, edits, shell commands,
searches), so the instruction → action → tool → result → decision chain is visible.
Subagent files are separate delegated runs launched from the main session.

## How these were produced

```bash
python scripts/export_agent_traces.py          # export with redaction
python scripts/export_agent_traces.py --check  # verify without writing
```

The script is committed at [`scripts/export_agent_traces.py`](../../../scripts/export_agent_traces.py).

## Redaction

Applied before writing:

1. Credential-looking values read from the local `.env` are replaced literally.
2. Known key shapes (`gsk_…`, `xai-…`, `sk-…`, `Bearer …`) are replaced by pattern.
3. `*_API_KEY` / `SECRET` / `TOKEN` / `PASSWORD` assignments are replaced.

Replacement marker: `[REDACTED_SECRET]` — 23 occurrences across these files.
Verified afterwards: **zero** credential-shaped strings remain.

## Contents notice

These logs contain the author's own project files, job descriptions, and test resume
content used while developing and demoing the app. No third-party private data and no
API keys are included.

## Relationship to the other trajectories

- **These files** = how the project was *built* (coding-agent use).
- `../` (`01_…` to `05_…`) = curated, readable summaries of the same sessions.
- `traces/` at the repo root = the *product's* own six agents at runtime.

Disclosure of tools used: [`docs/ai_disclosure.md`](../../ai_disclosure.md).
