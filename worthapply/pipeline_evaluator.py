"""Evaluate full pipeline results — same rubric as baseline.

Usage:
    python -m worthapply.pipeline_evaluator
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from baseline.evaluator import (
    save_evaluation,
    score_fit,
    score_priority,
    score_recommendation,
    score_risk,
)

RESULTS_DIR = PROJECT_ROOT / "results" / "final"


def evaluate_pipeline_results() -> dict:
    raw_path = RESULTS_DIR / "raw_results.json"
    if not raw_path.exists():
        print(f"No results at {raw_path}. Run pipeline first.")
        return {}

    with open(raw_path, encoding="utf-8") as f:
        results = json.load(f)

    scores = []
    category_scores: dict[str, list[float]] = {}
    failures: list[dict] = []

    for r in results:
        if r.get("status") != "success":
            failures.append({
                "case_id": r["case_id"],
                "failure_type": "execution_error",
                "error": r.get("error", "unknown"),
            })
            continue

        predicted = r.get("predicted", {})
        gt = r.get("ground_truth", {})

        case_scores = {
            "case_id": r["case_id"],
            "category": r.get("category", ""),
            "priority_score": score_priority(
                predicted.get("priority", ""), gt.get("expected_priority", "")
            ),
            "recommendation_score": score_recommendation(
                predicted.get("recommendation", ""),
                gt.get("expected_recommendation", ""),
            ),
            "fit_score": score_fit(
                predicted.get("fit_score", 50),
                gt.get("expected_fit_range", [0, 100]),
            ),
            "risk_score": score_risk(
                predicted.get("risk_level", ""),
                gt.get("expected_risk_level", ""),
            ),
            "predicted": predicted,
            "expected": gt,
        }

        scores.append(case_scores)

        cat = r.get("category", "?")
        category_scores.setdefault(cat, []).append(case_scores["priority_score"])

        if case_scores["priority_score"] < 1.0:
            failures.append({
                "case_id": r["case_id"],
                "category": r.get("category", ""),
                "failure_type": "priority_mismatch",
                "predicted_priority": predicted.get("priority", ""),
                "expected_priority": gt.get("expected_priority", ""),
                "predicted_recommendation": predicted.get("recommendation", ""),
                "expected_recommendation": gt.get("expected_recommendation", ""),
                "predicted_fit": predicted.get("fit_score", 0),
                "expected_fit_range": gt.get("expected_fit_range", []),
                "predicted_risk": predicted.get("risk_level", ""),
                "expected_risk": gt.get("expected_risk_level", ""),
            })

    n = len(scores)
    if n == 0:
        return {"error": "No successful results"}

    evaluation = {
        "total_cases": len(results),
        "evaluated": n,
        "errors": len(results) - n,
        "primary_metric": {
            "name": "Opportunity Decision Accuracy",
            "exact_accuracy": round(sum(1 for s in scores if s["priority_score"] == 1.0) / n, 4),
            "weighted_accuracy": round(sum(s["priority_score"] for s in scores) / n, 4),
        },
        "secondary_metrics": {
            "recommendation_accuracy": round(sum(s["recommendation_score"] for s in scores) / n, 4),
            "fit_accuracy": round(sum(s["fit_score"] for s in scores) / n, 4),
            "risk_accuracy": round(sum(s["risk_score"] for s in scores) / n, 4),
        },
        "per_category": {
            cat: {
                "count": len(vals),
                "avg_priority_score": round(sum(vals) / len(vals), 4),
            }
            for cat, vals in sorted(category_scores.items())
        },
        "failures": failures,
        "case_scores": scores,
    }

    return evaluation


def main():
    evaluation = evaluate_pipeline_results()
    if evaluation and "error" not in evaluation:
        save_evaluation.__func__ = lambda e: None  # avoid overwriting baseline
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        eval_path = RESULTS_DIR / "evaluation.json"
        with open(eval_path, "w", encoding="utf-8") as f:
            json.dump(evaluation, f, indent=2, default=str)

        pm = evaluation["primary_metric"]
        sm = evaluation["secondary_metrics"]
        print(f"\n{'='*60}")
        print("FULL PIPELINE RESULTS")
        print(f"{'='*60}")
        print(f"Exact Accuracy:    {pm['exact_accuracy']:.1%}")
        print(f"Weighted Accuracy: {pm['weighted_accuracy']:.1%}")
        print(f"Recommendation:    {sm['recommendation_accuracy']:.1%}")
        print(f"Fit Accuracy:      {sm['fit_accuracy']:.1%}")
        print(f"Risk Accuracy:     {sm['risk_accuracy']:.1%}")
        print(f"Failures:          {len(evaluation['failures'])}")
        print(f"{'='*60}")
        print(f"Saved to {eval_path}")
    elif evaluation:
        print(evaluation.get("error", "Unknown error"))


if __name__ == "__main__":
    main()
