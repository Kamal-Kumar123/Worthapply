"""WorthApply — Opportunity Intelligence for Students.

Run with:  streamlit run worthapply/app/ui/streamlit_app.py
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from dotenv import load_dotenv

load_dotenv()

from worthapply.agents.company_verification import is_job_board_url
from worthapply.agents.student_fit import sanitize_gap_list, sanitize_fit_narratives
from worthapply.models.schemas import (
    OpportunityReport,
    Recommendation,
    Priority,
    RiskLevel,
    SkillMatchLevel,
    VerificationStatus,
)
from worthapply.orchestration.workflow import AnalysisWorkflow
from worthapply.providers import get_provider
from worthapply.tools.resume_parser import parse_resume
from worthapply.tools.webpage_fetcher import fetch_webpage

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_HISTORY_PATH = _PROJECT_ROOT / "results" / "ui_history" / "history.json"
_HISTORY_MAX = 50

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="WorthApply",
    page_icon="\U0001f50d",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def _apply_streamlit_secrets() -> None:
    """Copy Streamlit Cloud secrets into env so get_provider() keeps working."""
    try:
        secrets = st.secrets
    except Exception:
        return
    for key in (
        "LLM_PROVIDER",
        "XAI_API_KEY",
        "XAI_MODEL",
        "XAI_BASE_URL",
        "SERPER_API_KEY",
    ):
        val = secrets.get(key)
        if val and not os.getenv(key):
            os.environ[key] = str(val)


_apply_streamlit_secrets()

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
/* ---------- global resets ---------- */
section[data-testid="stSidebar"] { display: none; }
.block-container {
    padding-top: 4.5rem !important;
    padding-bottom: 2rem;
    max-width: 1100px;
}
/* Keep report action row clear of Streamlit top chrome */
.report-toolbar-spacer { height: 0.35rem; }
div[data-testid="stHorizontalBlock"]:has(button[kind="secondary"]),
div[data-testid="stHorizontalBlock"]:has(button[kind="primary"]) {
    margin-top: 0.25rem;
}

/* ---------- badges ---------- */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 650;
    letter-spacing: 0.04em;
    line-height: 1.7;
}
.badge-green  { background: #064e3b; color: #a7f3d0; }
.badge-yellow { background: #78350f; color: #fde68a; }
.badge-red    { background: #7f1d1d; color: #fecaca; }
.badge-blue   { background: #1e3a8a; color: #bfdbfe; }
.badge-gray   { background: #374151; color: #e5e7eb; }

/* ---------- report shell ---------- */
.report-kicker {
    text-align: center;
    font-size: 0.72rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: #9ca3af;
    margin: 0.2rem 0 0.35rem 0;
}
.report-title {
    text-align: center;
    font-size: 1.65rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #f9fafb;
    margin: 0;
}
.report-sub {
    text-align: center;
    color: #9ca3af;
    font-size: 0.95rem;
    margin: 0.35rem 0 1.1rem 0;
}

/* ---------- recommendation card ---------- */
.rec-card {
    border-radius: 14px;
    padding: 1.45rem 1.6rem 1.55rem 1.6rem;
    text-align: left;
    margin-bottom: 1rem;
    border: 1px solid transparent;
}
.rec-card .rec-kicker {
    font-size: 0.7rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    opacity: 0.8;
    margin: 0 0 0.35rem 0;
}
.rec-card h1 {
    margin: 0 0 0.55rem 0;
    font-size: 1.7rem;
    letter-spacing: -0.02em;
    line-height: 1.15;
}
.rec-card p  { margin: 0; font-size: 0.95rem; line-height: 1.55; opacity: 0.92; }
.rec-green  { background: linear-gradient(145deg, #064e3b 0%, #065f46 55%, #047857 100%); color: #ecfdf5; border-color: #059669; }
.rec-yellow { background: linear-gradient(145deg, #78350f 0%, #92400e 55%, #b45309 100%); color: #fffbeb; border-color: #d97706; }
.rec-red    { background: linear-gradient(145deg, #7f1d1d 0%, #991b1b 55%, #b91c1c 100%); color: #fef2f2; border-color: #ef4444; }

/* ---------- score card ---------- */
.score-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.75rem;
    margin: 0.2rem 0 0.9rem 0;
}
@media (max-width: 900px) {
    .score-grid { grid-template-columns: repeat(2, 1fr); }
}
.score-card {
    background: #111827;
    border: 1px solid #374151;
    border-radius: 12px;
    padding: 1rem 0.9rem;
    text-align: left;
    color: #f3f4f6;
}
.score-card .label { font-size: 0.75rem; color: #9ca3af; margin-bottom: 0.35rem; letter-spacing: 0.02em; }
.score-card .value { font-size: 1.45rem; font-weight: 700; margin: 0.1rem 0; color: #f9fafb !important; line-height: 1.2; }
.score-card .sub   { font-size: 0.75rem; color: #9ca3af; margin-top: 0.2rem; }

.meta-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem 1rem;
    align-items: center;
    padding: 0.7rem 0.9rem;
    margin: 0 0 1rem 0;
    background: #111827;
    border: 1px solid #374151;
    border-radius: 10px;
    font-size: 0.88rem;
    color: #e5e7eb;
}
.meta-strip .meta-label { color: #9ca3af; margin-right: 0.25rem; }

/* ---------- job facts ---------- */
.fact-grid {
    display: grid;
    grid-template-columns: 140px 1fr;
    gap: 0.45rem 0.85rem;
    margin: 0.4rem 0 0.8rem 0;
    font-size: 0.92rem;
}
.fact-label { color: #9ca3af; }
.fact-value { color: #f3f4f6; word-break: break-word; }

/* ---------- next steps / reasons ---------- */
.step-list { margin: 0.4rem 0 1rem 0; }
.step-row {
    display: flex;
    gap: 0.85rem;
    align-items: flex-start;
    padding: 0.8rem 0.9rem;
    margin-bottom: 0.55rem;
    background: #111827;
    border: 1px solid #374151;
    border-radius: 10px;
}
.step-num {
    flex: 0 0 auto;
    width: 1.7rem;
    height: 1.7rem;
    border-radius: 999px;
    background: #1f2937;
    border: 1px solid #4b5563;
    color: #e5e7eb;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.78rem;
    font-weight: 700;
    margin-top: 0.05rem;
}
.step-text { color: #e5e7eb; font-size: 0.92rem; line-height: 1.5; }
.reason-list { margin: 0.3rem 0 0.6rem 0; }
.reason-item {
    padding: 0.65rem 0.85rem;
    margin: 0 0 0.45rem 0;
    background: #111827;
    border-left: 3px solid #4b5563;
    border-radius: 0 8px 8px 0;
    color: #e5e7eb;
    font-size: 0.9rem;
    line-height: 1.45;
}

/* ---------- progress stage ---------- */
.stage-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.45rem 0;
    font-size: 0.92rem;
}
.stage-icon { font-size: 1.1rem; width: 1.4rem; text-align: center; }

/* ---------- section header ---------- */
.section-hdr {
    font-size: 1.02rem;
    font-weight: 650;
    color: #f3f4f6 !important;
    margin: 1.15rem 0 0.55rem 0;
    padding-bottom: 0.3rem;
    border-bottom: 1px solid #374151;
}

/* ---------- evidence table ---------- */
.ev-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
.ev-table th {
    text-align: left; padding: 0.55rem 0.65rem;
    background: #1f2937; color: #9ca3af;
    border-bottom: 1px solid #374151; font-weight: 600;
}
.ev-table td {
    padding: 0.55rem 0.65rem;
    border-bottom: 1px solid #1f2937;
    vertical-align: top;
    color: #e5e7eb;
}
.ev-table tr:nth-child(even) td { background: #0b1220; }

/* ---------- stage chips ---------- */
.stage-chip {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.55rem 0.75rem;
    margin: 0 0 0.4rem 0;
    background: #111827;
    border: 1px solid #374151;
    border-radius: 8px;
    font-size: 0.86rem;
    color: #e5e7eb;
}
.stage-chip .ok { color: #6ee7b7; }
.stage-chip .bad { color: #fca5a5; }
.stage-chip .ms { color: #9ca3af; white-space: nowrap; }

/* ---------- disclaimer ---------- */
.disclaimer {
    font-size: 0.78rem;
    color: #9ca3af;
    text-align: center;
    padding: 1.5rem 0 0.5rem 0;
    border-top: 1px solid #374151;
    margin-top: 2rem;
}

/* ---------- verification checklist ---------- */
.verify-list {
    margin: 1rem 0 1.4rem 0;
    border: 1px solid #374151;
    border-radius: 10px;
    overflow: hidden;
}
.verify-row {
    display: flex;
    gap: 0.9rem;
    align-items: flex-start;
    padding: 0.85rem 1rem;
    border-bottom: 1px solid #374151;
    background: #111827;
}
.verify-row:last-child { border-bottom: none; }
.verify-pill {
    flex: 0 0 auto;
    min-width: 5.2rem;
    text-align: center;
    font-size: 0.72rem;
    font-weight: 650;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 0.28rem 0.55rem;
    border-radius: 6px;
    margin-top: 0.1rem;
}
.verify-yes { background: #064e3b; color: #a7f3d0; }
.verify-no  { background: #3f1d1d; color: #fecaca; }
.verify-body { flex: 1; min-width: 0; }
.verify-label {
    font-size: 0.95rem;
    font-weight: 600;
    color: #f3f4f6;
    margin: 0 0 0.2rem 0;
}
.verify-note {
    font-size: 0.82rem;
    color: #9ca3af;
    margin: 0;
    line-height: 1.45;
}
.verify-link {
    font-size: 0.82rem;
    color: #93c5fd !important;
    word-break: break-all;
    text-decoration: none;
}
.verify-link:hover { text-decoration: underline; }
.evidence-item {
    font-size: 0.9rem;
    color: #e5e7eb;
    line-height: 1.5;
    margin: 0 0 0.55rem 0;
    padding-left: 0.85rem;
    border-left: 2px solid #4b5563;
}
.empty-note {
    color: #9ca3af;
    font-size: 0.9rem;
    padding: 0.6rem 0.2rem;
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
_DEFAULTS: dict = {
    "report": None,
    "pipeline_state": None,
    "analysis_summary": None,
    "analysis_running": False,
    "stage_status": {},
    "error_msg": "",
    "history_view_id": None,
    "batch_results": None,
    "from_batch": False,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ---------------------------------------------------------------------------
# Analysis history (persisted on disk)
# ---------------------------------------------------------------------------

def _load_history() -> list[dict]:
    if not _HISTORY_PATH.exists():
        return []
    try:
        with open(_HISTORY_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_history(entries: list[dict]) -> None:
    _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(entries[:_HISTORY_MAX], f, indent=2, default=str)


def _append_history(
    report: OpportunityReport,
    pipeline_summary: dict | None = None,
) -> str:
    entry_id = str(uuid.uuid4())[:8]
    entry = {
        "id": entry_id,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "title": report.job.title or "Untitled role",
        "company": report.job.company or "Unknown company",
        "recommendation": report.recommendation.value,
        "priority": report.priority.value,
        "fit_score": report.student_fit.fit_score,
        "risk_level": report.risk_assessment.risk_level.value,
        "report": report.model_dump(mode="json"),
        "pipeline_summary": pipeline_summary or {},
    }
    history = _load_history()
    history.insert(0, entry)
    _save_history(history)
    return entry_id


def _get_history_entry(entry_id: str) -> dict | None:
    for item in _load_history():
        if item.get("id") == entry_id:
            return item
    return None


def _delete_history_entry(entry_id: str) -> None:
    _save_history([h for h in _load_history() if h.get("id") != entry_id])


def _clear_history() -> None:
    _save_history([])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STAGE_LABELS: dict[str, str] = {
    "job_intelligence": "Parsing opportunity\u2026",
    "student_fit": "Evaluating fit\u2026",
    "company_verification": "Checking company\u2026",
    "opportunity_risk": "Checking risk indicators\u2026",
    "evidence_verification": "Verifying evidence\u2026",
    "decision_synthesis": "Generating recommendation\u2026",
}

_STAGE_ORDER = list(_STAGE_LABELS.keys())


def _badge(text: str, color: str = "gray") -> str:
    return f'<span class="badge badge-{color}">{text}</span>'


def _short_url(url: str, max_len: int = 64) -> str:
    u = (url or "").strip()
    if len(u) <= max_len:
        return u
    return u[: max_len - 1] + "…"


def _link_html(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    safe = u.replace('"', "&quot;")
    return (
        f'<a class="verify-link" href="{safe}" target="_blank" rel="noopener noreferrer">'
        f"{_short_url(u)}</a>"
    )


def _humanize_evidence(text: str) -> str | None:
    """Turn raw debug evidence into readable copy; drop useless lines."""
    raw = (text or "").strip()
    if not raw:
        return None
    low = raw.lower()
    if "name_hits=" in low or "title_hits=" in low:
        name_m = re.search(r"name_hits\s*=\s*(\d+)", raw, re.I)
        title_m = re.search(r"title_hits\s*=\s*(\d+)", raw, re.I)
        bits = []
        if name_m:
            bits.append(f"company name appeared in about {name_m.group(1)} search/page mentions")
        if title_m:
            bits.append(f"job title matched in about {title_m.group(1)} places")
        if bits:
            return "Cross-check: " + "; ".join(bits) + "."
        return None
    if raw.lower().startswith("source is a known job board"):
        return (
            "Posted on a known job board — a common recruiting channel. "
            "That does not by itself confirm the role on the company's own careers page."
        )
    return raw


def _normalize_url_key(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    try:
        from urllib.parse import urlparse, urlunparse

        p = urlparse(u)
        host = (p.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        path = (p.path or "").rstrip("/")
        return urlunparse(("", host, path, "", "", "")).lower()
    except Exception:
        return u.rstrip("/").lower()


def _verify_row_html(
    label: str,
    found: bool,
    url: str = "",
    note_found: str = "",
    note_missing: str = "",
) -> str:
    pill = (
        '<span class="verify-pill verify-yes">Found</span>'
        if found
        else '<span class="verify-pill verify-no">Not found</span>'
    )
    link = _link_html(url) if found and url else ""
    note = note_found if found else note_missing
    if link and note:
        detail = f"{link}<p class='verify-note'>{note}</p>"
    elif link:
        detail = link
    else:
        detail = f"<p class='verify-note'>{note}</p>" if note else ""
    return (
        f'<div class="verify-row">{pill}'
        f'<div class="verify-body"><div class="verify-label">{label}</div>'
        f"{detail}</div></div>"
    )


def _verification_checks_html(checks: list[dict]) -> str:
    """Render Found/Not-found rows; show each distinct URL only once (dynamic)."""
    seen_keys: set[str] = set()
    rows: list[str] = []
    for c in checks:
        url = (c.get("url") or "").strip()
        found = bool(c.get("found"))
        key = _normalize_url_key(url) if url else ""
        show_url = ""
        note_found = c.get("note_found") or ""
        if found and url:
            if key and key in seen_keys:
                show_url = ""
                if "Same as" not in note_found:
                    note_found = (note_found + " Same link as above.").strip()
            else:
                show_url = url
                if key:
                    seen_keys.add(key)
        rows.append(
            _verify_row_html(
                c.get("label") or "Check",
                found,
                show_url,
                note_found=note_found,
                note_missing=c.get("note_missing") or "",
            )
        )
    return f'<div class="verify-list">{"".join(rows)}</div>'


def _unique_check_links(checks: list[dict]) -> list[tuple[str, str]]:
    """Return [(label, url), ...] with duplicate URLs collapsed to first label."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for c in checks:
        url = (c.get("url") or "").strip()
        if not c.get("found") or not url:
            continue
        key = _normalize_url_key(url)
        if key in seen:
            continue
        seen.add(key)
        out.append((c.get("label") or "Link", url))
    return out


def _match_color(level: SkillMatchLevel) -> str:
    return {"MATCHED": "green", "PARTIALLY_MATCHED": "yellow", "MISSING": "red"}.get(
        level.value, "gray"
    )


def _match_label(level: SkillMatchLevel) -> str:
    """User-facing High / Medium / Low instead of MATCHED / MISSING."""
    return {
        SkillMatchLevel.MATCHED: "HIGH",
        SkillMatchLevel.PARTIALLY_MATCHED: "MEDIUM",
        SkillMatchLevel.MISSING: "LOW",
    }.get(level, level.value)


def _risk_color(level: RiskLevel | str) -> str:
    val = level.value if isinstance(level, RiskLevel) else str(level).upper()
    return {"LOW": "green", "MEDIUM": "yellow", "HIGH": "red"}.get(val, "gray")


def _rec_css(rec: Recommendation) -> str:
    return {
        Recommendation.APPLY: "rec-green",
        Recommendation.APPLY_IF_TIME: "rec-yellow",
        Recommendation.LOW_PRIORITY: "rec-red",
    }.get(rec, "rec-yellow")


def _rec_label(rec: Recommendation) -> str:
    return {
        Recommendation.APPLY: "APPLY",
        Recommendation.APPLY_IF_TIME: "APPLY IF TIME",
        Recommendation.LOW_PRIORITY: "LOW PRIORITY",
    }.get(rec, rec.value)


def _priority_color(p: Priority) -> str:
    return {"HIGH": "green", "MEDIUM": "yellow", "LOW": "red"}.get(p.value, "gray")


def _verification_color(vs: VerificationStatus) -> str:
    return {
        "VERIFIED": "green",
        "PARTIALLY_VERIFIED": "yellow",
        "UNVERIFIED": "red",
        "CONFLICTING": "red",
        "INSUFFICIENT_EVIDENCE": "gray",
    }.get(vs.value, "gray")


def _pct_color(val: float) -> str:
    if val >= 70:
        return "green"
    if val >= 40:
        return "yellow"
    return "red"


def _score_card(label: str, value: str, sub: str = "", color: str = "") -> str:
    style = ""
    if color == "green":
        style = "border-left: 4px solid #34d399;"
    elif color == "yellow":
        style = "border-left: 4px solid #fbbf24;"
    elif color == "red":
        style = "border-left: 4px solid #f87171;"
    elif color == "blue":
        style = "border-left: 4px solid #60a5fa;"
    return (
        f'<div class="score-card" style="{style}">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}</div>'
        f'<div class="sub">{sub}</div>'
        f"</div>"
    )


def _prepare_report_for_display(report: OpportunityReport) -> OpportunityReport:
    """Display-only cleanup of false gaps; does not change pipeline results on disk."""
    fit = report.student_fit
    job = report.job
    student_hint = " ".join(
        [
            fit.summary or "",
            fit.education_match or "",
            " ".join(fit.project_evidence or []),
            "information technology"  # soft bias only if education_match already says IT
            if "information technology" in (fit.education_match or "").lower()
            or "information technology" in (fit.summary or "").lower()
            else "",
        ]
    )
    # Prefer explicit IT markers from narrative for history sanitization
    if re.search(r"\binformation technology\b|\b\bit\b", student_hint, re.I):
        student_hint = student_hint + " information technology"
    sanitize_fit_narratives(fit, student_hint, job, job_text="")
    report.missing_requirements = sanitize_gap_list(
        report.missing_requirements, student_text=student_hint, job=job
    )
    report.uncertainty = sanitize_gap_list(
        report.uncertainty, student_text=student_hint, job=job
    )
    report.next_steps = sanitize_gap_list(
        report.next_steps, student_text=student_hint, job=job
    )
    report.reasons = sanitize_gap_list(
        report.reasons, student_text=student_hint, job=job
    )
    # Dedupe uncertainty vs concerns
    concern_keys = {c.strip().lower() for c in (fit.concerns or []) if c.strip()}
    report.uncertainty = [
        u for u in report.uncertainty if u.strip().lower() not in concern_keys
    ]
    if report.summary:
        low = report.summary.lower()
        if ("aws" in low or "educational background" in low) and not any(
            s for s in (job.required_skills or []) if "aws" in s.lower()
        ):
            cleaned = re.sub(
                r"[^.!?]*\b(AWS|educational background)[^.!?]*[.!?]?",
                "",
                report.summary,
                flags=re.I,
            ).strip()
            cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,;")
            report.summary = cleaned or (
                "Strong skill fit with partial company verification — review details below."
            )
    report.student_fit = fit
    return report


def _report_filename_stem(report: OpportunityReport) -> str:
    company = re.sub(r"[^\w\-]+", "_", (report.job.company or "company").strip())[:40]
    title = re.sub(r"[^\w\-]+", "_", (report.job.title or "role").strip())[:40]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"WorthApply_{company}_{title}_{stamp}".strip("_")


def _md_link(url: str, label: str | None = None) -> str:
    u = (url or "").strip()
    if not u:
        return "—"
    return f"[{label or u}]({u})"


def _format_report_markdown(
    report: OpportunityReport,
    analysis: dict | None = None,
) -> str:
    """Human-readable full report for download (all sections + metrics)."""
    job = report.job
    fit = report.student_fit
    risk = report.risk_assessment
    cv = report.company_verification
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = [
        "# WorthApply Report",
        "",
        f"**Generated:** {generated}",
        "",
        "## Table of contents",
        "1. [Final scores](#final-scores)",
        "2. [Recommendation](#recommendation)",
        "3. [Job summary](#job-summary)",
        "4. [Fit breakdown](#fit-breakdown)",
        "5. [Risk indicators](#risk-indicators)",
        "6. [Company verification](#company-verification)",
        "7. [Gaps & uncertainty](#gaps--uncertainty)",
        "8. [Next steps](#next-steps)",
        "9. [Analysis details](#analysis-details)",
        "",
        "## Final scores",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Recommendation | {_rec_label(report.recommendation)} |",
        f"| Priority | {report.priority.value} |",
        f"| Student fit | {fit.fit_score:.0f}% |",
        f"| Opportunity confidence | {report.opportunity_confidence:.0f}% |",
        f"| Risk level | {risk.risk_level.value} |",
        f"| Evidence quality | {report.evidence_quality or 'N/A'} |",
        f"| Company verification | {cv.verification_status.value.replace('_', ' ')} |",
        "",
        "## Recommendation",
        "",
        f"**Decision:** {_rec_label(report.recommendation)}",
        "",
        "### Summary",
        report.summary or "—",
        "",
        "## Job summary",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Position | {job.title or '—'} |",
        f"| Company | {job.company or '—'} |",
        f"| Location | {job.location or '—'} |",
        f"| Employment type | {job.employment_type or '—'} |",
        f"| Experience required | {job.experience_requirement or '—'} |",
        f"| Posting date | {job.posting_date or 'Not listed'} |",
        f"| Source / posting link | {_md_link(job.source_url)} |",
        f"| Application URL | {_md_link(job.application_url)} |",
        "",
    ]
    if job.education_requirements:
        lines.append("### Education requirements (from posting)")
        lines.extend(f"- {e}" for e in job.education_requirements)
        lines.append("")
    if job.required_skills:
        lines.append("### Required skills (from posting)")
        lines.extend(f"- {s}" for s in job.required_skills)
        lines.append("")
    if job.preferred_skills:
        lines.append("### Preferred skills (from posting)")
        lines.extend(f"- {s}" for s in job.preferred_skills)
        lines.append("")
    if job.responsibilities:
        lines.append("### Responsibilities")
        lines.extend(f"- {r}" for r in job.responsibilities)
        lines.append("")

    lines += ["## Fit breakdown", ""]
    lines += [
        f"**Fit score:** {fit.fit_score:.0f} / 100",
        "",
    ]
    if fit.summary:
        lines += [fit.summary, ""]
    if fit.required_skills or fit.preferred_skills:
        lines.append("### Skills match table")
        lines.append("")
        lines.append("| Skill | Category | Match | Evidence |")
        lines.append("| --- | --- | --- | --- |")
        for cat, sm in (
            [("Required", s) for s in fit.required_skills]
            + [("Preferred", s) for s in fit.preferred_skills]
        ):
            ev = (sm.evidence or "—").replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| {sm.skill} | {cat} | {_match_label(sm.match_level)} | {ev} |"
            )
        lines.append("")
        lines.append(
            "_Match: **HIGH** = direct evidence · **MEDIUM** = related/transferable · "
            "**LOW** = little/no evidence._"
        )
        lines.append("")
    if fit.experience_match:
        lines.append("### Experience")
        lines.append(fit.experience_match)
        lines.append("")
    if fit.project_evidence:
        lines.append("### Relevant projects")
        lines.extend(f"- {p}" for p in fit.project_evidence)
        lines.append("")
    if fit.education_match:
        lines.append("### Education (secondary)")
        lines.append(fit.education_match)
        lines.append("")
        lines.append(
            "_Education is informational — fit prioritizes skills, projects, experience._"
        )
        lines.append("")

    lines += [
        "## Risk indicators",
        "",
        f"**Overall risk:** {risk.risk_level.value}",
        "",
    ]
    if risk.summary:
        lines += [risk.summary, ""]
    if risk.signals:
        lines.append("| Severity | Signal | Evidence |")
        lines.append("| --- | --- | --- |")
        for sig in risk.signals:
            ev = (sig.evidence or "—").replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {sig.severity.value} | {sig.signal} | {ev} |")
        lines.append("")
    else:
        lines += ["No risk indicators detected.", ""]

    lines += [
        "## Company verification",
        "",
        f"**Status:** {cv.verification_status.value.replace('_', ' ')}",
        f"**Confidence:** {cv.confidence * 100:.0f}%",
        "",
        "| Check | Result |",
        "| --- | --- |",
        f"| Company website | {'Found' if cv.website_found else 'Not found'} |",
        f"| Careers / jobs page | {'Found' if cv.careers_page_found else 'Not found'} |",
        f"| Role on company site | {'Found' if cv.job_listing_found else 'Not found'} |",
        "",
    ]
    # Dynamic unique links only (same URL once)
    link_checks = [
        {"label": "Company website", "found": cv.website_found, "url": getattr(cv, "website_url", "") or ""},
        {"label": "Careers / jobs page", "found": cv.careers_page_found, "url": getattr(cv, "careers_page_url", "") or ""},
        {"label": "Role on company site", "found": cv.job_listing_found, "url": getattr(cv, "job_listing_url", "") or ""},
    ]
    unique_links = _unique_check_links(link_checks)
    if unique_links:
        lines.append("### Links")
        for label, url in unique_links:
            lines.append(f"- **{label}:** {_md_link(url)}")
        lines.append("")
    if cv.summary:
        lines += ["### Verification summary", cv.summary, ""]
    if cv.evidence:
        lines.append("### Evidence")
        lines.extend(f"- {e}" for e in cv.evidence)
        lines.append("")
    if cv.source_urls:
        lines.append("### All source / reference URLs")
        lines.extend(f"- {_md_link(u)}" for u in cv.source_urls)
        lines.append("")
    if cv.unresolved_questions:
        lines.append("### Unresolved questions")
        lines.extend(f"- {q}" for q in cv.unresolved_questions)
        lines.append("")

    lines.append("## Gaps & uncertainty")
    lines.append("")
    if report.missing_requirements:
        lines.append("### Missing requirements")
        lines.extend(f"- {m}" for m in report.missing_requirements)
        lines.append("")
    else:
        lines += ["No critical gaps identified.", ""]
    if report.uncertainty:
        lines.append("### Uncertainty")
        lines.extend(f"- {u}" for u in report.uncertainty)
        lines.append("")
    if fit.concerns:
        lines.append("### Concerns")
        lines.extend(f"- {c}" for c in fit.concerns)
        lines.append("")

    lines.append("## Next steps")
    lines.append("")
    if report.next_steps:
        for i, step in enumerate(report.next_steps, 1):
            lines.append(f"{i}. {step}")
        lines.append("")
    else:
        lines += ["No specific next steps generated.", ""]
    if report.reasons:
        lines.append("### Key reasons")
        lines.extend(f"- {r}" for r in report.reasons)
        lines.append("")

    lines += ["## Analysis details", ""]
    if analysis:
        lines += [
            "| Metric | Value |",
            "| --- | --- |",
            f"| Run ID | {analysis.get('run_id', '—')} |",
            f"| Elapsed | {float(analysis.get('total_elapsed_ms') or 0):.0f} ms |",
            f"| Tokens | {int(analysis.get('total_tokens') or 0):,} |",
            f"| Est. cost | ${float(analysis.get('total_cost_usd') or 0):.4f} |",
            "",
        ]
        stages = analysis.get("stages") or {}
        if stages:
            lines.append("### Stage breakdown")
            lines.append("")
            lines.append("| Stage | Status | Elapsed |")
            lines.append("| --- | --- | --- |")
            for name, info in stages.items():
                label = _STAGE_LABELS.get(name, name).rstrip("\u2026")
                status = (info or {}).get("status", "—")
                elapsed = (info or {}).get("elapsed_ms")
                elapsed_s = f"{float(elapsed):.0f} ms" if elapsed else "—"
                err = (info or {}).get("error")
                if err:
                    status = f"{status} ({err})"
                lines.append(f"| {label} | {status} | {elapsed_s} |")
            lines.append("")
    else:
        lines += [
            "_Pipeline metrics were not saved with this report._",
            "",
        ]

    lines += [
        "---",
        "",
        "_WorthApply provides decision support only. Risk indicators are signals, "
        "not proof. Always verify independently._",
        "",
    ]
    return "\n".join(lines)


def _format_report_json(
    report: OpportunityReport,
    analysis: dict | None = None,
) -> str:
    payload = {
        "report": report.model_dump(mode="json"),
        "analysis_details": analysis or {},
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _resolve_analysis_summary(state=None) -> dict | None:
    if state is not None and hasattr(state, "to_summary"):
        return state.to_summary()
    summary = st.session_state.get("analysis_summary")
    return summary if isinstance(summary, dict) and summary else None


def _render_analysis_details(summary: dict | None) -> None:
    with st.expander("Analysis Details", expanded=False):
        if not summary:
            st.caption(
                "Pipeline metrics were not saved with this older history entry. "
                "New analyses will keep run ID, tokens, cost, and stage timings."
            )
            return
        det_c1, det_c2, det_c3, det_c4 = st.columns(4)
        det_c1.metric("Run ID", summary.get("run_id") or "—")
        det_c2.metric(
            "Elapsed", f'{float(summary.get("total_elapsed_ms") or 0):.0f} ms'
        )
        det_c3.metric("Tokens", f'{int(summary.get("total_tokens") or 0):,}')
        det_c4.metric(
            "Est. Cost", f'${float(summary.get("total_cost_usd") or 0):.4f}'
        )

        stages = summary.get("stages") or {}
        if stages:
            st.markdown(
                '<div class="section-hdr">Stage Breakdown</div>',
                unsafe_allow_html=True,
            )
            chips = []
            for name, info in stages.items():
                info = info or {}
                ok = info.get("status") == "COMPLETED"
                cls = "ok" if ok else "bad"
                elapsed = info.get("elapsed_ms")
                elapsed_s = f"{float(elapsed):.0f} ms" if elapsed else "—"
                err = f' — {info["error"]}' if info.get("error") else ""
                label = _STAGE_LABELS.get(name, name).rstrip("\u2026")
                chips.append(
                    f'<div class="stage-chip">'
                    f'<span class="{cls}">{label} · {info.get("status", "—")}{err}</span>'
                    f'<span class="ms">{elapsed_s}</span></div>'
                )
            st.markdown("".join(chips), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Progress callback — updates session state (called from async workflow)
# ---------------------------------------------------------------------------

def _progress_callback(stage: str, status: str) -> None:
    st.session_state["stage_status"][stage] = status


def _paint_stage(
    container,
    key: str,
    status: str,
) -> None:
    label = _STAGE_LABELS[key]
    if status == "RUNNING":
        icon, color, suffix = "\u23F3", "#2563eb", " (running\u2026)"
    elif status == "COMPLETED":
        icon, color, suffix = "\u2705", "#065f46", " — done"
        label = label.rstrip("\u2026")
    elif status == "FAILED":
        icon, color, suffix = "\u274C", "#ef4444", " — failed"
        label = label.rstrip("\u2026")
    else:
        icon, color, suffix = "\u23F3", "#9ca3af", ""
    container.markdown(
        f'<div class="stage-row">'
        f'<span class="stage-icon">{icon}</span>'
        f'<span style="color:{color}; font-weight:500;">'
        f"{label}{suffix}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Async runner
# ---------------------------------------------------------------------------

def _run_analysis(
    resume_text: str,
    job_text: str,
    job_url: str,
    *,
    stage_containers: dict | None = None,
    progress_bar=None,
    status_box=None,
) -> None:
    """Synchronous wrapper around the async pipeline with live UI updates."""

    def on_progress(stage: str, status: str) -> None:
        st.session_state["stage_status"][stage] = status
        print(f"[WorthApply] {stage}: {status}", flush=True)
        if stage_containers and stage in stage_containers:
            _paint_stage(stage_containers[stage], stage, status)
        if progress_bar is not None:
            done = sum(
                1
                for k in _STAGE_ORDER
                if st.session_state["stage_status"].get(k) in ("COMPLETED", "FAILED")
            )
            running = 1 if status == "RUNNING" else 0
            progress_bar.progress(
                min(99, int(100 * (done + 0.35 * running) / len(_STAGE_ORDER)))
            )
        if status_box is not None:
            if status == "RUNNING":
                status_box.info(
                    f"Working: **{_STAGE_LABELS.get(stage, stage)}**  \n"
                    "Local Ollama on CPU — each step can take 30–90s. Please wait."
                )
            elif status == "FAILED":
                status_box.warning(f"Stage failed: {_STAGE_LABELS.get(stage, stage)}")

    async def _inner():
        provider = get_provider()
        print(
            f"[WorthApply] provider={provider.provider_name} model={provider.model}",
            flush=True,
        )
        workflow = AnalysisWorkflow(
            provider=provider, progress_callback=on_progress
        )
        report, state = await workflow.analyze(
            student_text=resume_text,
            job_text=job_text,
            job_url=job_url,
        )
        return report, state

    report, state = asyncio.run(_inner())
    st.session_state["report"] = report
    st.session_state["pipeline_state"] = state
    summary = state.to_summary() if state else {}
    st.session_state["analysis_summary"] = summary
    try:
        hid = _append_history(report, pipeline_summary=summary)
        st.session_state["history_view_id"] = hid
        print(f"[WorthApply] Saved to history id={hid}", flush=True)
    except Exception as exc:
        print(f"[WorthApply] History save failed: {exc}", flush=True)


# ───────────────────────────────────────────────────────────────────────
#  HOME PAGE
# ───────────────────────────────────────────────────────────────────────

def _render_home() -> None:
    st.markdown(
        "<h1 style='text-align:center; margin-bottom:0;'>"
        "\U0001f50d WorthApply"
        "</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center; color:#6b7280; margin-top:0.2rem; "
        "font-size:1.05rem; letter-spacing:0.04em;'>"
        "Investigate. Verify. Match. Prioritize.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("")

    st.markdown(
        "WorthApply is an **opportunity intelligence system** built for students. "
        "Upload your resume and paste a job listing — WorthApply will extract "
        "requirements, verify the company, assess your fit, flag risk indicators, "
        "and deliver an evidence-backed recommendation so you spend time only on "
        "opportunities that matter."
    )

    st.divider()

    # --- Resume upload (shared) ---
    st.markdown("##### Your Resume")
    uploaded = st.file_uploader(
        "Upload your resume (PDF, DOCX, or TXT)",
        type=["pdf", "docx", "doc", "txt"],
        key="resume_file",
    )

    st.markdown("")

    single_tab, batch_tab = st.tabs(["\U0001f4cb Single Opportunity", "\U0001f4ca Batch Mode"])

    # ── Single Opportunity Tab ──
    with single_tab:
        st.markdown("##### Job Opportunity")
        input_mode = st.radio(
            "How would you like to provide the job posting?",
            ["Paste the job description", "Enter a URL"],
            horizontal=True,
            label_visibility="collapsed",
        )

        job_url = ""
        job_text = ""

        if input_mode == "Enter a URL":
            job_url = st.text_input(
                "Job posting URL",
                placeholder="https://boards.greenhouse.io/company/jobs/12345",
            )
        else:
            job_text = st.text_area(
                "Paste the full job description",
                height=220,
                placeholder="Paste the complete job posting here including title, company, requirements, responsibilities\u2026",
            )

        st.markdown("")

        col_l, col_c, col_r = st.columns([1, 2, 1])
        with col_c:
            analyze = st.button(
                "\U0001f50d  Analyze Opportunity",
                use_container_width=True,
                type="primary",
            )

        if analyze:
            if not uploaded:
                st.error("Please upload your resume before analyzing.")
                return
            if not job_text.strip() and not job_url.strip():
                st.error("Provide a job description or URL.")
                return

            resume_text = parse_resume(
                io.BytesIO(uploaded.read()), filename=uploaded.name
            )
            if not resume_text.strip():
                st.error(
                    "Could not extract text from the uploaded file. "
                    "Try a different format."
                )
                return

            # If only a URL was given, fetch real posting text first
            if job_url.strip() and not job_text.strip():
                with st.spinner("Fetching job posting from URL…"):
                    fetched = asyncio.run(fetch_webpage(job_url.strip()))
                if not fetched.ok or not fetched.content.strip():
                    st.error(
                        "Could not load job text from that URL "
                        f"({fetched.error or 'empty page'}). "
                        "Paste the job description instead — many sites block scrapers."
                    )
                    return
                job_text = fetched.content
                if fetched.title:
                    job_text = f"Page title: {fetched.title}\n\n{job_text}"
                st.success(f"Fetched {len(fetched.content):,} characters from URL.")

            st.session_state["stage_status"] = {}
            st.session_state["error_msg"] = ""
            st.session_state["report"] = None
            st.session_state["pipeline_state"] = None
            st.session_state["batch_results"] = None

            _render_progress(resume_text, job_text, job_url)
            return

    # ── Batch Mode Tab ──
    with batch_tab:
        st.markdown(
            "Compare multiple opportunities with the **same analysis pipeline** as single mode. "
            "Jobs run **in parallel**. Each job accepts a pasted description and/or a URL."
        )

        num_jobs = st.number_input(
            "Number of opportunities to compare",
            min_value=2, max_value=10, value=3, step=1,
        )

        batch_jobs: list[dict] = []
        for i in range(int(num_jobs)):
            with st.expander(f"Job {i+1}", expanded=(i < 2)):
                jurl = st.text_input(
                    f"Job URL #{i+1} (optional)",
                    key=f"batch_job_url_{i}",
                    placeholder="https://…",
                )
                jtext = st.text_area(
                    f"Job description #{i+1} (optional if URL is set)",
                    height=140,
                    key=f"batch_job_text_{i}",
                    placeholder=f"Paste job description {i+1}, or leave blank and use URL…",
                )
                if jtext.strip() or jurl.strip():
                    batch_jobs.append(
                        {
                            "text": jtext.strip(),
                            "url": jurl.strip(),
                            "index": i + 1,
                        }
                    )

        st.markdown("")
        col_l2, col_c2, col_r2 = st.columns([1, 2, 1])
        with col_c2:
            batch_analyze = st.button(
                "\U0001f4ca  Compare Opportunities",
                use_container_width=True,
                type="primary",
            )

        if batch_analyze:
            if not uploaded:
                st.error("Please upload your resume first.")
                return
            if len(batch_jobs) < 2:
                st.error("Provide at least 2 jobs (text and/or URL each).")
                return

            resume_text = parse_resume(
                io.BytesIO(uploaded.read()), filename=uploaded.name
            )
            if not resume_text.strip():
                st.error("Could not extract text from resume.")
                return

            st.session_state["report"] = None
            st.session_state["from_batch"] = False
            _run_batch_analysis(resume_text, batch_jobs)
            return

    _render_history_section()

    # --- Disclaimer ---
    st.markdown(
        '<div class="disclaimer">'
        "WorthApply provides decision support only. Risk indicators are signals, "
        "not proof. Always verify independently."
        "</div>",
        unsafe_allow_html=True,
    )


def _render_history_section() -> None:
    history = _load_history()
    st.divider()
    st.markdown("##### Past analyses")
    if not history:
        st.caption("No saved analyses yet. Run one above — it will appear here.")
        return

    top = st.columns([3, 1])
    with top[1]:
        if st.button("Clear all history", use_container_width=True):
            _clear_history()
            st.rerun()

    for item in history:
        rec = item.get("recommendation", "")
        title = item.get("title", "Untitled")
        company = item.get("company", "")
        created = item.get("created_at", "")
        fit = item.get("fit_score", 0)
        risk = item.get("risk_level", "")
        eid = item.get("id", "")

        row = st.columns([5, 1.2, 1.2])
        with row[0]:
            st.markdown(
                f"**{title}** — {company}  \n"
                f"<span style='color:#6b7280;font-size:0.85rem;'>"
                f"{created} · Fit {fit:.0f}% · Risk {risk} · {rec}</span>",
                unsafe_allow_html=True,
            )
        with row[1]:
            if st.button("View", key=f"hist_view_{eid}", use_container_width=True):
                try:
                    report = OpportunityReport.model_validate(item["report"])
                except Exception as exc:
                    st.error(f"Could not open report: {exc}")
                    continue
                st.session_state["report"] = report
                st.session_state["pipeline_state"] = None
                st.session_state["analysis_summary"] = item.get("pipeline_summary") or {}
                st.session_state["history_view_id"] = eid
                st.rerun()
        with row[2]:
            if st.button("Delete", key=f"hist_del_{eid}", use_container_width=True):
                _delete_history_entry(eid)
                st.rerun()


# ───────────────────────────────────────────────────────────────────────
#  ANALYSIS PROGRESS
# ───────────────────────────────────────────────────────────────────────

def _render_progress(resume_text: str, job_text: str, job_url: str) -> None:
    st.markdown("")
    st.markdown("#### Analyzing opportunity\u2026")
    st.caption(
        "Using local Ollama (`worthapply-dev`). CPU inference is slow — "
        "full run often takes 5–10 minutes. Stages update as each finishes."
    )

    progress_bar = st.progress(0)
    status_box = st.empty()
    status_box.info("Starting local model\u2026 first call may take a minute to load.")
    stage_containers: dict[str, st.delta_generator.DeltaGenerator] = {}

    for key in _STAGE_ORDER:
        stage_containers[key] = st.empty()
        _paint_stage(stage_containers[key], key, "PENDING")

    try:
        _run_analysis(
            resume_text,
            job_text,
            job_url,
            stage_containers=stage_containers,
            progress_bar=progress_bar,
            status_box=status_box,
        )
    except Exception as exc:
        st.error(f"Analysis failed: {exc}")
        st.session_state["error_msg"] = str(exc)
        print(f"[WorthApply] ERROR: {exc}", flush=True)
        return

    # Mark all stages complete in the UI
    for idx, key in enumerate(_STAGE_ORDER):
        status = st.session_state["stage_status"].get(key, "COMPLETED")
        _paint_stage(stage_containers[key], key, status)
        progress_bar.progress(int(100 * (idx + 1) / len(_STAGE_ORDER)))

    status_box.success("Analysis complete.")
    print("[WorthApply] Analysis complete.", flush=True)
    time.sleep(0.4)
    st.rerun()


# ───────────────────────────────────────────────────────────────────────
#  REPORT PAGE
# ───────────────────────────────────────────────────────────────────────

def _render_report(report: OpportunityReport) -> None:
    state = st.session_state.get("pipeline_state")
    report = _prepare_report_for_display(report)

    # --- Top actions: back + downloads (spacer avoids Streamlit header clip) ---
    st.markdown('<div class="report-toolbar-spacer"></div>', unsafe_allow_html=True)
    analysis = _resolve_analysis_summary(state)
    nav_l, nav_m, nav_r = st.columns([1.4, 1.6, 1.6], gap="small")
    with nav_l:
        back_label = (
            "\u2190 Back to batch"
            if st.session_state.get("from_batch") and st.session_state.get("batch_results")
            else "\u2190 Back to home"
        )
        if st.button(back_label, use_container_width=True):
            st.session_state["report"] = None
            st.session_state["pipeline_state"] = None
            st.session_state["analysis_summary"] = None
            st.session_state["history_view_id"] = None
            if st.session_state.get("from_batch") and st.session_state.get("batch_results"):
                st.session_state["from_batch"] = False
            else:
                st.session_state["batch_results"] = None
                st.session_state["from_batch"] = False
            st.rerun()
    stem = _report_filename_stem(report)
    md_bytes = _format_report_markdown(report, analysis).encode("utf-8")
    json_bytes = _format_report_json(report, analysis).encode("utf-8")
    with nav_m:
        st.download_button(
            label="Download report (.md)",
            data=md_bytes,
            file_name=f"{stem}.md",
            mime="text/markdown",
            use_container_width=True,
            key="dl_report_md",
        )
    with nav_r:
        st.download_button(
            label="Download data (.json)",
            data=json_bytes,
            file_name=f"{stem}.json",
            mime="application/json",
            use_container_width=True,
            key="dl_report_json",
        )

    if st.session_state.get("history_view_id"):
        st.caption("Viewing a saved analysis from history.")

    # ── Header ──
    st.markdown(
        '<div class="report-kicker">Opportunity intelligence</div>'
        '<h2 class="report-title">WorthApply Report</h2>',
        unsafe_allow_html=True,
    )
    if report.job.title or report.job.company:
        st.markdown(
            f'<p class="report-sub">{report.job.title or "Untitled role"}'
            f" &mdash; {report.job.company or 'Unknown company'}</p>",
            unsafe_allow_html=True,
        )

    # ── Recommendation card ──
    rec_class = _rec_css(report.recommendation)
    summary_html = (report.summary or "See detailed breakdown below.").replace(
        "<", "&lt;"
    ).replace(">", "&gt;")
    st.markdown(
        f'<div class="rec-card {rec_class}">'
        f'<div class="rec-kicker">Recommendation</div>'
        f"<h1>{_rec_label(report.recommendation)}</h1>"
        f"<p>{summary_html}</p>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Score cards (single HTML grid — more consistent than 4 columns) ──
    fit_score = report.student_fit.fit_score
    opp_conf = report.opportunity_confidence
    risk_lvl = report.risk_assessment.risk_level
    ev_qual = report.evidence_quality or "N/A"
    eq_color = {"STRONG": "green", "MODERATE": "yellow", "WEAK": "red"}.get(
        ev_qual.upper(), "gray"
    )
    st.markdown(
        '<div class="score-grid">'
        + _score_card("Student Fit", f"{fit_score:.0f}%", "match score", _pct_color(fit_score))
        + _score_card(
            "Opportunity Confidence",
            f"{opp_conf:.0f}%",
            "verification confidence",
            _pct_color(opp_conf),
        )
        + _score_card("Risk Level", risk_lvl.value, "overall risk", _risk_color(risk_lvl))
        + _score_card("Evidence Quality", ev_qual, "claim support", eq_color)
        + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="meta-strip">'
        f'<span><span class="meta-label">Priority</span>'
        f"{_badge(report.priority.value, _priority_color(report.priority))}</span>"
        f'<span><span class="meta-label">Company check</span>'
        f"{_badge(report.company_verification.verification_status.value.replace('_', ' '), _verification_color(report.company_verification.verification_status))}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Detailed sections ──
    tab_summary, tab_fit, tab_risk, tab_company, tab_gaps, tab_next = st.tabs(
        [
            "Job Summary",
            "Fit Breakdown",
            "Risk Indicators",
            "Company Verification",
            "Gaps & Uncertainty",
            "Next Steps",
        ]
    )

    fit = report.student_fit

    # ---- Job Summary ----
    with tab_summary:
        job = report.job
        source_html = (
            f'<a class="verify-link" href="{job.source_url}" target="_blank" '
            f'rel="noopener noreferrer">{_short_url(job.source_url)}</a>'
            if job.source_url
            else "—"
        )
        facts = [
            ("Position", job.title or "—"),
            ("Company", job.company or "—"),
            ("Location", job.location or "—"),
            ("Type", job.employment_type or "—"),
            ("Posting date", job.posting_date or "Not listed in posting"),
            ("Source", source_html),
        ]
        fact_rows = "".join(
            f'<div class="fact-label">{lab}</div><div class="fact-value">{val}</div>'
            for lab, val in facts
        )
        st.markdown(f'<div class="fact-grid">{fact_rows}</div>', unsafe_allow_html=True)

        if job.required_skills:
            st.markdown('<div class="section-hdr">Required skills (from posting)</div>', unsafe_allow_html=True)
            st.markdown(", ".join(job.required_skills))
        if job.preferred_skills:
            st.markdown('<div class="section-hdr">Preferred skills</div>', unsafe_allow_html=True)
            st.markdown(", ".join(job.preferred_skills))
        if job.responsibilities:
            st.markdown('<div class="section-hdr">Responsibilities</div>', unsafe_allow_html=True)
            for r in job.responsibilities:
                st.markdown(f"- {r}")

    # ---- Fit Breakdown ----
    with tab_fit:
        st.markdown(
            f'<div class="meta-strip"><span><span class="meta-label">Fit score</span>'
            f"<strong>{fit.fit_score:.0f}</strong> / 100</span></div>",
            unsafe_allow_html=True,
        )
        if fit.summary:
            st.markdown(fit.summary)

        all_skills = []
        for sm in fit.required_skills:
            all_skills.append(("Required", sm))
        for sm in fit.preferred_skills:
            all_skills.append(("Preferred", sm))

        if all_skills:
            header = (
                "<tr><th>Skill</th><th>Category</th>"
                "<th>Match</th><th>Evidence</th></tr>"
            )
            body = ""
            for cat, sm in all_skills:
                color = _match_color(sm.match_level)
                label = _match_label(sm.match_level)
                ev = (sm.evidence or "—").replace("<", "&lt;").replace(">", "&gt;")
                body += (
                    f"<tr>"
                    f"<td><strong>{sm.skill}</strong></td>"
                    f"<td>{cat}</td>"
                    f'<td>{_badge(label, color)}</td>'
                    f"<td>{ev}</td>"
                    f"</tr>"
                )
            st.markdown(
                f'<table class="ev-table">{header}{body}</table>',
                unsafe_allow_html=True,
            )
            st.caption(
                "Match strength: **HIGH** = direct evidence · "
                "**MEDIUM** = related skill (e.g. ML → ML pipelines) · "
                "**LOW** = little/no evidence in resume."
            )

        if fit.experience_match:
            st.markdown(f"**Experience:** {fit.experience_match}")
        if fit.project_evidence:
            st.markdown('<div class="section-hdr">Relevant Projects</div>', unsafe_allow_html=True)
            for p in fit.project_evidence:
                st.markdown(f"- {p}")
        if fit.education_match:
            st.markdown(f"**Education (secondary):** {fit.education_match}")
            st.caption(
                "Education is informational only — fit score prioritizes skills, "
                "projects, and experience."
            )

    # ---- Risk Indicators ----
    with tab_risk:
        risk = report.risk_assessment
        st.markdown(
            f'<div class="meta-strip"><span><span class="meta-label">Overall risk</span>'
            f"{_badge(risk.risk_level.value, _risk_color(risk.risk_level))}</span></div>",
            unsafe_allow_html=True,
        )
        if risk.summary:
            st.markdown(risk.summary)

        if risk.signals:
            for sig in risk.signals:
                sev_color = _risk_color(sig.severity)
                st.markdown(
                    f"- {_badge(sig.severity.value, sev_color)} **{sig.signal}**"
                    + (f" — {sig.evidence}" if sig.evidence else ""),
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                '<p class="empty-note">No risk indicators detected.</p>',
                unsafe_allow_html=True,
            )

    # ---- Company Verification ----
    with tab_company:
        cv = report.company_verification
        st.markdown(
            f'<div class="meta-strip">'
            f'<span><span class="meta-label">Status</span>'
            f"{_badge(cv.verification_status.value.replace('_', ' '), _verification_color(cv.verification_status))}</span>"
            f'<span><span class="meta-label">Confidence</span>{cv.confidence * 100:.0f}%</span>'
            f"</div>",
            unsafe_allow_html=True,
        )
        if cv.summary:
            st.markdown(cv.summary)

        fallback_urls = [u for u in (cv.source_urls or []) if u]
        website_url = getattr(cv, "website_url", "") or ""
        careers_url = getattr(cv, "careers_page_url", "") or ""
        listing_url = getattr(cv, "job_listing_url", "") or ""
        if not website_url and cv.website_found:
            for u in fallback_urls:
                if not is_job_board_url(u):
                    website_url = u
                    break
        board_url = ""
        for u in fallback_urls:
            if is_job_board_url(u):
                board_url = u
                break

        listing_found = bool(cv.job_listing_found)
        if listing_found and listing_url and is_job_board_url(listing_url):
            listing_found = False
            listing_url = ""
        if listing_found and not listing_url and not careers_url and board_url:
            listing_found = False
        careers_found = cv.careers_page_found or listing_found
        if listing_found and not careers_url and listing_url:
            careers_url = listing_url

        st.markdown('<div class="section-hdr">Verification checks</div>', unsafe_allow_html=True)
        checks = [
            {
                "label": "Company website",
                "found": cv.website_found,
                "url": website_url,
                "note_found": "Official or company identity page used in verification.",
                "note_missing": "No company website or LinkedIn company page confirmed.",
            },
            {
                "label": "Careers / jobs page",
                "found": careers_found,
                "url": careers_url,
                "note_found": "Careers or hiring surface linked to the company.",
                "note_missing": "No dedicated careers/jobs page confirmed on the company site.",
            },
            {
                "label": "Role on company careers site",
                "found": listing_found,
                "url": listing_url,
                "note_found": "This job title appears on the company's own careers page.",
                "note_missing": (
                    "Role not confirmed on the company careers page"
                    + (f" (still listed on job board: {_short_url(board_url)})" if board_url else "")
                    + "."
                ),
            },
        ]
        if board_url:
            checks.append(
                {
                    "label": "Source listing (job board)",
                    "found": True,
                    "url": board_url,
                    "note_found": "Original posting channel — common, but separate from company-site proof.",
                    "note_missing": "",
                }
            )
        st.markdown(_verification_checks_html(checks), unsafe_allow_html=True)

        human_evidence = []
        for e in cv.evidence or []:
            h = _humanize_evidence(e)
            if h and h not in human_evidence:
                human_evidence.append(h)
        if human_evidence:
            st.markdown('<div class="section-hdr">Evidence</div>', unsafe_allow_html=True)
            for e in human_evidence:
                linked = re.sub(
                    r"(https?://[^\s<>\"']+)",
                    lambda m: (
                        f'<a class="verify-link" href="{m.group(1)}" '
                        f'target="_blank" rel="noopener noreferrer">{_short_url(m.group(1))}</a>'
                    ),
                    e,
                )
                st.markdown(f'<p class="evidence-item">{linked}</p>', unsafe_allow_html=True)

        if cv.unresolved_questions:
            st.markdown('<div class="section-hdr">Unresolved Questions</div>', unsafe_allow_html=True)
            for q in cv.unresolved_questions:
                st.markdown(f"- {q}")

    # ---- Gaps & Uncertainty ----
    with tab_gaps:
        if report.missing_requirements:
            st.markdown('<div class="section-hdr">Missing Requirements</div>', unsafe_allow_html=True)
            for m in report.missing_requirements:
                st.markdown(f"- {m}")
        else:
            st.markdown(
                '<p class="empty-note">No critical gaps identified.</p>',
                unsafe_allow_html=True,
            )

        if report.uncertainty:
            st.markdown('<div class="section-hdr">Uncertainty</div>', unsafe_allow_html=True)
            st.caption("Things the system could not determine:")
            for u in report.uncertainty:
                st.markdown(f"- {u}")

        if fit.concerns:
            st.markdown('<div class="section-hdr">Concerns</div>', unsafe_allow_html=True)
            for c in fit.concerns:
                st.markdown(f"- {c}")

    # ---- Next Steps ----
    with tab_next:
        if report.next_steps:
            steps_html = ['<div class="step-list">']
            for i, step in enumerate(report.next_steps, 1):
                safe = step.replace("<", "&lt;").replace(">", "&gt;")
                steps_html.append(
                    f'<div class="step-row"><div class="step-num">{i}</div>'
                    f'<div class="step-text">{safe}</div></div>'
                )
            steps_html.append("</div>")
            st.markdown("".join(steps_html), unsafe_allow_html=True)
        else:
            st.markdown(
                '<p class="empty-note">No specific next steps generated.</p>',
                unsafe_allow_html=True,
            )

        if report.reasons:
            st.markdown('<div class="section-hdr">Key Reasons</div>', unsafe_allow_html=True)
            reasons_html = ['<div class="reason-list">']
            for r in report.reasons:
                safe = r.replace("<", "&lt;").replace(">", "&gt;")
                reasons_html.append(f'<div class="reason-item">{safe}</div>')
            reasons_html.append("</div>")
            st.markdown("".join(reasons_html), unsafe_allow_html=True)

    # ── Analysis details (expandable) ──
    _render_analysis_details(analysis)

    # --- Disclaimer ---
    st.markdown(
        '<div class="disclaimer">'
        "WorthApply provides decision support only. Risk indicators are signals, "
        "not proof. Always verify independently."
        "</div>",
        unsafe_allow_html=True,
    )




# ───────────────────────────────────────────────────────────────────────
#  BATCH MODE
# ───────────────────────────────────────────────────────────────────────

def _batch_concurrency() -> int:
    """Keep parallel jobs low so demo/interview runs don't hit API/Ollama limits."""
    return max(1, int(os.getenv("BATCH_CONCURRENCY", "2")))


async def _prepare_job_text(job_info: dict) -> tuple[str, str, str | None]:
    """Return (job_text, job_url, error). Same rules as single mode."""
    text = (job_info.get("text") or "").strip()
    url = (job_info.get("url") or "").strip()
    if url and not text:
        fetched = await fetch_webpage(url)
        if not fetched.ok or not fetched.content.strip():
            return (
                "",
                url,
                f"Could not load URL ({fetched.error or 'empty page'}). Paste the description instead.",
            )
        text = fetched.content
        if fetched.title:
            text = f"Page title: {fetched.title}\n\n{text}"
    if not text and not url:
        return "", "", "Provide a job description or URL."
    if not text:
        return "", url, "No job text available."
    return text, url, None


async def _analyze_batch_job(
    resume_text: str,
    job_info: dict,
    sem: asyncio.Semaphore,
) -> dict:
    idx = job_info.get("index", 0)
    async with sem:
        print(f"[WorthApply] batch job {idx}: START", flush=True)
        text, url, err = await _prepare_job_text(job_info)
        if err:
            print(f"[WorthApply] batch job {idx}: PREP FAILED — {err}", flush=True)
            return {"index": idx, "error": err, "report": None, "pipeline_summary": {}}

        provider = get_provider()
        workflow = AnalysisWorkflow(provider=provider)
        report, state = await workflow.analyze(
            student_text=resume_text,
            job_text=text,
            job_url=url,
        )
        summary = state.to_summary() if state else {}
        try:
            _append_history(report, pipeline_summary=summary)
        except Exception as exc:
            print(f"[WorthApply] batch job {idx}: history save failed: {exc}", flush=True)
        print(f"[WorthApply] batch job {idx}: DONE", flush=True)
        return {
            "index": idx,
            "error": None,
            "report": report.model_dump(mode="json"),
            "pipeline_summary": summary,
        }


def _run_batch_analysis(resume_text: str, batch_jobs: list[dict]) -> None:
    """Analyze multiple jobs in parallel with the same pipeline as single mode."""
    n = len(batch_jobs)
    conc = _batch_concurrency()
    st.markdown("#### Comparing opportunities…")
    st.caption(
        f"Same pipeline as single mode · **{n} jobs** · up to **{conc} in parallel** "
        f"(set `BATCH_CONCURRENCY` to change)."
    )
    progress = st.progress(0, text="Starting parallel analyses…")
    status = st.empty()
    status.info(f"Running up to {conc} jobs at a time…")

    async def _run_all() -> list[dict]:
        sem = asyncio.Semaphore(conc)
        tasks = [
            asyncio.create_task(_analyze_batch_job(resume_text, job, sem))
            for job in batch_jobs
        ]
        done = 0
        out: list[dict] = []
        for coro in asyncio.as_completed(tasks):
            try:
                item = await coro
            except Exception as exc:
                item = {
                    "index": 0,
                    "error": str(exc),
                    "report": None,
                    "pipeline_summary": {},
                }
            out.append(item)
            done += 1
            progress.progress(done / n, text=f"Finished {done} of {n}…")
            status.info(f"Finished {done} of {n} jobs…")
        return out

    try:
        raw_results = asyncio.run(_run_all())
    except Exception as exc:
        st.error(f"Batch analysis failed: {exc}")
        print(f"[WorthApply] BATCH ERROR: {exc}", flush=True)
        return

    progress.progress(1.0, text="All analyses complete!")
    time.sleep(0.3)
    progress.empty()
    status.empty()

    ok_results = [r for r in raw_results if r.get("report")]
    for r in raw_results:
        if r.get("error"):
            st.warning(f"Job {r.get('index', '?')}: {r['error']}")

    if not ok_results:
        st.error("All analyses failed.")
        return

    def _sort_key(item: dict):
        try:
            rpt = OpportunityReport.model_validate(item["report"])
        except Exception:
            return (9, 0)
        return (
            {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(rpt.priority.value, 3),
            -rpt.student_fit.fit_score,
        )

    ok_results.sort(key=_sort_key)
    st.session_state["batch_results"] = ok_results
    st.session_state["report"] = None
    st.rerun()


def _render_batch_results() -> None:
    """Ranked comparison + open the same full report view as single mode."""
    results = st.session_state.get("batch_results") or []
    if st.button("\u2190 Back to home"):
        st.session_state["batch_results"] = None
        st.session_state["report"] = None
        st.session_state["from_batch"] = False
        st.rerun()

    st.markdown(
        '<div class="report-kicker">Batch comparison</div>'
        '<h2 class="report-title">Ranked Opportunities</h2>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Each job used the same WorthApply pipeline as single mode. "
        "Open any row for the full report (tabs, downloads, analysis details)."
    )

    header_cols = st.columns([0.7, 2.4, 2.4, 1.2, 1.3, 1.1, 1.8, 1.3])
    for col, label in zip(
        header_cols,
        ["#", "Company", "Role", "Fit", "Confidence", "Risk", "Recommendation", ""],
    ):
        col.markdown(f"**{label}**")

    for rank, item in enumerate(results, 1):
        try:
            rpt = OpportunityReport.model_validate(item["report"])
        except Exception:
            continue
        cols = st.columns([0.7, 2.4, 2.4, 1.2, 1.3, 1.1, 1.8, 1.3])
        cols[0].write(f"**#{rank}**")
        cols[1].write(rpt.job.company or "Unknown")
        cols[2].write(rpt.job.title or "Unknown")
        cols[3].markdown(
            _badge(f"{rpt.student_fit.fit_score:.0f}%", _pct_color(rpt.student_fit.fit_score)),
            unsafe_allow_html=True,
        )
        cols[4].markdown(
            _badge(f"{rpt.opportunity_confidence:.0f}%", _pct_color(rpt.opportunity_confidence)),
            unsafe_allow_html=True,
        )
        cols[5].markdown(
            _badge(rpt.risk_assessment.risk_level.value, _risk_color(rpt.risk_assessment.risk_level)),
            unsafe_allow_html=True,
        )
        rec_color = {
            Recommendation.APPLY: "green",
            Recommendation.APPLY_IF_TIME: "yellow",
            Recommendation.LOW_PRIORITY: "red",
        }.get(rpt.recommendation, "gray")
        cols[6].markdown(
            _badge(_rec_label(rpt.recommendation), rec_color),
            unsafe_allow_html=True,
        )
        if cols[7].button("Full report", key=f"batch_view_{rank}", use_container_width=True):
            st.session_state["report"] = rpt
            st.session_state["pipeline_state"] = None
            st.session_state["analysis_summary"] = item.get("pipeline_summary") or {}
            st.session_state["history_view_id"] = None
            st.session_state["from_batch"] = True
            st.rerun()

    st.markdown("")
    st.markdown('<div class="section-hdr">Quick summaries</div>', unsafe_allow_html=True)
    for rank, item in enumerate(results, 1):
        try:
            rpt = OpportunityReport.model_validate(item["report"])
        except Exception:
            continue
        with st.expander(f"#{rank} — {rpt.job.company} / {rpt.job.title}"):
            st.markdown(rpt.summary or "No summary available.")
            if rpt.missing_requirements:
                st.markdown("**Missing:** " + ", ".join(rpt.missing_requirements))
            if rpt.uncertainty:
                st.markdown("**Uncertainty:** " + "; ".join(rpt.uncertainty))


# ───────────────────────────────────────────────────────────────────────
#  MAIN
# ───────────────────────────────────────────────────────────────────────

def main() -> None:
    report: OpportunityReport | None = st.session_state.get("report")
    if report is not None:
        _render_report(report)
    elif st.session_state.get("batch_results"):
        _render_batch_results()
    else:
        _render_home()


main()
