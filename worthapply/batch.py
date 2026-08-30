"""Batch mode — analyze multiple job opportunities against one resume.

Usage:
    python -m worthapply.batch --resume resume.pdf --jobs urls.txt
    python -m worthapply.batch --resume resume.pdf --url URL1 --url URL2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from worthapply.orchestration.workflow import AnalysisWorkflow
from worthapply.providers import get_provider
from worthapply.tools.resume_parser import parse_resume
from worthapply.tools.webpage_fetcher import fetch_webpage


@dataclass
class BatchResult:
    rank: int
    company: str
    role: str
    fit_score: float
    opportunity_confidence: float
    risk_level: str
    recommendation: str
    priority: str
    url: str


async def fetch_job_text(url: str) -> str:
    """Fetch job description text from a URL."""
    result = await fetch_webpage(url)
    if result.ok:
        return result.content
    return ""


async def analyze_batch(
    student_text: str,
    jobs: list[dict],
    provider=None,
) -> list[BatchResult]:
    """Analyze multiple job opportunities. Each job dict has 'url' and/or 'text'."""
    if provider is None:
        provider = get_provider()

    workflow = AnalysisWorkflow(provider)
    results: list[BatchResult] = []

    for i, job in enumerate(jobs):
        url = job.get("url", "")
        text = job.get("text", "")

        if not text and url:
            print(f"  [{i+1}/{len(jobs)}] Fetching {url}...", end=" ", flush=True)
            text = await fetch_job_text(url)
            if not text:
                print("FAILED to fetch")
                continue
            print("OK")

        if not text:
            continue

        print(f"  [{i+1}/{len(jobs)}] Analyzing...", end=" ", flush=True)
        try:
            report, state = await workflow.analyze(student_text, text, url)
            results.append(BatchResult(
                rank=0,
                company=report.job.company,
                role=report.job.title,
                fit_score=report.student_fit.fit_score,
                opportunity_confidence=report.opportunity_confidence,
                risk_level=report.risk_assessment.risk_level.value,
                recommendation=report.recommendation.value,
                priority=report.priority.value,
                url=url,
            ))
            print(f"{report.recommendation.value} (fit={report.student_fit.fit_score:.0f}%)")
        except Exception as exc:
            print(f"ERROR: {exc}")

    results.sort(key=lambda r: (
        {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(r.priority, 3),
        -r.fit_score,
    ))

    for i, r in enumerate(results):
        r.rank = i + 1

    return results


def print_batch_results(results: list[BatchResult]) -> None:
    """Print a ranked table of batch results."""
    if not results:
        print("No results to display.")
        return

    print(f"\n{'='*90}")
    print(f"{'Rank':<5} {'Company':<20} {'Role':<22} {'Fit':<6} {'Conf':<6} {'Risk':<8} {'Rec':<15}")
    print(f"{'-'*90}")
    for r in results:
        print(
            f"{r.rank:<5} {r.company[:19]:<20} {r.role[:21]:<22} "
            f"{r.fit_score:<6.0f} {r.opportunity_confidence:<6.0f} "
            f"{r.risk_level:<8} {r.recommendation:<15}"
        )
    print(f"{'='*90}")


def main():
    parser = argparse.ArgumentParser(description="WorthApply batch analysis")
    parser.add_argument("--resume", type=str, required=True, help="Path to resume (PDF/DOCX/TXT)")
    parser.add_argument("--url", type=str, action="append", default=[], help="Job URL(s)")
    parser.add_argument("--jobs", type=str, help="File with one job URL per line")
    parser.add_argument("--output", type=str, help="Output JSON file")
    args = parser.parse_args()

    student_text = parse_resume(args.resume)
    if not student_text:
        print(f"Could not parse resume: {args.resume}")
        sys.exit(1)

    jobs: list[dict] = []
    for url in args.url:
        jobs.append({"url": url.strip()})

    if args.jobs:
        with open(args.jobs, encoding="utf-8") as f:
            for line in f:
                url = line.strip()
                if url and not url.startswith("#"):
                    jobs.append({"url": url})

    if not jobs:
        print("No jobs specified. Use --url or --jobs.")
        sys.exit(1)

    print(f"Analyzing {len(jobs)} opportunities...")
    results = asyncio.run(analyze_batch(student_text, jobs))
    print_batch_results(results)

    if args.output:
        output_data = [
            {
                "rank": r.rank,
                "company": r.company,
                "role": r.role,
                "fit_score": r.fit_score,
                "opportunity_confidence": r.opportunity_confidence,
                "risk_level": r.risk_level,
                "recommendation": r.recommendation,
                "priority": r.priority,
                "url": r.url,
            }
            for r in results
        ]
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
        print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
