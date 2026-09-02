"""Export raw coding-agent session traces into the repo with secrets redacted.

Usage:
    python scripts/export_agent_traces.py
    python scripts/export_agent_traces.py --check   # report leftover secret patterns only

Source: Cursor agent transcripts for this workspace (one .jsonl per session,
plus subagent sessions). Destination: docs/coding_agent_trajectories/raw/.

Redaction:
  1. Every value found in .env that looks like a credential is replaced literally.
  2. Known key formats (gsk_, xai-, sk-, Bearer <token>) are replaced by pattern.
  3. `SOME_API_KEY=value` / "SOME_API_KEY": "value" assignments are replaced.

The script never prints secret values.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEST = PROJECT_ROOT / "docs" / "coding_agent_trajectories" / "raw"
SOURCE = Path.home() / ".cursor" / "projects" / "c-Users-kamal-Desktop-Frontier-Hacks" / "agent-transcripts"

PLACEHOLDER = "[REDACTED_SECRET]"

KEY_NAME_RE = re.compile(
    r"((?:XAI|GROQ|OPENAI|SERPER|ANTHROPIC|LLM|CURSOR)?_?API_?KEY|SECRET|TOKEN|PASSWORD)"
    r"(\\?[\"']?\s*[=:]\s*\\?[\"']?)"
    r"([A-Za-z0-9_\-\.]{12,})",
    re.IGNORECASE,
)

PATTERN_RULES = [
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    re.compile(r"xai-[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{20,}"),
]


def _env_secrets() -> list[str]:
    """Credential-looking values from .env, longest first so substrings don't survive."""
    env_path = PROJECT_ROOT / ".env"
    values: list[str] = []
    if not env_path.exists():
        return values
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        if len(value) >= 12 and any(
            token in name.upper() for token in ("KEY", "SECRET", "TOKEN", "PASSWORD")
        ):
            values.append(value)
    return sorted(set(values), key=len, reverse=True)


def redact(text: str, literals: list[str]) -> str:
    for secret in literals:
        text = text.replace(secret, PLACEHOLDER)
    for rule in PATTERN_RULES:
        text = rule.sub(PLACEHOLDER, text)
    text = KEY_NAME_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{PLACEHOLDER}", text)
    return text


def _source_files() -> list[Path]:
    if not SOURCE.exists():
        return []
    return sorted(SOURCE.rglob("*.jsonl"))


def _dest_name(path: Path) -> str:
    is_subagent = path.parent.name == "subagents"
    session = path.parent.parent.name if is_subagent else path.parent.name
    prefix = "subagent" if is_subagent else "session"
    return f"{prefix}_{session[:8]}_{path.stem[:8]}.jsonl"


def export(check_only: bool = False) -> int:
    files = _source_files()
    if not files:
        print(f"No transcripts found under {SOURCE}")
        return 1

    literals = _env_secrets()
    print(f"Loaded {len(literals)} credential value(s) from .env for literal redaction")

    DEST.mkdir(parents=True, exist_ok=True)
    leftovers = 0

    for src in files:
        raw = src.read_text(encoding="utf-8", errors="replace")
        clean = redact(raw, literals)

        remaining = sum(len(rule.findall(clean)) for rule in PATTERN_RULES)
        leftovers += remaining

        out = DEST / _dest_name(src)
        if not check_only:
            out.write_text(clean, encoding="utf-8")

        lines = clean.count("\n") + 1
        redactions = clean.count(PLACEHOLDER)
        print(
            f"{'checked' if check_only else 'wrote'} {out.name}: "
            f"{lines} events, {len(clean)/1024:.0f} KB, {redactions} redaction(s), "
            f"{remaining} suspicious pattern(s) left"
        )

    if leftovers:
        print(f"\nWARNING: {leftovers} credential-shaped string(s) still present — review before publishing.")
        return 2

    print("\nNo credential-shaped strings remain.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Export redacted coding-agent traces")
    parser.add_argument("--check", action="store_true", help="Do not write files, only report")
    args = parser.parse_args()
    raise SystemExit(export(check_only=args.check))


if __name__ == "__main__":
    main()
