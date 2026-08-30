"""Run evaluation across baseline and iteration results.

Usage:
    python -m evaluation.evaluate baseline
    python -m evaluation.evaluate final
    python -m evaluation.evaluate --all
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

RESULTS_DIR = PROJECT_ROOT / "results"


def load_results(version: str) -> list[dict] | None:
    path = RESULTS_DIR / version / "raw_results.json"
    if not path.exists():
        print(f"No results found at {path}")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compare_versions(versions: list[str]) -> str:
    """Generate a comparison table across versions."""
    lines = ["# Cross-Version Comparison", ""]
    headers = ["Metric"] + versions
    rows = []

    data = {}
    for v in versions:
        eval_path = RESULTS_DIR / v / "evaluation.json"
        if eval_path.exists():
            with open(eval_path, encoding="utf-8") as f:
                data[v] = json.load(f)
        else:
            data[v] = None

    metrics = [
        ("Exact Accuracy", lambda d: d.get("primary_metric", {}).get("exact_accuracy", "N/A")),
        ("Weighted Accuracy", lambda d: d.get("primary_metric", {}).get("weighted_accuracy", "N/A")),
        ("Recommendation Acc.", lambda d: d.get("secondary_metrics", {}).get("recommendation_accuracy", "N/A")),
        ("Fit Accuracy", lambda d: d.get("secondary_metrics", {}).get("fit_accuracy", "N/A")),
        ("Risk Accuracy", lambda d: d.get("secondary_metrics", {}).get("risk_accuracy", "N/A")),
    ]

    for name, extractor in metrics:
        row = [name]
        for v in versions:
            if data.get(v):
                val = extractor(data[v])
                row.append(f"{val}" if isinstance(val, str) else f"{val:.4f}")
            else:
                row.append("N/A")
        rows.append(row)

    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="WorthApply evaluation")
    parser.add_argument("version", nargs="?", default="baseline", help="Version to evaluate (baseline, final, etc.)")
    parser.add_argument("--all", action="store_true", help="Compare all available versions")
    args = parser.parse_args()

    if args.all:
        versions = []
        for d in sorted(RESULTS_DIR.iterdir()):
            if d.is_dir() and (d / "evaluation.json").exists():
                versions.append(d.name)
        if versions:
            report = compare_versions(versions)
            print(report)
            out = RESULTS_DIR / "comparison.md"
            out.write_text(report, encoding="utf-8")
            print(f"\nSaved to {out}")
        else:
            print("No evaluated versions found. Run baseline first.")
    else:
        # Import and run the appropriate evaluator
        if args.version == "baseline":
            from baseline.evaluator import main as eval_main
            eval_main()
        else:
            print(f"Evaluator for '{args.version}' not yet implemented.")


if __name__ == "__main__":
    main()
