"""Full pipeline runner — runs the complete analysis on evaluation cases.

Usage:
    python -m worthapply.pipeline                       # run all cases
    python -m worthapply.pipeline --case case_001       # run one case
    python -m worthapply.pipeline --dry-run             # schema check only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from worthapply.orchestration.workflow import AnalysisWorkflow
from worthapply.providers import get_provider

DATASET_PATH = PROJECT_ROOT / "data" / "evaluation_cases.json"
RESULTS_DIR = PROJECT_ROOT / "results" / "final"


def _load_cases(case_id: str | None = None) -> list[dict]:
    with open(DATASET_PATH, encoding="utf-8") as f:
        cases = json.load(f)
    if case_id:
        cases = [c for c in cases if c["case_id"] == case_id]
        if not cases:
            raise ValueError(f"Case '{case_id}' not found")
    return cases


def _format_student(profile: dict) -> str:
    parts = []
    if profile.get("name"):
        parts.append(f"Name: {profile['name']}")
    if profile.get("summary"):
        parts.append(f"Summary: {profile['summary']}")
    if profile.get("education"):
        parts.append("Education:\n" + "\n".join(f"  - {e}" for e in profile["education"]))
    if profile.get("skills"):
        parts.append("Skills: " + ", ".join(profile["skills"]))
    if profile.get("experience"):
        parts.append("Experience:\n" + "\n".join(f"  - {e}" for e in profile["experience"]))
    if profile.get("projects"):
        parts.append("Projects:\n" + "\n".join(f"  - {p}" for p in profile["projects"]))
    if profile.get("certifications"):
        parts.append("Certifications: " + ", ".join(profile["certifications"]))
    return "\n\n".join(parts)


def _format_job(job: dict) -> str:
    parts = []
    for key in ["title", "company", "location", "employment_type", "posting_date"]:
        if job.get(key):
            parts.append(f"{key.replace('_', ' ').title()}: {job[key]}")
    if job.get("description"):
        parts.append(f"\nDescription:\n{job['description']}")
    if job.get("required_skills"):
        parts.append("Required Skills: " + ", ".join(job["required_skills"]))
    if job.get("preferred_skills"):
        parts.append("Preferred Skills: " + ", ".join(job["preferred_skills"]))
    if job.get("experience_requirement"):
        parts.append(f"Experience: {job['experience_requirement']}")
    if job.get("education_requirements"):
        parts.append("Education: " + ", ".join(job["education_requirements"]))
    if job.get("responsibilities"):
        parts.append("Responsibilities:\n" + "\n".join(f"  - {r}" for r in job["responsibilities"]))
    if job.get("application_url"):
        parts.append(f"Apply: {job['application_url']}")
    if job.get("source_url"):
        parts.append(f"Source: {job['source_url']}")
    return "\n".join(parts)


async def run_case(case: dict, workflow: AnalysisWorkflow) -> dict:
    student_text = _format_student(case["student_profile"])
    job_text = _format_job(case["job"])
    job_url = case["job"].get("source_url", "")

    report, state = await workflow.analyze(
        student_text, job_text, job_url, case_id=case["case_id"]
    )

    result = {
        "case_id": case["case_id"],
        "category": case.get("category", ""),
        "status": "success",
        "output": report.model_dump(mode="json"),
        "predicted": {
            "priority": report.priority.value,
            "recommendation": report.recommendation.value,
            "fit_score": report.student_fit.fit_score,
            "risk_level": report.risk_assessment.risk_level.value,
            "opportunity_confidence": report.opportunity_confidence,
            "detected_signals": [s.signal for s in report.risk_assessment.signals],
        },
        "ground_truth": case.get("ground_truth", {}),
        "pipeline_summary": state.to_summary(),
        "usage": {
            "total_tokens": state.total_tokens,
            "total_cost_usd": state.total_cost,
            "total_elapsed_ms": state.total_elapsed_ms,
        },
    }
    return result


async def run_all(case_id: str | None = None) -> None:
    cases = _load_cases(case_id)
    provider = get_provider()
    workflow = AnalysisWorkflow(provider)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    total_start = time.perf_counter()

    for i, case in enumerate(cases):
        print(f"[{i+1}/{len(cases)}] Running {case['case_id']}...", end=" ", flush=True)
        try:
            result = await run_case(case, workflow)
            results.append(result)
            elapsed = result["usage"]["total_elapsed_ms"]
            print(f"success ({elapsed:.0f}ms)")
        except Exception as exc:
            print(f"EXCEPTION: {exc}")
            results.append({
                "case_id": case["case_id"],
                "status": "exception",
                "error": str(exc),
                "ground_truth": case.get("ground_truth", {}),
            })
        # Local/dev: short pause. Cloud/Groq free tier: longer (set via env).
        if i < len(cases) - 1:
            pause = float(os.getenv("CASE_PAUSE_SECONDS", "2"))
            if pause > 0:
                await asyncio.sleep(pause)

    total_elapsed = time.perf_counter() - total_start

    with open(RESULTS_DIR / "raw_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    successes = sum(1 for r in results if r["status"] == "success")
    total_cost = sum(r.get("usage", {}).get("total_cost_usd", 0) for r in results)
    total_tokens = sum(r.get("usage", {}).get("total_tokens", 0) for r in results)

    summary = {
        "total_cases": len(results),
        "successes": successes,
        "errors": len(results) - successes,
        "total_elapsed_s": round(total_elapsed, 2),
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "avg_cost_per_case": round(total_cost / max(successes, 1), 6),
    }

    with open(RESULTS_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Pipeline complete: {successes}/{len(results)} succeeded")
    print(f"Total time: {total_elapsed:.1f}s")
    print(f"Total cost: ${total_cost:.4f}")
    print(f"Total tokens: {total_tokens}")
    print(f"Results saved to: {RESULTS_DIR}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Run WorthApply full pipeline")
    parser.add_argument("--case", type=str, help="Run a specific case")
    parser.add_argument("--dry-run", action="store_true", help="Validate setup only")
    args = parser.parse_args()

    if args.dry_run:
        print("Dry run — validating setup...")
        cases = _load_cases(args.case)
        print(f"Loaded {len(cases)} cases")
        provider = get_provider()
        print(f"Provider: {provider.provider_name} / {provider.model}")
        print("Setup OK")
        return

    asyncio.run(run_all(case_id=args.case))


if __name__ == "__main__":
    main()
