"""Baseline runner — single LLM call per evaluation case.

Usage:
    python -m baseline.runner                     # run all cases
    python -m baseline.runner --case case_001     # run one case
    python -m baseline.runner --dry-run           # show prompt, don't call LLM
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

from baseline.schemas import BaselineReport
from worthapply.providers import get_provider


PROMPT_PATH = Path(__file__).parent / "prompt.txt"
DATASET_PATH = PROJECT_ROOT / "data" / "evaluation_cases.json"
RESULTS_DIR = PROJECT_ROOT / "results" / "baseline"


def _load_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _load_cases(case_id: str | None = None) -> list[dict]:
    with open(DATASET_PATH, encoding="utf-8") as f:
        cases = json.load(f)
    if case_id:
        cases = [c for c in cases if c["case_id"] == case_id]
        if not cases:
            raise ValueError(f"Case '{case_id}' not found in dataset")
    return cases


def _format_student_profile(profile: dict) -> str:
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


def _format_job_description(job: dict) -> str:
    parts = []
    if job.get("title"):
        parts.append(f"Title: {job['title']}")
    if job.get("company"):
        parts.append(f"Company: {job['company']}")
    if job.get("location"):
        parts.append(f"Location: {job['location']}")
    if job.get("employment_type"):
        parts.append(f"Type: {job['employment_type']}")
    if job.get("posting_date"):
        parts.append(f"Posted: {job['posting_date']}")
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


async def run_case(
    case: dict, provider, prompt_template: str, dry_run: bool = False
) -> dict:
    """Run one evaluation case through the baseline."""
    student_text = _format_student_profile(case["student_profile"])
    job_text = _format_job_description(case["job"])

    prompt = prompt_template.replace("{student_profile}", student_text)
    prompt = prompt.replace("{job_description}", job_text)

    if dry_run:
        return {
            "case_id": case["case_id"],
            "prompt_preview": prompt[:500] + "...",
            "status": "dry_run",
        }

    response = await provider.generate_structured(
        prompt,
        BaselineReport,
        agent_name="baseline",
        temperature=0.1,
        max_tokens=4096,
    )

    result: dict = {
        "case_id": case["case_id"],
        "category": case.get("category", ""),
        "status": "success" if response.ok else "error",
    }

    if response.ok and response.structured:
        report: BaselineReport = response.structured
        result["output"] = report.model_dump()
        result["predicted"] = {
            "priority": report.priority,
            "recommendation": report.recommendation,
            "fit_score": report.fit_score,
            "risk_level": report.risk_level,
            "opportunity_confidence": report.opportunity_confidence,
            "detected_signals": [s.signal for s in report.risk_signals],
        }
    else:
        result["error"] = response.error or "Unknown error"
        result["raw_content"] = response.content

    result["usage"] = {
        "model": response.usage.model,
        "provider": response.usage.provider,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "total_tokens": response.usage.total_tokens,
        "estimated_cost_usd": response.usage.estimated_cost_usd,
        "latency_ms": response.usage.latency_ms,
    }

    result["ground_truth"] = case.get("ground_truth", {})

    return result


async def run_all(case_id: str | None = None, dry_run: bool = False) -> None:
    """Run baseline against all (or one) evaluation cases."""
    cases = _load_cases(case_id)
    prompt_template = _load_prompt_template()

    if not dry_run:
        provider = get_provider()
    else:
        provider = None

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    total_start = time.perf_counter()

    for i, case in enumerate(cases):
        print(f"[{i+1}/{len(cases)}] Running {case['case_id']}...", end=" ", flush=True)
        try:
            result = await run_case(case, provider, prompt_template, dry_run)
            results.append(result)
            status = result.get("status", "unknown")
            latency = result.get("usage", {}).get("latency_ms", 0)
            print(f"{status} ({latency:.0f}ms)")
        except Exception as exc:
            print(f"EXCEPTION: {exc}")
            results.append({
                "case_id": case["case_id"],
                "status": "exception",
                "error": str(exc),
            })
        if i < len(cases) - 1 and not dry_run:
            pause = float(os.getenv("CASE_PAUSE_SECONDS", "2"))
            if pause > 0:
                await asyncio.sleep(pause)

    total_elapsed = time.perf_counter() - total_start

    # Save raw results
    output_path = RESULTS_DIR / "raw_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    # Summary
    successes = sum(1 for r in results if r["status"] == "success")
    errors = sum(1 for r in results if r["status"] != "success")
    total_cost = sum(
        r.get("usage", {}).get("estimated_cost_usd", 0) for r in results
    )
    total_tokens = sum(
        r.get("usage", {}).get("total_tokens", 0) for r in results
    )

    summary = {
        "total_cases": len(results),
        "successes": successes,
        "errors": errors,
        "total_elapsed_s": round(total_elapsed, 2),
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "avg_latency_ms": round(
            sum(r.get("usage", {}).get("latency_ms", 0) for r in results)
            / max(successes, 1),
            1,
        ),
        "avg_cost_per_case_usd": round(total_cost / max(successes, 1), 6),
        "provider": results[0].get("usage", {}).get("provider", "") if results else "",
        "model": results[0].get("usage", {}).get("model", "") if results else "",
    }

    summary_path = RESULTS_DIR / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Baseline complete: {successes}/{len(results)} succeeded")
    print(f"Total time: {total_elapsed:.1f}s")
    print(f"Total cost: ${total_cost:.4f}")
    print(f"Total tokens: {total_tokens}")
    print(f"Results saved to: {RESULTS_DIR}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Run WorthApply baseline evaluation")
    parser.add_argument("--case", type=str, help="Run a specific case by ID")
    parser.add_argument("--dry-run", action="store_true", help="Show prompts without calling LLM")
    args = parser.parse_args()
    asyncio.run(run_all(case_id=args.case, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
